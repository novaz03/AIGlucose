# prediction_model.py
from __future__ import annotations
import os
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


# ----------------------------- helpers -----------------------------
def _bucket_meal_type(x: object) -> str:
    s = (str(x) if x is not None else "").strip().lower()
    if "breakfast" in s: return "Breakfast"
    if "lunch" in s: return "Lunch"
    if "dinner" in s or "supper" in s: return "Dinner"
    if "snack" in s: return "Snacks"
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


# ----------------------------- model -----------------------------
class PredictionModel:
    """
    Sklearn Pipeline backend for CGMacros curve prediction.

    Artifacts:
      - a directory containing 'model_multioutput.pkl', OR
      - a direct path to that pickle file.

    The pickle is expected to be a Pipeline:
      preprocess (ColumnTransformer) -> MultiOutputRegressor(RandomForestRegressor)
    """

    def __init__(self, artifact: str | Path = "ml_outputs_mlcurve_rf",
                 n_jobs_targets: Optional[int] = None,
                 n_jobs_trees: int = 1) -> None:
        """
        Params
        ------
        artifact : str|Path
            Directory containing 'model_multioutput.pkl' OR direct path to the .pkl.
        n_jobs_targets : int|None
            Parallelism across outputs (MultiOutputRegressor.n_jobs). If None, leaves as-is.
            Tip: set to # of physical cores for speed; keep n_jobs_trees=1 to avoid oversubscription.
        n_jobs_trees : int
            Threads per RandomForest (each target). Usually 1 in production.
        """
        # (Optional) be nice to BLAS if present
        os.environ.setdefault("OMP_NUM_THREADS", "1")
        os.environ.setdefault("MKL_NUM_THREADS", "1")

        self.model_path = self._resolve_model_path(artifact)
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

        # Tune parallelism to speed inference
        self._optimize_parallelism(n_jobs_targets=n_jobs_targets, n_jobs_trees=n_jobs_trees)

    # ----- path handling -----
    @staticmethod
    def _resolve_model_path(artifact: str | Path) -> Path:
        p = Path(artifact)
        tried: List[Path] = []

        if p.suffix.lower() == ".pkl":  # direct file path
            tried.append(p)
            if p.exists():
                return p
        else:  # directory; standard location inside
            cand = p / "model_multioutput.pkl"
            tried.append(cand)
            if cand.exists():
                return cand

        # also try sibling if user passed a file inside the dir
        if p.is_file():
            alt = p.parent / "model_multioutput.pkl"
            tried.append(alt)
            if alt.exists():
                return alt

        raise FileNotFoundError(
            "Model file not found.\n"
            "  Tried:\n    - " + "\n    - ".join(str(t.resolve()) for t in tried) + "\n"
            "Pass a directory containing 'model_multioutput.pkl' or a direct path to the .pkl file."
        )

    # ----- speed tuning -----
    def _optimize_parallelism(self, n_jobs_targets: Optional[int], n_jobs_trees: int) -> None:
        """
        Set MultiOutputRegressor.n_jobs (parallel over outputs) and force each
        underlying RandomForest to be single-threaded (or given n_jobs_trees).
        """
        try:
            reg = self._model.named_steps.get("reg", None)
            if reg is None:
                return
            # parallelize across outputs
            if (n_jobs_targets is not None) and hasattr(reg, "n_jobs"):
                reg.n_jobs = n_jobs_targets
            # avoid nested parallelism per forest
            if hasattr(reg, "estimators_") and reg.estimators_:
                for est in reg.estimators_:
                    if hasattr(est, "n_jobs"):
                        est.n_jobs = int(n_jobs_trees)
        except Exception:
            # don't fail if pipeline shape differs
            pass

    # ----- schema utilities -----
    def expected_features(self) -> List[str]:
        return list(self.expected_columns)

    def version_info(self) -> Dict[str, str]:
        import sklearn, numpy
        return {"sklearn": sklearn.__version__, "numpy": numpy.__version__}

    # ----- Input mapping -----
    def _payload_to_df(self, payload: Mapping[str, Any]) -> pd.DataFrame:
        """
        Map inbound JSON dict -> single-row DataFrame with the exact column
        names expected by the sklearn pipeline.
        """
        # Accept both "Body weight" and common variants
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
            "Height": height,             # exact key
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

    # ----- Core predict (single) -----
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
        await asyncio.sleep(0)  # keep async-friendly

        if not isinstance(payload, Mapping):
            raise TypeError("payload must be a dict-like mapping")

        return_plot = bool(payload.get("return_plot", False))
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

        return json.dumps(result)

    # ----- Batch predict (vectorized & fast) -----
    async def predict_many(self, payloads: List[Mapping[str, Any]]) -> str:
        """
        Batch version: accepts a list of payload dicts, returns:
        {"items": [ <single predict() dict>, ... ]}
        """
        await asyncio.sleep(0)
        if not isinstance(payloads, list):
            raise TypeError("payloads must be a list of dicts")

        if not payloads:
            return json.dumps({"items": []})

        dfs, baselines, plots = [], [], []
        for p in payloads:
            return_plot = bool(p.get("return_plot", False))
            df = self._payload_to_df(p)
            dfs.append(df)
            baselines.append(float(df.loc[0, "baseline_avg_glucose"]))
            plots.append(return_plot)

        X = pd.concat(dfs, axis=0, ignore_index=True)  # vectorized
        try:
            Y = self._model.predict(X)   # shape [N, 120]
            Y = np.asarray(Y, dtype=float)
        except Exception as e:
            raise RuntimeError(f"Batch prediction failed: {e}") from e

        if Y.shape[1] != 120:
            raise RuntimeError(f"Model returned {Y.shape[1]} outputs; expected 120.")

        minutes = np.arange(1, 121, dtype=int)
        items = []
        for i, base in enumerate(baselines):
            y_delta = Y[i]
            y_abs = base + y_delta
            item = {
                "minutes": minutes.tolist(),
                "delta_glucose": y_delta.tolist(),
                "absolute_glucose": y_abs.tolist(),
                "inputs_used": json.loads(dfs[i].iloc[0].to_json()),
            }
            if plots[i]:
                item["png_base64"] = _build_plot(minutes, y_abs, y_delta)
            items.append(item)

        return json.dumps({"items": items})
