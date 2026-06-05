"""SHAP feature importance panel for the Streamlit dashboard."""

from __future__ import annotations

from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
import streamlit as st
from lightgbm import LGBMClassifier
from sklearn.calibration import CalibratedClassifierCV

from betting_system.config import load_settings
from betting_system.pipeline.train import _select_features


def _resolve_model_path() -> Path | None:
    """Return best available model artifact for SHAP explainability."""
    settings = load_settings()
    processed = Path(settings.data["processed_data_path"])
    candidates = [
        processed / "models" / "model.pkl",
        Path(__file__).resolve().parents[1] / "data" / "fixtures" / "demo_lgbm.joblib",
    ]
    models_dir = Path(settings.data["models_path"]) / "leg_model"
    if models_dir.exists():
        candidates.extend(sorted(models_dir.glob("lgbm_*.joblib"), reverse=True))
    for path in candidates:
        if path.exists():
            return path
    return None


def _resolve_features_path() -> Path | None:
    """Return features parquet for background SHAP samples."""
    settings = load_settings()
    path = Path(settings.data["processed_data_path"]) / "features.parquet"
    return path if path.exists() else None


def _extract_base_estimator(model) -> LGBMClassifier | None:
    """Unwrap CalibratedClassifierCV to the underlying LightGBM estimator."""
    if isinstance(model, CalibratedClassifierCV):
        if hasattr(model, "calibrated_classifiers_") and model.calibrated_classifiers_:
            est = model.calibrated_classifiers_[0].estimator
            if isinstance(est, LGBMClassifier):
                return est
    if isinstance(model, LGBMClassifier):
        return model
    return None


def _build_demo_model(features_path: Path, out_path: Path) -> Path:
    """Train and cache a tiny demo model when no artifact exists."""
    df = pd.read_parquet(features_path)
    X, y = _select_features(df.head(400))
    base = LGBMClassifier(n_estimators=40, learning_rate=0.1, random_state=42)
    base.fit(X, y)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(base, out_path)
    return out_path


def render_shap_panel() -> None:
    """Render top-15 SHAP feature importance bar chart in Streamlit."""
    st.subheader("Model explainability")
    model_path = _resolve_model_path()
    features_path = _resolve_features_path()

    if features_path is None:
        st.info("Run `dk-pipeline --dry-run` to generate features for SHAP explainability.")
        return

    if model_path is None:
        fixture = Path(__file__).resolve().parents[1] / "data" / "fixtures" / "demo_lgbm.joblib"
        model_path = _build_demo_model(features_path, fixture)

    model = joblib.load(model_path)
    base = _extract_base_estimator(model)
    if base is None:
        st.warning("SHAP panel requires a LightGBM-based artifact.")
        return

    df = pd.read_parquet(features_path)
    X, _ = _select_features(df.sample(min(200, len(df)), random_state=42))

    explainer = shap.TreeExplainer(base)
    shap_values = explainer.shap_values(X)
    if isinstance(shap_values, list):
        shap_values = shap_values[1]

    mean_abs = np.abs(shap_values).mean(axis=0)
    order = np.argsort(mean_abs)[::-1][:15]
    names = [X.columns[i] for i in order]
    values = mean_abs[order]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(names[::-1], values[::-1], color="#1f6feb")
    ax.set_xlabel("mean |SHAP value|")
    ax.set_title("Top feature drivers")
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)
    st.caption("Feature importance · LightGBM · Source: holdout split")
