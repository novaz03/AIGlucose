# prediction_model.py
from __future__ import annotations
import os
import asyncio
import json
import io
import base64
from typing import Any, Dict, List, Optional, Mapping, Tuple
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import joblib
import matplotlib

# Force a headless backend so Cocoa/Tk windows are never created server-side.
matplotlib.use("Agg", force=True)

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


def _build_plot_base64(minutes: np.ndarray, abs_curve: np.ndarray, delta_curve: np.ndarray) -> str:
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


def _save_plot_png(path: Path, minutes: np.ndarray, abs_curve: np.ndarray, delta_curve: np.ndarray) -> None:
    """Save a PNG plot to 'path'."""
    path.parent.mkdir(parents=True, exist_ok=True)
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
    plt.savefig(path, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _build_csv(df_row: pd.Series,
               minutes: np.ndarray,
               delta_curve: np.ndarray,
               abs_curve: np.ndarray) -> str:
    """
    CSV with per-minute rows + all input fields replicated.
    Columns: minute, delta_glucose, absolute_glucose, <input fields...>
    """
    base = pd.DataFrame({
        "minute": minutes.astype(int),
        "delta_glucose": delta_curve.astype(float),
        "absolute_glucose": abs_curve.astype(float),
    })
    inputs_df = pd.DataFrame([df_row.to_dict()])
    repeated = pd.concat([inputs_df]*len(base), ignore_index=True)
    out = pd.concat([base, repeated], axis=1)
    return out.to_csv(index=False)


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


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

    def __init__(self,
                 artifact: str | Path = "ml_outputs_mlcurve_rf",
                 n_jobs_targets: Optional[int] = None,
                 n_jobs_trees: int = 1,
                 output_dir: str | Path = "pred_outputs",
                 save_plot: bool = True,
                 save_json: bool = True) -> None:
        """
        Params
        ------
        artifact : str|Path
            Directory containing 'model_multioutput.pkl' OR direct path to the .pkl.
        n_jobs_targets : int|None
            Parallelism across outputs (MultiOutputRegressor.n_jobs). If None, leaves as-is.
            Tip: set to # of physical cores; keep n_jobs_trees=1 to avoid oversubscription.
        n_jobs_trees : int
            Threads per RandomForest (each target). Usually 1.
        output_dir : str|Path
            Directory to write PNGs/JSONs (created if missing).
        save_plot : bool
            By default, save PNG to disk and include its path.
        save_json : bool
            By default, save the JSON result to disk and include its path.
        """
        # (Optional) be nice to BLAS if present
        os.environ.setdefault("OMP_NUM_THREADS", "1")
        os.environ.setdefault("MKL_NUM_THREADS", "1")

        self.model_path = self._resolve_model_path(artifact)
        self._model = joblib.load(self.model_path)

        # input schema
        try:
            preprocess = self._model.named_steps["preprocess"]
            num_cols: List[str] = list(preprocess.transformers_[0][2])
            cat_cols_input: List[str] = list(preprocess.transformers_[1][2])  # ["meal_bucket","Gender"]
        except Exception:
            num_cols = [
                "baseline_avg_glucose","meal_calories","carbs_g","protein_g","fat_g","fiber_g","amount_consumed",
                "Age","Body weight","Height","activity_cal_mean","mets_mean"
            ]
            cat_cols_input = ["meal_bucket","Gender"]
        self.expected_columns: List[str] = num_cols + cat_cols_input

        # speed tuning
        self._optimize_parallelism(n_jobs_targets=n_jobs_targets, n_jobs_trees=n_jobs_trees)

        # output management
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.save_plot = bool(save_plot)
        self.save_json = bool(save_json)

    # ----- path handling -----
    @staticmethod
    def _resolve_model_path(artifact: str | Path) -> Path:
        p = Path(artifact)
        tried: List[Path] = []

        if p.suffix.lower() == ".pkl":
            tried.append(p)
            if p.exists():
                return p
        else:
            cand = p / "model_multioutput.pkl"
            tried.append(cand)
            if cand.exists():
                return cand

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
        try:
            reg = self._model.named_steps.get("reg", None)
            if reg is None:
                return
            if (n_jobs_targets is not None) and hasattr(reg, "n_jobs"):
                reg.n_jobs = n_jobs_targets
            if hasattr(reg, "estimators_") and reg.estimators_:
                for est in reg.estimators_:
                    if hasattr(est, "n_jobs"):
                        est.n_jobs = int(n_jobs_trees)
        except Exception:
            pass

    # ----- schema utilities -----
    def expected_features(self) -> List[str]:
        return list(self.expected_columns)

    def version_info(self) -> Dict[str, str]:
        import sklearn, numpy
        return {"sklearn": sklearn.__version__, "numpy": numpy.__version__}

    # ----- Input mapping -----
    def _payload_to_df(self, payload: Mapping[str, Any]) -> pd.DataFrame:
        body_weight = (
            payload.get("Body weight", None)
            or payload.get("Body_weight", None)
            or payload.get("BodyWeight", None)
            or payload.get("body_weight", None)
        )
        height = payload.get("Height", None) or payload.get("height", None)

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
            "Body weight": body_weight,
            "Height": height,
            "activity_cal_mean": payload.get("activity_cal_mean"),
            "mets_mean": payload.get("mets_mean"),
        }
        if row["baseline_avg_glucose"] is None:
            raise ValueError("baseline_avg_glucose is required (mean mg/dL during −30..0 min pre-meal).")

        row = {k: row.get(k, None) for k in self.expected_columns}
        df = pd.DataFrame([row])

        for col in ["baseline_avg_glucose","meal_calories","carbs_g","protein_g","fat_g","fiber_g",
                    "amount_consumed","Age","Body weight","Height","activity_cal_mean","mets_mean"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    # ----- Core predict (single) -----
    async def predict(self, payload: Any) -> Tuple[str, str, bool]: # json, png_path, b_is_safe
        """
        Returns JSON string; also writes PNG/JSON to disk by default.
        JSON fields:
          - minutes (1..120), delta_glucose, absolute_glucose, inputs_used
          - image_path (filesystem path of saved PNG)  [if save_plot=True]
          - json_path  (filesystem path of saved JSON) [if save_json=True]
          - png_base64 (optional, when return_plot==True)
          - csv, csv_base64, csv_filename (optional, when return_csv==True)
        """
        await asyncio.sleep(0)

        if not isinstance(payload, Mapping):
            raise TypeError("payload must be a dict-like mapping")

        return_plot = bool(payload.get("return_plot", False))
        return_csv  = bool(payload.get("return_csv", False))
        df = self._payload_to_df(payload)

        # Predict Δglucose 1..120
        try:
            yhat = self._model.predict(df)
            yhat = np.asarray(yhat).reshape(1, -1)
        except Exception as e:
            raise RuntimeError(f"Model prediction failed: {e}") from e

        if yhat.shape[1] != 120:
            raise RuntimeError(f"Model returned {yhat.shape[1]} outputs; expected 120.")

        y_delta = yhat[0].astype(float)
        minutes = np.arange(1, 121, dtype=int)
        baseline = float(df.loc[0, "baseline_avg_glucose"])
        y_abs = (baseline + y_delta).astype(float)

        inputs_used = json.loads(df.iloc[0].to_json())
        meal_name = inputs_used.get("meal_bucket", "meal")
        stamp = _ts()

        result: Dict[str, Any] = {
            "minutes": minutes.tolist(),
            "delta_glucose": y_delta.tolist(),
            "absolute_glucose": y_abs.tolist(),
            "inputs_used": inputs_used,
        }

        # Save PNG by default
        if self.save_plot:
            png_path = self.output_dir / f"{meal_name}_{stamp}.png"
            _save_plot_png(png_path, minutes, y_abs, y_delta)
            result["image_path"] = str(png_path.resolve())

        # Inline plot (base64) if requested
        if return_plot:
            result["png_base64"] = _build_plot_base64(minutes, y_abs, y_delta)

        # Optional CSV in response (not saved unless you want to)
        if return_csv:
            csv_text = _build_csv(df.iloc[0], minutes, y_delta, y_abs)
            result["csv"] = csv_text
            result["csv_base64"] = base64.b64encode(csv_text.encode("utf-8")).decode("utf-8")
            result["csv_filename"] = f"glucose_curve_{meal_name}.csv"

        # Save JSON by default
        if self.save_json:
            json_path = self.output_dir / f"{meal_name}_{stamp}.json"
            json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            result["json_path"] = str(json_path.resolve())

        return json.dumps(result), str(result.get("image_path", "")), all([i < 240 for i in result["absolute_glucose"]])

    # ----- Batch predict (vectorized & fast) -----
    async def predict_many(self, payloads: List[Mapping[str, Any]]) -> str:
        """
        Returns JSON string with {"items":[...]}.
        For each item, will save PNG/JSON to disk by default (image_path/json_path per item).
        """
        await asyncio.sleep(0)
        if not isinstance(payloads, list):
            raise TypeError("payloads must be a list of dicts")
        if not payloads:
            return json.dumps({"items": []})

        dfs, baselines, plots, csv_flags = [], [], [], []
        for p in payloads:
            df = self._payload_to_df(p)
            dfs.append(df)
            baselines.append(float(df.loc[0, "baseline_avg_glucose"]))
            plots.append(bool(p.get("return_plot", False)))
            csv_flags.append(bool(p.get("return_csv", False)))

        X = pd.concat(dfs, axis=0, ignore_index=True)
        try:
            Y = self._model.predict(X)
            Y = np.asarray(Y, dtype=float)
        except Exception as e:
            raise RuntimeError(f"Batch prediction failed: {e}") from e

        if Y.shape[1] != 120:
            raise RuntimeError(f"Model returned {Y.shape[1]} outputs; expected 120.")

        minutes = np.arange(1, 121, dtype=int)
        items = []
        stamp_all = _ts()

        for i, base in enumerate(baselines):
            y_delta = Y[i]
            y_abs = base + y_delta
            inputs_used = json.loads(dfs[i].iloc[0].to_json())
            meal_name = inputs_used.get("meal_bucket", "meal")
            stamp = f"{stamp_all}_{i}"

            item = {
                "minutes": minutes.tolist(),
                "delta_glucose": y_delta.tolist(),
                "absolute_glucose": y_abs.tolist(),
                "inputs_used": inputs_used,
            }

            if self.save_plot:
                png_path = self.output_dir / f"{meal_name}_{stamp}.png"
                _save_plot_png(png_path, minutes, y_abs, y_delta)
                item["image_path"] = str(png_path.resolve())

            if plots[i]:
                item["png_base64"] = _build_plot_base64(minutes, y_abs, y_delta)

            if csv_flags[i]:
                csv_text = _build_csv(dfs[i].iloc[0], minutes, y_delta, y_abs)
                item["csv"] = csv_text
                item["csv_base64"] = base64.b64encode(csv_text.encode("utf-8")).decode("utf-8")
                item["csv_filename"] = f"glucose_curve_{meal_name}_{i}.csv"

            if self.save_json:
                json_path = self.output_dir / f"{meal_name}_{stamp}.json"
                json_path.write_text(json.dumps(item, indent=2), encoding="utf-8")
                item["json_path"] = str(json_path.resolve())

            items.append(item)

        return json.dumps({"items": items})
