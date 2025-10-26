from __future__ import annotations
from pathlib import Path
from typing import Tuple
import time, logging
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
import joblib

from .features import build_meal_level_dataset
# Adapted from ml_curve_train_with_progress.py  :contentReference[oaicite:9]{index=9}

NUMERIC = [
    "baseline_avg_glucose","meal_calories","carbs_g","protein_g","fat_g","fiber_g","amount_consumed",
    "Age","Body weight","Height","activity_cal_mean","mets_mean"
]
CATEGORICAL = ["meal_bucket","Gender"]

def train_random_forest(all_segments_with_bio_csv: Path, out_dir: Path, test_size=0.2, random_state=42,
                        n_estimators=400, max_depth=None, min_samples_split=4, min_samples_leaf=2, n_jobs=-1) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(all_segments_with_bio_csv)
    X_df, Y = build_meal_level_dataset(df)
    X_tr, X_te, Y_tr, Y_te = train_test_split(X_df, Y, test_size=test_size, random_state=random_state)

    preprocess = ColumnTransformer([
        ("num", SimpleImputer(strategy="median"), NUMERIC),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                          ("oh", OneHotEncoder(handle_unknown="ignore"))]), CATEGORICAL)
    ])

    rf = RandomForestRegressor(
        n_estimators=n_estimators, max_depth=max_depth,
        min_samples_split=min_samples_split, min_samples_leaf=min_samples_leaf,
        random_state=random_state, n_jobs=n_jobs
    )
    model = Pipeline([("preprocess", preprocess), ("reg", MultiOutputRegressor(rf))])
    t0 = time.perf_counter(); model.fit(X_tr, Y_tr); t1 = time.perf_counter()

    mse_tr = mean_squared_error(Y_tr, model.predict(X_tr))
    mse_te = mean_squared_error(Y_te, model.predict(X_te))
    pd.DataFrame({"metric":["mse_train","mse_test"], "value":[mse_tr, mse_te]}).to_csv(out_dir/"summary.csv", index=False)

    joblib.dump(model, out_dir/"model_multioutput.pkl")
    return {"train_mse": float(mse_tr), "test_mse": float(mse_te), "train_seconds": t1-t0, "model_path": str(out_dir/"model_multioutput.pkl")}
