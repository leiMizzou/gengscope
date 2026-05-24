from __future__ import annotations

import csv
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from gengscope_api.db.models import AlgorithmicSignal, EvidencePointer, Paper, ReviewTask, SourceArtifact


ANALYZER_NAME = "gengscope.numeric"
ANALYZER_VERSION = "0.2.0"
TERMINAL_SIGNAL_STATUSES = {"confirmed_signal", "false_positive", "not_actionable", "promoted_to_event"}


def run_numeric_audit(
    db: Session,
    *,
    artifact_id: str,
    min_duplicate_length: int = 3,
    min_last_digit_sample: int = 10,
    create_review_tasks: bool = True,
    priority: int = 7,
) -> dict[str, Any]:
    artifact = db.get(SourceArtifact, artifact_id)
    if artifact is None:
        raise LookupError(f"No artifact found for id {artifact_id}")
    paper = db.get(Paper, artifact.paper_id)
    if paper is None:
        raise LookupError(f"No paper found for artifact {artifact_id}")

    table = _load_table(artifact)
    columns = _numeric_columns(table)
    findings = []
    findings.extend(_duplicate_sequence_findings(columns, min_duplicate_length))
    findings.extend(_last_digit_findings(columns, min_last_digit_sample))

    signals: list[AlgorithmicSignal] = []
    created_review_tasks = 0
    for finding in findings[:20]:
        signal, created_task = _upsert_signal(db, paper, artifact, finding, create_review_tasks, priority)
        signals.append(signal)
        created_review_tasks += int(created_task)

    paper.audit_status = "in_review" if signals else "reviewed"
    db.commit()
    for signal in signals:
        db.refresh(signal)
    return {
        "artifact_id": artifact.id,
        "paper_id": paper.id,
        "analyzed_rows": table["row_count"],
        "analyzed_numeric_columns": len(columns),
        "signal_count": len(signals),
        "created_review_tasks": created_review_tasks,
        "signals": [_signal_dict(signal) for signal in signals],
        "conclusion_boundary": "数值审计只产生 algorithmic_signal，用于排序和人工复核，不能单独证明论文或作者造假。",
    }


def _load_table(artifact: SourceArtifact) -> dict[str, Any]:
    path = _artifact_path(artifact)
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xlsm"}:
        rows = _read_xlsx(path)
    elif suffix in {".tsv", ".tab"}:
        rows = _read_delimited(path, delimiter="\t")
    else:
        rows = _read_delimited(path)
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        raise ValueError("artifact table is empty")
    headers, data_rows = _headers_and_rows(rows)
    return {"headers": headers, "rows": data_rows, "row_count": len(data_rows)}


def _artifact_path(artifact: SourceArtifact) -> Path:
    storage_uri = artifact.storage_uri
    if not storage_uri and artifact.source_url.startswith("file://"):
        storage_uri = artifact.source_url.removeprefix("file://")
    if not storage_uri:
        raise ValueError("numeric audit requires a locally stored CSV, TSV or XLSX artifact")
    path = Path(storage_uri)
    if not path.exists() or not path.is_file():
        raise ValueError(f"artifact file does not exist: {storage_uri}")
    return path


def _read_delimited(path: Path, delimiter: str | None = None) -> list[list[str]]:
    text = path.read_text(encoding="utf-8-sig")
    if delimiter is None:
        try:
            dialect = csv.Sniffer().sniff(text[:2048])
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ","
    return [[cell.strip() for cell in row] for row in csv.reader(text.splitlines(), delimiter=delimiter)]


def _read_xlsx(path: Path) -> list[list[str]]:
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as workbook:
        shared_strings = _xlsx_shared_strings(workbook, namespace)
        sheet_name = _first_sheet_name(workbook)
        root = ET.fromstring(workbook.read(sheet_name))

    rows: list[list[str]] = []
    for row_element in root.findall(".//x:sheetData/x:row", namespace):
        cells: dict[int, str] = {}
        for cell in row_element.findall("x:c", namespace):
            column_index = _xlsx_column_index(cell.attrib.get("r", "A1"))
            cells[column_index] = _xlsx_cell_value(cell, shared_strings, namespace)
        if cells:
            max_index = max(cells)
            rows.append([cells.get(index, "") for index in range(max_index + 1)])
    return rows


def _xlsx_shared_strings(workbook: zipfile.ZipFile, namespace: dict[str, str]) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    strings = []
    for item in root.findall(".//x:si", namespace):
        strings.append("".join(text.text or "" for text in item.findall(".//x:t", namespace)))
    return strings


def _first_sheet_name(workbook: zipfile.ZipFile) -> str:
    for name in workbook.namelist():
        if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"):
            return name
    raise ValueError("xlsx workbook has no worksheet")


def _xlsx_column_index(cell_ref: str) -> int:
    letters = "".join(char for char in cell_ref if char.isalpha()).upper() or "A"
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def _xlsx_cell_value(cell: ET.Element, shared_strings: list[str], namespace: dict[str, str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//x:t", namespace)).strip()
    value = cell.find("x:v", namespace)
    if value is None or value.text is None:
        return ""
    raw = value.text.strip()
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (IndexError, ValueError):
            return raw
    return raw


def _headers_and_rows(rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    first = rows[0]
    has_header = any(cell and _to_float(cell) is None for cell in first)
    if has_header:
        headers = [cell or f"Column {index + 1}" for index, cell in enumerate(first)]
        data_rows = rows[1:]
    else:
        headers = [f"Column {index + 1}" for index in range(max(len(row) for row in rows))]
        data_rows = rows
    width = max(len(headers), *(len(row) for row in data_rows)) if data_rows else len(headers)
    headers = headers + [f"Column {index + 1}" for index in range(len(headers), width)]
    data_rows = [row + [""] * (width - len(row)) for row in data_rows]
    return headers, data_rows


def _numeric_columns(table: dict[str, Any]) -> list[dict[str, Any]]:
    columns = []
    headers = table["headers"]
    rows = table["rows"]
    for index, header in enumerate(headers):
        values = []
        raw_values = []
        row_numbers = []
        for row_number, row in enumerate(rows, start=2):
            raw = row[index].strip() if index < len(row) else ""
            value = _to_float(raw)
            if value is None:
                continue
            values.append(value)
            raw_values.append(raw)
            row_numbers.append(row_number)
        if len(values) >= 2:
            columns.append({"index": index, "name": header, "values": values, "raw_values": raw_values, "row_numbers": row_numbers})
    return columns


def _duplicate_sequence_findings(columns: list[dict[str, Any]], min_length: int) -> list[dict[str, Any]]:
    findings = []
    seen_windows: dict[tuple[float, ...], list[tuple[str, int]]] = defaultdict(list)
    for column in columns:
        rounded = [round(value, 10) for value in column["values"]]
        for start in range(0, len(rounded) - min_length + 1):
            window = tuple(rounded[start : start + min_length])
            seen_windows[window].append((column["name"], column["row_numbers"][start]))

    for window, locations in seen_windows.items():
        distinct_locations = sorted(set(locations))
        distinct_columns = {location[0] for location in distinct_locations}
        if len(distinct_locations) >= 2 and (len(distinct_columns) >= 2 or len(window) >= min_length):
            columns_text = ", ".join(sorted(distinct_columns))
            findings.append(
                {
                    "signal_type": "numeric_duplicate_sequence",
                    "severity": "high" if len(distinct_columns) >= 2 else "medium",
                    "confidence": 0.9 if len(distinct_columns) >= 2 else 0.72,
                    "column_name": columns_text,
                    "summary": f"检测到长度为 {len(window)} 的重复数值序列，涉及列：{columns_text}。",
                    "metrics": {
                        "sequence_length": len(window),
                        "locations": [{"column": column, "row": row} for column, row in distinct_locations[:10]],
                        "sequence_preview": list(window),
                    },
                }
            )
            break
    return findings


def _last_digit_findings(columns: list[dict[str, Any]], min_sample: int) -> list[dict[str, Any]]:
    findings = []
    for column in columns:
        digits = [_last_digit(raw) for raw in column["raw_values"]]
        digits = [digit for digit in digits if digit is not None]
        if len(digits) < min_sample:
            continue
        counts = Counter(digits)
        expected = len(digits) / 10
        chi_square = sum(((counts.get(str(digit), 0) - expected) ** 2) / expected for digit in range(10))
        digit, count = counts.most_common(1)[0]
        majority_ratio = count / len(digits)
        if majority_ratio < 0.6 and chi_square < 30:
            continue
        severity = "high" if majority_ratio >= 0.8 or chi_square >= 50 else "medium"
        findings.append(
            {
                "signal_type": "numeric_last_digit_anomaly",
                "severity": severity,
                "confidence": round(min(0.99, 0.55 + majority_ratio / 2), 3),
                "column_name": column["name"],
                "summary": f"列 {column['name']} 的末位数字分布异常，数字 {digit} 占比 {majority_ratio:.0%}。",
                "metrics": {
                    "sample_size": len(digits),
                    "digit_counts": dict(counts),
                    "dominant_digit": digit,
                    "dominant_ratio": round(majority_ratio, 4),
                    "chi_square": round(chi_square, 4),
                },
            }
        )
    return findings


def _upsert_signal(
    db: Session,
    paper: Paper,
    artifact: SourceArtifact,
    finding: dict[str, Any],
    create_review_task: bool,
    priority: int,
) -> tuple[AlgorithmicSignal, bool]:
    signal = db.scalar(
        select(AlgorithmicSignal).where(
            AlgorithmicSignal.paper_id == paper.id,
            AlgorithmicSignal.artifact_id == artifact.id,
            AlgorithmicSignal.signal_type == finding["signal_type"],
            AlgorithmicSignal.analyzer_name == ANALYZER_NAME,
            AlgorithmicSignal.summary == finding["summary"],
        )
    )
    if signal is None:
        signal = AlgorithmicSignal(
            paper=paper,
            artifact_id=artifact.id,
            signal_type=finding["signal_type"],
            severity=finding["severity"],
            confidence=finding["confidence"],
            analyzer_name=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            summary=finding["summary"],
            metrics_json=finding["metrics"],
            status="needs_review",
        )
        db.add(signal)
        db.flush()
    else:
        signal.severity = finding["severity"]
        signal.confidence = finding["confidence"]
        signal.analyzer_version = ANALYZER_VERSION
        signal.metrics_json = finding["metrics"]
        if signal.status not in TERMINAL_SIGNAL_STATUSES:
            signal.status = "needs_review"
        db.execute(delete(EvidencePointer).where(EvidencePointer.signal_id == signal.id))

    db.add(
        EvidencePointer(
            paper_id=paper.id,
            signal=signal,
            artifact=artifact,
            table_label=artifact.filename,
            column_name=finding.get("column_name"),
            evidence_url=artifact.source_url,
            evidence_summary=finding["summary"],
        )
    )

    created_task = False
    if create_review_task and signal.status not in TERMINAL_SIGNAL_STATUSES:
        existing_task = db.scalar(select(ReviewTask).where(ReviewTask.signal_id == signal.id, ReviewTask.status == "open"))
        if existing_task is None:
            db.add(ReviewTask(paper=paper, signal=signal, task_type="signal_review", priority=priority))
            created_task = True
    return signal, created_task


def _signal_dict(signal: AlgorithmicSignal) -> dict[str, Any]:
    return {
        "id": signal.id,
        "paper_id": signal.paper_id,
        "artifact_id": signal.artifact_id,
        "signal_type": signal.signal_type,
        "severity": signal.severity,
        "confidence": signal.confidence,
        "status": signal.status,
        "summary": signal.summary,
        "metrics": signal.metrics_json,
    }


def _to_float(value: str) -> float | None:
    if value is None:
        return None
    raw = value.strip().replace(",", "")
    if raw in {"", "NA", "N/A", "nan", "NaN"}:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _last_digit(raw: str) -> str | None:
    digits = [char for char in raw.strip() if char.isdigit()]
    return digits[-1] if digits else None
