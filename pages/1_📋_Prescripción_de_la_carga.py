"""Bloque A: prescription of the training load relative to match demands.

Every session target is expressed as a percentage of the player's match
reference (MD = 100%), never as a share of a weekly total.
"""

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from config import (
    LAYOUT,
    PAGE_ICON,
    PAGE_TITLE,
    REFERENCIA_MINUTOS,
    REFERENCIA_MINUTOS_MINIMOS,
    REFERENCIA_PICO_ANTIGUO_DIAS,
    REFERENCIA_ULTIMOS_PARTIDOS,
    REFERENCIA_VIDA_MEDIA_DIAS,
)
from utils import filtrar_solo_partidos, render_sidebar
from utils import manual_references as manual_store
from utils.reference_engine import (
    REFERENCE_COLUMNS,
    aggregate_actual_loads,
    calculate_references,
    get_microcycle_structure,
    keep_total_rows,
    map_microcycle_dates,
)


METRIC_OPTIONS = {
    "Distancia HSR": "hsr",
    "Distancia sprint": "distance_vrange6",
    "HMLD": "hmld",
    "Max speed": "max_speed",
}
STATISTIC_OPTIONS = {
    "Pico máximo": "max",
    f"Promedio (últimos {REFERENCIA_ULTIMOS_PARTIDOS} partidos)": "last_n",
    "Promedio (todos los partidos)": "mean",
    "Percentil 70 (más peso a lo reciente)": "p70",
}
LOAD_VALUES = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3]

# Default session targets as % of the match reference. Orientative values
# for a one-match week; the staff adjusts them in the page.
DEFAULT_MATCH_PCT_VOLUME = {
    "MD-6": 20, "MD-5": 40, "MD-4": 30, "MD-3": 65,
    "MD-2": 30, "MD-1": 15, "MD+1": 20,
}
DEFAULT_MATCH_PCT_PEAK = {
    "MD-6": 85, "MD-5": 85, "MD-4": 85, "MD-3": 90,
    "MD-2": 95, "MD-1": 85, "MD+1": 0,
}
MAX_MATCH_PCT_VOLUME = 150
MAX_MATCH_PCT_PEAK = 110


st.set_page_config(
    page_title=f"{PAGE_TITLE} - Prescripción",
    page_icon=PAGE_ICON,
    layout=LAYOUT,
    initial_sidebar_state="collapsed",
)


def inject_styles() -> None:
    """Apply the compact dashboard styling used by this page."""
    st.markdown(
        """
        <style>
        .prescription-hero {
            padding: 1.3rem 1.5rem;
            border-radius: 18px;
            background: linear-gradient(135deg, #102a43, #1f4e79);
            color: white;
            margin-bottom: 1rem;
        }
        .prescription-hero h1 { margin: 0; }
        .prescription-hero p { margin: .35rem 0 0; opacity: .82; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_match_pct_controls(sessions: list[str], is_peak: bool) -> dict[str, int]:
    """Render one '% of match' input per session and return current values."""
    defaults = DEFAULT_MATCH_PCT_PEAK if is_peak else DEFAULT_MATCH_PCT_VOLUME
    max_pct = MAX_MATCH_PCT_PEAK if is_peak else MAX_MATCH_PCT_VOLUME
    mode = "peak" if is_peak else "volume"
    session_key = "_".join(sessions)
    values: dict[str, int] = {}
    for column, session in zip(st.columns(len(sessions)), sessions):
        with column:
            values[session] = st.number_input(
                f"{session} (% partido)",
                min_value=0,
                max_value=max_pct,
                value=int(defaults.get(session, 0)),
                step=5,
                key=f"prescription_match_pct_{mode}_{session_key}_{session}",
                help=(
                    "Objetivo de la sesión como % de la referencia de partido "
                    "del jugador (partido = 100%)."
                ),
            )
    st.caption(
        "Cada sesión se prescribe en relación al partido (100%), "
        "no como reparto de un total semanal."
    )
    return values


def _reference_frame(
    df: pd.DataFrame,
    metric_column: str,
    statistic: str,
    match_date: date,
) -> pd.DataFrame:
    """Calculate player references from full-match records only.

    Each player-match counts once: the 'Total' row is used, and halves are
    only added up when a match has no 'Total' row for that player. Every
    match played up to ``match_date`` is used.
    """
    empty = pd.DataFrame(columns=REFERENCE_COLUMNS)
    source = filtrar_solo_partidos(df)
    is_peak = metric_column == "max_speed"
    required = {"player", "position", "date", metric_column}
    if not is_peak and not {"minutes_played", "time"}.intersection(source.columns):
        return empty
    if not required.issubset(source.columns):
        return empty
    source = keep_total_rows(source)
    minute_columns = [
        column for column in ("time", "minutes_played") if column in source.columns
    ]
    for column in [*minute_columns, metric_column]:
        source[column] = pd.to_numeric(source[column], errors="coerce")
    source = source[source["player"].notna()].copy()
    source = source[source["player"].astype(str).str.strip().ne("")]
    source["date"] = pd.to_datetime(
        source["date"], errors="coerce", format="mixed"
    ).dt.date
    # One row per player and match (halves summed only when 'Total' is missing).
    source = source.groupby(["player", "date"], as_index=False).agg(
        {
            metric_column: "max" if is_peak else "sum",
            "position": "first",
            **({"session": "first"} if "session" in source.columns else {}),
            **{column: "sum" for column in minute_columns},
        }
    )
    # Every squad player in the GPS data is listed, so players without
    # valid matches still get a (positional) reference.
    squad = df[["player", "position"]].dropna(subset=["player"]).drop_duplicates("player")
    return calculate_references(
        source,
        metric_column,
        statistic,
        is_peak_metric=is_peak,
        reference_date=match_date,
        players=squad,
    )


def _reference_rules_caption(is_peak: bool) -> str:
    """Plain-language description of how the match reference is built."""
    if is_peak:
        minutes_rule = "Max speed usa todos los partidos, sin escalar."
    else:
        minutes_rule = (
            f"Solo cuentan partidos con al menos {REFERENCIA_MINUTOS_MINIMOS}'; "
            f"los de {REFERENCIA_MINUTOS_MINIMOS}'–{REFERENCIA_MINUTOS}' se llevan a "
            f"{REFERENCIA_MINUTOS}' y los más largos no se reducen."
        )
    return (
        "Referencia de partido: todos los partidos (liga y amistosos) hasta la fecha MD. "
        f"{minutes_rule} Pico máximo = mejor partido "
        f"(⚠️ si tiene más de {REFERENCIA_PICO_ANTIGUO_DIAS} días). "
        f"Percentil 70: un partido de hace {REFERENCIA_VIDA_MEDIA_DIAS} días cuenta la mitad. "
        "Sin partidos válidos → media de su posición. ✏️ = referencia manual."
    )


MANUAL_TABLE_STATE = "prescription_manual_table"
MANUAL_ERROR_STATE = "prescription_manual_error"


def _manual_table() -> pd.DataFrame:
    """Saved manual references, read from Google Drive once per app session."""
    if MANUAL_TABLE_STATE not in st.session_state:
        try:
            st.session_state[MANUAL_TABLE_STATE] = manual_store.load_table()
            st.session_state.pop(MANUAL_ERROR_STATE, None)
        except manual_store.ManualReferencesError as error:
            st.session_state[MANUAL_TABLE_STATE] = manual_store.empty_table()
            st.session_state[MANUAL_ERROR_STATE] = str(error)
    return st.session_state[MANUAL_TABLE_STATE]


def _changed_values(
    saved: dict[str, dict], players: pd.Series, values: pd.Series
) -> dict[str, float | None]:
    """Players whose manual value was typed, changed or deleted."""
    changes: dict[str, float | None] = {}
    for player, value in zip(players, values):
        new = float(value) if pd.notna(value) else None
        old = saved.get(player, {}).get("valor")
        if (old is None) != (new is None) or (new is not None and abs(old - new) > 1e-9):
            changes[player] = new
    return changes


def render_manual_references(
    references: pd.DataFrame, metric_column: str, unit: str
) -> dict[str, dict]:
    """Table to type a player's match reference by hand.

    Values are saved automatically in Google Drive (one per player and
    metric) and shared by the whole staff.
    """
    saved = manual_store.values_for_metric(_manual_table(), metric_column)
    manual_column = f"Referencia manual ({unit})"
    calculated_column = f"Referencia calculada ({unit})"
    title = "✏️ Ajuste manual de referencia"
    with st.expander(f"{title} ({len(saved)} activos)" if saved else title):
        st.caption(
            "Para nuevas incorporaciones, Return to Play o casos especiales. "
            "Escribe la referencia de partido del jugador; borra la celda para volver "
            "a la calculada. Se guarda automáticamente en Google Drive "
            f"(europa/{manual_store.FOLDER_NAME}) y la ve todo el staff."
        )
        if st.session_state.get(MANUAL_ERROR_STATE):
            st.warning(
                f"⚠️ {st.session_state[MANUAL_ERROR_STATE]} Mientras tanto, los valores "
                "manuales solo se mantienen mientras la app esté abierta."
            )
        table = pd.DataFrame(
            {
                "Player": references["player"],
                "Position": references["position"],
                calculated_column: pd.to_numeric(
                    references["baseline_target"], errors="coerce"
                ).round(2),
                manual_column: references["player"]
                .map(lambda player: saved.get(player, {}).get("valor"))
                .astype(float),
                "Guardado": references["player"].map(
                    lambda player: f"{saved[player]['fecha']} · {saved[player]['usuario']}"
                    if player in saved
                    else ""
                ),
            }
        )
        edited = st.data_editor(
            table,
            hide_index=True,
            use_container_width=True,
            disabled=["Player", "Position", calculated_column, "Guardado"],
            column_config={
                manual_column: st.column_config.NumberColumn(min_value=0, step=1, format="%.2f"),
            },
            key=f"prescription_manual_references_{metric_column}",
        )

    changes = _changed_values(saved, edited["Player"], edited[manual_column])
    if changes:
        user = st.session_state.get("usuario") or st.session_state.get("usuario_login") or "staff"
        try:
            st.session_state[MANUAL_TABLE_STATE] = manual_store.save_changes(
                metric_column, changes, user
            )
            st.session_state.pop(MANUAL_ERROR_STATE, None)
            st.toast("✏️ Referencia manual guardada en Drive")
        except manual_store.ManualReferencesError as error:
            # Keep the change for this session so the work is not lost.
            st.session_state[MANUAL_TABLE_STATE] = manual_store.apply_changes(
                _manual_table(), metric_column, changes, user
            )
            st.session_state[MANUAL_ERROR_STATE] = f"No se pudo guardar en Drive: {error}"
            st.error(f"❌ {st.session_state[MANUAL_ERROR_STATE]}")
        saved = manual_store.values_for_metric(st.session_state[MANUAL_TABLE_STATE], metric_column)
    return saved


def apply_manual_references(
    references: pd.DataFrame, manual_references: dict[str, dict]
) -> pd.DataFrame:
    """Replace calculated references with the values typed by the staff."""
    if not manual_references or references.empty:
        return references
    references = references.copy()
    for index, player in references["player"].items():
        if player in manual_references:
            entry = manual_references[player]
            calculated = references.at[index, "baseline_target"]
            references.at[index, "baseline_target"] = entry["valor"]
            references.at[index, "source"] = "manual"
            who = " · ".join(part for part in (entry.get("fecha"), entry.get("usuario")) if part)
            label = f"✏️ Manual · {who}" if who else "✏️ Manual"
            references.at[index, "origin"] = (
                f"{label} (calculada: {calculated:.0f})" if pd.notna(calculated) else label
            )
    return references


def _metric_unit(metric_label: str) -> str:
    return "km/h" if metric_label == "Max speed" else "m"


def _status(compliance_pct: float) -> tuple[str, str]:
    """Traffic-light label and icon for a session compliance percentage."""
    if compliance_pct < 90:
        return "Subóptimo", "🟡"
    if compliance_pct <= 110:
        return "Óptimo", "🟢"
    return "Sobre-óptimo", "🔴"


def _format_load(value: float, unit: str) -> str:
    return f"{value:.1f} {unit}" if unit == "km/h" else f"{value:.0f} {unit}"


def _semaforo_cell(prescribed: float, actual: float, unit: str) -> str:
    """'🟢 95% · 612 m': compliance vs. the session target and the real GPS load."""
    if pd.isna(actual):
        return "⚪ Sin datos"
    real = _format_load(actual, unit)
    if pd.isna(prescribed) or prescribed <= 0:
        return f"— {real}"
    compliance = actual / prescribed * 100
    return f"{_status(compliance)[1]} {compliance:.0f}% · {real}"


def main() -> None:
    if not st.session_state.get("autenticado", False):
        st.warning("⚠️ Por favor, inicia sesión desde la página principal")
        st.stop()

    render_sidebar()
    inject_styles()
    st.markdown(
        '<div class="prescription-hero"><h1>📋 Prescripción de la carga</h1>'
        "<p>Bloque A · Carga de cada sesión en relación a la exigencia del partido</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    df = st.session_state.get("df_procesado")
    latest_match_date = None
    if isinstance(df, pd.DataFrame) and "date" in df.columns:
        match_rows = filtrar_solo_partidos(df)
        parsed_dates = pd.to_datetime(match_rows["date"], errors="coerce").dropna()
        if not parsed_dates.empty:
            latest_match_date = parsed_dates.max().date()
    default_match_date = latest_match_date or date.today()

    st.subheader("Configuración del microciclo")
    control_columns = st.columns(5)
    with control_columns[0]:
        num_sessions = st.selectbox(
            "Microciclo",
            options=[6, 5, 4, 3, 2],
            index=2,
            key="prescription_microcycle",
        )
    with control_columns[1]:
        metric_label = st.selectbox(
            "Métrica",
            options=list(METRIC_OPTIONS),
            key="prescription_metric",
        )

    is_max_speed = metric_label == "Max speed"

    with control_columns[2]:
        if is_max_speed:
            statistic_label = st.selectbox(
                "Referencia de partido",
                options=["Pico máximo"],
                disabled=True,
                key="prescription_statistic_max_speed",
                help="Max speed requiere utilizar el estadístico de Pico máximo exclusivamente.",
            )
        else:
            statistic_label = st.selectbox(
                "Referencia de partido",
                options=list(STATISTIC_OPTIONS),
                key="prescription_statistic",
                help="Estadístico de los partidos del jugador que define el 100%.",
            )

    with control_columns[3]:
        match_date = st.date_input(
            "Fecha del partido (MD)",
            value=default_match_date,
            key="prescription_match_date",
            help="Las sesiones se sitúan respecto al partido: MD-k = k días antes, MD+1 = día siguiente.",
        )
    with control_columns[4]:
        load_multiplier = st.selectbox(
            "Valor de carga",
            options=LOAD_VALUES,
            index=2,
            format_func=lambda value: f"{value:.1f}",
            key="prescription_load_multiplier",
            help="Ajuste global sobre la referencia de partido (1.0 = partido).",
        )

    sessions = get_microcycle_structure(num_sessions)
    session_dates = map_microcycle_dates(match_date, sessions)
    st.caption(
        "Calendario: "
        + " · ".join(
            f"{session}: {session_dates[session].strftime('%d/%m/%Y')}"
            for session in sessions
        )
        + f" · Partido: {pd.Timestamp(match_date).strftime('%d/%m/%Y')}"
    )

    has_data = isinstance(df, pd.DataFrame) and not df.empty

    st.subheader("Carga de cada sesión respecto al partido")
    match_pct = render_match_pct_controls(sessions, is_peak=is_max_speed)

    metric_column = METRIC_OPTIONS[metric_label]
    unit = _metric_unit(metric_label)
    if not has_data:
        st.info("Carga los datos GPS desde la página principal para calcular las referencias.")
        references = pd.DataFrame(columns=REFERENCE_COLUMNS)
    else:
        references = _reference_frame(
            df, metric_column, STATISTIC_OPTIONS[statistic_label], match_date
        )
        if references.empty:
            st.warning(
                f"No hay partidos con la métrica '{metric_column}' hasta el "
                f"{pd.Timestamp(match_date).strftime('%d/%m/%Y')}."
            )
    st.subheader("Editor de prescripción individual")
    st.caption(
        f"Objetivo por sesión en {unit}. Edita cualquier celda para adaptar la carga "
        "a casos de Return to Play y fatiga."
    )
    st.caption(_reference_rules_caption(is_max_speed))
    manual_references = render_manual_references(references, metric_column, unit)
    references = apply_manual_references(references, manual_references)

    reference_column = f"Referencia partido ({unit})"
    origin_column = "Origen de la referencia"
    target_column = f"Objetivo partido ({unit})"

    editor_rows = []
    for _, reference in references.iterrows():
        match_reference = float(reference["baseline_target"])
        match_target = match_reference * float(load_multiplier)
        row = {
            "Player": reference["player"],
            "Position": reference["position"],
            reference_column: round(match_reference, 2),
            origin_column: reference["origin"],
            target_column: round(match_target, 2),
        }
        for session in sessions:
            row[session] = round(match_target * match_pct[session] / 100, 2)
        editor_rows.append(row)
    editor_data = pd.DataFrame(
        editor_rows,
        columns=[
            "Player", "Position", reference_column, origin_column, target_column, *sessions,
        ],
    )

    # The key includes every input that changes the base values, so manual
    # edits never get re-applied on top of a different metric or reference.
    editor_key = "_".join(
        [
            "prescription_editor",
            metric_column,
            STATISTIC_OPTIONS.get(statistic_label, "max"),
            f"{load_multiplier:.1f}",
            str(match_date),
            str(hash(tuple(sorted(
                (player, entry["valor"]) for player, entry in manual_references.items()
            )))),
            *(f"{session}{match_pct[session]}" for session in sessions),
        ]
    )
    edited = st.data_editor(
        editor_data,
        hide_index=True,
        use_container_width=True,
        disabled=["Player", "Position", reference_column, origin_column, target_column],
        column_config={
            **{
                session: st.column_config.NumberColumn(
                    f"{session} ({match_pct[session]}%)",
                    min_value=0,
                    step=1,
                    format="%.2f",
                )
                for session in sessions
            },
        },
        key=editor_key,
    )

    if edited.empty:
        st.info("No hay jugadores disponibles para mostrar el cumplimiento.")
        return

    actual_loads = aggregate_actual_loads(
        df if isinstance(df, pd.DataFrame) else pd.DataFrame(),
        edited["Player"],
        metric_column,
        session_dates,
        missing_value=float("nan"),
    ).set_index("player")
    actual = pd.DataFrame(
        {
            session: edited["Player"].map(actual_loads[f"Actual {session}"])
            for session in sessions
        }
    )
    prescribed = edited[sessions].astype(float)

    st.subheader("Semáforo de cumplimiento por sesión")
    st.caption(
        f"% = carga real GPS / objetivo prescrito de la sesión, seguido de la carga real en {unit}. "
        "🟢 90–110% · 🟡 < 90% · 🔴 > 110% · ⚪ sin registro GPS ese día · — sin objetivo."
    )
    semaforo = pd.DataFrame({"Player": edited["Player"]})
    for session in sessions:
        semaforo[f"{session} ({session_dates[session]:%d/%m})"] = [
            _semaforo_cell(p, a, unit) for p, a in zip(prescribed[session], actual[session])
        ]
    st.dataframe(semaforo, hide_index=True, use_container_width=True)


if __name__ == "__main__":
    main()
