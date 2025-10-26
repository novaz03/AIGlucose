from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from .features import build_meal_level_dataset
# Combined logic from ml_curve_eval_with_nulls.py and per-patient variant  

PANEL = ["Breakfast","Lunch","Dinner","Snacks"]

def eval_with_nulls(all_segments_with_bio_csv: Path, model_pkl: Path, out_dir: Path, test_size=0.2, random_state=42) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(all_segments_with_bio_csv)
    X_df, Y = build_meal_level_dataset(df)
    X_tr, X_te, Y_tr, Y_te = train_test_split(X_df, Y, test_size=test_size, random_state=random_state)

    model = joblib.load(model_pkl)
    Y_hat = model.predict(X_te)
    mse_test = mean_squared_error(Y_te, Y_hat)

    # Nulls
    Y0 = np.zeros_like(Y_te)
    y_mean = Y_tr.mean(axis=0, keepdims=True)
    Ym = np.repeat(y_mean, repeats=Y_te.shape[0], axis=0)
    # by meal type (if available)
    mean_by_type = {}
    for mt in PANEL:
        mask = (X_tr["meal_bucket"].values == mt)
        mean_by_type[mt] = Y_tr[mask].mean(axis=0) if mask.any() else y_mean.ravel()
    Yt = np.vstack([mean_by_type.get(mt, y_mean.ravel()) for mt in X_te["meal_bucket"].values])

    def mse_rows(Ya, Yb): return ((Ya - Yb)**2).mean(axis=1)
    summary = {
        "mse_model": float(mse_test),
        "mse_null_zero": float(mse_rows(Y_te, Y0).mean()),
        "mse_null_mean": float(mse_rows(Y_te, Ym).mean()),
        "mse_null_type_mean": float(mse_rows(Y_te, Yt).mean()),
    }
    pd.DataFrame([summary]).to_csv(out_dir/"null_comparison.csv", index=False)
    return summary
