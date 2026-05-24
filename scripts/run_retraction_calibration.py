#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_CASE_FILE = Path("data/seeds/retraction_calibration_cases.json")
IMAGE_REASON_CATEGORIES = {
    "image_duplication",
    "image_overlap",
    "image_identity_concern",
    "image_manipulation",
    "western_blot_duplication",
    "cross_paper_image_duplication",
    "image_flip_similarity",
    "cell_image_duplication",
    "image_rotation_similarity",
    "histology_inconsistency",
}
DATA_REASON_CATEGORIES = {
    "data_unreliable",
    "data_irregularity",
    "raw_data_unavailable",
    "reproducibility_concern",
}
TABLE_REASON_CATEGORIES = {"table_inconsistency"}


class ApiClient:
    def __init__(self, base_url: str, api_key: str | None = None, actor: str = "retraction-calibration") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.actor = actor

    def get(self, path: str) -> dict[str, Any]:
        return self._request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, payload)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {"accept": "application/json", "X-GengScope-Actor": self.actor}
        data = None
        if payload is not None:
            headers["content-type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {body}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run blind GengScope signal extraction on retracted papers, then align signals with official retraction reasons."
    )
    parser.add_argument("--base-url", default=os.getenv("GENGSCOPE_BASE_URL", "http://127.0.0.1:8010"))
    parser.add_argument("--api-key", default=os.getenv("GENGSCOPE_API_KEY"))
    parser.add_argument("--cases-file", default=str(DEFAULT_CASE_FILE))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--case-id")
    parser.add_argument("--inspect-landing-pages", action="store_true")
    parser.add_argument("--record-official-events", action="store_true")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cases = load_cases(Path(args.cases_file), limit=args.limit, case_id=args.case_id)
        client = ApiClient(args.base_url, args.api_key)
        results = [
            run_case(
                client,
                case,
                inspect_landing_pages=args.inspect_landing_pages,
                record_official_events=args.record_official_events,
            )
            for case in cases
        ]
        output = build_output(args.base_url, results)
        if args.format == "json":
            print(json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2))
        else:
            print(render_markdown(output))
        return 0 if output["case_count"] and output["completed_case_count"] == output["case_count"] else 2
    except Exception as exc:
        print(f"retraction-calibration: {exc}", file=sys.stderr)
        return 1


def load_cases(path: Path, *, limit: int | None = None, case_id: str | None = None) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload["cases"]
    if case_id:
        cases = [case for case in cases if case["case_id"] == case_id]
    if limit is not None:
        cases = cases[:limit]
    if not cases:
        raise ValueError("no calibration cases selected")
    return cases


def run_case(
    client: ApiClient,
    case: dict[str, Any],
    *,
    inspect_landing_pages: bool,
    record_official_events: bool,
) -> dict[str, Any]:
    doi = case["doi"]
    encoded_doi = urllib.parse.quote(doi, safe="")
    try:
        imported = client.post("/api/admin/import/doi", {"doi": doi, "sources": ["openalex", "crossref"]})
        detail = client.get(f"/api/papers/{encoded_doi}")
        paper_id = detail["paper"]["id"]
        artifacts = client.post(
            "/api/artifacts/discover",
            {
                "paper_id": paper_id,
                "inspect_landing_pages": bool(inspect_landing_pages),
                "max_landing_pages": 3,
                "max_discovered_links": 30,
            },
        )
        blind_detail = client.get(f"/api/papers/{encoded_doi}")
        blind = blind_evidence(blind_detail, artifacts)
        alignment = align_blind_signals_with_official_reasons(blind, case["reason_categories"])
        official_event = None
        if record_official_events:
            official_event = ensure_official_event(client, blind_detail, case)
        return {
            "case": case_summary(case, imported, blind_detail),
            "completed": True,
            "blind": blind,
            "official_reason": {
                "source_url": case["official_notice"]["source_url"],
                "notice_doi": case["official_notice"]["notice_doi"],
                "event_date": case["official_notice"]["event_date"],
                "reason_summary": case["official_notice"]["reason_summary"],
                "reason_categories": case["reason_categories"],
            },
            "alignment": alignment,
            "recorded_official_event": official_event,
            "conclusion_boundary": "这是回顾性校准：系统先输出 blind signals，再与官方撤稿原因对齐；不能把对齐结果当作独立造假认定。",
        }
    except Exception as exc:  # noqa: BLE001 - report every failed case in aggregate output.
        return {
            "case": {"case_id": case["case_id"], "doi": doi, "title_hint": case.get("title_hint")},
            "completed": False,
            "error": str(exc),
        }


def blind_evidence(detail: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
    signals = [
        {
            "signal_type": signal["signal_type"],
            "severity": signal.get("severity"),
            "status": signal.get("status"),
            "summary": signal.get("summary"),
            "metrics": signal.get("metrics") or {},
            "group": signal_group(signal["signal_type"]),
        }
        for signal in detail.get("algorithmic_signals", [])
        if signal.get("status") in {"needs_review", "in_review", "confirmed_signal", "promoted_to_event"}
    ]
    artifact_items = artifacts.get("items", detail.get("artifacts", []))
    artifact_types = sorted({item["artifact_type"] for item in artifact_items})
    return {
        "material_status": artifacts.get("material_status") or detail["paper"]["material_status"],
        "artifact_count": len(artifact_items),
        "artifact_types": artifact_types,
        "artifacts": [
            {
                "artifact_type": item["artifact_type"],
                "source_url": item.get("source_url"),
                "filename": item.get("filename"),
                "license_status": item.get("license_status"),
            }
            for item in artifact_items[:20]
        ],
        "algorithmic_signal_count": len(signals),
        "signal_groups": sorted({signal["group"] for signal in signals if signal["group"] != "other"}),
        "signals": signals[:20],
    }


def align_blind_signals_with_official_reasons(blind: dict[str, Any], reason_categories: list[str]) -> dict[str, Any]:
    expected_groups = sorted({reason_group(category) for category in reason_categories})
    signal_groups = set(blind.get("signal_groups", []))
    artifact_types = set(blind.get("artifact_types", []))
    group_results = []
    for group in expected_groups:
        if group in signal_groups:
            status = "matched_by_blind_signal"
            recommendation = "Use this case as a positive calibration example for the existing analyzer."
        elif group == "image_integrity":
            if artifact_types & {"figure_image", "image_panel", "supplementary_image"}:
                status = "analyzer_gap"
                recommendation = "Figure/image material was present, but no image-integrity signal fired; inspect analyzer thresholds and panel matching."
            elif artifact_types & {"paper_pdf", "publisher_landing_page"}:
                status = "extraction_gap"
                recommendation = "Only PDF/landing material was found; add PDF/HTML figure extraction before judging image analyzer recall."
            else:
                status = "material_gap"
                recommendation = "No figure or PDF material was found; improve artifact discovery/fetching first."
        elif group == "data_integrity":
            if artifact_types & {"source_data", "source_data_table", "supplementary_data", "supplementary_table"}:
                status = "analyzer_gap"
                recommendation = "Source/supplementary data was present, but no numeric/data signal fired; improve data parsers and numeric checks."
            elif artifact_types & {"paper_pdf", "publisher_landing_page"}:
                status = "material_gap"
                recommendation = "Paper/landing material was found but no auditable source-data table; improve supplementary/source-data discovery."
            else:
                status = "material_gap"
                recommendation = "No auditable data material was found; improve material discovery before scoring recall."
        elif group == "table_or_metadata":
            status = "unsupported_signal_family"
            recommendation = "Official reason concerns table/metadata consistency; add table extraction and primer/metadata consistency checks."
        else:
            status = "unsupported_signal_family"
            recommendation = "No current analyzer family maps to this official reason category."
        group_results.append({"group": group, "status": status, "recommendation": recommendation})
    matched_groups = [item["group"] for item in group_results if item["status"] == "matched_by_blind_signal"]
    return {
        "expected_groups": expected_groups,
        "blind_signal_groups": sorted(signal_groups),
        "matched_groups": matched_groups,
        "match_count": len(matched_groups),
        "group_results": group_results,
        "case_alignment_status": "matched" if matched_groups else "gap_found",
    }


def signal_group(signal_type: str) -> str:
    if signal_type.startswith("image_"):
        return "image_integrity"
    if signal_type.startswith("numeric_"):
        return "data_integrity"
    if signal_type.startswith("metadata_"):
        return "table_or_metadata"
    return "other"


def reason_group(category: str) -> str:
    if category in IMAGE_REASON_CATEGORIES:
        return "image_integrity"
    if category in DATA_REASON_CATEGORIES:
        return "data_integrity"
    if category in TABLE_REASON_CATEGORIES:
        return "table_or_metadata"
    return "other"


def ensure_official_event(client: ApiClient, detail: dict[str, Any], case: dict[str, Any]) -> dict[str, Any] | None:
    notice = case["official_notice"]
    for event in detail.get("events", []):
        if event.get("status_level") == "official_retraction" and event.get("source_url") == notice["source_url"]:
            return {"id": event["id"], "status": "already_present"}
    created = client.post(
        "/api/admin/events",
        {
            "doi": case["doi"],
            "event_type": "retraction_notice",
            "status_level": "official_retraction",
            "source_type": "publisher",
            "source_name": notice["source_name"],
            "source_url": notice["source_url"],
            "event_date": notice["event_date"],
            "claim_summary": notice["reason_summary"][:800],
            "verification_status": "official_confirmed",
            "created_by": "retraction-calibration",
        },
    )
    return {"id": created["id"], "status": "created"}


def case_summary(case: dict[str, Any], imported: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "doi": case["doi"],
        "title_hint": case.get("title_hint"),
        "imported_title": imported.get("title"),
        "indexed_title": detail["paper"]["title"],
        "paper_id": detail["paper"]["id"],
        "publication_year": detail["paper"].get("publication_year"),
        "journal_name": detail["paper"].get("journal_name"),
    }


def build_output(base_url: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [result for result in results if result.get("completed")]
    matched = [result for result in completed if result["alignment"]["case_alignment_status"] == "matched"]
    status_counts: dict[str, int] = {}
    for result in completed:
        for item in result["alignment"]["group_results"]:
            status_counts[item["status"]] = status_counts.get(item["status"], 0) + 1
    return {
        "base_url": base_url,
        "case_count": len(results),
        "completed_case_count": len(completed),
        "matched_case_count": len(matched),
        "status_counts": status_counts,
        "cases": results,
        "next_actions": next_actions(status_counts),
        "conclusion_boundary": "回顾性校准用于衡量 blind signals 与官方撤稿原因的贴合度，不能据此直接认定任何未被官方确认的论文、作者或机构造假。",
    }


def next_actions(status_counts: dict[str, int]) -> list[str]:
    actions = []
    if status_counts.get("extraction_gap"):
        actions.append("Build PDF/HTML figure-panel extraction so image-related notices can be tested before reading the reason.")
    if status_counts.get("material_gap"):
        actions.append("Improve publisher/PMC supplementary and source-data discovery before interpreting analyzer recall.")
    if status_counts.get("analyzer_gap"):
        actions.append("Tune numeric/image analyzers on cases where auditable material exists but no signal fires.")
    if status_counts.get("unsupported_signal_family"):
        actions.append("Add table/primer/metadata consistency checks for non-image official reasons.")
    if not actions:
        actions.append("Add more calibration cases and lock matched examples as regression fixtures.")
    return actions


def render_markdown(output: dict[str, Any]) -> str:
    lines = [
        "# Retraction Calibration Run",
        "",
        f"- Cases: {output['completed_case_count']}/{output['case_count']} completed",
        f"- Matched cases: {output['matched_case_count']}",
        f"- Status counts: `{json.dumps(output['status_counts'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "| Case | DOI | Blind material | Blind signals | Official reason groups | Alignment |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for result in output["cases"]:
        if not result.get("completed"):
            lines.append(f"| {result['case']['case_id']} | `{result['case']['doi']}` | error | 0 | - | {result['error']} |")
            continue
        case = result["case"]
        blind = result["blind"]
        alignment = result["alignment"]
        group_summary = ", ".join(
            f"{item['group']}:{item['status']}" for item in alignment["group_results"]
        )
        lines.append(
            f"| {case['case_id']} | `{case['doi']}` | {blind['material_status']} / {', '.join(blind['artifact_types']) or 'none'} | "
            f"{blind['algorithmic_signal_count']} | {', '.join(alignment['expected_groups'])} | {group_summary} |"
        )
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in output["next_actions"])
    lines.extend(["", f"结论边界：{output['conclusion_boundary']}"])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
