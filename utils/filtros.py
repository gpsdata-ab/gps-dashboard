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
    txt = str(valor or "").strip().lower()
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    txt = re.sub(r"[^a-z0-9]+", " ", txt)
    return txt.strip()


def es_partido(row):
    session_txt = _normalizar_texto(row.get("session", ""))
    task_txt = _normalizar_texto(row.get("task", ""))
    combinado = f"{session_txt} {task_txt}".strip()

    if re.search(r"\bj\d+\b", session_txt):
        return True
    if "san luqueno" in session_txt:
        return True
    if re.search(r"\b(partido|match|game)\b", combinado):
        return True
    if re.search(r"\b(periodo|parte|half|mitad|temps|tiempo)\b", task_txt):
        return True
    return False


def filtrar_solo_partidos(df):
    if df is None or len(df) == 0:
        return df
    return df[df.apply(es_partido, axis=1)].copy()


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
    
    # Obtener fechas disponibles
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
            n_partidos = st.selectbox(
                "Últimos N partidos:",
                options=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                index=2,  # Default: 3
                key='n_partidos_filtro'
            )
            fechas_recientes = fechas_disponibles[-n_partidos:]
            df_filtrado = df_rango[df_rango['date'].isin(fechas_recientes)].copy()
            
            info_dict = {
                'n_partidos': n_partidos,
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
