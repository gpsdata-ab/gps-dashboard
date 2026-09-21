"""Reference and microcycle calculations for GPS workloads."""

from collections.abc import Callable
from datetime import date, datetime, timedelta

import pandas as pd

from .normalization import get_positional_average, normalize_to_75_min


def get_microcycle_structure(num_sessions: int) -> list[str]:
    """Return the standard match-day labels for a microcycle length."""
    if num_sessions < 1:
        return []
    return ["MD+1"] + [f"MD-{i}" for i in range(num_sessions, 0, -1)]


def map_microcycle_dates(
    start_date: date | datetime | str,
    sessions: list[str],
) -> dict[str, date]:
    """Map sessions to consecutive calendar dates starting at MD+1."""
    selected_date = pd.Timestamp(start_date).date()
    return {
        session: selected_date + timedelta(days=offset)
        for offset, session in enumerate(sessions)
    }


def aggregate_actual_loads(
    df: pd.DataFrame,
    players: pd.Series,
    metric: str,
    session_dates: dict[str, date],
) -> pd.DataFrame:
    """Sum a metric per player for the exact date mapped to each session.

    Missing dates and missing player records are represented by ``0.0``.
    """
    result = pd.DataFrame({"player": players.drop_duplicates().tolist()})
    if result.empty:
        return result

    for session, session_date in session_dates.items():
        result[f"Actual {session}"] = 0.0

    if "player" not in df.columns or "date" not in df.columns or metric not in df.columns:
        return result

    source = df[["player", "date", metric]].copy()
    source["date"] = pd.to_datetime(source["date"], errors="coerce").dt.date
    source[metric] = pd.to_numeric(source[metric], errors="coerce").fillna(0.0)
    source = source[source["player"].notna()]

    for session, session_date in session_dates.items():
        matching = source[source["date"] == session_date]
        totals = matching.groupby("player", dropna=False)[metric].sum()
        result[f"Actual {session}"] = (
            result["player"].map(totals).fillna(0.0).astype(float)
        )
    return result


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