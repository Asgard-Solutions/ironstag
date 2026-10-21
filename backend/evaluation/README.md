# Iron Stag known-age evaluation benchmark

This benchmark checks whether a change (prompt, model, multi-photo input, cropping, or calibration) actually improves age estimates on deer whose age is reliably known. It runs the same pipeline code as `/api/analyze-deer`: image preparation, de-duplication, the prompt, the model call with selective consensus, the multi-photo guards, and region calibration. It runs offline and never touches:

- the database
- user accounts or scan credits
- R2 storage
- production records

Each run writes only to `evaluation/runs/<run_id>/`.

> **No real reference data is included.** Numbers produced from synthetic fixtures or `--mock` runs carry a "NOT ACCURACY EVIDENCE" banner and must not be quoted as accuracy.

## 1. Dataset format (JSON Lines)
Each line holds one **encounter**: one sighting of one deer, with 1–3 photos. An optional first line `{"_dataset": {...}}` holds metadata; set `"synthetic": true` for test fixtures. See `templates/dataset_template.jsonl`.

| Field | Required | Notes |
|---|---|---|
| `encounter_id` | yes | Unique. |
| `deer_id` | yes | Stable identity of the animal (ear tag, ranch ID). Splits are assigned per deer. |
| `species` | yes | `whitetail` \| `mule_deer` |
| `sex` | yes | `buck` \| `doe` \| `unknown` |
| `region_state` / `region_key` | recommended | Two-letter state or region key, used for calibration. |
| `encounter_date` | yes | `YYYY-MM-DD`. `reference_age` is the age **on this date**. |
| `images[]` | yes | Each image has `path` (relative to the dataset file) and optionally `view`, `captured_at`, and `crop_rect` {x, y, width, height} as fractions. |
| `reference_age` | yes | Years, using the half-year convention (x.5). |
| `age_basis` | yes | How the age was established (see tiers below). |
| `age_established_by` / `age_established_on` | recommended | The source document or person. |
| `label_uncertainty_years` | yes for ground truth | ± years. Missing or > 0.5 means the record is not eligible as ground truth. |
| `image_quality` | recommended | `excellent` \| `good` \| `fair` \| `poor`; optionally `quality_factors`. |
| `split` | optional | Forces `development` \| `calibration` \| `test`. Otherwise the split is assigned per deer by hashing `deer_id`. |
| `identity_unverified` | optional | Set to true when the deer's identity is not verified; leakage cannot be ruled out. |

### Label reliability tiers (never silently pooled)
| Tier | `age_basis` values | Default use |
|---|---|---|
| A – documented known age | `known_birth_record`, `tagged_as_fawn`, `captive_record` | ground truth |
| B – laboratory estimate | `cementum_annuli` | ground truth (with uncertainty ≤ 0.5) |
| C – expert assessment | `jawbone`, `tooth_wear`, `biologist_assessment`, `taxidermist` | flagged; only included with `--label-tiers` and reported per tier |
| D – hunter guess / unknown | `hunter_best_estimate`, `other`, `unknown` | flagged; excluded |

## 2. Validation, splits, leakage
```
cd /app/backend
python -m evaluation validate path/to/dataset.jsonl
python -m evaluation splits   path/to/dataset.jsonl --out split_manifest.json
```
**Errors** exclude records:
- missing fields
- invalid values
- duplicate encounter IDs
- missing or unreadable images
- a deer appearing in more than one split (all of that deer's encounters are excluded)
- exact or near-duplicate images shared by different deer (leakage or an identity conflict)

**Warnings** flag records without excluding them:
- labels that are not ground truth (tier C/D)
- missing or high label uncertainty
- off-convention ages
- unknown sex, missing region or quality
- duplicate images within the same deer

Splits are deterministic per deer (salt `ironstag-eval-split-v1`; default 20% development, 30% calibration, 50% test). This keeps every image and encounter of a deer in one split.

- **development**: prompt and model iteration
- **calibration**: building calibration curves
- **test**: held out; it can only be run with `--allow-test-split`, and each access is logged to `runs/test_access_log.jsonl`

## 3. Configs and controlled comparisons
Config files live in `configs/`. Factors:
- `model` (null means production `OPENAI_ANALYSIS_MODEL`)
- `prompt` (`label`, plus `system_prompt_append_file` or `system_prompt_override_file`)
- `multi_photo` (false means first photo only, which is the production single-photo baseline)
- `use_crops`
- `max_edge`
- `consensus` {enabled, total_passes}
- `calibration` (`heuristic` = production code without live DB curves; `none` = raw model confidence)
- `pricing_usd_per_1m_tokens`

The first `--config` is the baseline. The report lists which factors each candidate changes and warns when more than one changed. Every config is scored on the **same eligible cases**, which are fixed before the run. Failures and abstentions count as unanswered, never as dropped.

```
# Free plumbing check (mock model, not evidence)
python -m evaluation run DATA.jsonl --split development --config evaluation/configs/baseline.json \
    --config evaluation/configs/multi_photo.json --mock

# Paid run: plan first, then run within the agreed budget
python -m evaluation plan DATA.jsonl --split test --config evaluation/configs/baseline.json --config evaluation/configs/multi_photo.json
python -m evaluation run  DATA.jsonl --split test --config evaluation/configs/baseline.json --config evaluation/configs/multi_photo.json \
    --budget-usd 25 --max-calls 600 --allow-test-split
python -m evaluation report evaluation/runs/<run_id> --calibration-target exact
```
A non-mock run refuses to start if any of these is true:
- `--budget-usd` or `--max-calls` is missing
- pricing is missing from a config
- the planned upper bound exceeds the budget

It stops calling the model once spending reaches the budget; any remaining cases are marked `not_run_budget`.

## 4. Metrics (see `metrics.py` docstring)
- Exact age-class accuracy, within one year, and mean absolute error (MAE) in years. Accuracy among answered cases is always shown next to the unanswered count, together with overall accuracy (where unanswered counts as wrong).
- Coverage, abstention rate, and failure rate.
- Age-range coverage, scored separately from exact-age accuracy, with mean range width.
- Calibration: age confidence against **one declared correctness target** (`exact` or `within_one_year`), with ECE, Brier score, and a reliability table.
- Breakdowns by species, sex, region, age group, image quality, and label tier. Each shows n and a 95% interval (Wilson for proportions; bootstrap clustered by deer for MAE and differences). Groups with n < 30 are marked **inconclusive**.
- Paired comparisons: the difference in accuracy with a deer-clustered bootstrap CI, an exact McNemar test, the coverage difference, and the MAE difference on cases both configs answered.
  - A verdict is given only when the CI excludes 0.
  - Synthetic or mock runs never produce a verdict.

## 5. Reusing in-app feedback
`python -m evaluation export-labels --out feedback.jsonl` is a read-only export of exact-age `scan_labels`, joined with their scans and photo URLs. Every exported record:
- uses the scan ID as `deer_id`
- is flagged `identity_unverified`
- has no uncertainty set

Most exports are tier C/D, so they are **not** ground truth until someone verifies them and downloads the images locally.

## 6. Missing data (needed before any accuracy claim)
- Real known-age photos (tier A/B) with verified `deer_id`, encounter dates, and documented age provenance.
- Enough animals per subgroup: at least 30 per species, sex, age group, and region to draw conclusions; ideally hundreds of deer in the test split.
- Mule-deer and doe coverage. In-app feedback is mostly whitetail bucks with hunter- or tooth-wear-based ages.
- An agreed run budget, plus a valid OpenAI key in the evaluation environment (the dev key currently returns 401).
