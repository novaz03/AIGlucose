from __future__ import annotations
from typing import Tuple, Dict, Any
import numpy as np
import pandas as pd
from tqdm.auto import tqdm

# Build meal-level feature table + 120-d target vector
# Adapted from training/eval scripts  

def bucket_meal_type(x: object) -> str | None:
    s = str(x).strip().lower()
    if "breakfast" in s: return "Breakfast"
    if "lunch" in s: return "Lunch"
    if "dinner" in s or "supper" in s: return "Dinner"
    if "snack" in s: return "Snacks"
    return None

def build_meal_level_dataset(df: pd.DataFrame, verbose: bool=False) -> tuple[pd.DataFrame, np.ndarray]:
    df = df.copy()
    df.columns = [c.rstrip() for c in df.columns]
    if "Body weight " in df.columns: df = df.rename(columns={"Body weight ": "Body weight"})
    if "Height " in df.columns: df = df.rename(columns={"Height ": "Height"})
    df["meal_bucket"] = df["meal_type"].map(bucket_meal_type)
    for c in ["rel_minute","glucose_mgdl","delta_glucose_mgdl","activity_cal","mets",
              "meal_calories","carbs_g","protein_g","fat_g","fiber_g","amount_consumed",
              "Age","Body weight","Height"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["patient_id"] = df["patient_id"].astype(str)

    keys = ["patient_id","meal_index","meal_timestamp","meal_bucket"]
    meals = df.dropna(subset=["meal_bucket"]).groupby(keys, as_index=False)

    rows, ys = [], []
    n_skipped_base = n_skipped_post = 0

    for key, g in tqdm(meals, total=meals.ngroups, desc="Meals"):
        g = g.sort_values("rel_minute")
        base = g[(g["rel_minute"] >= -30) & (g["rel_minute"] < 0)]["glucose_mgdl"].dropna()
        if not len(base):
            pre = g[(g["rel_minute"] >= -60) & (g["rel_minute"] < 0)]["glucose_mgdl"].dropna()
            if not len(pre):
                n_skipped_base += 1
                continue
            baseline = float(pre.mean())
        else:
            baseline = float(base.mean())

        post = g[(g["rel_minute"] >= 1) & (g["rel_minute"] <= 120)][["rel_minute","delta_glucose_mgdl"]].dropna()
        idx = pd.Index(range(1,121), name="rel_minute")
        post = post.set_index("rel_minute").reindex(idx)
        post["delta_glucose_mgdl"] = post["delta_glucose_mgdl"].interpolate(limit_direction="both")
        y_vec = post["delta_glucose_mgdl"].values.astype(float)
        if np.isnan(y_vec).any():
            n_skipped_post += 1
            continue

        def first(col: str):
            return float(g[col].dropna().iloc[0]) if col in g and g[col].notna().any() else np.nan

        rows.append({
            "patient_id": str(key[0]),
            "meal_bucket": key[3],
            "baseline_avg_glucose": baseline,
            "meal_calories": first("meal_calories"),
            "carbs_g": first("carbs_g"),
            "protein_g": first("protein_g"),
            "fat_g": first("fat_g"),
            "fiber_g": first("fiber_g"),
            "amount_consumed": first("amount_consumed"),
            "Age": first("Age"),
            "Gender": str(g["Gender"].dropna().iloc[0]) if g["Gender"].notna().any() else "Unknown",
            "Body weight": first("Body weight"),
            "Height": first("Height"),
            "activity_cal_mean": float(g["activity_cal"].mean()) if g["activity_cal"].notna().any() else np.nan,
            "mets_mean": float(g["mets"].mean()) if g["mets"].notna().any() else np.nan,
        })
        ys.append(y_vec)

    X = pd.DataFrame.from_records(rows)
    Y = np.vstack(ys) if ys else np.empty((0,120))
    if verbose:
        print(f"Features: {X.shape}  Target: {Y.shape}  Skipped baseline={n_skipped_base}, post={n_skipped_post}")
    return X, Y
