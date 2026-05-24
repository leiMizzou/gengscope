from __future__ import annotations

import sys
from pathlib import Path

from gengscope_api.demo_seed import seed_demo_data

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.append(str(ROOT_DIR / "scripts"))

from run_skill_case_demo import render_markdown, run_case  # noqa: E402


def test_skill_case_demo_generates_numeric_and_image_signals(api_client, db_session) -> None:
    seed_demo_data(db_session)

    result = run_case(api_client, seed_mode="none")

    signal_types = {row["signal_type"] for row in result["signal_rows"]}
    assert "numeric_duplicate_sequence" in signal_types
    assert "numeric_last_digit_anomaly" in signal_types
    assert "image_panel_similarity" in signal_types
    assert result["total_signal_count"] >= 3
    assert result["agent_summary"]["risk_card"]["algorithmic_signal_count"] >= 3

    markdown = render_markdown(result)
    assert "耿同学.skill 案例 Demo" in markdown
    assert "不能据此直接认定论文造假" in markdown
