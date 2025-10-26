from __future__ import annotations
from pathlib import Path
from typing import Tuple, Dict
import time
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
import joblib

from .features import build_meal_level_dataset

# Features used by the ColumnTransformer
NUMERIC = [
    "baseline_avg_glucose","meal_calories","carbs_g","protein_g","fat_g","fiber_g","amount_consumed",
    "Age","Body weight","Height","activity_cal_mean","mets_mean"
]
CATEGORICAL = ["meal_bucket","Gender"]


def train_random_forest(
    all_segments_with_bio_csv: Path,
    out_dir: Path,
    test_size: float = 0.2,
    random_state: int = 42,
    n_estimators: int = 300,
    max_depth: int | None = 14,
    min_samples_split: int = 6,
    min_samples_leaf: int = 3,
    n_jobs: int = -1,
) -> Dict[str, float | str]:
    """
    Train a single multi-output RandomForestRegressor to predict Δglucose at minutes 1..120.

    Parameters
    ----------
    all_segments_with_bio_csv : Path
        CSV produced by the pipeline (meal segments joined with bio).
    out_dir : Path
        Output directory for artifacts and metrics.
    test_size : float
        Fraction for train/test split.
    random_state : int
        Random seed for reproducibility.
    n_estimators, max_depth, min_samples_split, min_samples_leaf, n_jobs
        Random forest hyperparameters.

    Returns
    -------
    dict
        {"train_mse": float, "test_mse": float, "train_seconds": float, "model_path": str}
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(all_segments_with_bio_csv)

    # Build X (meal-level features) and Y (targets: Δglucose for minutes 1..120)
    X_df, Y = build_meal_level_dataset(df)  # Y.shape == (N, 120)

    X_tr, X_te, Y_tr, Y_te = train_test_split(
        X_df, Y, test_size=test_size, random_state=random_state
    )

    preprocess = ColumnTransformer(
        transformers=[
            ("num", SimpleImputer(strategy="median"), NUMERIC),
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imp", SimpleImputer(strategy="most_frequent")),
                        ("oh", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                CATEGORICAL,
            ),
        ]
    )

    # Single RF that natively handles multi-output regression (Y is 2D)
    rf = RandomForestRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_split=min_samples_split,
        min_samples_leaf=min_samples_leaf,
        random_state=random_state,
        n_jobs=n_jobs,
    )

    model = Pipeline([("preprocess", preprocess), ("reg", rf)])

    t0 = time.perf_counter()
    model.fit(X_tr, Y_tr)
    t1 = time.perf_counter()

    # Evaluate
    Y_tr_pred = model.predict(X_tr)
    Y_te_pred = model.predict(X_te)
    mse_tr = mean_squared_error(Y_tr, Y_tr_pred)
    mse_te = mean_squared_error(Y_te, Y_te_pred)

    # Write summary
    pd.DataFrame(
        {"metric": ["mse_train", "mse_test"], "value": [mse_tr, mse_te]}
    ).to_csv(out_dir / "summary.csv", index=False)

    # Export feature importances (using fitted one-hot names)
    preprocess_fitted = model.named_steps["preprocess"]
    oh: OneHotEncoder = preprocess_fitted.named_transformers_["cat"].named_steps["oh"]
    num_cols = preprocess_fitted.transformers_[0][2]
    cat_cols = oh.get_feature_names_out(CATEGORICAL).tolist()
    all_feature_names = list(num_cols) + cat_cols

    rf_fitted: RandomForestRegressor = model.named_steps["reg"]
    fi = rf_fitted.feature_importances_
    pd.DataFrame({"feature": all_feature_names, "importance": fi}).sort_values(
        "importance", ascending=False
    ).to_csv(out_dir / "feature_importances.csv", index=False)

    # Save model (compressed)
    model_path = out_dir / "model_multioutput.pkl"
    joblib.dump(model, model_path, compress=("xz", 3))

    return {
        "train_mse": float(mse_tr),
        "test_mse": float(mse_te),
        "train_seconds": float(t1 - t0),
        "model_path": str(model_path),
    }
