import pandas as pd

from betting_system.pipeline.features import _rolling_features


def test_rolling_features_shift_prevents_leakage():
    df = pd.DataFrame(
        {
            "player_id": ["a"] * 5,
            "stat_type": ["points"] * 5,
            "game_date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]).date,
            "actual_value": [10, 20, 30, 40, 50],
        }
    )
    out = _rolling_features(df, group_cols=["player_id", "stat_type"], value_col="actual_value", windows=[3], ewm_span=5)
    # At index 0, shifted rolling mean should equal NaN -> filled later; here it should be NaN
    assert pd.isna(out.loc[0, "actual_value_roll_mean_3"])
    # At index 1, mean should be previous value (10)
    assert out.loc[1, "actual_value_roll_mean_3"] == 10

