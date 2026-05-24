from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.append(str(ROOT_DIR / "scripts"))

from run_retraction_calibration import align_blind_signals_with_official_reasons  # noqa: E402


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
