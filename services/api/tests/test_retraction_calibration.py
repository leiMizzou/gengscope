from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.append(str(ROOT_DIR / "scripts"))

from run_retraction_calibration import align_blind_signals_with_official_reasons  # noqa: E402
from run_retraction_calibration import evaluate_baseline_checks  # noqa: E402
from run_retraction_calibration import import_doi_or_existing  # noqa: E402
from run_retraction_calibration import load_cases  # noqa: E402
from run_retraction_calibration import prefix_match_checkpoints  # noqa: E402
from run_retraction_calibration import reason_group  # noqa: E402
from run_retraction_calibration import render_markdown  # noqa: E402


def test_alignment_matches_image_reason_when_blind_image_signal_exists() -> None:
    blind = {
        "signal_groups": ["image_integrity"],
        "artifact_types": ["figure_image"],
    }

    alignment = align_blind_signals_with_official_reasons(blind, ["image_duplication"])

    assert alignment["case_alignment_status"] == "matched"
    assert alignment["matched_groups"] == ["image_integrity"]
    assert alignment["group_results"][0]["status"] == "matched_by_blind_signal"


def test_alignment_distinguishes_pdf_extraction_gap_from_analyzer_gap() -> None:
    blind = {
        "signal_groups": [],
        "artifact_types": ["paper_pdf", "publisher_landing_page"],
    }

    alignment = align_blind_signals_with_official_reasons(blind, ["western_blot_duplication"])

    assert alignment["case_alignment_status"] == "gap_found"
    assert alignment["group_results"][0]["status"] == "extraction_gap"


def test_alignment_flags_table_family_as_unsupported() -> None:
    blind = {
        "signal_groups": [],
        "artifact_types": ["source_data"],
    }

    alignment = align_blind_signals_with_official_reasons(blind, ["table_inconsistency"])

    assert alignment["case_alignment_status"] == "gap_found"
    assert alignment["group_results"][0]["status"] == "unsupported_signal_family"


def test_alignment_treats_data_unreliable_as_downstream_reliability_label() -> None:
    blind = {
        "signal_groups": ["image_integrity"],
        "artifact_types": ["figure_image"],
    }

    alignment = align_blind_signals_with_official_reasons(blind, ["image_duplication", "data_unreliable"])

    assert alignment["case_alignment_status"] == "matched"
    assert alignment["matched_groups"] == ["image_integrity"]
    statuses = {item["group"]: item["status"] for item in alignment["group_results"]}
    assert statuses["image_integrity"] == "matched_by_blind_signal"
    assert statuses["reliability_conclusion"] == "covered_by_primary_signal"


def test_render_markdown_includes_material_operations_when_present() -> None:
    output = {
        "case_count": 1,
        "completed_case_count": 1,
        "matched_case_count": 1,
        "prefix_checkpoints": [{"case_count": 1, "completed_case_count": 1, "matched_case_count": 1}],
        "status_counts": {"matched_by_blind_signal": 1},
        "next_actions": ["Add more calibration cases."],
        "conclusion_boundary": "boundary",
        "cases": [
            {
                "completed": True,
                "case": {"case_id": "case-a", "doi": "10.1/demo"},
                "blind": {
                    "material_status": "manual_upload_available",
                    "artifact_types": ["paper_pdf", "figure_image"],
                    "algorithmic_signal_count": 2,
                },
                "material_operations": {
                    "fetched_pdf_count": 1,
                    "pdf_fetch_error_count": 0,
                    "fetched_image_count": 3,
                    "image_fetch_error_count": 0,
                    "pdf_image_extraction_count": 2,
                    "pdf_image_extraction_error_count": 0,
                    "image_audit_signal_count": 1,
                    "image_audit_error_count": 0,
                },
                "alignment": {
                    "expected_groups": ["image_integrity"],
                    "group_results": [{"group": "image_integrity", "status": "matched_by_blind_signal"}],
                },
            }
        ],
    }

    markdown = render_markdown(output)

    assert "case-a" in markdown
    assert "1/1 matched" in markdown
    assert "pdf=1, remote_images=3, images=2, image_signals=1, errors=0" in markdown


def test_prefix_match_checkpoints_report_five_ten_and_full_run() -> None:
    def result(matched: bool) -> dict:
        return {
            "completed": True,
            "alignment": {"case_alignment_status": "matched" if matched else "gap_found"},
        }

    results = [result(index in {0, 1, 4, 5, 8, 10}) for index in range(12)]

    checkpoints = prefix_match_checkpoints(results)

    assert checkpoints == [
        {"case_count": 5, "completed_case_count": 5, "matched_case_count": 3},
        {"case_count": 10, "completed_case_count": 10, "matched_case_count": 5},
        {"case_count": 12, "completed_case_count": 12, "matched_case_count": 6},
    ]


def test_import_falls_back_to_existing_local_paper_after_rate_limit() -> None:
    class LocalPaperClient:
        def post(self, path: str, payload: dict) -> dict:
            raise RuntimeError("HTTP 429: Too Many Requests")

        def get(self, path: str) -> dict:
            return {
                "paper": {
                    "id": "paper-1",
                    "doi": "10.1/existing",
                    "title": "Already indexed paper",
                }
            }

    imported, detail = import_doi_or_existing(LocalPaperClient(), "10.1/existing", "10.1%2Fexisting")

    assert detail["paper"]["id"] == "paper-1"
    assert imported["source"] == "existing_local_record"
    assert "429" in imported["import_warning"]


def test_seed_cases_have_twenty_unique_calibration_labels() -> None:
    cases = load_cases(ROOT_DIR / "data/seeds/retraction_calibration_cases.json")
    case_ids = [case["case_id"] for case in cases]
    dois = [case["doi"].lower() for case in cases]
    notice_dois = [case["official_notice"]["notice_doi"].lower() for case in cases]
    expected_title_terms = {
        "10.1155/2023/6916819": ["p-glycoprotein", "cerebral ischemia"],
        "10.1155/2021/4704771": ["valine", "nonalcoholic fatty liver disease"],
        "10.1113/ep091162": ["continuous exercise", "methotrexate"],
        "10.1155/2015/874906": ["maize", "electric field"],
        "10.1021/acsomega.3c05957": ["oil spill", "magnetite"],
        "10.1021/acsomega.2c08058": ["alkylamine", "dimethacrylate"],
        "10.1155/2019/2523032": ["mir-509-5p", "osteosarcoma"],
        "10.1155/2018/8481243": ["uv-a", "hyaluronic acid"],
        "10.1155/2019/9450368": ["melittin", "renal tubule"],
        "10.1155/2019/4050327": ["hydroxysafflor", "lung fibroblasts"],
        "10.1155/2015/490209": ["arctigenin", "subarachnoid"],
        "10.1155/2022/1373160": ["convolvulus", "wound healing"],
        "10.1155/2016/5850739": ["xiao yao san", "corticosterone"],
        "10.1155/2022/1178874": ["rose bengal", "antitumour"],
        "10.1155/2012/595603": ["scopoletin", "inflammation pain"],
        "10.1155/2013/524165": ["h9n2", "apoptosis"],
        "10.1155/2015/675921": ["factor x", "bhk-21"],
        "10.1155/2014/678123": ["retinal neurons", "diabetic rats"],
        "10.1155/2022/2614599": ["malva neglecta", "obesity"],
        "10.1155/2022/6708871": ["mir-223", "gastric cancer"],
    }

    assert len(cases) >= 20
    assert len(case_ids) == len(set(case_ids))
    assert len(dois) == len(set(dois))
    assert len(notice_dois) == len(set(notice_dois))
    assert all(case["official_notice"].get("source_url") for case in cases)
    assert all(case["official_notice"].get("reason_summary") for case in cases)
    assert all(reason_group(category) != "other" for case in cases for category in case["reason_categories"])
    assert set(expected_title_terms).issubset(set(dois))
    for case in cases:
        title = case["title_hint"].lower()
        for term in expected_title_terms[case["doi"].lower()]:
            assert term in title


def test_baseline_checks_guard_current_twenty_case_thresholds() -> None:
    output = {
        "completed_case_count": 20,
        "matched_case_count": 18,
        "status_counts": {"analyzer_gap": 2},
    }

    passing = evaluate_baseline_checks(
        output,
        min_completed_cases=20,
        min_matched_cases=18,
        max_analyzer_gap=2,
    )
    failing = evaluate_baseline_checks(
        output,
        min_completed_cases=20,
        min_matched_cases=19,
        max_analyzer_gap=1,
    )

    assert passing["passed"] is True
    assert failing["passed"] is False
    assert [item["name"] for item in failing["items"]] == [
        "min_completed_cases",
        "min_matched_cases",
        "max_analyzer_gap",
    ]
