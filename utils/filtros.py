"""
Módulo de filtros reutilizables para todas las páginas
"""

import streamlit as st
import pandas as pd
from datetime import timedelta
import re
import unicodedata
from utils import filtrar_por_fechas


def _normalizar_texto(valor):
    if pd.isna(valor):
        return ""
    txt = str(valor).strip().lower()
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    txt = re.sub(r"[^a-z0-9]+", " ", txt)
    return txt.strip()


def es_partido(row):
    session_txt = _normalizar_texto(row.get("session", ""))
    task_txt = _normalizar_texto(row.get("task", ""))
    combinado = f"{session_txt} {task_txt}".strip()

    if re.search(
        r"\b(entrenamiento|entrenamientos|entreno|training|gym|gimnasio|"
        r"gimnasia|reco|recovery|activacion)\b",
        combinado,
    ):
        return False

    return bool(
        re.search(r"\b(j\s*\d+|jornada\s*\d+)\b", combinado)
        or re.search(
            r"\b(amistoso|amistosos|pretemporada|preseason|pre\s+season|"
            r"friendly|friendlies|test|trofeo|trofeos|torneo|torneos|"
            r"copa|copas|liga|league)\b",
            combinado,
        )
    )


def clasificar_tramo_partido(task):
    task_txt = _normalizar_texto(task)
    task_compacto = task_txt.replace(" ", "")

    if re.search(r"\btotal\b", task_txt):
        return "Total"

    tiene_token_parte = re.search(
        r"\b(parte|part|periodo|period|half|mitad|temps|tiempo)\b",
        task_txt,
    ) is not None
    es_primera = re.search(
        r"\b(1|1a|1r|1st|p1|primera|primer|first)\b",
        task_txt,
    ) is not None
    es_segunda = re.search(
        r"\b(2|2a|2n|2nd|p2|segunda|segundo|second)\b",
        task_txt,
    ) is not None
    primera_compacta = any(
        token in task_compacto
        for token in [
            "1apart", "part1", "parte1", "periodo1", "period1", "half1",
            "mitad1", "primertemps", "primerapart", "p1"
        ]
    ) or "firsthalf" in task_compacto
    segunda_compacta = any(
        token in task_compacto
        for token in [
            "2apart", "part2", "parte2", "periodo2", "period2", "half2",
            "mitad2", "segontemps", "segundapart", "p2"
        ]
    ) or "secondhalf" in task_compacto

    if (es_primera and tiene_token_parte) or primera_compacta:
        return "1ª parte"
    if (es_segunda and tiene_token_parte) or segunda_compacta:
        return "2ª parte"
    return None


def filtrar_solo_partidos(df):
    if df is None or len(df) == 0:
        return df
    partidos_validos = df.apply(es_partido, axis=1)
    tareas_validas = df["task"].map(clasificar_tramo_partido).notna()
    return df[partidos_validos & tareas_validas].copy()


def render_filtro_partidos(
    df,
    titulo="🎯 Filtros de Partido",
    incluir_rango_fechas=True,
):
    """
    Renderiza el filtro de partidos independiente para cada página
    ...
    """
    
    if incluir_rango_fechas:
        # Respetar el rango global solo en las páginas que lo habilitan.
        if 'fecha_desde' not in st.session_state or st.session_state.fecha_desde is None:
            st.session_state.fecha_desde = pd.to_datetime(df['date'].min())
        if 'fecha_hasta' not in st.session_state or st.session_state.fecha_hasta is None:
            st.session_state.fecha_hasta = pd.to_datetime(df['date'].max())
        df_rango = filtrar_por_fechas(
            df,
            st.session_state.fecha_desde,
            st.session_state.fecha_hasta,
        )
    else:
        df_rango = df.copy()
    
    # Sólo ofrecer fechas válidas que tengan filas tras los filtros aplicados.
    df_rango = df_rango.copy()
    df_rango['date'] = pd.to_datetime(df_rango['date'], errors='coerce')
    df_rango = df_rango.dropna(subset=['date'])
    fechas_disponibles = sorted(df_rango['date'].unique())
    
    if len(fechas_disponibles) == 0:
        st.error("⚠️ No hay partidos disponibles en el rango seleccionado")
        st.stop()
    
    # ========================================
    # INTERFAZ DE FILTROS
    # ========================================
    
    st.subheader(titulo)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        modo_partido = st.radio(
            "Modo de selección:",
            options=(
                ['Partido Específico', 'Últimos N partidos', 'Rango de Fechas']
                if incluir_rango_fechas
                else ['Partido Específico', 'Últimos N partidos']
            ),
            key='modo_partido_filtro'
        )
    
    with col2:
        if modo_partido == 'Partido Específico':
            partido_sel = st.selectbox(
                "Seleccionar partido:",
                options=fechas_disponibles,
                index=len(fechas_disponibles)-1,
                format_func=lambda x: x.strftime('%d/%m/%Y'),
                key='partido_especifico_filtro'
            )
            df_filtrado = df_rango[df_rango['date'] == partido_sel].copy()
            
            info_dict = {
                'partido_seleccionado': partido_sel,
                'n_partidos': 1,
                'fecha_inicio': partido_sel,
                'fecha_fin': partido_sel
            }
            
        elif modo_partido == 'Últimos N partidos':
            max_partidos = min(10, len(fechas_disponibles))
            n_partidos = st.selectbox(
                "Últimos N partidos:",
                options=list(range(1, max_partidos + 1)),
                index=min(2, max_partidos - 1),
                key='n_partidos_filtro'
            )
            fechas_recientes = fechas_disponibles[-n_partidos:]
            df_filtrado = df_rango[df_rango['date'].isin(fechas_recientes)].copy()
            
            info_dict = {
                'n_partidos': len(fechas_recientes),
                'fecha_inicio': fechas_recientes[0],
                'fecha_fin': fechas_recientes[-1],
                'fechas_incluidas': fechas_recientes
            }
            
        else:  # Rango de Fechas
            fecha_min = df_rango['date'].min()
            fecha_max = df_rango['date'].max()
            
            fecha_inicio = st.date_input(
                "Fecha inicio:",
                value=fecha_max - timedelta(days=30),
                min_value=fecha_min,
                max_value=fecha_max,
                key='fecha_inicio_filtro'
            )
            df_filtrado = df_rango[df_rango['date'] >= pd.to_datetime(fecha_inicio)].copy()
            
            info_dict = {
                'fecha_inicio': pd.to_datetime(fecha_inicio),
                'n_partidos': len(df_filtrado['date'].unique())
            }
    
    with col3:
        if modo_partido == 'Rango de Fechas':
            fecha_min = df_rango['date'].min()
            fecha_max = df_rango['date'].max()
            
            fecha_fin = st.date_input(
                "Fecha fin:",
                value=fecha_max,
                min_value=fecha_min,
                max_value=fecha_max,
                key='fecha_fin_filtro'
            )
            df_filtrado = df_filtrado[df_filtrado['date'] <= pd.to_datetime(fecha_fin)].copy()
            
            info_dict['fecha_fin'] = pd.to_datetime(fecha_fin)
            info_dict['n_partidos'] = len(df_filtrado['date'].unique())
        
        # Métrica de resumen
        st.metric(
            "Partidos seleccionados",
            info_dict.get('n_partidos', len(df_filtrado['date'].unique()))
        )
    
    st.markdown("---")
    
    return df_filtrado, modo_partido, info_dict
