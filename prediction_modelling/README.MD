# CGMacros Pipeline

End-to-end, modular data pipeline for turning **CGMacros** raw exports into aligned meal segments, engineered features, an ML model that predicts post-meal **Δ-glucose curves (1–120 min)**, and evaluation utilities (including null-model baselines).

---

## Why this exists

CGMacros data are rich but scattered across per-user CSVs. This repo gives you:

- **Robust parsing & alignment** of CGM + meal annotations (−60 to +120 min around each meal).
- **Meal-level features** + **120-step targets** (Δ-mg/dL per minute).
- A **RandomForest Multi-Output** regression pipeline with proper preprocessing.
- **Evaluation** vs. simple nulls (zero, global mean, meal-type mean).
- Clean **CLI** and importable modules so you can script or integrate.

---

## Directory conventions (input)

We assume CGMacros’ standard layout:

```
./CGMacros/
  CGMacros-001/
    CGMacros-001.csv
  CGMacros-002/
    CGMacros-002.csv
  ...
bio.csv                       # demographics & labs (optional but recommended)
```

### Expected columns in raw CGMacros CSV

The pipeline is resilient, but it relies on these (case-insensitive when possible):

- CGM: `Dexcom GL` **or** `Libre GL`
- Timestamps: one of `Timestamp`, `Time`, `DateTime`
- Activity (optional): `Calories (Activity)`, `METs`
- Meal annotations/macros (as available):  
  `Meal Type`, `Calories`, `Carbs`, `Protein`, `Fat`, `Fiber`, `Amount Consumed`

> If both `Dexcom GL` and `Libre GL` are present, we prefer the first non-empty column.

### Demographics (bio.csv)

Your `bio.csv` should include a **patient ID** column (any of `patient_id`, `PatientID`, `id`, etc.) and may include: `Age`, `Gender`, `Body weight`, `Height`, fasting lab values, etc. The merge step canonicalizes IDs (e.g., `001` → `1`).

---

## What the pipeline produces

- **Meal segments CSV** (`all_users_all_meal_segments.csv`): per-minute series for each meal (−60..+120), including baseline and Δ-glucose.
- **All segments + bio CSV** (`all_meal_segments_with_bio.csv`): segments left-joined with demographics.
- **Trained model** (`ml_outputs_mlcurve_rf/model_multioutput.pkl`):  
  `Pipeline(preprocess=ColumnTransformer(...), reg=MultiOutputRegressor(RandomForest))`
- **Metrics & eval** (in `ml_outputs_mlcurve_rf/` & `ml_outputs_mlcurve_eval/`): MSE summary, per-minute MSE, and null comparisons.

---

## Package layout

```
cgmacros_pipeline/
  __init__.py
  segments.py     # parse/align CGM around meals (−60..+120), baseline & delta
  bio.py          # demographic merge & patient ID canonicalization
  features.py     # meal-level feature matrix + 120-d target vector
  train.py        # train RF MultiOutput model; save artifacts and summaries
  evaluate.py     # compare against nulls; optional per-patient views
  cli.py          # command-line entry points for each step and full pipeline
```

---

## Installation

Use your preferred Python 3.10+ environment.

```bash
# In the repo root:
pip install -e .
```

(If you use Conda, ensure `numpy`, `pandas`, `scikit-learn`, `tqdm`, `joblib`, `matplotlib` are available.)

---

## Quick start (one command)

From your project root (where `CGMacros/` and `bio.csv` live):

```bash
python -m cgmacros_pipeline.cli pipeline --root . --bio bio.csv --workdir .
```

This runs:

1) **extract** → `all_users_all_meal_segments.csv`  
2) **merge-bio** → `all_meal_segments_with_bio.csv`  
3) **train** → `ml_outputs_mlcurve_rf/model_multioutput.pkl` (+ `summary.csv`)  
4) **eval** → `ml_outputs_mlcurve_eval/null_comparison.csv`

---

## Step-by-step CLI

```bash
# 1) Extract aligned meal segments from all users
python -m cgmacros_pipeline.cli extract --root .   --out all_users_all_meal_segments.csv

# 2) Merge demographics (optional but recommended)
python -m cgmacros_pipeline.cli merge-bio   --segments all_users_all_meal_segments.csv   --bio bio.csv   --out all_meal_segments_with_bio.csv

# 3) Train RF MultiOutput model
python -m cgmacros_pipeline.cli train   --data all_meal_segments_with_bio.csv   --out ml_outputs_mlcurve_rf

# 4) Evaluate against null baselines
python -m cgmacros_pipeline.cli eval   --data all_meal_segments_with_bio.csv   --model ml_outputs_mlcurve_rf/model_multioutput.pkl   --out ml_outputs_mlcurve_eval
```

---

## Programmatic usage

```python
import pandas as pd
from pathlib import Path
from cgmacros_pipeline.segments import build_meal_segments_from_root
from cgmacros_pipeline.bio import merge_segments_with_bio
from cgmacros_pipeline.train import train_random_forest
from cgmacros_pipeline.evaluate import eval_with_nulls

# Extract
segs = build_meal_segments_from_root(root_dir=".")
pd.concat(segs, ignore_index=True).to_csv("all_users_all_meal_segments.csv", index=False)

# Merge
merge_segments_with_bio(Path("all_users_all_meal_segments.csv"), Path("bio.csv"),
                        Path("all_meal_segments_with_bio.csv"))

# Train
train_info = train_random_forest(Path("all_meal_segments_with_bio.csv"), Path("ml_outputs_mlcurve_rf"))
print(train_info)

# Evaluate
eval_info = eval_with_nulls(Path("all_meal_segments_with_bio.csv"),
                            Path("ml_outputs_mlcurve_rf/model_multioutput.pkl"),
                            Path("ml_outputs_mlcurve_eval"))
print(eval_info)
```

---

## Feature set (meal-level)

The training feature vector per meal includes:

- **Baseline**: `baseline_avg_glucose` = average mg/dL from −30 to 0 min pre-meal (fallback to −60..0 if missing).
- **Macros**: `meal_calories`, `carbs_g`, `protein_g`, `fat_g`, `fiber_g`, `amount_consumed` (as available).
- **Demographics**: `Age`, `Gender`, `Body weight`, `Height`.
- **Activity summary**: mean of `activity_cal`, `mets` within the (−60..+120) window.
- **Meal bucket**: Breakfast / Lunch / Dinner / Snacks (derived from `meal_type`).

**Target** is a 120-dim vector: **Δ-glucose** (mg/dL) at minutes **1..120** after the meal.

---

## Model artifact

`ml_outputs_mlcurve_rf/model_multioutput.pkl` is a scikit-learn Pipeline:

- `preprocess`: `ColumnTransformer` with
  - Numeric: `SimpleImputer(median)`
  - Categorical (meal_bucket, Gender): `SimpleImputer(most_frequent)` + `OneHotEncoder(handle_unknown="ignore")`
- `reg`: `MultiOutputRegressor(RandomForestRegressor(...))`

This supports **inference with partial inputs** thanks to imputers.

---

## Using the trained model in your backend

Example request payload (minimum fields shown):

```python
payload = {
  "meal_bucket": "Lunch",
  "baseline_avg_glucose": 110,
  "carbs_g": 75, "protein_g": 25, "fat_g": 20, "fiber_g": 8,
  "Age": 44, "Gender": "Male",
  "Body weight": 82, "Height": 178,
  # Optional:
  "activity_cal_mean": 120, "mets_mean": 1.4
}
```

The model returns **Δ-glucose** for minutes 1..120. To get **absolute** glucose, add the baseline back:
`absolute_glucose[t] = baseline_avg_glucose + delta_glucose[t]`.

For a fully wired inference helper, see your `prediction_model.py` (accepts JSON, adds plotting/CSV if enabled).

---

## Evaluation & null baselines

We report MSE for:

- **Model** predictions
- **Zero** curve (all 0)
- **Global mean** curve (train-set mean)
- **Meal-type mean** curve (train-set mean per bucket)

This tells you if the learned model meaningfully beats trivial baselines.

---

## Troubleshooting

- **No glucose column found**  
  Ensure at least one of `Dexcom GL` or `Libre GL` exists and is non-empty.

- **No timestamp column found**  
  Include a recognizable column (`Timestamp`, `Time`, `DateTime`).

- **Sparse meal annotations**  
  Segments will still build using CGM; macros may be `NaN` and imputed during training.

- **Mismatched patient IDs**  
  The merge step canonicalizes IDs, but if you still see missing bio fields, confirm the ID column in `bio.csv` and normalize (e.g., `001` vs `1`).

- **Over-smooth predictions**  
  Try increasing RF `n_estimators`, reducing `min_samples_leaf`, or incorporating `activity_cal_mean`/`mets_mean`, which often improves curve shape.

---

## Development tips

- Add unit tests in `cgmacros_pipeline/tests/` (simple smoke tests for segment extraction and feature shapes).
- Keep **build strings** out of env files for cross-platform installs.
- Use `column names with spaces` exactly as in training (e.g., `"Body weight"`, `"Height"`).

---

## Acknowledgments

- **CGMacros** dataset (raw inputs).
- This pipeline draws on your previously developed scripts (`meal_segments.py`, `bio_match.py`, train/eval utilities), now modularized for clarity and reuse.

---
