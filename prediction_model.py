# prediction_model.py
from __future__ import annotations
import asyncio
import json
import io
import base64
from typing import Any, Dict, List, Optional, Mapping
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
import matplotlib.pyplot as plt


def _bucket_meal_type(x: object) -> str:
    s = (str(x) if x is not None else "").strip().lower()
    if "breakfast" in s: return "Breakfast"
    if "lunch" in s: return "Lunch"
    if "dinner" in s or "supper" in s: return "Dinner"
    if "snack" in s: return "Snacks"
    # If unknown, raise so the caller can fix input
    raise ValueError("meal_bucket must be one of: Breakfast, Lunch, Dinner, Snacks")


def _normalize_gender(x: Optional[str]) -> str:
    s = (x or "Unknown").strip().title()
    return s if s else "Unknown"


def _build_plot(minutes: np.ndarray, abs_curve: np.ndarray, delta_curve: np.ndarray) -> str:
    """Return a base64-encoded PNG of absolute and delta curves."""
    fig, ax1 = plt.subplots(figsize=(8, 4.5))
    ax1.plot(minutes, abs_curve, linewidth=2, label="Absolute glucose (mg/dL)")
    ax1.set_xlabel("Minutes after meal")
    ax1.set_ylabel("mg/dL")
    ax1.grid(True, alpha=0.25)

    ax2 = ax1.twinx()
    ax2.plot(minutes, delta_curve, linewidth=1.5, linestyle="--", label="ΔGlucose (mg/dL)", alpha=0.9)
    ax2.set_ylabel("Δ mg/dL")

    ax1.axvline(0, linestyle="--", alpha=0.5)
    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")
    fig.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


class PredictionModel:
    """
    Sklearn Pipeline backend for CGMacros curve prediction.
    Expects a joblib'd Pipeline with a ColumnTransformer + MultiOutput RandomForestRegressor.

    Artifacts:
      - {artifact_dir}/model_multioutput.pkl
    """

    def __init__(self, artifact_dir: str | Path = "ml_outputs_mlcurve_rf") -> None:
        self.artifact_dir = Path(artifact_dir)
        self.model_path = self.artifact_dir / "model_multioutput.pkl"
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model file not found: {self.model_path.resolve()}. "
                "Train and save the RF model (model_multioutput.pkl) before using the API."
            )
        # Load once (thread-safe for inference in sklearn)
        self._model = joblib.load(self.model_path)

        # Try to extract input schema (numeric + categorical columns) from the pipeline
        try:
            preprocess = self._model.named_steps["preprocess"]
            num_cols: List[str] = list(preprocess.transformers_[0][2])  # numeric_features
            cat_cols_input: List[str] = list(preprocess.transformers_[1][2])  # ["meal_bucket","Gender"]
        except Exception:
            # Fallback to default training columns if the pipeline structure differs
            num_cols = [
                "baseline_avg_glucose","meal_calories","carbs_g","protein_g","fat_g","fiber_g","amount_consumed",
                "Age","Body weight","Height","activity_cal_mean","mets_mean"
            ]
            cat_cols_input = ["meal_bucket","Gender"]

        self.expected_columns: List[str] = num_cols + cat_cols_input

    # ----- Input mapping -----
    def _payload_to_df(self, payload: Mapping[str, Any]) -> pd.DataFrame:
        """
        Map inbound JSON dict -> single-row DataFrame with the exact column
        names expected by the sklearn pipeline.
        """
        # Accept both "Body weight" and "Body_weight"/"BodyWeight" etc.
        body_weight = (
            payload.get("Body weight", None)
            or payload.get("Body_weight", None)
            or payload.get("BodyWeight", None)
            or payload.get("body_weight", None)
        )
        height = (
            payload.get("Height", None)
            or payload.get("height", None)
        )

        meal_bucket_raw = payload.get("meal_bucket", payload.get("meal_type", None))
        meal_bucket = _bucket_meal_type(meal_bucket_raw)

        gender = _normalize_gender(payload.get("Gender"))

        row: Dict[str, Any] = {
            "meal_bucket": meal_bucket,
            "baseline_avg_glucose": payload.get("baseline_avg_glucose"),
            "meal_calories": payload.get("meal_calories"),
            "carbs_g": payload.get("carbs_g"),
            "protein_g": payload.get("protein_g"),
            "fat_g": payload.get("fat_g"),
            "fiber_g": payload.get("fiber_g"),
            "amount_consumed": payload.get("amount_consumed"),
            "Age": payload.get("Age"),
            "Gender": gender,
            "Body weight": body_weight,   # exact key with space
            "Height": height,             # exact key (no trailing space)
            "activity_cal_mean": payload.get("activity_cal_mean"),
            "mets_mean": payload.get("mets_mean"),
        }

        # Minimal validation
        if row["baseline_avg_glucose"] is None:
            raise ValueError("baseline_avg_glucose is required (mean mg/dL during −30..0 min pre-meal).")

        # Keep only columns the model expects (in consistent order)
        row = {k: row.get(k, None) for k in self.expected_columns}
        df = pd.DataFrame([row])

        # Ensure numeric types can be coerced by the pipeline's imputers
        for col in ["baseline_avg_glucose","meal_calories","carbs_g","protein_g","fat_g","fiber_g",
                    "amount_consumed","Age","Body weight","Height","activity_cal_mean","mets_mean"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    # ----- Core predict -----
    async def predict(self, payload: Any) -> str:
        """
        Accepts a dict-like payload:
          {
            "meal_bucket": "Lunch",
            "baseline_avg_glucose": 110,
            "carbs_g": 75, "protein_g": 25, "fat_g": 20, "fiber_g": 8,
            "Age": 44, "Gender": "Male",
            "Body weight": 82, "Height": 178,
            "activity_cal_mean": 120, "mets_mean": 1.4,
            "return_plot": true   # optional
          }
        Returns a JSON string with:
          - minutes (1..120)
          - delta_glucose (Δ mg/dL)
          - absolute_glucose (mg/dL)
          - inputs_used (the normalized row)
          - png_base64 (optional, when return_plot==True)
        """
        # Simulate async boundary so this method integrates well with async servers
        await asyncio.sleep(0)

        if not isinstance(payload, Mapping):
            raise TypeError("payload must be a dict-like mapping")

        # Optional flag to include a base64 plot in the response
        return_plot = bool(payload.get("return_plot", False))

        # Map payload -> DataFrame
        df = self._payload_to_df(payload)

        # Predict Δglucose 1..120
        try:
            yhat = self._model.predict(df)
            yhat = np.asarray(yhat).reshape(1, -1)  # (1,120)
        except Exception as e:
            raise RuntimeError(f"Model prediction failed: {e}") from e

        if yhat.shape[1] != 120:
            raise RuntimeError(f"Model returned {yhat.shape[1]} outputs; expected 120.")

        y_delta = yhat[0].astype(float)  # (120,)
        minutes = np.arange(1, 121, dtype=int)
        baseline = float(df.loc[0, "baseline_avg_glucose"])
        y_abs = (baseline + y_delta).astype(float)

        result: Dict[str, Any] = {
            "minutes": minutes.tolist(),
            "delta_glucose": y_delta.tolist(),
            "absolute_glucose": y_abs.tolist(),
            "inputs_used": json.loads(df.iloc[0].to_json()),
        }

        if return_plot:
            result["png_base64"] = _build_plot(minutes, y_abs, y_delta)

        # Return as JSON string (to match the original mock signature)
        return json.dumps(result)
