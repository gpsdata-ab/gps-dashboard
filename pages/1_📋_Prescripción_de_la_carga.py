"""Bloque A: prescription of the weekly training load."""

import sys
from datetime import date, timedelta
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
        .status-card {
            border-radius: 12px;
            padding: .8rem 1rem;
            color: white;
            min-height: 88px;
        }
        .status-card strong { display: block; font-size: 1.15rem; }
        .status-card small { opacity: .9; }
        .status-green { background: #20874c; }
        .status-yellow { background: #b88900; }
        .status-red { background: #b43c3c; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def default_allocations(
    sessions: list[str],
    independent_exposure: bool = False,
) -> dict[str, int]:
    """Create default allocation percentages in 5-point increments."""
    if not sessions:
        return {}
    if independent_exposure:
        return {session: 100 for session in sessions}

    allocations = {session: 5 for session in sessions}
    remaining = 100 - sum(allocations.values())
    for session in reversed(sessions):
        increment = min(remaining, 80 - allocations[session])
        allocations[session] += increment
        remaining -= increment
        if remaining == 0:
            break
    return allocations


def render_allocation_controls(
    sessions: list[str],
    independent_exposure: bool = False,
) -> dict[str, int]:
    """Render one percentage input per session and return current values."""
    defaults = default_allocations(sessions, independent_exposure)
    values: dict[str, int] = {}
    session_key = "_".join(sessions)
    allocation_mode = "exposure" if independent_exposure else "weekly"
    columns = st.columns(len(sessions))
    for column, session in zip(columns, sessions):
        with column:
            values[session] = st.number_input(
                session,
                min_value=50 if independent_exposure else 5,
                max_value=100 if independent_exposure else 80,
                value=int(defaults[session]),
                step=5,
                key=f"prescription_allocation_{allocation_mode}_{session_key}_{session}",
                help=(
                    "Porcentaje independiente de exposición para esta sesión."
                    if independent_exposure
                    else "Porcentaje de la carga semanal asignado a esta sesión."
                ),
            )
    total = sum(values.values())
    if independent_exposure:
        st.caption("Exposición por sesión independiente (50–100%).")
    elif total != 100:
        st.warning(
            f"La distribución actual suma {total}%. Ajusta las sesiones para llegar a 100%."
        )
    else:
        st.caption("Distribución semanal: 100%")
    return values


def _reference_frame(
    df: pd.DataFrame,
    metric_column: str,
    statistic: str,
) -> pd.DataFrame:
    """Calculate player references from match records only."""
    source = filtrar_solo_partidos(df)
    is_peak = metric_column == "max_speed"
    required = {"player", "position", metric_column}
    if not is_peak and not {"minutes_played", "time"}.intersection(source.columns):
        return pd.DataFrame(columns=["player", "position", "baseline_target"])
    if not required.issubset(source.columns):
        return pd.DataFrame(columns=["player", "position", "baseline_target"])
    source = source.copy()
    if "time" in source.columns:
        source["time"] = pd.to_numeric(source["time"], errors="coerce")
    if "minutes_played" in source.columns:
        source["minutes_played"] = pd.to_numeric(
            source["minutes_played"], errors="coerce"
        )
    source[metric_column] = pd.to_numeric(source[metric_column], errors="coerce")
    source = source[source["player"].notna()].copy()
    source = source[source["player"].astype(str).str.strip().ne("")]
    if statistic == "mean" and "date" in source.columns:
        source["date"] = pd.to_datetime(
            source["date"], errors="coerce", format="mixed"
        ).dt.date
        recent_dates = source["date"].dropna().drop_duplicates()
        recent_dates = sorted(recent_dates, reverse=True)[:4]
        if recent_dates:
            source = source[source["date"].isin(recent_dates)]
    if source.empty:
        return pd.DataFrame(columns=["player", "position", "baseline_target"])

    return calculate_references(source, metric_column, statistic, is_peak_metric=is_peak)


def _metric_unit(metric_label: str) -> str:
    return "km/h" if metric_label == "Max speed" else "m"


def _status(ratio: float) -> tuple[str, str, str]:
    if ratio < 0.9:
        return "Subóptimo", "status-yellow", "🟡"
    if ratio <= 1.1:
        return "Óptimo", "status-green", "🟢"
    return "Sobre-óptimo", "status-red", "🔴"


def render_semáforo(editor_data: pd.DataFrame) -> None:
    """Render weekly completion cards for the edited prescriptions."""
    st.subheader("Semáforo de cumplimiento semanal")
    if editor_data.empty:
        st.info("No hay jugadores disponibles para mostrar el semáforo.")
        return

    cards = []
    for _, row in editor_data.iterrows():
        compliance = float(row["% Cumplimiento"])
        ratio = compliance / 100
        label, css_class, icon = _status(ratio)
        cards.append(
            f'<div class="status-card {css_class}">'
            f"<strong>{icon} {row['Player']}</strong>"
            f"<small>{label} · {compliance:.1f}% · "
            f"GPS {float(row['Carga Real GPS']):.2f} / "
            f"{float(row['Target Prescrito']):.2f}</small>"
            "</div>"
        )

    columns = st.columns(min(4, len(cards)))
    for index, card in enumerate(cards):
        with columns[index % len(columns)]:
            st.markdown(card, unsafe_allow_html=True)


def main() -> None:
    if not st.session_state.get("autenticado", False):
        st.warning("⚠️ Por favor, inicia sesión desde la página principal")
        st.stop()

    render_sidebar()
    inject_styles()
    st.markdown(
        '<div class="prescription-hero"><h1>📋 Prescripción de la carga</h1>'
        "<p>Bloque A · Planificación de la carga semanal por jugador y sesión</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    df = st.session_state.get("df_procesado")
    latest_match_date = None
    if isinstance(df, pd.DataFrame) and "date" in df.columns:
        parsed_dates = pd.to_datetime(df["date"], errors="coerce").dropna()
        if not parsed_dates.empty:
            latest_match_date = parsed_dates.max().date()
    default_start_date = latest_match_date or (
        date.today() - timedelta(days=date.today().weekday())
    )

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
                "Estadístico",
                options=["Pico máximo"],
                disabled=True,
                key="prescription_statistic_max_speed",
                help="Max speed requiere utilizar el estadístico de Pico máximo exclusivamente.",
            )
        else:
            statistic_label = st.selectbox(
                "Estadístico",
                options=list(STATISTIC_OPTIONS),
                key="prescription_statistic",
            )
            
    with control_columns[3]:
        microcycle_start = st.date_input(
            "Inicio microciclo",
            value=default_start_date,
            key="prescription_microcycle_start",
            help="Fecha de inicio del microciclo (MD-N). Las sesiones avanzan hasta MD+1 al final.",
        )
    with control_columns[4]:
        load_multiplier = st.selectbox(
            "Valor de carga",
            options=LOAD_VALUES,
            index=2,
            format_func=lambda value: f"{value:.1f}",
            key="prescription_load_multiplier",
        )

    sessions = get_microcycle_structure(num_sessions)
    session_dates = map_microcycle_dates(microcycle_start, sessions)
    st.caption(
        "Calendario: "
        + " · ".join(
            f"{session}: {session_dates[session].strftime('%d/%m/%Y')}"
            for session in sessions
        )
    )
    st.subheader("Distribución de la carga por sesión")
    allocations = render_allocation_controls(
        sessions,
        independent_exposure=is_max_speed,
    )
    if not is_max_speed and sum(allocations.values()) != 100:
        st.warning("La prescripción de volumen requiere una distribución semanal del 100%.")
        st.stop()

    if not isinstance(df, pd.DataFrame) or df.empty:
        st.info("Carga los datos GPS desde la página principal para calcular las referencias.")
        references = pd.DataFrame(columns=["player", "position", "baseline_target"])
    else:
        references = _reference_frame(
            df,
            METRIC_OPTIONS[metric_label],
            STATISTIC_OPTIONS[statistic_label],
        )
        if references.empty:
            st.warning(
                f"No existe la columna '{METRIC_OPTIONS[metric_label]}' en los datos cargados."
            )

    unit = _metric_unit(metric_label)
    editor_rows = []
    actual_loads = aggregate_actual_loads(
        df if isinstance(df, pd.DataFrame) else pd.DataFrame(),
        references["player"],
        METRIC_OPTIONS[metric_label],
        session_dates,
    )
    actual_by_player = actual_loads.set_index("player").to_dict("index")
    target_column = "Target exposure" if is_max_speed else "Target weekly total"
    for _, reference in references.iterrows():
        target = float(reference["baseline_target"]) * float(load_multiplier)
        row = {
            "Player": reference["player"],
            "Position": reference["position"],
            f"Reference ({unit})": round(float(reference["baseline_target"]), 2),
            target_column: round(target, 2),
        }
        for session, allocation in allocations.items():
            row[session] = round(target * allocation / 100, 2)
        editor_rows.append(row)

    session_columns = list(allocations)
    session_key = "_".join(session_columns)
    editor_columns = [
        "Player",
        "Position",
        f"Reference ({unit})",
        target_column,
        *session_columns,
    ]
    editor_data = pd.DataFrame(editor_rows, columns=editor_columns)
    st.subheader("Editor de prescripción individual")
    st.caption(
        "Edita el objetivo semanal o cualquier sesión para adaptar la carga a casos de Return to Play y fatiga."
    )
    edited = st.data_editor(
        editor_data,
        hide_index=True,
        use_container_width=True,
        disabled=[
            "Player",
            "Position",
            f"Reference ({unit})",
            target_column,
        ],
        column_config={
            target_column: st.column_config.NumberColumn(
                "Target Prescrito", min_value=0, step=1, format="%.2f"
            ),
            **{
                session: st.column_config.NumberColumn(
                    session, min_value=0, step=1, format="%.2f"
                )
                for session in session_columns
            },
        },
        key=f"prescription_editor_{session_key}",
    )

    if not edited.empty:
        edited = edited.copy()
        if is_max_speed:
            edited["Prescribed weekly load"] = edited[session_columns].max(axis=1)
        else:
            edited["Prescribed weekly load"] = edited[session_columns].sum(axis=1)
        edited["Target Prescrito"] = edited["Prescribed weekly load"].round(2)
        actual_totals = {
            player: (
                max(values.values(), default=0.0)
                if is_max_speed
                else sum(values.values())
            )
            for player, values in actual_by_player.items()
        }
        edited["Carga Real GPS"] = (
            edited["Player"].map(actual_totals).fillna(0.0).round(2)
        )
        edited["% Cumplimiento"] = (
            edited["Carga Real GPS"]
            .div(edited["Target Prescrito"].where(
                edited["Target Prescrito"].ne(0), float("nan")
            ))
            .fillna(0.0)
            .mul(100)
            .round(1)
        )
        edited["Estado"] = edited["% Cumplimiento"].map(
            lambda compliance: _status(compliance / 100)[0]
        )
    else:
        edited["Prescribed weekly load"] = pd.Series(dtype=float)
        edited["Target Prescrito"] = pd.Series(dtype=float)
        edited["Carga Real GPS"] = pd.Series(dtype=float)
        edited["% Cumplimiento"] = pd.Series(dtype=float)
        edited["Estado"] = pd.Series(dtype=str)
    summary_columns = [
        "Player",
        "Target Prescrito",
        "Carga Real GPS",
        "% Cumplimiento",
        "Estado",
    ]
    st.subheader("Resumen de cumplimiento")
    st.dataframe(
        edited[summary_columns],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Target Prescrito": st.column_config.NumberColumn(format="%.2f"),
            "Carga Real GPS": st.column_config.NumberColumn(format="%.2f"),
            "% Cumplimiento": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )
    render_semáforo(edited)


if __name__ == "__main__":
    main()