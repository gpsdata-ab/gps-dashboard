"""Reference and microcycle calculations for GPS workloads."""

from collections.abc import Callable

import pandas as pd

from .normalization import get_positional_average, normalize_to_75_min


def get_microcycle_structure(num_sessions: int) -> list[str]:
    """Return the standard match-day labels for a microcycle length."""
    structures = {
        6: ["MD+1", "MD-5", "MD-4", "MD-3", "MD-2", "MD-1"],
        5: ["MD+1", "MD-4", "MD-3", "MD-2", "MD-1"],
        4: ["MD+1", "MD-3", "MD-2", "MD-1"],
        3: ["MD+1", "MD-2", "MD-1"],
        2: ["MD+1", "MD-1"],
    }
    return structures.get(num_sessions, []).copy()


def _get_statistic(stat_type: str) -> Callable[[pd.Series], float]:
    """Resolve the supported baseline statistic names."""
    normalized_stat_type = stat_type.strip().lower()
    statistics: dict[str, Callable[[pd.Series], float]] = {
        "mean": lambda values: float(values.mean()),
        "average": lambda values: float(values.mean()),
        "median": lambda values: float(values.median()),
        "min": lambda values: float(values.min()),
        "max": lambda values: float(values.max()),
        "p70": lambda values: float(values.quantile(0.70)),
        "p75": lambda values: float(values.quantile(0.75)),
        "p90": lambda values: float(values.quantile(0.90)),
        "p95": lambda values: float(values.quantile(0.95)),
    }
    try:
        return statistics[normalized_stat_type]
    except KeyError as error:
        supported = ", ".join(sorted(statistics))
        raise ValueError(
            f"Unsupported stat_type {stat_type!r}; expected one of: {supported}"
        ) from error


def calculate_references(
    df: pd.DataFrame,
    metric: str,
    stat_type: str,
) -> pd.DataFrame:
    """Calculate one normalized baseline target per player.

    Values are normalized to a 75-minute equivalent before aggregation.  A
    player's missing metric values are imputed with the positional average
    calculated from rows with at least 75 minutes.  The returned frame has
    ``player``, ``position`` and ``baseline_target`` columns.
    """
    minutes_column = (
        "minutes_played" if "minutes_played" in df.columns else "time"
    )
    required_columns = {"player", "position", minutes_column, metric}
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise KeyError(f"Missing required column(s): {missing}")

    statistic = _get_statistic(stat_type)
    working = df[["player", "position", minutes_column, metric]].copy()
    working["_normalized_metric"] = [
        normalize_to_75_min(value, minutes)
        if pd.notna(value) and pd.notna(minutes)
        else float("nan")
        for value, minutes in zip(working[metric], working[minutes_column])
    ]

    positional_averages = {
        position: get_positional_average(
            working,
            "_normalized_metric",
            position,
        )
        for position in working["position"].dropna().unique()
    }

    targets = []
    for player, player_rows in working.groupby("player", dropna=False, sort=False):
        position = player_rows["position"].dropna().iloc[0] if player_rows["position"].notna().any() else None
        values = player_rows["_normalized_metric"].dropna()
        if values.empty:
            values = pd.Series([positional_averages.get(position, 0.0)])
        targets.append(
            {
                "player": player,
                "position": position,
                "baseline_target": statistic(values),
            }
        )

    return pd.DataFrame(targets, columns=["player", "position", "baseline_target"])