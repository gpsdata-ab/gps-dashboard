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

from config import LAYOUT, PAGE_ICON, PAGE_TITLE
from utils import filtrar_solo_partidos, render_sidebar
from utils.reference_engine import (
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
    "Promedio (últimos 4 partidos)": "mean",
    "Percentil 70": "p70",
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
) -> pd.DataFrame:
    """Calculate player references from full-match records only.

    Each player-match counts once: the 'Total' row is used, and halves are
    only added up when a match has no 'Total' row for that player.
    """
    source = filtrar_solo_partidos(df)
    is_peak = metric_column == "max_speed"
    required = {"player", "position", "date", metric_column}
    if not is_peak and not {"minutes_played", "time"}.intersection(source.columns):
        return pd.DataFrame(columns=["player", "position", "baseline_target"])
    if not required.issubset(source.columns):
        return pd.DataFrame(columns=["player", "position", "baseline_target"])
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
            **{column: "sum" for column in minute_columns},
        }
    )
    if statistic == "mean":
        recent_dates = source["date"].dropna().drop_duplicates()
        recent_dates = sorted(recent_dates, reverse=True)[:4]
        if recent_dates:
            source = source[source["date"].isin(recent_dates)]
    if source.empty:
        return pd.DataFrame(columns=["player", "position", "baseline_target"])

    return calculate_references(source, metric_column, statistic, is_peak_metric=is_peak)


def _metric_unit(metric_label: str) -> str:
    return "km/h" if metric_label == "Max speed" else "m"


def _status(compliance_pct: float) -> tuple[str, str]:
    """Traffic-light label and icon for a session compliance percentage."""
    if compliance_pct < 90:
        return "Subóptimo", "🟡"
    if compliance_pct <= 110:
        return "Óptimo", "🟢"
    return "Sobre-óptimo", "🔴"


def _semaforo_cell(prescribed: float, actual: float) -> str:
    if pd.isna(actual):
        return "⚪ Sin datos"
    if pd.isna(prescribed) or prescribed <= 0:
        return "— Sin objetivo"
    compliance = actual / prescribed * 100
    return f"{_status(compliance)[1]} {compliance:.0f}%"


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

    st.subheader("Carga de cada sesión respecto al partido")
    match_pct = render_match_pct_controls(sessions, is_peak=is_max_speed)

    metric_column = METRIC_OPTIONS[metric_label]
    if not isinstance(df, pd.DataFrame) or df.empty:
        st.info("Carga los datos GPS desde la página principal para calcular las referencias.")
        references = pd.DataFrame(columns=["player", "position", "baseline_target"])
    else:
        references = _reference_frame(
            df, metric_column, STATISTIC_OPTIONS[statistic_label]
        )
        if references.empty:
            st.warning(f"No existe la columna '{metric_column}' en los datos cargados.")

    unit = _metric_unit(metric_label)
    reference_column = f"Referencia partido ({unit})"
    target_column = f"Objetivo partido ({unit})"

    editor_rows = []
    for _, reference in references.iterrows():
        match_reference = float(reference["baseline_target"])
        match_target = match_reference * float(load_multiplier)
        row = {
            "Player": reference["player"],
            "Position": reference["position"],
            reference_column: round(match_reference, 2),
            target_column: round(match_target, 2),
        }
        for session in sessions:
            row[session] = round(match_target * match_pct[session] / 100, 2)
        editor_rows.append(row)
    editor_data = pd.DataFrame(
        editor_rows,
        columns=["Player", "Position", reference_column, target_column, *sessions],
    )

    st.subheader("Editor de prescripción individual")
    st.caption(
        f"Objetivo por sesión en {unit}. Edita cualquier celda para adaptar la carga "
        "a casos de Return to Play y fatiga."
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
            *(f"{session}{match_pct[session]}" for session in sessions),
        ]
    )
    edited = st.data_editor(
        editor_data,
        hide_index=True,
        use_container_width=True,
        disabled=["Player", "Position", reference_column, target_column],
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
    reference = edited[reference_column].astype(float).where(lambda s: s > 0)

    st.subheader("Semáforo de cumplimiento por sesión")
    st.caption(
        "Carga real GPS / objetivo prescrito de la sesión. "
        "🟢 90–110% · 🟡 < 90% · 🔴 > 110% · ⚪ sin registro GPS ese día."
    )
    semaforo = pd.DataFrame({"Player": edited["Player"]})
    for session in sessions:
        semaforo[session] = [
            _semaforo_cell(p, a) for p, a in zip(prescribed[session], actual[session])
        ]
    st.dataframe(semaforo, hide_index=True, use_container_width=True)

    st.subheader("Carga real respecto al partido")
    st.caption(
        "Carga GPS de cada sesión como % de la referencia de partido del jugador "
        "(partido = 100%). Entre paréntesis, el % prescrito."
    )
    real_vs_match = pd.DataFrame({"Player": edited["Player"]})
    for session in sessions:
        real_pct = actual[session].div(reference).mul(100)
        prescribed_pct = prescribed[session].div(reference).mul(100)
        real_vs_match[session] = [
            "—" if pd.isna(r) else f"{r:.0f}% ({p:.0f}%)" if pd.notna(p) else f"{r:.0f}%"
            for r, p in zip(real_pct, prescribed_pct)
        ]
    st.dataframe(real_vs_match, hide_index=True, use_container_width=True)

    with st.expander("📋 Detalle por sesión"):
        detail = []
        for index, row in edited.iterrows():
            for session in sessions:
                p, a, ref = prescribed.at[index, session], actual.at[index, session], reference.at[index]
                compliance = a / p * 100 if pd.notna(a) and p > 0 else float("nan")
                if pd.isna(a):
                    estado = "Sin datos"
                elif not p > 0:
                    estado = "Sin objetivo"
                else:
                    estado = _status(compliance)[0]
                detail.append(
                    {
                        "Player": row["Player"],
                        "Sesión": session,
                        "Fecha": session_dates[session].strftime("%d/%m/%Y"),
                        f"Prescrito ({unit})": p,
                        f"Real GPS ({unit})": a,
                        "Prescrito (% partido)": p / ref * 100 if pd.notna(ref) else float("nan"),
                        "Real (% partido)": a / ref * 100 if pd.notna(ref) else float("nan"),
                        "% Cumplimiento": compliance,
                        "Estado": estado,
                    }
                )
        st.dataframe(
            pd.DataFrame(detail),
            hide_index=True,
            use_container_width=True,
            column_config={
                f"Prescrito ({unit})": st.column_config.NumberColumn(format="%.1f"),
                f"Real GPS ({unit})": st.column_config.NumberColumn(format="%.1f"),
                "Prescrito (% partido)": st.column_config.NumberColumn(format="%.0f%%"),
                "Real (% partido)": st.column_config.NumberColumn(format="%.0f%%"),
                "% Cumplimiento": st.column_config.NumberColumn(format="%.0f%%"),
            },
        )


if __name__ == "__main__":
    main()
