"""Bloque A: prescription of the weekly training load."""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from config import LAYOUT, PAGE_ICON, PAGE_TITLE
from utils import render_sidebar
from utils.reference_engine import calculate_references, get_microcycle_structure


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


def default_allocations(sessions: list[str]) -> dict[str, int]:
    """Create a 100% allocation in 5-point increments."""
    if not sessions:
        return {}
    allocations = {session: 5 for session in sessions}
    allocations[sessions[0]] = 70
    remaining = 30 - 5 * (len(sessions) - 1)
    for session in sessions[1:]:
        if remaining <= 0:
            break
        allocations[session] += 5
        remaining -= 5
    return allocations


def render_allocation_controls(sessions: list[str]) -> dict[str, int]:
    """Render one percentage input per session and return current values."""
    defaults = default_allocations(sessions)
    values: dict[str, int] = {}
    columns = st.columns(len(sessions))
    for column, session in zip(columns, sessions):
        with column:
            values[session] = st.number_input(
                session,
                min_value=5,
                max_value=80,
                value=int(defaults[session]),
                step=5,
                key=f"prescription_allocation_{session}",
                help="Porcentaje de la carga semanal asignado a esta sesión.",
            )
    total = sum(values.values())
    if total != 100:
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
    """Calculate player references from the loaded GPS data."""
    required = {"player", "position", "time", metric_column}
    if not required.issubset(df.columns):
        return pd.DataFrame(columns=["player", "position", "baseline_target"])
    source = df.copy()
    source["time"] = pd.to_numeric(source["time"], errors="coerce")
    source[metric_column] = pd.to_numeric(source[metric_column], errors="coerce")
    source = source[source["player"].notna()].copy()
    source = source[source["player"].astype(str).str.strip().ne("")]
    if statistic == "mean" and "date" in source.columns:
        source["date"] = pd.to_datetime(source["date"], errors="coerce")
        recent_dates = source["date"].dropna().drop_duplicates().nlargest(4)
        if not recent_dates.empty:
            source = source[source["date"].isin(recent_dates)]
    if source.empty:
        return pd.DataFrame(columns=["player", "position", "baseline_target"])
    return calculate_references(source, metric_column, statistic)


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
        target = float(row["Target weekly total"])
        session_total = float(row["Prescribed weekly load"])
        ratio = session_total / target if target > 0 else 0.0
        label, css_class, icon = _status(ratio)
        cards.append(
            f'<div class="status-card {css_class}">'
            f"<strong>{icon} {row['Player']}</strong>"
            f"<small>{label} · {ratio:.0%} del objetivo</small>"
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

    st.subheader("Configuración del microciclo")
    control_columns = st.columns(4)
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
    with control_columns[2]:
        statistic_label = st.selectbox(
            "Estadístico",
            options=list(STATISTIC_OPTIONS),
            key="prescription_statistic",
        )
    with control_columns[3]:
        load_multiplier = st.selectbox(
            "Valor de carga",
            options=LOAD_VALUES,
            index=2,
            format_func=lambda value: f"{value:.1f}",
            key="prescription_load_multiplier",
        )

    sessions = get_microcycle_structure(num_sessions)
    st.subheader("Distribución de la carga por sesión")
    allocations = render_allocation_controls(sessions)

    df = st.session_state.get("df_procesado")
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
    for _, reference in references.iterrows():
        target = float(reference["baseline_target"]) * float(load_multiplier)
        row = {
            "Player": reference["player"],
            "Position": reference["position"],
            f"Reference ({unit})": round(float(reference["baseline_target"]), 2),
            "Target weekly total": round(target, 2),
        }
        for session, allocation in allocations.items():
            row[session] = round(target * allocation / 100, 2)
        editor_rows.append(row)

    session_columns = list(allocations)
    editor_columns = [
        "Player",
        "Position",
        f"Reference ({unit})",
        "Target weekly total",
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
        disabled=["Player", "Position", f"Reference ({unit})"],
        column_config={
            "Target weekly total": st.column_config.NumberColumn(
                "Target weekly total", min_value=0, step=1, format="%.2f"
            ),
            **{
                session: st.column_config.NumberColumn(
                    session, min_value=0, step=1, format="%.2f"
                )
                for session in session_columns
            },
        },
        key="prescription_editor",
    )

    if not edited.empty:
        edited = edited.copy()
        edited["Prescribed weekly load"] = edited[session_columns].sum(axis=1)
    else:
        edited["Prescribed weekly load"] = pd.Series(dtype=float)
    render_semáforo(edited)


if __name__ == "__main__":
    main()