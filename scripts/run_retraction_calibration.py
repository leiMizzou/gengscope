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
    "data_irregularity",
    "raw_data_unavailable",
    "reproducibility_concern",
}
RELIABILITY_REASON_CATEGORIES = {"data_unreliable"}
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
    parser.add_argument("--metadata-sources", default="openalex,crossref")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--case-id")
    parser.add_argument("--inspect-landing-pages", action="store_true")
    parser.add_argument("--fetch-pdfs", action="store_true")
    parser.add_argument("--fetch-images", action="store_true")
    parser.add_argument("--extract-pdf-images", action="store_true")
    parser.add_argument("--run-image-audits", action="store_true")
    parser.add_argument("--deep-image-audits", action="store_true", help="Enable slower shift-correlation checks during image audits.")
    parser.add_argument("--max-image-artifacts", type=int, default=12)
    parser.add_argument("--record-official-events", action="store_true")
    parser.add_argument("--min-completed-cases", type=int)
    parser.add_argument("--min-matched-cases", type=int)
    parser.add_argument("--max-analyzer-gap", type=int)
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
                metadata_sources=[source.strip() for source in args.metadata_sources.split(",") if source.strip()],
                inspect_landing_pages=args.inspect_landing_pages,
                record_official_events=args.record_official_events,
                fetch_pdfs=args.fetch_pdfs,
                fetch_images=args.fetch_images or args.run_image_audits,
                extract_pdf_images=args.extract_pdf_images,
                run_image_audits=args.run_image_audits,
                deep_image_audits=args.deep_image_audits,
                max_image_artifacts=args.max_image_artifacts,
            )
            for case in cases
        ]
        output = build_output(args.base_url, results)
        baseline_checks = evaluate_baseline_checks(
            output,
            min_completed_cases=args.min_completed_cases,
            min_matched_cases=args.min_matched_cases,
            max_analyzer_gap=args.max_analyzer_gap,
        )
        if baseline_checks["items"]:
            output["baseline_checks"] = baseline_checks
        if args.format == "json":
            print(json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2))
        else:
            print(render_markdown(output))
        if not output["case_count"] or output["completed_case_count"] != output["case_count"]:
            return 2
        if baseline_checks["items"] and not baseline_checks["passed"]:
            return 3
        return 0
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
    metadata_sources: list[str],
    inspect_landing_pages: bool,
    record_official_events: bool,
    fetch_pdfs: bool,
    fetch_images: bool,
    extract_pdf_images: bool,
    run_image_audits: bool,
    deep_image_audits: bool,
    max_image_artifacts: int,
) -> dict[str, Any]:
    doi = case["doi"]
    encoded_doi = urllib.parse.quote(doi, safe="")
    try:
        imported, detail = import_doi_or_existing(client, doi, encoded_doi, metadata_sources=metadata_sources)
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
        fetch_results = []
        image_fetch_results = []
        extraction_results = []
        image_audit_results = []
        if fetch_pdfs or extract_pdf_images:
            fetch_results = fetch_pdf_artifacts(client, artifacts)
            artifacts = client.get(f"/api/artifacts/papers/{paper_id}")
        if extract_pdf_images:
            extraction_results = extract_images_from_pdf_artifacts(client, artifacts)
            artifacts = client.get(f"/api/artifacts/papers/{paper_id}")
        if fetch_images:
            image_fetch_results = fetch_image_artifacts(client, artifacts)
            artifacts = client.get(f"/api/artifacts/papers/{paper_id}")
        if run_image_audits:
            image_audit_results = run_pairwise_image_audits(
                client,
                artifacts,
                max_image_artifacts=max_image_artifacts,
                deep_image_audits=deep_image_audits,
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
            "material_operations": {
                "fetched_pdf_count": sum(1 for item in fetch_results if item.get("artifact", {}).get("storage_uri")),
                "pdf_fetch_error_count": sum(1 for item in fetch_results if item.get("error")),
                "fetched_image_count": sum(1 for item in image_fetch_results if item.get("artifact", {}).get("storage_uri")),
                "image_fetch_error_count": sum(1 for item in image_fetch_results if item.get("error")),
                "pdf_image_extraction_count": sum(item.get("extracted_count", 0) for item in extraction_results),
                "pdf_image_extraction_error_count": sum(1 for item in extraction_results if item.get("error")),
                "image_audit_signal_count": sum(item.get("signal_count", 0) for item in image_audit_results),
                "image_audit_error_count": sum(1 for item in image_audit_results if item.get("error")),
            },
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


def import_doi_or_existing(
    client: ApiClient,
    doi: str,
    encoded_doi: str,
    *,
    metadata_sources: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        imported = client.post(
            "/api/admin/import/doi",
            {"doi": doi, "sources": metadata_sources or ["openalex", "crossref"]},
        )
        detail = client.get(f"/api/papers/{encoded_doi}")
        return imported, detail
    except Exception as exc:
        try:
            detail = client.get(f"/api/papers/{encoded_doi}")
        except Exception:
            raise exc
        paper = detail["paper"]
        return {
            "doi": paper.get("doi") or doi,
            "title": paper.get("title"),
            "source": "existing_local_record",
            "import_warning": str(exc),
        }, detail


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


def fetch_pdf_artifacts(client: ApiClient, artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for artifact in artifacts.get("items", []):
        if artifact["artifact_type"] != "paper_pdf":
            continue
        if artifact.get("storage_uri"):
            continue
        try:
            results.append(
                client.post(
                    "/api/artifacts/fetch",
                    {
                        "artifact_id": artifact["id"],
                        "license_status": "open_or_linked",
                        "max_bytes": 50 * 1024 * 1024,
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001 - keep calibration batch moving.
            results.append({"artifact_id": artifact["id"], "error": str(exc)})
    return results


def extract_images_from_pdf_artifacts(client: ApiClient, artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for artifact in artifacts.get("items", []):
        if artifact["artifact_type"] != "paper_pdf" or not artifact.get("storage_uri"):
            continue
        try:
            results.append(
                client.post(
                    "/api/artifacts/extract/pdf-images",
                    {
                        "artifact_id": artifact["id"],
                        "max_pages": 12,
                        "max_images": 60,
                        "min_width": 90,
                        "min_height": 90,
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            results.append({"artifact_id": artifact["id"], "error": str(exc)})
    return results


def fetch_image_artifacts(client: ApiClient, artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for artifact in artifacts.get("items", []):
        if artifact["artifact_type"] not in {"figure_image", "image_panel", "supplementary_image"}:
            continue
        if artifact.get("storage_uri"):
            continue
        try:
            results.append(
                client.post(
                    "/api/artifacts/fetch",
                    {
                        "artifact_id": artifact["id"],
                        "license_status": "open_or_linked",
                        "max_bytes": 25 * 1024 * 1024,
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            results.append({"artifact_id": artifact["id"], "error": str(exc)})
    return results


def run_pairwise_image_audits(
    client: ApiClient,
    artifacts: dict[str, Any],
    *,
    max_image_artifacts: int,
    deep_image_audits: bool,
) -> list[dict[str, Any]]:
    images = [
        item
        for item in artifacts.get("items", [])
        if item["artifact_type"] in {"figure_image", "image_panel", "supplementary_image"} and item.get("storage_uri")
    ][: max(1, max_image_artifacts)]
    results = []
    for index, artifact in enumerate(images):
        peers = [item["id"] for item in images[index + 1 :]]
        try:
            results.append(
                client.post(
                    "/api/audits/image",
                    {
                        "artifact_id": artifact["id"],
                        "compare_artifact_ids": peers,
                        "max_hamming_distance": 4,
                        "enable_patch_similarity": True,
                        "enable_shift_correlation": deep_image_audits,
                        "priority": 8,
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            results.append({"artifact_id": artifact["id"], "error": str(exc)})
    return results


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
        elif group == "reliability_conclusion":
            primary_groups = signal_groups & {"image_integrity", "data_integrity", "table_or_metadata"}
            if primary_groups:
                status = "covered_by_primary_signal"
                recommendation = "Reliability concern is a downstream official conclusion; review the matched primary evidence signal before treating this as a separate data-material miss."
            else:
                status = "context_label_only"
                recommendation = "Reliability concern is a downstream official conclusion; improve primary evidence analyzers rather than counting this as missing source-data material."
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
    if category in RELIABILITY_REASON_CATEGORIES:
        return "reliability_conclusion"
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
        "import_warning": imported.get("import_warning"),
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
        "prefix_checkpoints": prefix_match_checkpoints(results),
        "status_counts": status_counts,
        "cases": results,
        "next_actions": next_actions(status_counts),
        "conclusion_boundary": "回顾性校准用于衡量 blind signals 与官方撤稿原因的贴合度，不能据此直接认定任何未被官方确认的论文、作者或机构造假。",
    }


def prefix_match_checkpoints(results: list[dict[str, Any]], sizes: tuple[int, ...] = (5, 10, 20)) -> list[dict[str, int]]:
    checkpoints = []
    result_count = len(results)
    for size in sizes:
        if size <= result_count:
            checkpoints.append(prefix_match_checkpoint(results, size))
    if result_count and (not checkpoints or checkpoints[-1]["case_count"] != result_count):
        checkpoints.append(prefix_match_checkpoint(results, result_count))
    return checkpoints


def prefix_match_checkpoint(results: list[dict[str, Any]], size: int) -> dict[str, int]:
    prefix = results[:size]
    completed = [result for result in prefix if result.get("completed")]
    matched = [result for result in completed if result["alignment"]["case_alignment_status"] == "matched"]
    return {
        "case_count": size,
        "completed_case_count": len(completed),
        "matched_case_count": len(matched),
    }


def evaluate_baseline_checks(
    output: dict[str, Any],
    *,
    min_completed_cases: int | None = None,
    min_matched_cases: int | None = None,
    max_analyzer_gap: int | None = None,
) -> dict[str, Any]:
    items = []
    if min_completed_cases is not None:
        actual = output["completed_case_count"]
        items.append(
            {
                "name": "min_completed_cases",
                "actual": actual,
                "expected": min_completed_cases,
                "passed": actual >= min_completed_cases,
            }
        )
    if min_matched_cases is not None:
        actual = output["matched_case_count"]
        items.append(
            {
                "name": "min_matched_cases",
                "actual": actual,
                "expected": min_matched_cases,
                "passed": actual >= min_matched_cases,
            }
        )
    if max_analyzer_gap is not None:
        actual = output["status_counts"].get("analyzer_gap", 0)
        items.append(
            {
                "name": "max_analyzer_gap",
                "actual": actual,
                "expected": max_analyzer_gap,
                "passed": actual <= max_analyzer_gap,
            }
        )
    return {"passed": all(item["passed"] for item in items), "items": items}


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
    ]
    if output.get("prefix_checkpoints"):
        lines.append(
            "- Prefix checkpoints: "
            + ", ".join(
                f"{item['matched_case_count']}/{item['case_count']} matched"
                for item in output["prefix_checkpoints"]
            )
        )
    lines.extend(
        [
            "",
            "| Case | DOI | Blind material | Material ops | Blind signals | Official reason groups | Alignment |",
            "| --- | --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for result in output["cases"]:
        if not result.get("completed"):
            lines.append(f"| {result['case']['case_id']} | `{result['case']['doi']}` | error | - | 0 | - | {result['error']} |")
            continue
        case = result["case"]
        blind = result["blind"]
        alignment = result["alignment"]
        group_summary = ", ".join(
            f"{item['group']}:{item['status']}" for item in alignment["group_results"]
        )
        operations = result.get("material_operations") or {}
        operation_summary = (
            f"pdf={operations.get('fetched_pdf_count', 0)}, "
            f"remote_images={operations.get('fetched_image_count', 0)}, "
            f"images={operations.get('pdf_image_extraction_count', 0)}, "
            f"image_signals={operations.get('image_audit_signal_count', 0)}, "
            f"errors={sum(operations.get(key, 0) for key in ('pdf_fetch_error_count', 'image_fetch_error_count', 'pdf_image_extraction_error_count', 'image_audit_error_count'))}"
        )
        lines.append(
            f"| {case['case_id']} | `{case['doi']}` | {blind['material_status']} / {', '.join(blind['artifact_types']) or 'none'} | "
            f"{operation_summary} | {blind['algorithmic_signal_count']} | {', '.join(alignment['expected_groups'])} | {group_summary} |"
        )
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in output["next_actions"])
    baseline_checks = output.get("baseline_checks")
    if baseline_checks and baseline_checks.get("items"):
        lines.extend(["", "## Baseline Checks", ""])
        lines.append(f"- Passed: `{baseline_checks['passed']}`")
        for item in baseline_checks["items"]:
            comparator = ">=" if item["name"].startswith("min_") else "<="
            lines.append(
                f"- {item['name']}: actual `{item['actual']}` {comparator} expected `{item['expected']}` -> `{item['passed']}`"
            )
    lines.extend(["", f"结论边界：{output['conclusion_boundary']}"])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
