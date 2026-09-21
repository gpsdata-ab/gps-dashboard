"""Helpers for normalising GPS metrics and calculating positional baselines."""

import pandas as pd


def normalize_to_75_min(metric_value: float, minutes_played: float) -> float:
    """Scale a metric to a 75-minute equivalent when appropriate."""
    if 0 < minutes_played < 75:
        return (metric_value / minutes_played) * 75
    if minutes_played >= 75:
        return metric_value
    return 0.0


def get_positional_average(
    df: pd.DataFrame,
    metric_column: str,
    position: str,
    min_minutes: int = 75,
) -> float:
    """Return the mean metric value for qualifying players in a position.

    The input metric is expected to already be on the desired scale.  Rows
    without a usable metric value are excluded from the average.
    """
    minutes_column = (
        "minutes_played" if "minutes_played" in df.columns else "time"
    )
    required_columns = {"position", minutes_column, metric_column}
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise KeyError(f"Missing required column(s): {missing}")

    values = df.loc[
        (df["position"] == position) & (df[minutes_column] >= min_minutes),
        metric_column,
    ].dropna()
    if values.empty:
        return 0.0
    return float(values.mean())