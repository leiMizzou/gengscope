#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


REAL_CASES = [
    {
        "case_id": "hindawi-pgp-ischemia-2023",
        "doi": "10.1155/2023/6916819",
        "expected_title": "P-Glycoprotein Exacerbates Brain Injury",
        "expected_institution": "China Pharmaceutical University",
        "expected_authors": ["Yunman Li", "Weirong Fang"],
        "official_event": {
            "event_type": "retraction_notice",
            "status_level": "official_retraction",
            "source_type": "publisher",
            "source_name": "Wiley / Hindawi",
            "source_url": "https://onlinelibrary.wiley.com/doi/10.1155/omcl/9837687",
            "event_date": "2025-11-07",
            "claim_summary": (
                "Publisher retraction notice reports multiple image duplication concerns, including overlap and "
                "duplicated figures; the publisher considered the data and conclusions unreliable."
            ),
            "verification_status": "official_confirmed",
            "created_by": "real-cases-e2e",
        },
    },
    {
        "case_id": "hindawi-valine-nafld-2021",
        "doi": "10.1155/2021/4704771",
        "expected_title": "Dietary Valine Ameliorated Gut Health",
        "expected_institution": "Zhejiang University",
        "expected_authors": ["Huafeng Jian", "Xiaoting Zou"],
        "official_event": {
            "event_type": "retraction_notice",
            "status_level": "official_retraction",
            "source_type": "publisher",
            "source_name": "Wiley / Hindawi",
            "source_url": "https://onlinelibrary.wiley.com/doi/10.1155/omcl/9784052",
            "event_date": "2025-10-16",
            "claim_summary": (
                "Publisher retraction notice reports duplicated Figure 2 panels, incorrect primer information in "
                "Table 2, overlapping features in Figure 1, and unreliable data and conclusions."
            ),
            "verification_status": "official_confirmed",
            "created_by": "real-cases-e2e",
        },
    },
    {
        "case_id": "wiley-methotrexate-lung-injury-2023",
        "doi": "10.1113/EP091162",
        "expected_title": "Comparison of preventive and therapeutic effects of continuous exercise",
        "expected_institution": "Kerman University of Medical Sciences",
        "expected_authors": ["Mohammad-Amin Rajizadeh", "Mohammad Abbas Bejeshk"],
        "official_event": {
            "event_type": "retraction_notice",
            "status_level": "official_retraction",
            "source_type": "publisher",
            "source_name": "Wiley / Experimental Physiology",
            "source_url": "https://physoc.onlinelibrary.wiley.com/doi/10.1113/EPH.13825",
            "event_date": "2025-03-20",
            "claim_summary": (
                "Publisher retraction notice reports concerns about figure tissue identity, unavailable original "
                "immunohistochemistry slides, inconsistent histology and magnification, and unreliable data and conclusions."
            ),
            "verification_status": "official_confirmed",
            "created_by": "real-cases-e2e",
        },
    },
]


RISK_KEYWORDS = (
    "data",
    "image",
    "figure",
    "table",
    "duplicat",
    "overlap",
    "unreliable",
    "histology",
    "raw data",
    "manipulat",
    "slides",
)


class ApiClient:
    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def get(self, path: str) -> dict[str, Any]:
        return self._request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, payload)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {"accept": "application/json", "X-GengScope-Actor": "real-cases-e2e"}
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run GengScope against multiple public real retraction cases.")
    parser.add_argument("--base-url", default=os.getenv("GENGSCOPE_BASE_URL", "http://127.0.0.1:8010"))
    parser.add_argument("--api-key", default=os.getenv("GENGSCOPE_API_KEY"))
    parser.add_argument("--min-risky-cases", type=int, default=3)
    parser.add_argument("--inspect-landing-pages", action="store_true")
    args = parser.parse_args()

    client = ApiClient(args.base_url, args.api_key)
    cases = []
    for case in REAL_CASES:
        try:
            cases.append(run_case(client, case, inspect_landing_pages=args.inspect_landing_pages))
        except Exception as exc:  # noqa: BLE001 - this script should report all case failures as JSON.
            cases.append({"case": {"case_id": case["case_id"], "doi": case["doi"]}, "passed": False, "error": str(exc)})

    risky_case_count = sum(1 for case in cases if case.get("checks", {}).get("risk_case_detected"))
    output = {
        "base_url": args.base_url,
        "required_risky_case_count": args.min_risky_cases,
        "risky_case_count": risky_case_count,
        "case_count": len(cases),
        "passed": risky_case_count >= args.min_risky_cases and all(case.get("passed") for case in cases),
        "cases": cases,
        "assessment": (
            "Each passing case is a source-attributed official retraction with data, figure, image, table or "
            "related evidentiary concerns mapped back to local paper, author and institution entities."
        ),
        "conclusion_boundary": "这些结果只能说明公开来源记录了高风险科研完整性问题，不能单独证明论文、作者、实验室或机构造假。",
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output["passed"] else 2


def run_case(client: ApiClient, case: dict[str, Any], *, inspect_landing_pages: bool) -> dict[str, Any]:
    doi = case["doi"]
    encoded_doi = urllib.parse.quote(doi, safe="")
    imported = client.post("/api/admin/import/doi", {"doi": doi, "sources": ["openalex", "crossref"]})
    detail = client.get(f"/api/papers/{encoded_doi}")
    ensure_event(client, detail, doi, case)
    paper_id = detail["paper"]["id"]
    artifacts = client.post(
        "/api/artifacts/discover",
        {"paper_id": paper_id, "inspect_landing_pages": bool(inspect_landing_pages), "max_landing_pages": 3, "max_discovered_links": 30},
    )
    detail = client.get(f"/api/papers/{encoded_doi}")
    risk_card = client.get(f"/api/papers/{encoded_doi}/risk-card")

    institution_authorship = choose_institution_authorship(detail["authorships"], case["expected_institution"])
    institution_profile = None
    institution_breakdown = None
    institution_report = None
    if institution_authorship and institution_authorship.get("institution_id"):
        institution_id = institution_authorship["institution_id"]
        institution_profile = client.get(f"/api/entities/institution/{institution_id}/profile")
        institution_breakdown = client.get(f"/api/entities/institution/{institution_id}/breakdown?limit=12&min_papers=1")
        institution_report = client.get(f"/api/reports/entity?entity_type=institution&entity_id={urllib.parse.quote(institution_id, safe='')}")

    author_profiles = []
    for authorship in choose_author_authorships(detail["authorships"], case.get("expected_authors", [])):
        author_id = authorship.get("author_id")
        if not author_id:
            continue
        profile = client.get(f"/api/entities/author/{author_id}/profile")
        author_profiles.append(
            {
                "author_id": author_id,
                "display_name": authorship["author_name_raw"],
                "author_role": authorship.get("author_role"),
                "is_corresponding": authorship.get("is_corresponding"),
                "profile": compact_profile(profile),
            }
        )

    authorship_names = [authorship.get("author_name_raw") or "" for authorship in detail["authorships"]]
    checks = {
        "paper_imported": imported["doi"] == doi.casefold() and normalized_contains(imported["title"], case["expected_title"]),
        "official_retraction_detected": risk_card["official_status"] == "retracted" and risk_card["highest_signal_level"] == "official",
        "publisher_retraction_detected": risk_card["publisher_status"] == "retraction",
        "source_attributed_integrity_issue_detected": source_attributed_integrity_issue_detected(risk_card),
        "expected_institution_identified": bool(
            institution_authorship
            and (
                normalized_contains(institution_authorship.get("institution_display_name") or "", case["expected_institution"])
                or normalized_contains(institution_authorship.get("affiliation_raw") or "", case["expected_institution"])
            )
        ),
        "institution_breakdown_available": bool(institution_breakdown and institution_breakdown.get("affiliation_units")),
        "expected_authors_identified": expected_authors_identified(authorship_names, case.get("expected_authors", [])),
        "specific_authors_profiled": bool(author_profiles),
        "pdf_or_landing_material_found": detail["paper"]["material_status"] in {"landing_page_found", "pdf_found", "source_data_found", "full_auditable"},
    }
    checks["risk_case_detected"] = (
        checks["official_retraction_detected"]
        and checks["publisher_retraction_detected"]
        and checks["source_attributed_integrity_issue_detected"]
    )

    return {
        "case": {
            "case_id": case["case_id"],
            "doi": doi,
            "paper_title": detail["paper"]["title"],
            "official_source_url": case["official_event"]["source_url"],
            "official_event_date": case["official_event"]["event_date"],
            "expected_institution": case["expected_institution"],
            "expected_authors": case.get("expected_authors", []),
        },
        "checks": checks,
        "passed": all(checks.values()),
        "paper": {
            "id": paper_id,
            "material_status": detail["paper"]["material_status"],
            "is_oa_pdf_available": detail["paper"]["is_oa_pdf_available"],
            "is_source_data_available": detail["paper"]["is_source_data_available"],
            "event_count": len(detail["events"]),
            "algorithmic_signal_count": len(detail["algorithmic_signals"]),
        },
        "risk_card": risk_card,
        "identified_institution": compact_authorship(institution_authorship) if institution_authorship else None,
        "institution_profile": compact_profile(institution_profile) if institution_profile else None,
        "institution_breakdown": compact_breakdown(institution_breakdown) if institution_breakdown else None,
        "institution_report": compact_report(institution_report) if institution_report else None,
        "author_profiles": author_profiles,
        "artifacts": {
            "material_status": artifacts["material_status"],
            "artifact_count": len(artifacts.get("items", [])),
            "items": [
                {
                    "artifact_type": item["artifact_type"],
                    "source_url": item["source_url"],
                    "license_status": item["license_status"],
                    "filename": item.get("filename"),
                }
                for item in artifacts.get("items", [])[:10]
            ],
        },
        "assessment": (
            "This case is counted as risky because a publisher/official source has a retraction notice with "
            "data, figure, image, table or related evidentiary concerns. It is not an independent fraud finding."
        ),
        "conclusion_boundary": "真实案例结果只复述公开来源状态与本地索引/审计信号，不能据此直接认定论文、作者、实验室或机构造假。",
    }


def ensure_event(client: ApiClient, detail: dict[str, Any], doi: str, case: dict[str, Any]) -> None:
    event = case["official_event"]
    for existing in detail.get("events", []):
        if existing.get("status_level") == event["status_level"] and existing.get("source_url") == event["source_url"]:
            return
    payload = {"doi": doi, **event}
    client.post("/api/admin/events", payload)


def choose_institution_authorship(authorships: list[dict[str, Any]], expected_institution: str) -> dict[str, Any] | None:
    for authorship in authorships:
        if normalized_contains(authorship.get("institution_display_name") or "", expected_institution):
            return authorship
    for authorship in authorships:
        if normalized_contains(authorship.get("affiliation_raw") or "", expected_institution):
            return authorship
    for authorship in authorships:
        if authorship.get("institution_id"):
            return authorship
    return None


def choose_author_authorships(authorships: list[dict[str, Any]], expected_authors: list[str]) -> list[dict[str, Any]]:
    selected = []
    seen_ids = set()
    for expected in expected_authors:
        for authorship in authorships:
            author_id = authorship.get("author_id")
            if author_id and author_id not in seen_ids and normalized_contains(authorship.get("author_name_raw") or "", expected):
                selected.append(authorship)
                seen_ids.add(author_id)
                break
    for authorship in authorships:
        author_id = authorship.get("author_id")
        if authorship.get("is_corresponding") and author_id and author_id not in seen_ids:
            selected.append(authorship)
            seen_ids.add(author_id)
    for authorship in authorships:
        author_id = authorship.get("author_id")
        if author_id and author_id not in seen_ids:
            selected.append(authorship)
            seen_ids.add(author_id)
        if len(selected) >= 4:
            break
    return selected[:4]


def source_attributed_integrity_issue_detected(risk_card: dict[str, Any]) -> bool:
    for item in risk_card.get("evidence", []):
        summary = normalize_text(item.get("summary") or "")
        if any(keyword in summary for keyword in RISK_KEYWORDS):
            return True
    return False


def expected_authors_identified(actual_names: list[str], expected_names: list[str]) -> bool:
    if not expected_names:
        return bool(actual_names)
    return all(any(normalized_contains(actual, expected) for actual in actual_names) for expected in expected_names)


def normalized_contains(haystack: str, needle: str) -> bool:
    return normalize_text(needle) in normalize_text(haystack)


def normalize_text(value: str) -> str:
    value = value.casefold()
    value = value.replace("\u2010", "-").replace("\u2011", "-").replace("\u2012", "-").replace("\u2013", "-").replace("\u2014", "-")
    return re.sub(r"\s+", " ", value).strip()


def compact_authorship(authorship: dict[str, Any] | None) -> dict[str, Any] | None:
    if not authorship:
        return None
    return {
        "author_id": authorship.get("author_id"),
        "institution_id": authorship.get("institution_id"),
        "author_name_raw": authorship.get("author_name_raw"),
        "author_role": authorship.get("author_role"),
        "is_corresponding": authorship.get("is_corresponding"),
        "institution_display_name": authorship.get("institution_display_name"),
        "affiliation_raw": authorship.get("affiliation_raw"),
    }


def compact_profile(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    if not profile:
        return None
    return {
        "entity": profile["entity"],
        "paper_count": profile["paper_count"],
        "auditable_paper_count": profile["auditable_paper_count"],
        "official_event_count": profile["official_event_count"],
        "algorithmic_signal_count": profile["algorithmic_signal_count"],
        "priority": profile["priority"],
        "summary": profile["summary"],
        "conclusion_boundary": profile["conclusion_boundary"],
    }


def compact_breakdown(breakdown: dict[str, Any] | None) -> dict[str, Any] | None:
    if not breakdown:
        return None
    return {
        "affiliation_unit_count": breakdown["affiliation_unit_count"],
        "author_count": breakdown["author_count"],
        "affiliation_units": breakdown["affiliation_units"][:5],
        "top_authors": breakdown["top_authors"][:5],
        "method": breakdown["method"],
        "conclusion_boundary": breakdown["conclusion_boundary"],
    }


def compact_report(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    return {
        "entity": report["entity"],
        "profile": {
            "paper_count": report["profile"]["paper_count"],
            "official_event_count": report["profile"]["official_event_count"],
            "algorithmic_signal_count": report["profile"]["algorithmic_signal_count"],
            "priority": report["profile"]["priority"],
        },
        "signal_count": len(report.get("signals", {}).get("items", [])),
        "conclusion_boundary": report["conclusion_boundary"],
    }


if __name__ == "__main__":
    sys.exit(main())
