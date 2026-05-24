# 耿同学.skill Case Demo

This demo shows the intended runtime shape:

```text
Codex -> 耿同学.skill -> local GengScope API/CLI -> numeric/image audit signals -> neutral Codex summary
```

It uses synthetic data only. The result demonstrates review-priority signals, not misconduct findings.

## Run

Start the local engine:

```bash
docker compose -f infra/docker/docker-compose.yml up -d --build api worker
```

Run the case demo from the repo root:

```bash
python3 scripts/run_skill_case_demo.py --base-url http://127.0.0.1:8010
```

The script will seed the synthetic demo paper with `gengscope demo-seed` inside the Docker API container when needed, upload one source-data CSV and two figure images, run numeric and image audits, then print a Markdown summary.

For machine-readable output:

```bash
python3 scripts/run_skill_case_demo.py --base-url http://127.0.0.1:8010 --format json
```

## Expected Signals

The demo should produce at least these signal types:

- `numeric_duplicate_sequence`: repeated numeric sequence across source-data columns.
- `numeric_last_digit_anomaly`: skewed final-digit distribution in numeric columns.
- `image_panel_similarity`: highly similar figure panels under a horizontal flip transform.

The required conclusion boundary remains:

```text
以上为已索引的公开状态、公开讨论和算法信号，不能据此直接认定论文造假。
```

## Interpretation

This is the shape an agent should expose to a user:

- say what artifact was inspected;
- list the signal type, severity, confidence and evidence location;
- create or reference review tasks when available;
- avoid calling the paper, author, lab or institution fraudulent unless an official source explicitly says so.
