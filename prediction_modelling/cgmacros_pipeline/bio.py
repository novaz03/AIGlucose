from __future__ import annotations
from pathlib import Path
from typing import Tuple
import numpy as np
import pandas as pd

# Ported from bio_match.py (ID canonicalization + merge)  :contentReference[oaicite:7]{index=7}

CANDIDATE_ID_COLS = ["patient_id","PatientID","patient","Patient","id","ID","subject","Subject","user","User"]

def _canon_pid(x) -> str | float:
    if pd.isna(x):
        return np.nan
    s = str(x).strip()
    try:
        return str(int(float(s)))  # removes leading zeros & .0
    except Exception:
        return s

def merge_segments_with_bio(segments_csv: Path, bio_csv: Path, out_csv: Path) -> Path:
    seg = pd.read_csv(segments_csv)
    bio = pd.read_csv(bio_csv)

    bio_id_col = next((c for c in CANDIDATE_ID_COLS if c in bio.columns), bio.columns[0])

    seg["_pid"] = seg["patient_id"].apply(_canon_pid)
    bio["_pid"] = bio[bio_id_col].apply(_canon_pid)

    merged = seg.merge(bio.drop(columns=[bio_id_col]), on="_pid", how="left", suffixes=("", "_bio")).drop(columns=["_pid"])
    id_cols = ["timestamp","patient_id","meal_index","meal_timestamp","rel_minute"]
    front = [c for c in id_cols if c in merged.columns]
    ordered = front + [c for c in merged.columns if c not in front]
    merged = merged[ordered]

    merged.to_csv(out_csv, index=False)
    return out_csv
