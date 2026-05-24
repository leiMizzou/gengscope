#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from PIL import Image, ImageDraw, ImageOps


DEMO_DOI = "10.5555/gengscope.demo.1"
DEFAULT_BASE_URL = "http://127.0.0.1:8010"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a synthetic Codex + 耿同学.skill case demo against a local GengScope API."
    )
    parser.add_argument("--base-url", default=os.getenv("GENGSCOPE_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--api-key", default=os.getenv("GENGSCOPE_API_KEY"))
    parser.add_argument("--actor", default="codex-skill-demo")
    parser.add_argument(
        "--seed-mode",
        choices=["docker", "local", "none"],
        default="docker",
        help="How to seed the synthetic demo paper if it is not already indexed.",
    )
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    headers = auth_headers(api_key=args.api_key, actor=args.actor)
    try:
        with httpx.Client(base_url=args.base_url, timeout=60.0) as client:
            result = run_case(
                client,
                headers=headers,
                seed_mode=args.seed_mode,
                repo_root=Path(args.repo_root),
            )
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        else:
            print(render_markdown(result))
        return 0
    except Exception as exc:
        print(f"skill-case-demo: {exc}", file=sys.stderr)
        return 1


def auth_headers(*, api_key: str | None = None, actor: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if api_key:
        headers["X-API-Key"] = api_key
    if actor:
        headers["X-GengScope-Actor"] = actor
    return headers


def run_case(
    client: httpx.Client,
    *,
    headers: dict[str, str] | None = None,
    seed_mode: str = "none",
    repo_root: Path | None = None,
) -> dict[str, Any]:
    headers = headers or {}
    ensure_ready(client)
    initial_summary = ensure_demo_paper(client, headers=headers, seed_mode=seed_mode, repo_root=repo_root)
    paper = initial_summary["paper"]

    source_upload = upload_artifact(
        client,
        headers=headers,
        doi=DEMO_DOI,
        artifact_type="source_data",
        filename="skill-case-source-data.csv",
        content_type="text/csv",
        content=source_data_fixture().encode("utf-8"),
    )
    numeric_audit = request_json(
        client,
        "POST",
        "/api/audits/numeric",
        headers=headers,
        json={
            "artifact_id": source_upload["artifact"]["id"],
            "min_duplicate_length": 3,
            "min_last_digit_sample": 10,
            "priority": 8,
        },
    )

    base_png, flipped_png = image_panel_fixture()
    base_upload = upload_artifact(
        client,
        headers=headers,
        doi=DEMO_DOI,
        artifact_type="figure_image",
        filename="skill-case-figure-1a.png",
        content_type="image/png",
        content=base_png,
    )
    flipped_upload = upload_artifact(
        client,
        headers=headers,
        doi=DEMO_DOI,
        artifact_type="figure_image",
        filename="skill-case-figure-2b.png",
        content_type="image/png",
        content=flipped_png,
    )
    image_audit = request_json(
        client,
        "POST",
        "/api/audits/image",
        headers=headers,
        json={
            "artifact_id": base_upload["artifact"]["id"],
            "compare_artifact_ids": [flipped_upload["artifact"]["id"]],
            "max_hamming_distance": 4,
            "priority": 9,
        },
    )

    final_summary = get_agent_summary(client, headers=headers)
    artifacts = [
        source_upload["artifact"],
        base_upload["artifact"],
        flipped_upload["artifact"],
    ]
    signal_rows = summarize_signals(
        numeric_audit["signals"] + image_audit["signals"],
        artifacts=artifacts,
    )
    return {
        "demo_name": "耿同学.skill synthetic case demo",
        "runtime_chain": [
            "Codex follows skills/gengscope/SKILL.md",
            "Codex calls the local GengScope API/CLI runtime",
            "GengScope stores artifacts and emits review signals",
            "Codex summarizes signals with the conclusion boundary",
        ],
        "paper": paper,
        "artifacts": artifacts,
        "audits": {
            "numeric": numeric_audit,
            "image": image_audit,
        },
        "agent_summary": final_summary,
        "signal_rows": signal_rows,
        "total_signal_count": len(signal_rows),
        "conclusion_boundary": final_summary["conclusion_boundary"],
    }


def ensure_ready(client: httpx.Client) -> dict[str, Any]:
    return request_json(client, "GET", "/health/ready")


def ensure_demo_paper(
    client: httpx.Client,
    *,
    headers: dict[str, str],
    seed_mode: str,
    repo_root: Path | None,
) -> dict[str, Any]:
    summary = maybe_agent_summary(client, headers=headers)
    if summary is not None:
        return summary
    if seed_mode == "none":
        raise RuntimeError(
            f"demo DOI {DEMO_DOI} is not indexed. Run `gengscope demo-seed` or use `--seed-mode docker`."
        )
    seed_demo_data(seed_mode=seed_mode, repo_root=repo_root or Path.cwd())
    summary = maybe_agent_summary(client, headers=headers)
    if summary is None:
        raise RuntimeError(f"demo DOI {DEMO_DOI} is still not indexed after {seed_mode} seed")
    return summary


def seed_demo_data(*, seed_mode: str, repo_root: Path) -> None:
    if seed_mode == "docker":
        command = [
            "docker",
            "compose",
            "-f",
            "infra/docker/docker-compose.yml",
            "exec",
            "-T",
            "api",
            "gengscope",
            "demo-seed",
        ]
    elif seed_mode == "local":
        command = ["gengscope", "demo-seed"]
    else:
        return
    completed = subprocess.run(command, cwd=repo_root, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} failed with exit code {completed.returncode}: {completed.stderr.strip() or completed.stdout.strip()}"
        )


def get_agent_summary(client: httpx.Client, *, headers: dict[str, str]) -> dict[str, Any]:
    return request_json(client, "GET", f"/api/agent/doi/{quote(DEMO_DOI, safe='')}", headers=headers)


def maybe_agent_summary(client: httpx.Client, *, headers: dict[str, str]) -> dict[str, Any] | None:
    response = client.get(f"/api/agent/doi/{quote(DEMO_DOI, safe='')}", headers=headers)
    if response.status_code == 404:
        return None
    return parse_response(response, "GET", f"/api/agent/doi/{DEMO_DOI}")


def upload_artifact(
    client: httpx.Client,
    *,
    headers: dict[str, str],
    doi: str,
    artifact_type: str,
    filename: str,
    content_type: str,
    content: bytes,
) -> dict[str, Any]:
    return request_json(
        client,
        "POST",
        "/api/artifacts/upload",
        headers=headers,
        data={
            "doi": doi,
            "artifact_type": artifact_type,
            "license_status": "manual_upload",
        },
        files={"file": (filename, content, content_type)},
    )


def source_data_fixture() -> str:
    rows = [
        "replicate,tumor_a,tumor_b,tumor_copy,last_digit",
        "r1,1.10,4.11,1.10,10",
        "r2,2.20,5.12,2.20,20",
        "r3,3.30,6.13,3.30,30",
        "r4,4.40,7.14,4.40,40",
        "r5,5.50,8.15,5.50,50",
        "r6,6.60,9.16,6.60,60",
        "r7,7.70,10.17,7.70,70",
        "r8,8.80,11.18,8.80,80",
        "r9,9.90,12.19,9.90,90",
        "r10,10.00,13.10,10.00,100",
    ]
    return "\n".join(rows) + "\n"


def image_panel_fixture() -> tuple[bytes, bytes]:
    base = Image.new("RGB", (96, 96), "white")
    draw = ImageDraw.Draw(base)
    draw.rectangle((8, 14, 42, 66), fill="black")
    draw.rectangle((52, 30, 64, 84), fill="gray")
    draw.ellipse((24, 48, 74, 72), outline=(80, 80, 80), width=3)
    flipped = ImageOps.mirror(base)
    return png_bytes(base), png_bytes(flipped)


def png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def summarize_signals(signals: list[dict[str, Any]], *, artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filename_by_id = {artifact["id"]: artifact.get("filename") or artifact["id"] for artifact in artifacts}
    rows = []
    for signal in signals:
        metrics = signal.get("metrics") or {}
        artifact_id = signal.get("artifact_id")
        matched_id = metrics.get("matched_artifact_id")
        evidence = filename_by_id.get(artifact_id, artifact_id)
        if matched_id:
            evidence = f"{evidence} vs {filename_by_id.get(matched_id, matched_id)}"
        elif "locations" in metrics:
            locations = "; ".join(
                f"{item.get('column')} row {item.get('row')}"
                for item in metrics["locations"][:3]
            )
            evidence = f"{evidence}; {locations}"
        elif "dominant_digit" in metrics:
            evidence = f"{evidence}; dominant_digit={metrics['dominant_digit']}; ratio={metrics.get('dominant_ratio')}"
        rows.append(
            {
                "signal_type": signal["signal_type"],
                "severity": signal["severity"],
                "confidence": signal["confidence"],
                "status": signal["status"],
                "evidence": evidence,
                "summary": signal["summary"],
            }
        )
    return rows


def render_markdown(result: dict[str, Any]) -> str:
    paper = result["paper"]
    lines = [
        "# 耿同学.skill 案例 Demo",
        "",
        "运行链路：Codex -> 耿同学.skill -> 本地 GengScope API/CLI -> 数值/图像审计器 -> Codex 摘要。",
        "",
        f"- DOI: `{paper['doi']}`",
        f"- 论文: {paper['title']}",
        f"- 期刊: {paper.get('journal_name') or 'unknown'}",
        f"- 本次运行产生/确认的待复核信号数: {result['total_signal_count']}",
        "",
        "| 类型 | 严重度 | 置信度 | 证据位置 | 说明 |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in result["signal_rows"]:
        lines.append(
            "| {signal_type} | {severity} | {confidence:.2f} | `{evidence}` | {summary} |".format(
                signal_type=row["signal_type"],
                severity=row["severity"],
                confidence=float(row["confidence"]),
                evidence=str(row["evidence"]).replace("|", "\\|"),
                summary=str(row["summary"]).replace("|", "\\|"),
            )
        )
    risk_card = result["agent_summary"]["risk_card"]
    lines.extend(
        [
            "",
            "## Codex 给用户看的结论",
            "",
            f"这次 demo 运行产生/确认 `{result['total_signal_count']}` 个待复核算法信号；"
            f"当前该论文总计索引到 `{risk_card['algorithmic_signal_count']}` 个可见算法信号。"
            "这些信号涉及 source data 的数值模式和 figure image 的面板相似性，适合进入人工复核队列。",
            "",
            f"结论边界：{result['conclusion_boundary']}",
        ]
    )
    return "\n".join(lines)


def request_json(client: httpx.Client, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    response = client.request(method, path, **kwargs)
    return parse_response(response, method, path)


def parse_response(response: httpx.Response, method: str, path: str) -> dict[str, Any]:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"{method} {path} failed: HTTP {response.status_code}: {response.text}") from exc
    return response.json()


if __name__ == "__main__":
    raise SystemExit(main())
