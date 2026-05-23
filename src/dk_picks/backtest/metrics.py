import pandas as pd
from sqlalchemy import select

from dk_picks.db.models import PickLog
from dk_picks.db.session import get_session


def pick_performance() -> pd.DataFrame:
    session = get_session()
    try:
        rows = session.execute(select(PickLog)).scalars().all()
    finally:
        session.close()

    if not rows:
        return pd.DataFrame()

    data = [
        {
            "id": r.id,
            "is_parlay": r.is_parlay,
            "model_prob": r.model_prob,
            "edge": r.edge,
            "stake": r.stake,
            "result": r.result,
            "clv": r.clv,
        }
        for r in rows
        if r.result in ("win", "loss", "push")
    ]
    df = pd.DataFrame(data)
    if df.empty:
        return df

    df["won"] = (df["result"] == "win").astype(int)
    df["pnl"] = df.apply(
        lambda r: r["stake"] if r["won"] else -r["stake"],
        axis=1,
    )
    return df


def calibration_report() -> dict:
    df = pick_performance()
    if df.empty or len(df) < 10:
        return {"message": "Log at least 10 settled picks for calibration report"}

    df["bucket"] = pd.cut(df["model_prob"], bins=[0, 0.5, 0.55, 0.6, 0.65, 1.0])
    grouped = df.groupby("bucket", observed=True).agg(
        n=("won", "count"),
        predicted=("model_prob", "mean"),
        actual=("won", "mean"),
    )
    brier = ((df["model_prob"] - df["won"]) ** 2).mean()
    roi = df["pnl"].sum() / df["stake"].sum() if df["stake"].sum() else 0

    return {
        "brier_score": float(brier),
        "roi": float(roi),
        "hit_rate": float(df["won"].mean()),
        "n_picks": int(len(df)),
        "by_bucket": grouped.reset_index().to_dict(orient="records"),
    }
