#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


REAL_CASE = {
    "doi": "10.1155/2023/6916819",
    "expected_title": "P-Glycoprotein Exacerbates Brain Injury Following Experimental Cerebral Ischemia",
    "expected_institution": "China Pharmaceutical University",
    "official_event": {
        "event_type": "retraction_notice",
        "status_level": "official_retraction",
        "source_type": "publisher",
        "source_name": "Wiley / Hindawi",
        "source_url": "https://onlinelibrary.wiley.com/doi/10.1155/omcl/9837687",
        "event_date": "2025-11-07",
        "claim_summary": (
            "Publisher retraction notice reports data and image-integrity concerns involving multiple figures, "
            "including image/data overlap; the article was retracted."
        ),
        "verification_status": "official_confirmed",
        "created_by": "real-case-e2e",
    },
}


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
        headers = {"accept": "application/json", "X-GengScope-Actor": "real-case-e2e"}
        data = None
        if payload is not None:
            headers["content-type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {body}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Run GengScope against a public real retraction case.")
    parser.add_argument("--base-url", default=os.getenv("GENGSCOPE_BASE_URL", "http://127.0.0.1:8010"))
    parser.add_argument("--api-key", default=os.getenv("GENGSCOPE_API_KEY"))
    parser.add_argument("--inspect-landing-pages", action="store_true")
    args = parser.parse_args()

    client = ApiClient(args.base_url, args.api_key)
    doi = REAL_CASE["doi"]
    encoded_doi = urllib.parse.quote(doi, safe="")

    imported = client.post("/api/admin/import/doi", {"doi": doi, "sources": ["openalex", "crossref"]})
    detail = client.get(f"/api/papers/{encoded_doi}")
    paper_id = detail["paper"]["id"]
    ensure_event(client, detail, doi)
    artifacts = client.post(
        "/api/artifacts/discover",
        {"paper_id": paper_id, "inspect_landing_pages": bool(args.inspect_landing_pages), "max_landing_pages": 3, "max_discovered_links": 30},
    )
    detail = client.get(f"/api/papers/{encoded_doi}")
    risk_card = client.get(f"/api/papers/{encoded_doi}/risk-card")

    institution_authorship = choose_institution_authorship(detail["authorships"])
    institution_profile = None
    institution_breakdown = None
    institution_report = None
    if institution_authorship and institution_authorship.get("institution_id"):
        institution_id = institution_authorship["institution_id"]
        institution_profile = client.get(f"/api/entities/institution/{institution_id}/profile")
        institution_breakdown = client.get(f"/api/entities/institution/{institution_id}/breakdown?limit=12&min_papers=1")
        institution_report = client.get(f"/api/reports/entity?entity_type=institution&entity_id={urllib.parse.quote(institution_id, safe='')}")

    author_profiles = []
    for authorship in choose_author_authorships(detail["authorships"]):
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

    checks = {
        "paper_imported": imported["doi"] == doi and REAL_CASE["expected_title"] in imported["title"],
        "official_retraction_detected": risk_card["official_status"] == "retracted" and risk_card["highest_signal_level"] == "official",
        "publisher_retraction_detected": risk_card["publisher_status"] == "retraction",
        "source_attributed_data_issue_detected": any(
            "data" in (item.get("summary") or "").casefold() and "image" in (item.get("summary") or "").casefold()
            for item in risk_card.get("evidence", [])
        ),
        "expected_institution_identified": bool(
            institution_authorship
            and REAL_CASE["expected_institution"].casefold() in (institution_authorship.get("affiliation_raw") or "").casefold()
        ),
        "institution_breakdown_available": bool(institution_breakdown and institution_breakdown.get("affiliation_units")),
        "specific_authors_identified": bool(author_profiles),
        "pdf_or_landing_material_found": detail["paper"]["material_status"] in {"landing_page_found", "pdf_found", "source_data_found", "full_auditable"},
    }

    output = {
        "case": {
            "doi": doi,
            "paper_title": detail["paper"]["title"],
            "official_source_url": REAL_CASE["official_event"]["source_url"],
            "expected_institution": REAL_CASE["expected_institution"],
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
            "This real-case run identifies a public official retraction linked to the paper, authors and institution. "
            "It is evidence for review prioritization and source-attributed reporting, not an independent misconduct finding."
        ),
        "conclusion_boundary": "真实案例结果只复述公开来源状态与本地索引/审计信号，不能据此直接认定论文、作者、实验室或机构造假。",
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output["passed"] else 2


def ensure_event(client: ApiClient, detail: dict[str, Any], doi: str) -> None:
    event = REAL_CASE["official_event"]
    for existing in detail.get("events", []):
        if existing.get("status_level") == event["status_level"] and existing.get("source_url") == event["source_url"]:
            return
    payload = {"doi": doi, **event}
    client.post("/api/admin/events", payload)


def choose_institution_authorship(authorships: list[dict[str, Any]]) -> dict[str, Any] | None:
    expected = REAL_CASE["expected_institution"].casefold()
    for authorship in authorships:
        if expected in (authorship.get("institution_display_name") or "").casefold():
            return authorship
    for authorship in authorships:
        if expected in (authorship.get("affiliation_raw") or "").casefold():
            return authorship
    for authorship in authorships:
        if authorship.get("institution_id"):
            return authorship
    return None


def choose_author_authorships(authorships: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [authorship for authorship in authorships if authorship.get("is_corresponding") and authorship.get("author_id")]
    if selected:
        return selected[:3]
    return [authorship for authorship in authorships if authorship.get("author_id")][:3]


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
