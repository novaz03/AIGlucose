from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import re
import numpy as np
import pandas as pd

# ——— Helpers adapted from your meal_segments.py ———
# (normalize, detect_meals, extract_meal_segment, build_... functions)
# Source: meal_segments.py  :contentReference[oaicite:6]{index=6}

def _choose_glucose_column(df: pd.DataFrame) -> str:
    for col in ("Dexcom GL", "Libre GL"):
        if col in df.columns and df[col].notna().sum() > 0:
            return col
    raise ValueError("No glucose column found among: 'Dexcom GL', 'Libre GL'.")

def _find_timestamp_column(df: pd.DataFrame) -> str:
    for c in ("Timestamp", "timestamp", "Time", "time", "DateTime", "datetime"):
        if c in df.columns:
            return c
    raise ValueError("No timestamp-like column found.")

def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    ts_col = _find_timestamp_column(df)
    df["Timestamp"] = pd.to_datetime(df[ts_col])
    df = df.sort_values("Timestamp").reset_index(drop=True)

    gl_col = _choose_glucose_column(df)
    df["glucose_mgdl"] = pd.to_numeric(df[gl_col], errors="coerce")
    df["activity_cal"] = pd.to_numeric(df.get("Calories (Activity)", np.nan), errors="coerce")
    df["mets"] = pd.to_numeric(df.get("METs", np.nan), errors="coerce")

    # Meal annotations & nutrition
    df["meal_type"] = df.get("Meal Type")
    df["meal_calories"] = pd.to_numeric(df.get("Calories", np.nan), errors="coerce")
    df["carbs_g"] = pd.to_numeric(df.get("Carbs", np.nan), errors="coerce")
    df["protein_g"] = pd.to_numeric(df.get("Protein", np.nan), errors="coerce")
    df["fat_g"] = pd.to_numeric(df.get("Fat", np.nan), errors="coerce")
    df["fiber_g"] = pd.to_numeric(df.get("Fiber", np.nan), errors="coerce")
    df["amount_consumed"] = pd.to_numeric(df.get("Amount Consumed", np.nan), errors="coerce")
    return df.set_index("Timestamp", drop=True)

def detect_meals(df: pd.DataFrame) -> pd.DataFrame:
    meal_mask = (
        df["meal_type"].notna()
        | df["meal_calories"].notna()
        | df["carbs_g"].notna()
        | df["protein_g"].notna()
        | df["fat_g"].notna()
        | df["fiber_g"].notna()
        | df["amount_consumed"].notna()
    )
    return df.loc[meal_mask].copy()

def _nearest_meal_row(df: pd.DataFrame, meal_time: pd.Timestamp) -> pd.Series:
    try:
        cols = ["meal_type","meal_calories","carbs_g","protein_g","fat_g","fiber_g","amount_consumed"]
        return df.loc[meal_time, cols]
    except KeyError:
        take = df.index.get_indexer([meal_time], method="nearest")
        idx = take[0]
        nearest = df.index[idx]
        if abs((nearest - meal_time).total_seconds()) <= 120:
            return df.loc[nearest, cols]
        return pd.Series({c: np.nan for c in cols})

def extract_meal_segment(
    df: pd.DataFrame,
    meal_time: pd.Timestamp,
    pre_minutes: int = 60,
    post_minutes: int = 120,
    baseline_window: int = 15,
    resample_rule: str = "1min",
    meal_index: int = 0,
    patient_id: str = "unknown",
) -> pd.DataFrame:
    start = meal_time - pd.Timedelta(minutes=pre_minutes)
    end = meal_time + pd.Timedelta(minutes=post_minutes)
    cols = ["glucose_mgdl","activity_cal","mets"]
    seg = df.loc[start:end, cols].copy()
    if seg.empty:
        return pd.DataFrame()

    if resample_rule:
        seg = seg.resample(resample_rule).mean().interpolate(limit_direction="both")

    seg["rel_minute"] = ((seg.index - meal_time).total_seconds() / 60.0).astype(int)

    m = (seg["rel_minute"] >= -baseline_window) & (seg["rel_minute"] < 0)
    if m.any() and seg.loc[m, "glucose_mgdl"].notna().any():
        baseline = float(np.nanmedian(seg.loc[m, "glucose_mgdl"].values))
    else:
        baseline = float(seg["glucose_mgdl"].dropna().iloc[0]) if seg["glucose_mgdl"].notna().any() else np.nan

    seg["delta_glucose_mgdl"] = seg["glucose_mgdl"] - baseline

    meta = _nearest_meal_row(df, meal_time)
    seg["meal_timestamp"] = meal_time
    seg["meal_index"] = meal_index
    seg["patient_id"] = patient_id
    for c in ["meal_type","meal_calories","carbs_g","protein_g","fat_g","fiber_g","amount_consumed"]:
        seg[c] = meta.get(c, np.nan)

    seg = seg.reset_index().rename(columns={"index": "timestamp", "Timestamp": "timestamp"})
    return seg[[
        "timestamp","patient_id","meal_index","meal_timestamp","rel_minute",
        "glucose_mgdl","delta_glucose_mgdl","activity_cal","mets",
        "meal_type","meal_calories","carbs_g","protein_g","fat_g","fiber_g","amount_consumed"
    ]]

def build_meal_segments_from_csv(
    csv_path: str,
    patient_id: Optional[str] = None,
    pre_minutes: int = 60,
    post_minutes: int = 120,
    baseline_window: int = 15,
    resample_rule: str = "1min",
) -> List[pd.DataFrame]:
    raw = pd.read_csv(csv_path)
    df = _normalize(raw)
    meals = detect_meals(df)
    if patient_id is None:
        stem = Path(csv_path).stem
        m = re.search(r"CGMacros-(.+)$", stem)
        patient_id = m.group(1) if m else stem
    out: List[pd.DataFrame] = []
    for i, meal_time in enumerate(meals.index):
        seg = extract_meal_segment(df, meal_time,
                                   pre_minutes, post_minutes, baseline_window, resample_rule,
                                   i, patient_id)
        if not seg.empty:
            out.append(seg)
    return out

def build_meal_segments_from_root(
    root_dir: str = ".",
    pre_minutes: int = 60,
    post_minutes: int = 120,
    baseline_window: int = 15,
    resample_rule: str = "1min",
) -> List[pd.DataFrame]:
    base = Path(root_dir) / "CGMacros"
    out: List[pd.DataFrame] = []
    if not base.exists():
        return out
    for folder in sorted(base.glob("CGMacros-*")):
        if not folder.is_dir(): 
            continue
        pid = folder.name.replace("CGMacros-", "")
        csv_path = folder / f"CGMacros-{pid}.csv"
        if not csv_path.exists():
            continue
        out.extend(build_meal_segments_from_csv(str(csv_path), patient_id=pid,
                                                pre_minutes=pre_minutes, post_minutes=post_minutes,
                                                baseline_window=baseline_window, resample_rule=resample_rule))
    return out
