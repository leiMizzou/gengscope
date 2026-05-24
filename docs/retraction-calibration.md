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

For image-heavy retractions, fetch linked PDFs, extract embedded images as `figure_image` artifacts and run image audits before alignment:

```bash
python3 scripts/run_retraction_calibration.py \
  --base-url http://127.0.0.1:8010 \
  --limit 5 \
  --inspect-landing-pages \
  --fetch-pdfs \
  --fetch-images \
  --extract-pdf-images \
  --run-image-audits \
  --max-image-artifacts 12
```

By default, batch image audit uses faster hash/patch checks. Add `--deep-image-audits` only for smaller focused runs that need slower shift-correlation checks.

If Crossref starts rate-limiting a large calibration batch, use OpenAlex-only metadata import and rely on the official notice fields in the seed file for labels:

```bash
python3 scripts/run_retraction_calibration.py \
  --base-url http://127.0.0.1:8010 \
  --limit 20 \
  --metadata-sources openalex \
  --inspect-landing-pages \
  --fetch-images \
  --run-image-audits
```

If a trusted local proxy or DNS layer maps public hosts such as `pmc.ncbi.nlm.nih.gov` to `198.18.x.x`, start the temporary calibration API with `ARTIFACT_FETCH_ALLOW_PRIVATE_NETWORKS=1`. Keep the default block enabled for normal deployments.

Only after blind alignment, record official notices into the local database:

```bash
python3 scripts/run_retraction_calibration.py \
  --base-url http://127.0.0.1:8010 \
  --limit 20 \
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

The first seed set contains at least 20 official retraction cases and intentionally emphasizes image/data-integrity retractions because those map most directly to the current numeric and image analyzers.

The offline test suite guards seed quality: case IDs, original DOIs and notice DOIs must be unique, reason categories must map to a known calibration family, and every seeded DOI must keep a title hint containing expected DOI-specific title terms. This prevents calibration drift from accidental DOI/title mismatches.

## Current Baseline

The current 20-case calibration batch was rerun on 2026-05-24 against a clean temporary SQLite database with:

```bash
python3 scripts/run_retraction_calibration.py \
  --base-url http://127.0.0.1:8012 \
  --limit 20 \
  --metadata-sources openalex \
  --inspect-landing-pages \
  --fetch-images \
  --run-image-audits \
  --max-image-artifacts 8 \
  --min-completed-cases 20 \
  --min-matched-cases 18 \
  --max-analyzer-gap 2
```

Observed result after adding PMC article-page prioritization, HTML image-source discovery, multi-scale same-figure internal patch similarity detection and running internal-only audits for the final image artifact in each case:

- `20/20` cases completed.
- Prefix checkpoints from the same ordered run: `5/5`, `9/10`, `18/20` cases matched at least one official reason family by blind algorithmic signal.
- `18/20` cases matched at least one official reason family by blind algorithmic signal.
- Status counts: `matched_by_blind_signal=18`, `analyzer_gap=2`, `material_gap=6`, `covered_by_primary_signal=17`, `context_label_only=2`, `unsupported_signal_family=1`.
- The dominant remaining blockers are true data-material gaps for data-irregularity/raw-data/reproducibility labels, one table/primer consistency family without an analyzer, and two image analyzer misses where figure images were available but no signal fired.

Use the threshold flags above for a nightly or manual live regression gate. The script exits non-zero when the batch fails to complete, matched cases drop below the current baseline or analyzer gaps exceed the current baseline.

The live 20-case run performs DOI import, landing-page inspection, remote image fetches and image audits, so it can take minutes and depends on publisher/PMC/network behavior. Keep ordinary pull-request CI on offline tests and seed-quality checks; run the live calibration gate manually or on a scheduled job with a temporary local API and cached artifacts.

## Alignment Status

- `matched_by_blind_signal`: an existing analyzer produced a signal in the same family as the official reason.
- `material_gap`: the needed auditable material was not discovered.
- `extraction_gap`: PDF or landing material was found, but figure/table/source-data extraction is missing.
- `material ops`: runtime counts for successfully fetched PDFs, extracted PDF images, image-audit signals and operation errors during the blind pass.
- `analyzer_gap`: relevant auditable material was found, but no matching signal fired.
- `covered_by_primary_signal`: an official reliability conclusion such as `data_unreliable` is downstream of an image/data/table concern already matched by a blind signal.
- `context_label_only`: an official reliability conclusion is present, but no primary evidence signal fired; improve primary analyzers rather than counting this as missing source-data material.
- `unsupported_signal_family`: the reason category has no analyzer family yet, such as primer/table consistency.

## Boundary

This calibration workflow evaluates recall against official retrospective labels. It must not be presented as an independent misconduct classifier.
