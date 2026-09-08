"""
Página: GPS UBIKO
Integración profesional de sesiones reales Ubiko.

Objetivo: añadir una pestaña/página nueva sin alterar el resto de la app.
Métricas principales: total_distance, minute_distance, hmld, hsr, sprints.
"""

import re
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Añadir directorio raíz al path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from config import PAGE_TITLE, PAGE_ICON, LAYOUT, COLORES
from utils import render_sidebar, cargar_plantilla_desde_drive, mapear_posicion, obtener_foto_jugador
from utils.drive_loader import autenticar_google_drive, listar_archivos_carpeta, FOLDER_IDS

st.set_page_config(
    page_title=f"{PAGE_TITLE} - GPS UBIKO",
    page_icon=PAGE_ICON,
    layout=LAYOUT,
    initial_sidebar_state="collapsed",
)

METRICAS_UBIKO = {
    "Aceleraciones": "num_acc_expl",
    "Deceleraciones": "num_dec_expl",
    "Distancia / minuto": "minute_distance",
    "Distancia a Sprint": "distance_vrange6",
    "Distancia Total": "total_distance",
    "HMLD": "hmld",
    "HMLD Relativo": "hmld_relative",
    "HSR": "hsr",
    "HSR Relativo": "hsr_rel",
    "Sprints": "sprints",
    "Velocidad Máxima": "max_speed",
}

METRIC_LABELS = {v: k for k, v in METRICAS_UBIKO.items()}

# Métricas que representan volumen/cuenta y, si hubiera que reconstruir una
# sesión sin fila "Total", deben sumarse entre tareas.
UBIKO_METRICAS_ACUMULATIVAS = {
    "total_distance",
    "distance_vrange6",
    "hmld",
    "hsr",
    "sprints",
    "num_acc_expl",
    "num_dec_expl",
}
UBIKO_METRICAS_MAXIMAS = {"max_speed"}

SESSION_ORDER = {
    "partido": 0,
    "j31": 0,
    "j32": 0,
    "j34": 0,
    "san luqueno": 0,
    "compensatori": 1,
    "introductoria": 2,
    "extensiva": 3,
    "intensiva": 4,
    "mixta": 5,
    "tappering": 6,
    "pre partit": 7,
}


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --gps-bg: #070C12;
            --gps-panel: #0E1721;
            --gps-panel-2: #101C28;
            --gps-border: rgba(139, 190, 255, .18);
            --gps-blue: #8EC7FF;
            --gps-cyan: #47D7FF;
            --gps-green: #6BEF9A;
            --gps-text: #F6FAFF;
            --gps-muted: #F2F6FB;
        }

        .stApp {
            background: radial-gradient(circle at top left, rgba(40,117,180,.16), transparent 28%), var(--gps-bg);
            color: var(--gps-text);
        }

        .block-container {
            padding-top: 2.2rem;
            padding-bottom: 3rem;
        }

        .gps-hero {
            padding: 30px 32px;
            border-radius: 30px;
            background:
                linear-gradient(135deg, rgba(20,45,67,.98), rgba(6,18,29,.98)),
                radial-gradient(circle at top right, rgba(71,215,255,.16), transparent 40%);
            border: 1px solid var(--gps-border);
            box-shadow: 0 24px 70px rgba(0,0,0,.36);
            margin-bottom: 24px;
        }
        .gps-kicker {
            font-size: 12px;
            letter-spacing: .18em;
            text-transform: uppercase;
            color: var(--gps-blue);
            font-weight: 850;
            margin-bottom: 10px;
        }
        .gps-title {
            font-size: 44px;
            line-height: 1.02;
            letter-spacing: -.045em;
            font-weight: 950;
            color: var(--gps-text);
            margin-bottom: 10px;
        }
        .gps-subtitle {
            font-size: 15px;
            line-height: 1.7;
            color: var(--gps-muted);
            max-width: 1120px;
        }
        .gps-card {
            border-radius: 24px;
            padding: 22px 24px;
            background: linear-gradient(180deg, rgba(18,29,41,.98), rgba(12,20,29,.98));
            border: 1px solid rgba(142,199,255,.16);
            box-shadow: 0 18px 45px rgba(0,0,0,.26);
        }
        .gps-player-card {
            border-radius: 28px;
            padding: 20px 18px 16px 18px;
            background: linear-gradient(180deg, rgba(18,29,41,.98), rgba(12,20,29,.98));
            border: 1px solid rgba(142,199,255,.16);
            box-shadow: 0 18px 45px rgba(0,0,0,.26);
            text-align: center;
            height: 100%;
        }
        .gps-player-name {
            font-size: 22px;
            line-height: 1.1;
            letter-spacing: -.03em;
            font-weight: 900;
            color: var(--gps-text);
            margin: 14px 0 6px 0;
        }
        .gps-player-meta {
            color: var(--gps-muted);
            font-size: 13px;
            line-height: 1.5;
        }
        .gps-section-title {
            font-size: 23px;
            font-weight: 900;
            letter-spacing: -.03em;
            color: var(--gps-text);
            margin: 28px 0 12px 0;
        }
        .gps-muted {
            color: var(--gps-muted);
            font-size: 13px;
        }

        div[data-testid="stMetric"] {
            min-height: 122px;
            border-radius: 22px;
            padding: 18px 20px;
            background:
                linear-gradient(145deg, rgba(19,33,47,.98), rgba(11,18,27,.98));
            border: 1px solid rgba(142,199,255,.18);
            box-shadow: 0 16px 42px rgba(0,0,0,.30);
        }
        div[data-testid="stMetricLabel"] {
            color: #FFFFFF;
            font-weight: 750;
        }
        div[data-testid="stMetricValue"] {
            color: #FFFFFF;
            font-weight: 900;
            letter-spacing: -.04em;
        }
        div[data-testid="stMetricDelta"] {
            color: var(--gps-green) !important;
            font-weight: 800;
        }

        .gps-range-card {
            min-height: 122px;
            border-radius: 22px;
            padding: 18px 20px;
            background: linear-gradient(145deg, rgba(19,33,47,.98), rgba(11,18,27,.98));
            border: 1px solid rgba(142,199,255,.18);
            box-shadow: 0 16px 42px rgba(0,0,0,.30);
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .gps-range-label {
            color: #FFFFFF;
            font-weight: 750;
            font-size: 16px;
            margin-bottom: 14px;
        }
        .gps-range-value {
            color: #FFFFFF;
            font-weight: 900;
            letter-spacing: -.04em;
            font-size: clamp(28px, 2.4vw, 42px);
            line-height: 1;
            white-space: nowrap;
        }

        .gps-kpi-grid {
            max-width: 1540px;
            margin: 0 auto 30px auto;
            display: grid;
            grid-template-columns: repeat(5, minmax(190px, 1fr));
            gap: 22px;
            align-items: stretch;
        }
        .gps-kpi-card-custom {
            min-height: 122px;
            border-radius: 22px;
            padding: 20px 24px;
            background: linear-gradient(145deg, rgba(19,33,47,.98), rgba(11,18,27,.98));
            border: 1px solid rgba(142,199,255,.18);
            box-shadow: 0 16px 42px rgba(0,0,0,.30);
            display: flex;
            flex-direction: column;
            justify-content: center;
            overflow: hidden;
        }
        .gps-kpi-label-custom {
            color: #FFFFFF;
            font-weight: 750;
            font-size: 15px;
            line-height: 1.15;
            margin-bottom: 14px;
            white-space: nowrap;
        }
        .gps-kpi-value-custom {
            color: #FFFFFF;
            font-weight: 900;
            letter-spacing: -.04em;
            font-size: clamp(30px, 2.6vw, 42px);
            line-height: 1;
            white-space: nowrap;
        }
        .gps-kpi-value-custom.is-range {
            font-size: clamp(20px, 1.65vw, 28px) !important;
            letter-spacing: -.035em;
        }
        @media (max-width: 1200px) {
            .gps-kpi-grid { grid-template-columns: repeat(3, minmax(190px, 1fr)); }
        }
        @media (max-width: 760px) {
            .gps-kpi-grid { grid-template-columns: 1fr; max-width: 420px; }
        }

        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div {
            background-color: #1B2230 !important;
            border: 1px solid rgba(142,199,255,.12) !important;
            color: #F6FAFF !important;
            border-radius: 13px !important;
        }

        label, .stMarkdown, p, span {
            color: inherit;
        }

        [data-testid="stWidgetLabel"] *,
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li,
        div[data-baseweb="select"] span,
        div[data-baseweb="tag"] span,
        div[data-baseweb="input"] input,
        div[data-baseweb="select"] input,
        .stSelectbox label,
        .stMultiSelect label,
        .stDateInput label,
        .stRadio label {
            color: #FFFFFF !important;
        }

        [data-testid="stSidebar"] *,
        [data-testid="stSidebarNav"] *,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] li {
            color: #1F2937 !important;
        }

        [data-testid="stSidebar"] div[data-testid="stMetric"] {
            background: linear-gradient(145deg, rgba(19,33,47,.98), rgba(11,18,27,.98)) !important;
            border: 1px solid rgba(142,199,255,.18) !important;
            box-shadow: 0 16px 42px rgba(0,0,0,.18) !important;
        }
        [data-testid="stSidebar"] div[data-testid="stMetric"] *,
        [data-testid="stSidebar"] div[data-testid="stMetric"] label,
        [data-testid="stSidebar"] div[data-testid="stMetric"] p,
        [data-testid="stSidebar"] div[data-testid="stMetric"] span,
        [data-testid="stSidebar"] div[data-testid="stMetric"] div {
            color: #FFFFFF !important;
        }
        [data-testid="stSidebar"] div[data-testid="stMetricLabel"],
        [data-testid="stSidebar"] div[data-testid="stMetricLabel"] *,
        [data-testid="stSidebar"] div[data-testid="stMetricLabel"] label,
        [data-testid="stSidebar"] div[data-testid="stMetricLabel"] p,
        [data-testid="stSidebar"] div[data-testid="stMetricLabel"] span,
        [data-testid="stSidebar"] div[data-testid="stMetricValue"],
        [data-testid="stSidebar"] div[data-testid="stMetricValue"] *,
        [data-testid="stSidebar"] div[data-testid="stMetricValue"] p,
        [data-testid="stSidebar"] div[data-testid="stMetricValue"] span {
            color: #FFFFFF !important;
        }
        [data-testid="stSidebar"] div[data-testid="stMetricDelta"],
        [data-testid="stSidebar"] div[data-testid="stMetricDelta"] * {
            color: #E7EEF7 !important;
        }
        [data-testid="stSidebar"] [data-testid="stAlertContainer"],
        [data-testid="stSidebar"] [data-testid="stAlertContainer"] * {
            color: #1F2937 !important;
        }

        [data-testid="stDataFrame"] {
            border: 1px solid rgba(142,199,255,.12);
            border-radius: 18px;
            overflow: hidden;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def normalizar_texto(valor: object) -> str:
    txt = str(valor or "").strip().lower()
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    txt = re.sub(r"[^a-z0-9]+", " ", txt)
    return txt.strip()


def limpiar_numero_ubiko(valor: object) -> float:
    """
    Convierte el formato exportado por Ubiko.

    Ejemplos reales detectados:
    - "3.548 448" -> 3548.448
    - "848   627" -> 848.627
    - "65 615" -> 65.615
    - "5 000" -> 5.000
    """
    if pd.isna(valor):
        return np.nan

    if isinstance(valor, (int, float, np.number)):
        return float(valor)

    txt = str(valor).strip()
    if txt == "" or txt.lower() in {"nan", "none", "null"}:
        return np.nan

    txt = txt.replace("\u00a0", " ").replace("'", "").strip()
    txt = re.sub(r"\s+", " ", txt)

    # Formatos reales detectados en Ubiko:
    # 1) "1.008,498" -> punto millar + coma decimal
    # 2) "3.548 448" -> punto millar + espacio decimal
    # 3) "848,627"   -> coma decimal
    # 4) "65 615"    -> espacio decimal
    if "," in txt:
        txt = txt.replace(".", "").replace(",", ".")
    elif " " in txt:
        partes = txt.split(" ")
        entero = "".join(partes[:-1]).replace(".", "")
        decimal = partes[-1]
        txt = f"{entero}.{decimal}"
    else:
        # Si solo hay punto y patrón de millar, eliminar millares.
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", txt):
            txt = txt.replace(".", "")

    try:
        return float(txt)
    except ValueError:
        return np.nan


def extract_date_from_filename(path: Path) -> Optional[pd.Timestamp]:
    match = re.search(r"(\d{1,2}-\d{1,2}-\d{4})", path.name)
    if match:
        return pd.to_datetime(match.group(1), dayfirst=True, errors="coerce")
    return None


def pretty_session_name(raw: object) -> str:
    txt = str(raw or "").strip()
    txt = txt.replace("_", " ").replace("-", " ")
    txt_norm = normalizar_texto(txt)
    if txt_norm.startswith("j") and any(ch.isdigit() for ch in txt_norm):
        return txt_norm.upper().replace(" ", "")
    mapping = {
        "pre partit": "Pre-partit",
        "san luqueno": "San Luqueño",
        "compensatori": "Compensatori",
        "extensiva": "Extensiva",
        "intensiva": "Intensiva",
        "introductoria": "Introductoria",
        "mixta": "Mixta",
        "tappering": "Tappering",
    }
    return mapping.get(txt_norm, txt.title())


def infer_session_group(row: pd.Series) -> str:
    session = normalizar_texto(row.get("session", ""))
    task = normalizar_texto(row.get("task", ""))

    if session.startswith("j") or "san luqueno" in session:
        return "Partido"
    if "compensatori" in session:
        return "Compensatori"
    if "pre partit" in session:
        return "Pre-partit"
    if "introductoria" in session:
        return "Introductoria"
    if "extensiva" in session:
        return "Extensiva"
    if "intensiva" in session:
        return "Intensiva"
    if "mixta" in session:
        return "Mixta"
    if "tappering" in session:
        return "Tappering"
    if "periodo" in task and row.get("total_distance", 0) > 0:
        return "Partido"
    return pretty_session_name(row.get("session", "Sesión"))


def build_match_label(row: pd.Series) -> str:
    session_label = str(row.get("session_label", "") or "").strip()
    session_group = str(row.get("session_group", "") or "").strip()
    if session_group != "Partido":
        return ""

    session_norm = normalizar_texto(row.get("session", session_label))
    if session_norm.startswith("j") and any(ch.isdigit() for ch in session_norm):
        jornada = session_norm.upper().replace(" ", "")
        return f"Partido · {jornada}"

    if "san luqueno" in session_norm:
        return "Partido · Rival: San Luqueño"

    if session_label:
        return f"Partido · {session_label}"

    return "Partido"


@st.cache_data(show_spinner=False, ttl=3600)
def load_drive_positions() -> pd.DataFrame:
    try:
        df_plantilla = cargar_plantilla_desde_drive(equipo="europa")
        if df_plantilla is None or df_plantilla.empty:
            return pd.DataFrame(columns=["Jugador GPS", "Posición"])

        required_cols = {"Jugador GPS", "Posición"}
        if not required_cols.issubset(df_plantilla.columns):
            return pd.DataFrame(columns=["Jugador GPS", "Posición"])

        df_plantilla = df_plantilla[list(required_cols)].copy()
        df_plantilla["Jugador GPS"] = df_plantilla["Jugador GPS"].astype(str).str.strip()
        df_plantilla["Posición"] = df_plantilla["Posición"].astype(str).str.strip()
        df_plantilla = df_plantilla[df_plantilla["Jugador GPS"].ne("")]
        df_plantilla = df_plantilla.drop_duplicates(subset=["Jugador GPS"], keep="first")
        df_plantilla["player_norm"] = df_plantilla["Jugador GPS"].apply(normalizar_texto)
        df_plantilla = df_plantilla[df_plantilla["player_norm"].ne("")]
        df_plantilla = df_plantilla.drop_duplicates(subset=["player_norm"], keep="first")
        return df_plantilla
    except Exception:
        return pd.DataFrame(columns=["Jugador GPS", "Posición", "player_norm"])


@st.cache_data(show_spinner=False)
def prepare_ubiko_dataset(df_all: pd.DataFrame) -> pd.DataFrame:
    if df_all is None or df_all.empty:
        return pd.DataFrame()

    df_all = df_all.copy()
    # Columnas mínimas esperadas.
    for col in ["session", "task", "date", "position", "dorsal", "player"]:
        if col not in df_all.columns:
            df_all[col] = np.nan

    if "source_file" not in df_all.columns:
        session_part = df_all["session"].fillna("sesion").astype(str).str.strip()
        if "date" in df_all.columns:
            date_part = pd.to_datetime(df_all["date"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("sin-fecha")
        else:
            date_part = pd.Series(["sin-fecha"] * len(df_all), index=df_all.index)
        df_all["source_file"] = session_part + "_" + date_part

    numeric_cols = [
        "time", "active_time", "effective_time", "total_distance", "minute_distance",
        "hmld", "hmld_relative", "hsr", "hsr_rel", "sprints", "max_speed", "num_acc_expl",
        "num_dec_expl", "player_load", "distance_vrange6",
    ]
    for col in numeric_cols:
        if col in df_all.columns:
            df_all[col] = df_all[col].apply(limpiar_numero_ubiko)

    if {"hsr", "time"}.issubset(df_all.columns):
        df_all["hsr_rel"] = np.where(df_all["time"] > 0, df_all["hsr"] / df_all["time"], np.nan)

    if {"hmld", "time"}.issubset(df_all.columns):
        df_all["hmld_relative"] = np.where(df_all["time"] > 0, df_all["hmld"] / df_all["time"], np.nan)

    df_all["date"] = pd.to_datetime(df_all["date"], errors="coerce")
    df_all["player"] = df_all["player"].astype(str).str.strip()
    df_all = df_all[df_all["player"].notna()]
    df_all = df_all[df_all["player"].str.lower().ne("nan")]
    df_all = df_all[df_all["player"].str.strip().ne("")]
    df_all = df_all[df_all["player"].str.strip().ne("0")]

    df_all["session_group"] = df_all.apply(infer_session_group, axis=1)
    df_all["session_label"] = df_all["session"].apply(pretty_session_name)
    df_all["match_label"] = df_all.apply(build_match_label, axis=1)
    df_all["position_csv"] = df_all["position"].fillna("").astype(str).str.strip()
    df_all["player_norm"] = df_all["player"].apply(normalizar_texto)

    df_positions = load_drive_positions()
    if not df_positions.empty:
        position_map = df_positions.set_index("player_norm")["Posición"]
        df_all["position_drive"] = df_all["player_norm"].map(position_map)
        faltantes = df_all["position_drive"].isna()
        if faltantes.any():
            df_all.loc[faltantes, "position_drive"] = df_all.loc[faltantes, "player"].apply(
                lambda nombre: mapear_posicion(str(nombre), df_positions)
            )
            df_all.loc[df_all["position_drive"] == "Sin posición", "position_drive"] = np.nan
    else:
        df_all["position_drive"] = np.nan

    df_all["position_source"] = np.where(
        df_all["position_drive"].notna(),
        "drive",
        "csv_fallback",
    )

    df_all["position"] = (
        df_all["position_drive"]
        .fillna(df_all["position_csv"])
        .replace("", "Sin posición")
        .fillna("Sin posición")
        .astype(str)
        .str.strip()
    )
    df_all["task"] = df_all["task"].fillna("Total").astype(str)

    # Orden de sesión para lecturas más naturales.
    df_all["session_order"] = df_all["session_group"].apply(
        lambda x: SESSION_ORDER.get(normalizar_texto(x), 99)
    )

    return df_all.sort_values(["date", "session_order", "player"]).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_ubiko_dataset() -> pd.DataFrame:
    frames = []
    drive = autenticar_google_drive(mostrar_mensajes=False)
    folder_id = FOLDER_IDS.get("datos")

    if drive is not None and folder_id:
        archivos = listar_archivos_carpeta(drive, folder_id, patron="*.csv", mostrar_mensajes=False)
        for archivo in sorted(archivos, key=lambda f: str(f.get("title", "")).lower()):
            title = str(archivo.get("title", ""))
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp_file:
                    archivo.GetContentFile(tmp_file.name)
                    temp_path = Path(tmp_file.name)

                try:
                    df = pd.read_csv(temp_path, sep=";", dtype=str, encoding="utf-8")
                except UnicodeDecodeError:
                    df = pd.read_csv(temp_path, sep=";", dtype=str, encoding="latin1")

                df.columns = [str(c).strip() for c in df.columns]
                df["source_file"] = title

                if len(df.columns) == 1 and ";" in df.columns[0]:
                    df = pd.read_csv(temp_path, sep=";", dtype=str, engine="python")
                    df.columns = [str(c).strip() for c in df.columns]
                    df["source_file"] = title

                if "date" not in df.columns or df["date"].isna().all():
                    df["date"] = extract_date_from_filename(Path(title))

                if "session" not in df.columns:
                    df["session"] = Path(title).stem.split("_")[0]

                frames.append(df)
            except Exception:
                continue
            finally:
                try:
                    if temp_path is not None:
                        temp_path.unlink(missing_ok=True)
                except Exception:
                    pass

    if not frames:
        return pd.DataFrame()

    return prepare_ubiko_dataset(pd.concat(frames, ignore_index=True))


def fmt_num(value: object, decimals: int = 1) -> str:
    if pd.isna(value):
        return "—"
    return f"{float(value):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(value: object) -> str:
    if pd.isna(value):
        return "—"
    return f"{float(value):+.1f}%".replace(".", ",")


def aggregate_metric(df: pd.DataFrame, metrica: str, estadistico: str) -> float:
    serie = pd.to_numeric(df[metrica], errors="coerce").dropna()
    if serie.empty:
        return np.nan
    if estadistico == "Media":
        return float(serie.mean())
    if estadistico == "Máximo":
        return float(serie.max())
    if estadistico == "P70":
        return float(serie.quantile(0.70))
    if estadistico == "P95":
        return float(serie.quantile(0.95))
    if estadistico == "Sumatorio":
        return float(serie.sum())
    return float(serie.mean())


def aggregate_session_rows(df_input: pd.DataFrame) -> pd.DataFrame:
    if df_input is None or df_input.empty:
        return pd.DataFrame(columns=df_input.columns if df_input is not None else [])

    group_cols = ["source_file", "date", "player"]
    df_sorted = df_input.sort_values(group_cols + ["session_order"]).copy()
    rows = []

    for _, group in df_sorted.groupby(group_cols, dropna=False, sort=False):
        task_norm = group["task"].fillna("").astype(str).str.strip().str.lower() if "task" in group.columns else pd.Series("", index=group.index)
        total_rows = group[task_norm.eq("total")].copy()
        non_total_rows = group[~task_norm.eq("total")].copy()

        # Si la sesión ya trae una fila "Total", la usamos como referencia para evitar
        # duplicar la carga al sumar también todas las tareas individuales.
        # Si no existe, agregamos sobre las tareas disponibles.
        if not total_rows.empty:
            metric_source = total_rows
            row = total_rows.iloc[0].copy()
        else:
            metric_source = group
            row = group.iloc[0].copy()

        time_sum = pd.to_numeric(metric_source.get("time"), errors="coerce").sum(min_count=1) if "time" in metric_source.columns else np.nan
        if pd.notna(time_sum):
            row["time"] = float(time_sum)

        for metric in METRICAS_UBIKO.values():
            if metric not in metric_source.columns:
                continue

            serie = pd.to_numeric(metric_source[metric], errors="coerce")
            valor = np.nan

            if metric in UBIKO_METRICAS_ACUMULATIVAS:
                valor = serie.sum(min_count=1)
            elif metric == "minute_distance":
                total_distance = pd.to_numeric(metric_source.get("total_distance"), errors="coerce").sum(min_count=1) if "total_distance" in metric_source.columns else np.nan
                total_time = pd.to_numeric(metric_source.get("time"), errors="coerce").sum(min_count=1) if "time" in metric_source.columns else np.nan
                if pd.notna(total_distance) and pd.notna(total_time) and total_time > 0:
                    valor = total_distance / total_time
                else:
                    valor = serie.mean()
            elif metric == "hsr_rel":
                total_hsr = pd.to_numeric(metric_source.get("hsr"), errors="coerce").sum(min_count=1) if "hsr" in metric_source.columns else np.nan
                total_time = pd.to_numeric(metric_source.get("time"), errors="coerce").sum(min_count=1) if "time" in metric_source.columns else np.nan
                if pd.notna(total_hsr) and pd.notna(total_time) and total_time > 0:
                    valor = total_hsr / total_time
                else:
                    valor = serie.mean()
            elif metric == "hmld_relative":
                total_hmld = pd.to_numeric(metric_source.get("hmld"), errors="coerce").sum(min_count=1) if "hmld" in metric_source.columns else np.nan
                total_time = pd.to_numeric(metric_source.get("time"), errors="coerce").sum(min_count=1) if "time" in metric_source.columns else np.nan
                if pd.notna(total_hmld) and pd.notna(total_time) and total_time > 0:
                    valor = total_hmld / total_time
                else:
                    valor = serie.mean()
            elif metric in UBIKO_METRICAS_MAXIMAS:
                valor = serie.max()
            else:
                valor = serie.mean()

            row[metric] = valor

        rows.append(row)

    return pd.DataFrame(rows).reset_index(drop=True)


def create_line_chart(df_player: pd.DataFrame, metrica: str, jugador: str) -> go.Figure:
    plot_df = df_player.sort_values(["date", "session_order", "source_file"]).copy()
    plot_df["valor"] = pd.to_numeric(plot_df[metrica], errors="coerce")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=plot_df["date"],
            y=plot_df["valor"],
            mode="lines+markers",
            name=jugador,
            line=dict(width=4, color="#47D7FF"),
            marker=dict(size=10),
            customdata=plot_df[["session_group", "session_label"]],
            hovertemplate="%{x|%d/%m/%Y}<br>%{customdata[0]}<br>%{customdata[1]}<br>%{y:.1f}<extra></extra>",
        )
    )

    matches_df = plot_df[plot_df["session_group"] == "Partido"].copy()
    if not matches_df.empty:
        fig.add_trace(
            go.Scatter(
                x=matches_df["date"],
                y=matches_df["valor"],
                mode="markers",
                name="Partido",
                marker=dict(size=12, color="#FF4D4F", line=dict(width=1.5, color="#FFD6D6")),
                customdata=matches_df[["match_label"]],
                hovertemplate="%{x|%d/%m/%Y}<br>%{customdata[0]}<br>%{y:.1f}<extra></extra>",
            )
        )

        for _, row in matches_df.iterrows():
            etiqueta = row["match_label"] or "Partido"
            fig.add_vline(
                x=row["date"],
                line_dash="dash",
                line_color="#FF4D4F",
                line_width=1,
                opacity=0.8,
            )
            fig.add_annotation(
                x=row["date"],
                y=0.02,
                yref="paper",
                text=etiqueta,
                showarrow=False,
                textangle=-90,
                font=dict(size=10, color="#FF9EA0"),
                xanchor="left",
                yanchor="bottom",
                bgcolor="rgba(7,12,18,0.65)",
            )

    baseline = plot_df["valor"].mean()
    if not pd.isna(baseline):
        fig.add_hline(
            y=baseline,
            line_dash="dash",
            line_color="#6BEF9A",
            annotation_text=f"Baseline {fmt_num(baseline)}",
            annotation_position="top left",
        )

    fig.update_layout(
        height=430,
        margin=dict(l=20, r=20, t=30, b=20),
        template="plotly_dark",
        hovermode="x unified",
        xaxis_title="Fecha",
        yaxis_title=METRIC_LABELS.get(metrica, metrica),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#F6FAFF"),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#F6FAFF"),
        xaxis=dict(gridcolor="rgba(255,255,255,.10)", zerolinecolor="rgba(255,255,255,.12)"),
        yaxis=dict(gridcolor="rgba(255,255,255,.10)", zerolinecolor="rgba(255,255,255,.12)"),
    )
    return fig


def create_comparison_bar_chart(
    df_all: pd.DataFrame,
    df_player: pd.DataFrame,
    metrica: str,
    estadistico: str,
    jugador: str,
    posicion_jugador: str,
) -> pd.DataFrame:
    fechas = sorted(df_player["date"].dropna().unique())
    rows = []

    for fecha in fechas:
        df_fecha = df_all[df_all["date"] == fecha].copy()
        df_fecha_jugador = df_fecha[df_fecha["player"] == jugador].copy()
        df_fecha_posicion = df_fecha[df_fecha["position"] == posicion_jugador].copy()

        rows.append(
            {
                "date": fecha,
                "Jugador": aggregate_metric(df_fecha_jugador, metrica, estadistico),
                "Posición": aggregate_metric(df_fecha_posicion, metrica, estadistico),
                "Equipo": aggregate_metric(df_fecha, metrica, estadistico),
                "session_group": (
                    df_fecha_jugador["session_group"].iloc[0]
                    if not df_fecha_jugador.empty
                    else df_fecha["session_group"].iloc[0]
                ),
                "match_label": (
                    df_fecha_jugador["match_label"].dropna().iloc[0]
                    if not df_fecha_jugador.empty and "match_label" in df_fecha_jugador.columns and not df_fecha_jugador["match_label"].dropna().empty
                    else (
                        df_fecha["match_label"].dropna().iloc[0]
                        if "match_label" in df_fecha.columns and not df_fecha["match_label"].dropna().empty
                        else ""
                    )
                ),
            }
        )

    plot_df = pd.DataFrame(rows)
    if plot_df.empty:
        return plot_df

    plot_df = plot_df.sort_values("date")
    return plot_df


def create_comparison_bar_figure(plot_df: pd.DataFrame, metrica: str) -> go.Figure:
    if plot_df is None or plot_df.empty:
        return go.Figure()

    x_labels = plot_df["date"].dt.strftime("%d/%m")
    tick_text = []
    for _, row in plot_df.iterrows():
        label = row["date"].strftime("%d/%m")
        if row.get("session_group") == "Partido":
            tick_text.append(f"<span style='color:#FF5A5F'>{label}</span>")
        else:
            tick_text.append(label)

    series_config = [
        ("Equipo", "#4F8FCB"),
        ("Posición", "#F4B942"),
        ("Jugador", "#4DE0A8"),
    ]

    fig = go.Figure()
    for serie, color in series_config:
        fig.add_trace(
            go.Bar(
                x=x_labels,
                y=plot_df[serie],
                name=serie,
                marker=dict(
                    color=color,
                    line=dict(color="rgba(255,255,255,.18)", width=1),
                ),
                hovertemplate="%{x}<br>" + serie + ": %{y:.1f}<extra></extra>",
            )
        )

    fig.update_layout(
        height=360,
        margin=dict(l=20, r=20, t=25, b=20),
        template="plotly_dark",
        barmode="group",
        bargap=0.34,
        bargroupgap=0.16,
        xaxis_title="Fecha",
        yaxis_title=METRIC_LABELS.get(metrica, metrica),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#F6FAFF"),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#F6FAFF"),
        xaxis=dict(
            gridcolor="rgba(255,255,255,.08)",
            zerolinecolor="rgba(255,255,255,.10)",
            tickmode="array",
            tickvals=list(x_labels),
            ticktext=tick_text,
        ),
        yaxis=dict(gridcolor="rgba(255,255,255,.10)", zerolinecolor="rgba(255,255,255,.12)"),
    )
    return fig


def create_comparison_line_figure(plot_df: pd.DataFrame, metrica: str) -> go.Figure:
    if plot_df is None or plot_df.empty:
        return go.Figure()

    series_config = [
        ("Equipo", "#4F8FCB"),
        ("Posición", "#F4B942"),
        ("Jugador", "#4DE0A8"),
    ]

    fig = go.Figure()
    for serie, color in series_config:
        fig.add_trace(
            go.Scatter(
                x=plot_df["date"],
                y=plot_df[serie],
                mode="lines+markers",
                name=serie,
                line=dict(color=color, width=3),
                marker=dict(size=7),
                hovertemplate="%{x|%d/%m/%Y}<br>" + serie + ": %{y:.1f}<extra></extra>",
            )
        )

    matches_df = plot_df[plot_df["session_group"] == "Partido"].copy() if "session_group" in plot_df.columns else pd.DataFrame()
    if not matches_df.empty:
        fig.add_trace(
            go.Scatter(
                x=matches_df["date"],
                y=matches_df["Jugador"],
                mode="markers",
                name="Partido",
                marker=dict(
                    size=10,
                    color="#FF5A5F",
                    line=dict(width=1.5, color="#FFD6D6"),
                    symbol="diamond",
                ),
                customdata=matches_df[["match_label"]],
                hovertemplate="%{x|%d/%m/%Y}<br>%{customdata[0]}<br>Jugador: %{y:.1f}<extra></extra>",
            )
        )

        for _, row in matches_df.iterrows():
            etiqueta = row["match_label"] or "Partido"
            fig.add_vline(
                x=row["date"],
                line_dash="dash",
                line_color="#FF5A5F",
                line_width=1,
                opacity=0.7,
            )
            fig.add_annotation(
                x=row["date"],
                y=0.02,
                yref="paper",
                text=etiqueta,
                showarrow=False,
                textangle=-90,
                font=dict(size=9, color="#FF9EA0"),
                xanchor="left",
                yanchor="bottom",
                bgcolor="rgba(7,12,18,0.60)",
            )

    fig.update_layout(
        height=360,
        margin=dict(l=20, r=20, t=25, b=20),
        template="plotly_dark",
        hovermode="x unified",
        xaxis_title="Fecha",
        yaxis_title=METRIC_LABELS.get(metrica, metrica),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#F6FAFF"),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#F6FAFF"),
        xaxis=dict(gridcolor="rgba(255,255,255,.08)", zerolinecolor="rgba(255,255,255,.10)"),
        yaxis=dict(gridcolor="rgba(255,255,255,.10)", zerolinecolor="rgba(255,255,255,.12)"),
    )
    return fig


def create_ranking_chart(ranking: pd.DataFrame, metrica: str, jugador: str) -> go.Figure:
    top_n = ranking.head(15).copy()

    # Mantener el foco del usuario: si el jugador seleccionado cae fuera del top 15,
    # lo añadimos igualmente para que siempre aparezca en el ranking.
    if jugador not in top_n["player"].values:
        fila_jugador = ranking[ranking["player"] == jugador].head(1)
        if not fila_jugador.empty:
            top_n = pd.concat([top_n, fila_jugador], ignore_index=True)

    top = (
        top_n.drop_duplicates(subset=["player"], keep="last")
        .sort_values("valor", ascending=True)
    )
    colors = ["#6BEF9A" if p == jugador else "#2E86C1" for p in top["player"]]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=top["valor"],
            y=top["player"],
            orientation="h",
            marker_color=colors,
            text=top["valor"].map(lambda v: fmt_num(v)),
            textposition="outside",
            hovertemplate="%{y}<br>%{x:.1f}<extra></extra>",
        )
    )
    fig.update_layout(
        height=470,
        margin=dict(l=10, r=40, t=25, b=20),
        template="plotly_dark",
        xaxis_title=METRIC_LABELS.get(metrica, metrica),
        yaxis_title="",
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#F6FAFF"),
        xaxis=dict(gridcolor="rgba(255,255,255,.10)", zerolinecolor="rgba(255,255,255,.12)"),
        yaxis=dict(gridcolor="rgba(255,255,255,.10)", zerolinecolor="rgba(255,255,255,.12)"),
    )
    return fig


def main() -> None:
    if not st.session_state.get("autenticado", False):
        st.warning("⚠️ Por favor, inicia sesión desde la página principal")
        st.stop()

    render_sidebar()
    inject_css()

    st.markdown(
        """
        <div class="gps-hero">
            <div class="gps-kicker">CE Europa · GPS externo · Ubiko</div>
            <div class="gps-title">GPS UBIKO</div>
            <div class="gps-subtitle">
                Lectura profesional de carga por jugador con datos reales de sesiones: distancia total, distancia por minuto, HMLD, HSR y sprints. La página se integra como módulo nuevo sin alterar Equipo ni Individual.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df_session = st.session_state.get("df_procesado")
    if st.session_state.get("datos_cargados", False) and df_session is not None and not df_session.empty:
        ubiko_cache_key = (
            st.session_state.get("ultima_carga_drive"),
            len(df_session),
            tuple(df_session.columns),
        )
        if st.session_state.get("ubiko_dataset_cache_key") == ubiko_cache_key:
            df = st.session_state.get("ubiko_dataset_preparado", pd.DataFrame())
        else:
            df = prepare_ubiko_dataset(df_session)
            st.session_state.ubiko_dataset_preparado = df
            st.session_state.ubiko_dataset_cache_key = ubiko_cache_key
    else:
        df = load_ubiko_dataset()

    if df.empty:
        st.error("No se han encontrado CSV de Ubiko en Google Drive.")
        st.stop()

    metricas_disponibles = {k: v for k, v in METRICAS_UBIKO.items() if v in df.columns}
    if not metricas_disponibles:
        st.error("No hay métricas Ubiko disponibles en los CSV cargados.")
        st.stop()

    jugadores_sin_match = (
        df.loc[df["position_source"] == "csv_fallback", ["player", "position_csv"]]
        .drop_duplicates()
        .sort_values(["player", "position_csv"])
    )

    if not jugadores_sin_match.empty:
        st.warning(
            f"⚠️ {len(jugadores_sin_match)} jugador(es) siguen usando la posición del CSV porque no han enlazado con la plantilla de Drive."
        )
        with st.expander("Ver jugadores sin match con plantilla"):
            tabla_sin_match = jugadores_sin_match.rename(
                columns={
                    "player": "Jugador Ubiko",
                    "position_csv": "Posición CSV",
                }
            )
            st.dataframe(tabla_sin_match, use_container_width=True, hide_index=True)

    # ================================
    # CONTEXTO GLOBAL
    # Cards HTML centradas para controlar tamaño, alineación y evitar overflow.
    # ================================
    fecha_min = df["date"].min()
    fecha_max = df["date"].max()
    rango_corto = f"{fecha_min:%d/%m} - {fecha_max:%d/%m}"
    rango_largo = f"{fecha_min:%d/%m/%Y} - {fecha_max:%d/%m/%Y}"

    st.markdown(
        f"""
        <div class="gps-kpi-grid">
            <div class="gps-kpi-card-custom">
                <div class="gps-kpi-label-custom">Registros Ubiko</div>
                <div class="gps-kpi-value-custom">{f'{len(df):,}'.replace(',', '.')}</div>
            </div>
            <div class="gps-kpi-card-custom">
                <div class="gps-kpi-label-custom">Jugadores</div>
                <div class="gps-kpi-value-custom">{df['player'].nunique()}</div>
            </div>
            <div class="gps-kpi-card-custom">
                <div class="gps-kpi-label-custom">Sesiones</div>
                <div class="gps-kpi-value-custom">{df['source_file'].nunique()}</div>
            </div>
            <div class="gps-kpi-card-custom">
                <div class="gps-kpi-label-custom">Tipos</div>
                <div class="gps-kpi-value-custom">{df['session_group'].nunique()}</div>
            </div>
            <div class="gps-kpi-card-custom" title="{rango_largo}">
                <div class="gps-kpi-label-custom">Rango</div>
                <div class="gps-kpi-value-custom is-range">{rango_corto}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='gps-section-title'>Filtros de análisis</div>", unsafe_allow_html=True)

    # ================================
    # FILTROS
    # ================================
    jugadores = sorted(df["player"].dropna().astype(str).unique())
    posiciones = sorted(df["position"].dropna().astype(str).unique())
    tipos_sesion = sorted(df["session_group"].dropna().astype(str).unique(), key=lambda x: SESSION_ORDER.get(normalizar_texto(x), 99))
    tareas = sorted(df["task"].dropna().astype(str).unique())

    c1, c2, c3, c4 = st.columns([1.35, 1.15, 1, 1])
    jugador = c1.selectbox("Jugador", jugadores, index=0)
    metrica_nombre = c2.selectbox("Métrica", list(metricas_disponibles.keys()), index=0)
    metrica = metricas_disponibles[metrica_nombre]
    opciones_tipo_sesion = ["Todas", "Todas menos partido"] + tipos_sesion
    seleccion_tipos = c3.multiselect(
        "Tipo sesión",
        options=opciones_tipo_sesion,
        default=["Todas"],
        help="Puedes mantener una vista completa, excluir partidos o combinar los tipos de sesión que quieras.",
    )
    posicion = c4.selectbox("Posición", ["Todas"] + posiciones, index=0)

    d1, d2, d3, d4 = st.columns([1, 1, 1, 1])
    fecha_desde = d1.date_input("Desde", value=df["date"].min().date(), min_value=df["date"].min().date(), max_value=df["date"].max().date())
    fecha_hasta = d2.date_input("Hasta", value=df["date"].max().date(), min_value=df["date"].min().date(), max_value=df["date"].max().date())
    tarea = d3.selectbox("Task", ["Todas"] + tareas, index=0)
    estadistico = d4.selectbox("Estadístico", ["Media", "Máximo", "P70", "P95", "Sumatorio"], index=0)

    df_f_raw = df.copy()
    df_f_raw = df_f_raw[(df_f_raw["date"].dt.date >= fecha_desde) & (df_f_raw["date"].dt.date <= fecha_hasta)]

    seleccion_tipos = seleccion_tipos or ["Todas"]
    if "Todas" in seleccion_tipos:
        tipos_filtrados = tipos_sesion
    elif "Todas menos partido" in seleccion_tipos:
        tipos_filtrados = [tipo for tipo in tipos_sesion if normalizar_texto(tipo) != "partido"]
        extras = [tipo for tipo in seleccion_tipos if tipo not in {"Todas", "Todas menos partido"}]
        if extras:
            tipos_filtrados = sorted(
                set(tipos_filtrados).intersection(extras),
                key=lambda x: SESSION_ORDER.get(normalizar_texto(x), 99)
            )
    else:
        tipos_filtrados = [tipo for tipo in seleccion_tipos if tipo in tipos_sesion]

    if tipos_filtrados:
        df_f_raw = df_f_raw[df_f_raw["session_group"].isin(tipos_filtrados)]
    else:
        df_f_raw = df_f_raw.iloc[0:0]

    if posicion != "Todas":
        df_f_raw = df_f_raw[df_f_raw["position"] == posicion]
    if tarea != "Todas":
        df_f_raw = df_f_raw[df_f_raw["task"] == tarea]

    if df_f_raw.empty:
        st.warning("No hay datos con los filtros seleccionados.")
        st.stop()

    df_f = aggregate_session_rows(df_f_raw)
    df_j = df_f[df_f["player"] == jugador].copy()
    if df_j.empty:
        st.warning("El jugador seleccionado no tiene registros con los filtros actuales.")
        st.stop()

    valor_jugador = aggregate_metric(df_j, metrica, estadistico)
    valor_equipo = aggregate_metric(df_f, metrica, estadistico)
    df_ref_pos = df_f[df_f["position"].eq(df_j["position"].mode().iloc[0])] if not df_j["position"].mode().empty else df_f
    valor_posicion = aggregate_metric(df_ref_pos, metrica, estadistico)
    pct_equipo = ((valor_jugador / valor_equipo) - 1) * 100 if valor_equipo and not pd.isna(valor_equipo) else np.nan
    pct_pos = ((valor_jugador / valor_posicion) - 1) * 100 if valor_posicion and not pd.isna(valor_posicion) else np.nan
    p70_jugador = df_j[metrica].quantile(0.70)
    pico_jugador = df_j[metrica].max()
    posicion_jugador = df_j["position"].mode().iloc[0] if not df_j["position"].mode().empty else "Sin posición"
    foto_path = obtener_foto_jugador(jugador)

    st.markdown("<div class='gps-section-title'>Resumen ejecutivo del jugador</div>", unsafe_allow_html=True)

    c_foto, c_m1, c_m2, c_m3, c_m4, c_m5 = st.columns([0.9, 1, 1, 1, 1, 1])

    with c_foto:
        st.markdown('<div class="gps-player-card">', unsafe_allow_html=True)
        if foto_path:
            st.image(foto_path, use_container_width=True)
        st.markdown(
            f"""
            <div class="gps-player-name">{jugador}</div>
            <div class="gps-player-meta">{posicion_jugador}</div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    c_m1.metric(f"{estadistico} jugador", fmt_num(valor_jugador), metrica_nombre)
    c_m2.metric("Pico", fmt_num(pico_jugador), "máximo sesión")
    c_m3.metric("P70", fmt_num(p70_jugador), "umbral alto")
    c_m4.metric("% vs equipo", fmt_pct(pct_equipo), "referencia global")
    c_m5.metric("% vs posición", fmt_pct(pct_pos), "referencia específica")

    # ================================
    # VISUALES PRINCIPALES
    # ================================
    st.markdown("<div class='gps-section-title'>Evolución y ranking</div>", unsafe_allow_html=True)
    left, right = st.columns([1.25, 1])

    with left:
        st.plotly_chart(create_line_chart(df_j, metrica, jugador), use_container_width=True)

    ranking = (
        df_f.groupby(["player", "position"], as_index=False)
        .apply(lambda g: pd.Series({
            "valor": aggregate_metric(g, metrica, estadistico),
            "sesiones": len(g),
            "pico": g[metrica].max(),
            "p70": g[metrica].quantile(0.70),
        }))
        .dropna(subset=["valor"])
        .sort_values("valor", ascending=False)
    )
    ranking["rank"] = np.arange(1, len(ranking) + 1)
    ranking["% vs media"] = ((ranking["valor"] / ranking["valor"].mean()) - 1) * 100 if len(ranking) else np.nan

    with right:
        st.markdown(
            f"""
            <div class="gps-muted" style="margin-bottom:8px;">
                Ranking de referencia: se muestra el top 15 de la métrica seleccionada y, si hace falta,
                también el jugador elegido (<b>{jugador}</b>) para mantener la comparación visible.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.plotly_chart(create_ranking_chart(ranking, metrica, jugador), use_container_width=True)

    plot_df_comparison = create_comparison_bar_chart(
        df_f,
        df_j,
        metrica,
        estadistico,
        jugador,
        posicion_jugador,
    )
    comp_left, comp_right = st.columns([1.45, 1], gap="large")
    with comp_left:
        st.markdown(
            """
            <div class="gps-muted" style="margin:0 0 10px 2px;">
                Comparativa por fecha entre el jugador, la media de su posición y la referencia global del equipo.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            create_comparison_bar_figure(plot_df_comparison, metrica),
            use_container_width=True,
        )
    with comp_right:
        st.markdown(
            """
            <div class="gps-muted" style="margin:0 0 8px 2px;">
                Tendencia resumida de las tres referencias según el estadístico seleccionado.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            create_comparison_line_figure(plot_df_comparison, metrica),
            use_container_width=True,
        )

    # ================================
    # TABLAS PREMIUM
    # ================================
    st.markdown("<div class='gps-section-title'>Tabla de control por jugador</div>", unsafe_allow_html=True)

    tabla = ranking[["rank", "player", "position", "valor", "pico", "p70", "% vs media", "sesiones"]].copy()
    tabla = tabla.rename(columns={
        "rank": "#",
        "player": "Jugador",
        "position": "Posición",
        "valor": estadistico,
        "pico": "Pico",
        "p70": "P70",
        "% vs media": "% vs media",
        "sesiones": "Sesiones",
    })

    st.dataframe(
        tabla,
        use_container_width=True,
        hide_index=True,
        column_config={
            estadistico: st.column_config.NumberColumn(estadistico, format="%.1f"),
            "Pico": st.column_config.NumberColumn("Pico", format="%.1f"),
            "P70": st.column_config.NumberColumn("P70", format="%.1f"),
            "% vs media": st.column_config.NumberColumn("% vs media", format="%.1f%%"),
        },
    )

    st.markdown("<div class='gps-section-title'>Matriz multivariable Ubiko</div>", unsafe_allow_html=True)

    resumen = (
        df_f.groupby(["player", "position"], as_index=False)
        .agg(
            sesiones=("source_file", "nunique"),
            distancia_total_media=("total_distance", "mean"),
            distancia_min_media=("minute_distance", "mean"),
            hmld_media=("hmld", "mean"),
            hsr_media=("hsr", "mean"),
            sprints_media=("sprints", "mean"),
            pico_hsr=("hsr", "max"),
            pico_hmld=("hmld", "max"),
        )
        .sort_values("hsr_media", ascending=False)
    )

    for col in ["distancia_total_media", "distancia_min_media", "hmld_media", "hsr_media", "sprints_media"]:
        avg = resumen[col].mean()
        resumen[col.replace("_media", "_%equipo")] = (resumen[col] / avg) * 100 if avg else np.nan

    resumen = resumen.rename(columns={
        "player": "Jugador",
        "position": "Posición",
        "sesiones": "Sesiones",
        "distancia_total_media": "Distancia total media",
        "distancia_min_media": "Distancia/min media",
        "hmld_media": "HMLD media",
        "hsr_media": "HSR media",
        "sprints_media": "Sprints media",
        "pico_hsr": "Pico HSR",
        "pico_hmld": "Pico HMLD",
        "distancia_total_%equipo": "Distancia total % equipo",
        "distancia_min_%equipo": "Distancia/min % equipo",
        "hmld_%equipo": "HMLD % equipo",
        "hsr_%equipo": "HSR % equipo",
        "sprints_%equipo": "Sprints % equipo",
    })

    st.dataframe(resumen, use_container_width=True, hide_index=True)

    # ================================
    # LECTURA AUTOMÁTICA
    # ================================
    st.markdown("<div class='gps-section-title'>Lectura automática</div>", unsafe_allow_html=True)

    if pct_equipo >= 12:
        lectura = f"{jugador} presenta una carga claramente superior al grupo en {metrica_nombre}."
        foco = "Controlar acumulación si la tendencia se mantiene en las siguientes sesiones."
    elif pct_equipo <= -12:
        lectura = f"{jugador} queda por debajo de la referencia colectiva en {metrica_nombre}."
        foco = "Revisar si responde a minutaje, rol, retorno progresivo o necesidad de compensación."
    else:
        lectura = f"{jugador} se mueve cerca del baseline colectivo en {metrica_nombre}."
        foco = "Mantener seguimiento por tipo de sesión y comparar con su baseline individual."

    st.markdown(
        f"""
        <div class="gps-card">
            <div style="font-size:20px;font-weight:850;letter-spacing:-.02em;margin-bottom:6px;">{lectura}</div>
            <div style="font-size:14px;color:#A8B4C2;">
                Valor jugador: <b>{fmt_num(valor_jugador)}</b> · Referencia equipo: <b>{fmt_num(valor_equipo)}</b> · Referencia posición: <b>{fmt_num(valor_posicion)}</b> · Diferencia vs equipo: <b>{fmt_pct(pct_equipo)}</b>.<br>
                {foco}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Ver registros originales de Ubiko filtrados"):
        cols = ["source_file", "date", "session_group", "task", "position", "dorsal", "player"] + [c for c in METRICAS_UBIKO.values() if c in df_f_raw.columns]
        st.dataframe(df_f_raw[cols].sort_values(["date", "player"]), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
