"""Optional supervised LSTM form features for tabular ensemble."""

from __future__ import annotations

import numpy as np
import pandas as pd

from betting_system.config import load_settings
from betting_system.logging_utils import get_logger


logger = get_logger(__name__)


def _build_sequences(
    df: pd.DataFrame,
    *,
    seq_len: int = 10,
    value_col: str = "actual_value",
) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """Build (n, seq_len) sequences and targets from player stat history."""
    sequences: list[np.ndarray] = []
    targets: list[float] = []
    row_indices: list[int] = []

    work = df.sort_values(["player_id", "stat_type", "game_date"]).copy()
    for (_, _), grp in work.groupby(["player_id", "stat_type"], sort=False):
        vals = grp[value_col].astype(float).tolist()
        idxs = grp.index.tolist()
        for i in range(seq_len, len(vals)):
            sequences.append(np.array(vals[i - seq_len : i], dtype=np.float32))
            targets.append(float(vals[i]))
            row_indices.append(idxs[i])

    if not sequences:
        return np.empty((0, seq_len), dtype=np.float32), np.array([]), []

    return np.stack(sequences), np.array(targets, dtype=np.float32), row_indices


def train_lstm_form_features(
    stat_df: pd.DataFrame,
    *,
    seq_len: int | None = None,
    embedding_dim: int | None = None,
) -> dict:
    """Train a small LSTM and return form feature arrays keyed by row index.

    Disabled when config sequence.enabled is False. Uses PyTorch if available.
    """
    settings = load_settings()
    seq_cfg = settings.raw.get("sequence", {})
    if not seq_cfg.get("enabled", False):
        logger.info("LSTM form features disabled in config")
        return {}

    seq_len = int(seq_len or seq_cfg.get("seq_len", 10))
    embedding_dim = int(embedding_dim or seq_cfg.get("embedding_dim", 4))

    try:
        import torch
        import torch.nn as nn
    except ImportError:
        logger.warning("PyTorch not installed; skipping LSTM form features")
        return {}

    X, y, row_indices = _build_sequences(stat_df, seq_len=seq_len)
    if len(X) < 20:
        logger.warning("Not enough sequences for LSTM (%d)", len(X))
        return {}

    class FormLSTM(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.lstm = nn.LSTM(1, embedding_dim, batch_first=True)
            self.head = nn.Linear(embedding_dim, 1)

        def forward(self, x):
            out, (h, _) = self.lstm(x.unsqueeze(-1))
            return self.head(h[-1]).squeeze(-1)

    model = FormLSTM()
    opt = torch.optim.Adam(model.parameters(), lr=0.01)
    loss_fn = nn.MSELoss()
    xt = torch.tensor(X)
    yt = torch.tensor(y)

    model.train()
    for _ in range(int(seq_cfg.get("epochs", 15))):
        opt.zero_grad()
        pred = model(xt)
        loss = loss_fn(pred, yt)
        loss.backward()
        opt.step()

    model.eval()
    with torch.no_grad():
        preds = model(xt).numpy()
        _, (h, _) = model.lstm(xt.unsqueeze(-1))
        embeddings = h[-1].numpy()

    features: dict[int, dict] = {}
    for i, idx in enumerate(row_indices):
        emb = embeddings[i]
        features[idx] = {
            "lstm_pred_actual_value": float(preds[i]),
            "lstm_uncertainty": float(abs(preds[i] - y[i])),
            **{f"lstm_form_embedding_{j}": float(emb[j]) for j in range(embedding_dim)},
        }
    return features


def apply_lstm_features_to_frame(df: pd.DataFrame, lstm_features: dict) -> pd.DataFrame:
    """Merge LSTM form features into a feature dataframe by index."""
    if not lstm_features:
        return df
    out = df.copy()
    for col in ["lstm_pred_actual_value", "lstm_uncertainty"]:
        out[col] = np.nan
    emb_cols = [k for k in next(iter(lstm_features.values())).keys() if k.startswith("lstm_form_embedding_")]
    for col in emb_cols:
        out[col] = np.nan
    for idx, feats in lstm_features.items():
        if idx not in out.index:
            continue
        for k, v in feats.items():
            out.at[idx, k] = v
    out = out.fillna(0.0)
    return out
