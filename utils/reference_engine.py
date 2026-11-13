"""Reference and microcycle calculations for GPS workloads."""

from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from config import (
    REFERENCIA_MINUTOS,
    REFERENCIA_MINUTOS_MINIMOS,
    REFERENCIA_PICO_ANTIGUO_DIAS,
    REFERENCIA_ULTIMOS_PARTIDOS,
    REFERENCIA_VIDA_MEDIA_DIAS,
)

REFERENCE_COLUMNS = [
    "player", "position", "baseline_target", "source", "origin",
    "n_matches", "peak_date",
]


def get_microcycle_structure(num_sessions: int) -> list[str]:
    """Return the standard match-day labels for a microcycle length.

    MD+1 is placed at the end of the sequence.
    Example for 4 sessions: ['MD-4', 'MD-3', 'MD-2', 'MD-1', 'MD+1']
    """
    if num_sessions < 1:
        return []
    return [f"MD-{i}" for i in range(num_sessions, 0, -1)] + ["MD+1"]


def _match_day_offset(session: str) -> int:
    """Return the day offset encoded in a label: 'MD-3' -> -3, 'MD+1' -> 1."""
    try:
        return int(session.strip().upper().removeprefix("MD"))
    except ValueError as error:
        raise ValueError(f"Invalid match-day label: {session!r}") from error


def map_microcycle_dates(
    match_date: date | datetime | str,
    sessions: list[str],
) -> dict[str, date]:
    """Map each MD±k session to its calendar date relative to the match.

    MD-k is always k days before the match and MD+1 the day after it, so
    rest days inside the microcycle are handled implicitly.
    """
    match_day = pd.Timestamp(match_date).date()
    return {
        session: match_day + timedelta(days=_match_day_offset(session))
        for session in sessions
    }


def keep_total_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Keep each player-day's 'Total' rows and drop the partial rows they include.

    GPS exports repeat the data of a day as partial rows (match halves,
    training drills) plus a 'Total' row with their sum. Player-days that
    have no 'Total' row keep all their rows so nothing is lost.
    """
    if df.empty or not {"player", "date", "task"}.issubset(df.columns):
        return df.copy()
    day = pd.to_datetime(df["date"], errors="coerce", format="mixed").dt.normalize()
    is_total = df["task"].astype(str).str.contains(r"\btotal\b", case=False, regex=True)
    has_total = (
        is_total.groupby([df["player"], day], dropna=False)
        .transform("any")
        .fillna(False)
        .astype(bool)
    )
    return df[is_total | ~has_total].copy()


def aggregate_actual_loads(
    df: pd.DataFrame,
    players: pd.Series,
    metric: str,
    session_dates: dict[str, date],
    missing_value: float = 0.0,
) -> pd.DataFrame:
    """Sum a metric per player for the exact date mapped to each session.

    Players without a record on a session date get ``missing_value``
    (``0.0`` by default; pass ``float("nan")`` to tell "no data" apart
    from a real zero).
    """
    result = pd.DataFrame({"player": players.drop_duplicates().tolist()})
    if result.empty:
        return result

    for session in session_dates:
        result[f"Actual {session}"] = missing_value

    if "player" not in df.columns or "date" not in df.columns or metric not in df.columns:
        return result

    # Count each day once: the 'Total' row already includes its drills.
    source = keep_total_rows(df)[["player", "date", metric]].copy()
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
            result["player"].map(totals).fillna(missing_value).astype(float)
        )
    return result


_QUANTILES = {"median": 0.50, "p70": 0.70, "p75": 0.75, "p90": 0.90, "p95": 0.95}
_STATISTICS = ("max", "min", "mean", "average", "last_n", *_QUANTILES)


def _statistic(
    values: np.ndarray,
    weights: np.ndarray,
    dates: np.ndarray,
    stat_type: str,
    last_n: int,
) -> float:
    """Apply a baseline statistic to one player's match values.

    * 'max' / 'min': all-time extremes of the given matches.
    * 'mean': plain average of the given matches.
    * 'last_n': plain average of the ``last_n`` most recent matches.
    * percentiles ('p70'...): weighted by recency, so recent matches count more.
    """
    stat = stat_type.strip().lower()
    if stat == "max":
        return float(values.max())
    if stat == "min":
        return float(values.min())
    if stat in ("mean", "average"):
        return float(values.mean())
    if stat == "last_n":
        recent = np.argsort(dates, kind="stable")[-last_n:]
        return float(values[recent].mean())
    if stat in _QUANTILES:
        order = np.argsort(values)
        sorted_values, sorted_weights = values[order], weights[order]
        positions = (np.cumsum(sorted_weights) - 0.5 * sorted_weights) / sorted_weights.sum()
        return float(np.interp(_QUANTILES[stat], positions, sorted_values))
    supported = ", ".join(sorted(_STATISTICS))
    raise ValueError(f"Unsupported stat_type {stat_type!r}; expected one of: {supported}")


def _count(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def calculate_references(
    df: pd.DataFrame,
    metric: str,
    stat_type: str,
    is_peak_metric: bool = False,
    reference_date: date | datetime | str | None = None,
    players: pd.DataFrame | None = None,
    reference_minutes: float = REFERENCIA_MINUTOS,
    min_minutes: float = REFERENCIA_MINUTOS_MINIMOS,
    half_life_days: float = REFERENCIA_VIDA_MEDIA_DIAS,
    stale_peak_days: int = REFERENCIA_PICO_ANTIGUO_DIAS,
    last_n: int = REFERENCIA_ULTIMOS_PARTIDOS,
) -> pd.DataFrame:
    """Calculate each player's match reference (match = 100%).

    ``df`` holds one row per player and match (already limited to the
    matches the staff selected). Rules:

    * Only matches up to ``reference_date`` count.
    * Volume metrics: a match of ``reference_minutes`` or more is used as
      it is; one between ``min_minutes`` and ``reference_minutes`` is scaled
      up to ``reference_minutes``; shorter matches are not used. Longer
      matches are never scaled down, because the GPS ``time`` includes the
      whole recording window.
    * Peak metrics (max speed) use every match, unscaled.
    * See ``_statistic`` for each statistic.
    * A player without valid matches gets the average reference of the
      teammates in their position.

    ``players`` (player, position) lists players to include even when they
    have no matches. Returns the columns in ``REFERENCE_COLUMNS``.
    """
    is_peak = is_peak_metric or metric == "max_speed"
    minutes_column = "minutes_played" if "minutes_played" in df.columns else "time"
    required_columns = {"player", "position", "date", metric}
    if not is_peak:
        required_columns.add(minutes_column)
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise KeyError(f"Missing required column(s): {missing}")
    stat = stat_type.strip().lower()
    if stat not in _STATISTICS:
        _statistic(np.array([0.0]), np.array([1.0]), np.array([0]), stat, last_n)  # raises

    working = df.reset_index(drop=True)
    working["_date"] = pd.to_datetime(working["date"], errors="coerce", format="mixed").dt.normalize()
    working["_value"] = pd.to_numeric(working[metric], errors="coerce")
    working["_minutes"] = (
        pd.to_numeric(working[minutes_column], errors="coerce")
        if minutes_column in working.columns
        else np.nan
    )
    working = working[working["player"].notna() & working["_date"].notna() & working["_value"].notna()]

    # Everyone in the input is listed, even if no match passes the filters.
    roster = working[["player", "position"]]
    if players is not None and not players.empty:
        roster = pd.concat([players[["player", "position"]], roster], ignore_index=True)
    roster = (
        roster[roster["player"].notna()]
        .groupby("player", sort=False)["position"]
        .agg(lambda s: s.dropna().iloc[0] if s.notna().any() else None)
    )

    ref_day = (
        pd.Timestamp(reference_date).normalize()
        if reference_date is not None
        else working["_date"].max()
    )
    if pd.notna(ref_day):
        working = working[working["_date"] <= ref_day]
    if not is_peak:
        working = working[working["_minutes"] >= min_minutes]
        scale = (reference_minutes / working["_minutes"]).clip(lower=1.0)
        working["_value"] = working["_value"] * scale
    working["_age_days"] = (ref_day - working["_date"]).dt.days if pd.notna(ref_day) else 0
    working["_weight"] = 0.5 ** (working["_age_days"] / half_life_days)

    rows = []
    for player, position in roster.items():
        player_rows = working[working["player"] == player].sort_values("_date")
        row = {
            "player": player, "position": position, "baseline_target": np.nan,
            "source": "none", "origin": "Sin partidos válidos",
            "n_matches": len(player_rows), "peak_date": pd.NaT,
        }
        if not player_rows.empty:
            row["source"] = "player"
            row["baseline_target"] = _statistic(
                player_rows["_value"].to_numpy(float),
                player_rows["_weight"].to_numpy(float),
                player_rows["_date"].to_numpy(),
                stat,
                last_n,
            )
            last = player_rows["_date"].iloc[-1].strftime("%d/%m/%y")
            if stat == "max":
                best = player_rows.loc[player_rows["_value"].idxmax()]
                row["peak_date"] = best["_date"].date()
                parts = [str(best.get("session", "")).strip(), best["_date"].strftime("%d/%m/%y")]
                if pd.notna(best["_minutes"]):
                    parts.append(f"{best['_minutes']:.0f}'")
                origin = " · ".join(part for part in parts if part and part != "nan")
                if best["_age_days"] > stale_peak_days:
                    origin = f"⚠️ {origin} (hace {best['_age_days']} días)"
                row["origin"] = origin
            elif stat == "last_n":
                used = min(last_n, len(player_rows))
                first = player_rows["_date"].iloc[-used].strftime("%d/%m/%y")
                row["origin"] = (
                    f"Último partido · {last}"
                    if used == 1
                    else f"Últimos {used} partidos · {first} – {last}"
                )
            else:
                row["origin"] = f"{_count(len(player_rows), 'partido', 'partidos')} · último {last}"
        rows.append(row)

    references = pd.DataFrame(rows, columns=REFERENCE_COLUMNS)
    own = references[references["source"] == "player"]
    positional = own.groupby("position")["baseline_target"].agg(["mean", "size"])
    for index in references.index[references["source"] == "none"]:
        position = references.at[index, "position"]
        if position in positional.index:
            average, size = positional.loc[position]
            references.at[index, "baseline_target"] = float(average)
            references.at[index, "source"] = "position"
            references.at[index, "origin"] = (
                f"Media posición: {position} ({_count(int(size), 'jugador', 'jugadores')})"
            )
    return references
