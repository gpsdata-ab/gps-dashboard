"""Reference and microcycle calculations for GPS workloads."""

from collections.abc import Callable
from datetime import date, datetime, timedelta

import pandas as pd

from .normalization import get_positional_average, normalize_to_75_min


def get_microcycle_structure(num_sessions: int) -> list[str]:
    """Return the standard match-day labels for a microcycle length.

    MD+1 is placed at the end of the sequence.
    Example for 4 sessions: ['MD-4', 'MD-3', 'MD-2', 'MD-1', 'MD+1']
    """
    if num_sessions < 1:
        return []
    return [f"MD-{i}" for i in range(num_sessions, 0, -1)] + ["MD+1"]


def map_microcycle_dates(
    start_date: date | datetime | str,
    sessions: list[str],
) -> dict[str, date]:
    """Map sessions to consecutive calendar dates starting at MD-N and ending at MD+1."""
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

    for session in session_dates:
        result[f"Actual {session}"] = 0.0

    if "player" not in df.columns or "date" not in df.columns or metric not in df.columns:
        return result

    source = df[["player", "date", metric]].copy()
    source["date"] = pd.to_datetime(
        source["date"], errors="coerce", format="mixed"
    ).dt.date
    source[metric] = pd.to_numeric(source[metric], errors="coerce").fillna(0.0)
    source = source[source["player"].notna()]

    for session, session_date in session_dates.items():
        matching = source[source["date"] == session_date]
        # For max_speed take the maximum value in that day instead of sum
        if metric == "max_speed":
            totals = matching.groupby("player", dropna=False)[metric].max()
        else:
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
    is_peak_metric: bool = False,
) -> pd.DataFrame:
    """Calculate one baseline target per player.

    Volume metrics are normalized to a 75-minute equivalent. Peak metrics (e.g., max_speed)
    are taken as raw unscaled values without minute normalization.
    """
    is_peak = is_peak_metric or metric == "max_speed"
    minutes_column = "minutes_played" if "minutes_played" in df.columns else "time"
    required_columns = {"player", "position", metric}
    if not is_peak:
        required_columns.add(minutes_column)
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise KeyError(f"Missing required column(s): {missing}")

    statistic = _get_statistic(stat_type)
    working_columns = ["player", "position", metric]
    if minutes_column in df.columns:
        working_columns.append(minutes_column)
    working = df[working_columns].copy()

    if is_peak:
        working["_normalized_metric"] = pd.to_numeric(working[metric], errors="coerce")
    else:
        working[minutes_column] = pd.to_numeric(
            working[minutes_column], errors="coerce"
        )
        metric_values = pd.to_numeric(working[metric], errors="coerce")
        working["_normalized_metric"] = [
            normalize_to_75_min(value, minutes)
            if pd.notna(value) and pd.notna(minutes)
            else float("nan")
            for value, minutes in zip(metric_values, working[minutes_column])
        ]

    if is_peak:
        positional_averages = (
            working.groupby("position")["_normalized_metric"]
            .mean()
            .to_dict()
        )
    else:
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
        position = (
            player_rows["position"].dropna().iloc[0]
            if player_rows["position"].notna().any()
            else None
        )
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