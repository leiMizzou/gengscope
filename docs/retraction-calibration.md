# Retraction Calibration

The goal is to make `耿同学.skill` closer to expert review by using already retracted papers as retrospective calibration cases.

The process must stay blind until the alignment step:

```text
1. Import the retracted paper DOI.
2. Discover available materials and read existing algorithmic signals.
3. Do not register or read the official retraction reason during the blind pass.
4. Load the official retraction notice as the calibration label.
5. Compare blind signal groups with official reason groups.
6. Classify every miss as a material gap, extraction gap, analyzer gap, or unsupported signal family.
```

Run against the local API:

```bash
python3 scripts/run_retraction_calibration.py --base-url http://127.0.0.1:8010 --limit 5
```

Optionally inspect publisher/PMC landing pages:

```bash
python3 scripts/run_retraction_calibration.py \
  --base-url http://127.0.0.1:8010 \
  --limit 10 \
  --inspect-landing-pages
```

Only after blind alignment, record official notices into the local database:

```bash
python3 scripts/run_retraction_calibration.py \
  --base-url http://127.0.0.1:8010 \
  --limit 10 \
  --record-official-events
```

## Case Data

The seed cases live in:

```text
data/seeds/retraction_calibration_cases.json
```

Each case stores:

- original article DOI;
- title hint;
- official notice URL and notice DOI;
- optional public mirror URL for easier manual reading;
- short paraphrased official reason summary;
- structured reason categories.

The first seed set intentionally emphasizes image/data-integrity retractions because those map most directly to the current numeric and image analyzers.

## Alignment Status

- `matched_by_blind_signal`: an existing analyzer produced a signal in the same family as the official reason.
- `material_gap`: the needed auditable material was not discovered.
- `extraction_gap`: PDF or landing material was found, but figure/table/source-data extraction is missing.
- `analyzer_gap`: relevant auditable material was found, but no matching signal fired.
- `unsupported_signal_family`: the reason category has no analyzer family yet, such as primer/table consistency.

## Boundary

This calibration workflow evaluates recall against official retrospective labels. It must not be presented as an independent misconduct classifier.
