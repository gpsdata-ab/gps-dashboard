"""
Página: Análisis de partidos
Vista general y comparativa del rendimiento
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import re
import unicodedata
import sys
from pathlib import Path

# Añadir directorio raíz al path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from config import PAGE_TITLE, PAGE_ICON, LAYOUT, COLORES, METRICAS_DICT
from utils import (
    render_sidebar,
    cargar_plantilla_europa,
    mapear_posicion,
    obtener_foto_jugador
)
from utils.filtros import (
    clasificar_tramo_partido,
    render_filtro_partidos,
    filtrar_solo_partidos,
)

# Configuración
st.set_page_config(
    page_title=f"{PAGE_TITLE} - Análisis de partidos",
    page_icon=PAGE_ICON,
    layout=LAYOUT,
    initial_sidebar_state="collapsed"
)


def normalizar_texto(valor):
    if pd.isna(valor):
        return ""
    txt = str(valor).strip().lower()
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    txt = re.sub(r"[^a-z0-9]+", " ", txt)
    return txt.strip()


def clasificar_tramo(row):
    return clasificar_tramo_partido(row.get('task')) or 'Total'


def main():
    # ==========================================
    # AUTENTICACIÓN
    # ==========================================
    if not st.session_state.get('autenticado', False):
        st.warning("⚠️ Por favor, inicia sesión desde la página principal")
        st.stop()
    
    # ==========================================
    # SIDEBAR
    # ==========================================
    render_sidebar()
    
    st.title("📊 Análisis de partidos")
    
    # ==========================================
    # VERIFICAR DATOS
    # ==========================================
    if not st.session_state.get('datos_cargados', False):
        st.warning("⚠️ No hay datos cargados")
        st.stop()
    
    df = st.session_state.get('df_procesado')
    if df is None or len(df) == 0:
        st.error("⚠️ Error: datos no disponibles")
        st.stop()
    
    # ========================================
    # FILTRO DE PARTIDOS
    # ========================================
    df_partidos = filtrar_solo_partidos(df)
    if df_partidos is not None and len(df_partidos) > 0:
        df_partidos = df_partidos.copy()
        df_partidos['date'] = pd.to_datetime(df_partidos['date'], errors='coerce')
        df_partidos = (
            df_partidos.sort_values('date', kind='stable')
            .copy()
        )
    if df_partidos is None or len(df_partidos) == 0:
        st.warning("⚠️ No se han identificado partidos en los datos cargados.")
        st.stop()

    df_partidos['tramo_partido'] = df_partidos.apply(clasificar_tramo, axis=1)
    st.markdown("## ⚙️ Configuración del Análisis")
    filtro_parte = st.selectbox(
        "⏱️ Tramo de partido:",
        options=[
            "Total",
            "1ª parte",
            "2ª parte",
            "1ª y 2ª parte",
        ],
        key="filtro_parte_analisis",
        help="Total, primera parte, segunda parte o ambas partes."
    )

    df_partidos_selector = df_partidos[
        df_partidos['player'].notna()
        & df_partidos['player'].astype(str).str.strip().ne('')
        & df_partidos['player'].astype(str).ne('0')
    ].copy()
    if filtro_parte == "Total":
        df_tramo_selector = df_partidos_selector[
            df_partidos_selector['tramo_partido'] == 'Total'
        ]
        if len(df_tramo_selector) == 0:
            df_tramo_selector = df_partidos_selector
    elif filtro_parte == "1ª parte":
        df_tramo_selector = df_partidos_selector[
            df_partidos_selector['tramo_partido'] == '1ª parte'
        ]
    elif filtro_parte == "2ª parte":
        df_tramo_selector = df_partidos_selector[
            df_partidos_selector['tramo_partido'] == '2ª parte'
        ]
    else:
        df_tramo_selector = df_partidos_selector[
            df_partidos_selector['tramo_partido'].isin(['1ª parte', '2ª parte'])
        ]
    if len(df_tramo_selector) == 0:
        st.warning("⚠️ No hay datos para el tramo de partido seleccionado.")
        st.stop()

    df_filtrado, modo_partido, info_filtro = render_filtro_partidos(
        df_tramo_selector,
        titulo="🎯 Filtros de Partido",
        incluir_rango_fechas=False,
    )
    
    st.markdown("---")
    
    # ========================================
    # CONFIGURACIÓN DEL ANÁLISIS
    # ========================================
    col1, col2, col3 = st.columns(3)
    
    with col1:
        nivel_analisis = st.selectbox(
            "📊 Nivel de análisis:",
            options=['Equipo', 'Individual', 'Por posiciones'],
            key='nivel_analisis',
            help="Equipo: Promedio del equipo por partido\nIndividual: Analizar uno o varios jugadores\nPor posiciones: Comparar posiciones"
        )
    
    with col2:
        # Métricas disponibles
        metricas_disponibles = {k: v for k, v in METRICAS_DICT.items() if v in df_filtrado.columns}
        
        if len(metricas_disponibles) == 0:
            st.error("❌ No hay métricas disponibles")
            st.stop()
        
        metrica_nombre = st.selectbox(
            "📈 Métrica:",
            options=list(metricas_disponibles.keys()),
            key='metrica_analisis'
        )
        metrica_col = METRICAS_DICT[metrica_nombre]
    
    with col3:
        opciones_estadistico = ['Media', 'Máxima', 'Sumatorio']

        estadistico = st.selectbox(
            "📊 Estadístico:",
            options=opciones_estadistico,
            key='estadistico_analisis',
            help="Media: Promedio\nMáxima: Valor más alto\nSumatorio: Suma de valores"
        )

    mostrar_tendencia_lineal = st.checkbox(
        "Mostrar línea de tendencia lineal",
        value=True,
        key="mostrar_tendencia_equipo",
        help="Añade una línea discontinua para facilitar la lectura (sube, baja o estable)."
    )

    st.markdown("---")
    
    # ========================================
    # SELECCIÓN ESPECÍFICA SEGÚN NIVEL
    # ========================================
    
    # Limpiar datos inválidos
    df_limpio = df_filtrado.copy()
    df_limpio = df_limpio[df_limpio['player'].notna()]
    df_limpio = df_limpio[df_limpio['player'].astype(str).str.strip() != '']
    df_limpio = df_limpio[df_limpio['player'].astype(str) != '0']
    df_limpio_base = df_limpio.copy()

    df_limpio['tramo_partido'] = df_limpio.apply(clasificar_tramo, axis=1)

    # Aplicar filtro de tramo.
    if filtro_parte == "Total":
        df_limpio = df_limpio[df_limpio['tramo_partido'] == 'Total']
        if len(df_limpio) == 0:
            # Fallback: si los datos no traen task='Total', usar todo el dataset filtrado.
            df_limpio = df_limpio_base.copy()
    elif filtro_parte == "1ª parte":
        df_limpio = df_limpio[df_limpio['tramo_partido'] == '1ª parte']
    elif filtro_parte == "2ª parte":
        df_limpio = df_limpio[df_limpio['tramo_partido'] == '2ª parte']
    elif filtro_parte == "1ª y 2ª parte":
        df_limpio = df_limpio[df_limpio['tramo_partido'].isin(['1ª parte', '2ª parte'])].copy()

    if len(df_limpio) == 0:
        st.warning("⚠️ No hay datos para el tramo de partido seleccionado.")
        st.stop()
    df_tramo = df_limpio.copy()
    posiciones_seleccionadas = []
    jugadores_seleccionados = []
    df_plantilla_cache = None

    def normalizar_posicion(valor):
        posicion = normalizar_texto(valor)
        grupos_posicion = {
            'Centrocampista': {
                'centrocampista', 'centrocampistas', 'mediocampista',
                'mediocampistas', 'medio', 'mc', 'med',
            },
            'Defensa': {
                'defensa', 'defensas', 'defender', 'def',
                'dfc', 'ld', 'li', 'lateral', 'laterales',
                'lateral derecho', 'lateral izquierdo',
            },
            'Delantero': {
                'delantero', 'delanteros', 'forward', 'del',
                'dc', 'ed', 'ei',
            },
        }
        for grupo, alias in grupos_posicion.items():
            if posicion in alias:
                return grupo
        return 'Sin posición'

    def obtener_df_con_posiciones(df_input):
        nonlocal df_plantilla_cache
        df_out = df_input.copy()
        try:
            if df_plantilla_cache is None:
                df_plantilla_cache = cargar_plantilla_europa()
        except (FileNotFoundError, ValueError) as error:
            st.warning(
                f"⚠️ No se pudo cargar la plantilla de posiciones: {error}. "
                "Se usará la posición del archivo GPS."
            )
            df_plantilla_cache = None

        position_columns = [
            column for column in ('posicion', 'position')
            if column in df_out.columns
        ]
        fallback_positions = (
            df_out[position_columns[0]].map(normalizar_posicion)
            if position_columns
            else pd.Series('Sin posición', index=df_out.index)
        )

        # The shared loader already applies the authoritative roster mapping.
        if 'position' in df_out.columns and df_out['position'].notna().any():
            df_out['posicion'] = df_out['position'].map(normalizar_posicion)
            return df_out

        if df_plantilla_cache is None or 'player' not in df_out.columns:
            df_out['posicion'] = fallback_positions
            return df_out

        plantilla_positions = df_out['player'].apply(
            lambda player: normalizar_posicion(
                mapear_posicion(str(player).strip(), df_plantilla_cache)
            )
            if pd.notna(player) and str(player).strip()
            else 'Sin posición'
        )
        df_out['posicion'] = plantilla_positions.where(
            plantilla_positions.ne('Sin posición'),
            fallback_positions,
        )
        return df_out
    
    if nivel_analisis == 'Por posiciones':
        st.markdown("### 🎯 Seleccionar Posiciones")
        
        # Cargar plantilla para mapear posiciones
        df_limpio = obtener_df_con_posiciones(df_limpio)
        
        posiciones_seleccionadas = st.multiselect(
            "Selecciona posiciones:",
            options=['Defensa', 'Centrocampista', 'Delantero'],
            default=['Defensa', 'Centrocampista', 'Delantero'],
            key='posiciones_seleccionadas'
        )
        
        if len(posiciones_seleccionadas) == 0:
            st.warning("⚠️ Selecciona al menos una posición")
            st.stop()
        
        df_limpio = df_limpio[df_limpio['posicion'].isin(posiciones_seleccionadas)]
        
        if len(df_limpio) == 0:
            st.warning("⚠️ No hay datos para las posiciones seleccionadas")
            st.stop()
    elif nivel_analisis == 'Individual':
        st.markdown("### 👤 Seleccionar jugadores")

        jugadores_disponibles = sorted(df_limpio['player'].astype(str).unique())
        jugadores_seleccionados = st.multiselect(
            "Selecciona jugadores:",
            options=jugadores_disponibles,
            default=jugadores_disponibles[:1],
            key='jugadores_analisis'
        )
        if len(jugadores_seleccionados) == 0:
            st.warning("⚠️ Selecciona al menos un jugador")
            st.stop()
        df_limpio = df_limpio[df_limpio['player'].astype(str).isin(jugadores_seleccionados)]
    
    st.markdown("---")
    
    # ========================================
    # PREPARAR DATOS PARA EL GRÁFICO
    # ========================================
    
    # Función auxiliar para calcular estadístico
    def calcular_estadistico(valores, tipo):
        if tipo == 'Media':
            return valores.mean()
        elif tipo == 'Máxima':
            return valores.max()
        elif tipo == 'Sumatorio':
            return valores.sum()
        return valores.mean()
    
    def aplicar_filtro_minutos(df_in, nivel_analisis_local):
        # Regla >60' solo para vista TOTAL en Equipo/Posiciones.
        # En mitades, aplicar >60' vacía el resultado (minutos por tramo suelen ser <60).
        if nivel_analisis_local in ['Equipo', 'Por posiciones'] and filtro_parte == "Total":
            return df_in[df_in['time'] > 60]
        return df_in

    def construir_datos_grafico(
        metrica_objetivo,
        nivel_analisis_local=None,
        df_base_local=None,
        posiciones_sel=None,
        jugadores_sel=None,
    ):
        nivel_local = nivel_analisis_local or nivel_analisis
        df_base = df_base_local.copy() if df_base_local is not None else df_limpio.copy()
        posiciones_sel = posiciones_sel if posiciones_sel is not None else posiciones_seleccionadas
        jugadores_sel = jugadores_sel if jugadores_sel is not None else jugadores_seleccionados
        fechas_disponibles_local = sorted(df_base['date'].unique())
        datos = []

        if nivel_local == 'Equipo':
            # Una barra por partido (estadístico del equipo completo)
            for fecha in fechas_disponibles_local:
                df_fecha_base = df_base[df_base['date'] == fecha]
                subgrupos = [("general", df_fecha_base)]
                if filtro_parte == "1ª y 2ª parte" and 'tramo_partido' in df_fecha_base.columns:
                    subgrupos = list(df_fecha_base.groupby('tramo_partido'))

                for tramo_key, df_fecha in subgrupos:
                    df_fecha = aplicar_filtro_minutos(df_fecha, nivel_local)
                    if len(df_fecha) == 0:
                        continue

                    valor = calcular_estadistico(df_fecha[metrica_objetivo], estadistico)
                    minutaje_promedio = df_fecha['time'].mean()
                    nombre_serie = 'Equipo'
                    if filtro_parte == "1ª y 2ª parte":
                        nombre_serie = f"Equipo - {tramo_key}"

                    datos.append({
                        'fecha': fecha,
                        'nombre': nombre_serie,
                        'valor': valor,
                        'minutaje': minutaje_promedio,
                        'color': COLORES['primario'],
                        'grupo': nombre_serie
                    })

        elif nivel_local == 'Individual':
            colores_individuales = ['#1E88E5', '#FF6F00', '#43A047', '#E53935', '#8E24AA', '#00ACC1']

            for idx, jugador in enumerate(jugadores_sel):
                for fecha in fechas_disponibles_local:
                    df_jug_fecha_base = df_base[
                        (df_base['player'] == jugador) &
                        (df_base['date'] == fecha)
                    ]
                    subgrupos = [("general", df_jug_fecha_base)]
                    if filtro_parte == "1ª y 2ª parte" and 'tramo_partido' in df_jug_fecha_base.columns:
                        subgrupos = list(df_jug_fecha_base.groupby('tramo_partido'))

                    for tramo_key, df_jug_fecha in subgrupos:
                        if len(df_jug_fecha) == 0:
                            continue
                        valor = calcular_estadistico(df_jug_fecha[metrica_objetivo], estadistico)
                        nombre_serie = jugador
                        if filtro_parte == "1ª y 2ª parte":
                            nombre_serie = f"{jugador} - {tramo_key}"

                        datos.append({
                            'fecha': fecha,
                            'nombre': nombre_serie,
                            'valor': valor,
                            'minutaje': df_jug_fecha['time'].mean(),
                            'color': colores_individuales[idx % len(colores_individuales)],
                            'grupo': nombre_serie
                        })

        elif nivel_local == 'Por posiciones':
            colores_posicion = {
                'Defensa': '#ef4444',
                'Centrocampista': '#3b82f6',
                'Delantero': '#22c55e'
            }

            colores_individuales = ['#1E88E5', '#FF6F00', '#43A047', '#E53935', '#8E24AA', '#00ACC1']

            if len(posiciones_sel) == 1:
                # UNA SOLA POSICIÓN: barras por jugador
                jugadores_posicion = sorted(df_base['player'].unique())

                for idx, jugador in enumerate(jugadores_posicion):
                    for fecha in fechas_disponibles_local:
                        df_jug_fecha_base = df_base[
                            (df_base['player'] == jugador) &
                            (df_base['date'] == fecha)
                        ]
                        subgrupos = [("general", df_jug_fecha_base)]
                        if filtro_parte == "1ª y 2ª parte" and 'tramo_partido' in df_jug_fecha_base.columns:
                            subgrupos = list(df_jug_fecha_base.groupby('tramo_partido'))

                        for tramo_key, df_jug_fecha in subgrupos:
                            df_jug_fecha = aplicar_filtro_minutos(df_jug_fecha, nivel_local)
                            if len(df_jug_fecha) == 0:
                                continue
                            valor = calcular_estadistico(df_jug_fecha[metrica_objetivo], estadistico)
                            minutaje = df_jug_fecha['time'].mean()
                            nombre_serie = jugador
                            if filtro_parte == "1ª y 2ª parte":
                                nombre_serie = f"{jugador} - {tramo_key}"

                            datos.append({
                                'fecha': fecha,
                                'nombre': nombre_serie,
                                'valor': valor,
                                'minutaje': minutaje,
                                'color': colores_individuales[idx % len(colores_individuales)],
                                'grupo': nombre_serie
                            })
            else:
                # MÚLTIPLES POSICIONES: barras por posición
                for posicion in posiciones_sel:
                    for fecha in fechas_disponibles_local:
                        df_pos_fecha_base = df_base[
                            (df_base['posicion'] == posicion) &
                            (df_base['date'] == fecha)
                        ]
                        subgrupos = [("general", df_pos_fecha_base)]
                        if filtro_parte == "1ª y 2ª parte" and 'tramo_partido' in df_pos_fecha_base.columns:
                            subgrupos = list(df_pos_fecha_base.groupby('tramo_partido'))

                        for tramo_key, df_pos_fecha in subgrupos:
                            df_pos_fecha = aplicar_filtro_minutos(df_pos_fecha, nivel_local)
                            if len(df_pos_fecha) == 0:
                                continue
                            valor = calcular_estadistico(df_pos_fecha[metrica_objetivo], estadistico)
                            minutaje_promedio = df_pos_fecha['time'].mean()
                            nombre_serie = posicion
                            if filtro_parte == "1ª y 2ª parte":
                                nombre_serie = f"{posicion} - {tramo_key}"

                            datos.append({
                                'fecha': fecha,
                                'nombre': nombre_serie,
                                'valor': valor,
                                'minutaje': minutaje_promedio,
                                'color': colores_posicion[posicion],
                                'grupo': nombre_serie
                            })

        return datos

    def preparar_df_grafico(datos):
        df_out = pd.DataFrame(datos)
        df_out['fecha'] = pd.to_datetime(df_out['fecha'])
        sesiones_por_fecha = (
            df_limpio[['date', 'session']]
            .dropna(subset=['date'])
            .assign(date=lambda x: pd.to_datetime(x['date']))
            .sort_values('date')
            .groupby('date', as_index=False)['session']
            .first()
        )
        mapa_sesion = {
            pd.to_datetime(row['date']): str(row['session']).strip()
            for _, row in sesiones_por_fecha.iterrows()
            if pd.notna(row['session']) and str(row['session']).strip() != ''
        }

        df_out['session_label'] = df_out['fecha'].map(mapa_sesion).fillna('')
        df_out['fecha_base'] = df_out['fecha'].dt.strftime('%d/%m')
        df_out['fecha_label'] = np.where(
            df_out['session_label'].str.strip() != '',
            df_out['session_label'] + ' - ' + df_out['fecha_base'],
            df_out['fecha_base']
        )
        df_out['fecha_full'] = np.where(
            df_out['session_label'].str.strip() != '',
            df_out['session_label'] + ' - ' + df_out['fecha'].dt.strftime('%d/%m/%Y'),
            df_out['fecha'].dt.strftime('%d/%m/%Y')
        )
        return df_out

    # Crear datos del gráfico para la métrica principal
    datos_grafico = construir_datos_grafico(metrica_col)
    
    if len(datos_grafico) == 0:
        st.warning("⚠️ No hay datos para mostrar con la configuración actual")
        st.stop()
    
    df_grafico = preparar_df_grafico(datos_grafico)
    
    def crear_figura_plotly(df_grafico_plot, metrica_nombre_plot, mostrar_tendencia=False):
        orden_fechas_plot = (
            df_grafico_plot[['fecha', 'fecha_label']]
            .drop_duplicates()
            .sort_values('fecha')
        )
        orden_labels_plot = orden_fechas_plot['fecha_label'].tolist()

        fig_plot = go.Figure()
        df_local = df_grafico_plot.copy()
        df_local["trend"] = np.nan

        def extraer_base_y_tramo(nombre_serie):
            partes = str(nombre_serie).rsplit(" - ", 1)
            if len(partes) == 2 and partes[1] in ["1ª parte", "2ª parte"]:
                return partes[0], partes[1]
            return str(nombre_serie), None

        # Orden descendente por valor y, en modo separadas, emparejar 1ª/2ª por entidad.
        if filtro_parte == "1ª y 2ª parte":
            df_orden = df_local.copy()
            df_orden[["base", "tramo"]] = df_orden["nombre"].apply(
                lambda n: pd.Series(extraer_base_y_tramo(n))
            )
            orden_base = (
                df_orden.groupby("base")["valor"]
                .mean()
                .sort_values(ascending=False)
                .index
                .tolist()
            )
            idx_base = {b: i for i, b in enumerate(orden_base)}
            idx_tramo = {"1ª parte": 0, "2ª parte": 1, None: 2}

            series_unicas = sorted(
                df_local["nombre"].unique().tolist(),
                key=lambda n: (
                    idx_base.get(extraer_base_y_tramo(n)[0], 999),
                    idx_tramo.get(extraer_base_y_tramo(n)[1], 2),
                ),
            )
            orden_series = series_unicas
        else:
            orden_series = (
                df_local.groupby('nombre')['valor']
                .mean()
                .sort_values(ascending=False)
                .index
                .tolist()
            )

        for nombre in orden_series:
            df_grupo = df_local[df_local['nombre'] == nombre].sort_values('fecha').copy()

            if mostrar_tendencia and len(df_grupo) >= 2:
                y_vals = df_grupo["valor"].astype(float).values
                x_idx = np.arange(len(df_grupo))
                coef = np.polyfit(x_idx, y_vals, 1)
                df_grupo["trend"] = coef[0] * x_idx + coef[1]

            fig_plot.add_trace(go.Bar(
                x=df_grupo['fecha_label'],
                y=df_grupo['valor'],
                name=nombre,
                marker_color=df_grupo['color'].iloc[0],
                hovertemplate=(
                    '<b>%{customdata[0]}</b><br>' +
                    f'{nombre}<br>' +
                    f'{metrica_nombre_plot}: %{{y:.1f}}<br>' +
                    '<extra></extra>'
                ),
                customdata=df_grupo[['fecha_full']].to_numpy()
            ))

            if mostrar_tendencia and df_grupo["trend"].notna().any():
                fig_plot.add_trace(go.Scatter(
                    x=df_grupo['fecha_label'],
                    y=df_grupo['trend'],
                    mode='lines',
                    name=f'{nombre} (tendencia)',
                    line=dict(color=df_grupo['color'].iloc[0], width=2, dash='dash'),
                    hovertemplate=(
                        '<b>%{x}</b><br>' +
                        f'{nombre} tendencia: %{{y:.1f}}<extra></extra>'
                    ),
                    showlegend=(nivel_analisis != 'Equipo')
                ))

        titulo_grafico_plot = f"{estadistico} de {metrica_nombre_plot} - {nivel_analisis}"
        valor_max_plot = float(df_grafico_plot['valor'].max())
        valor_min_plot = float(df_grafico_plot['valor'].min())
        margen_superior_plot = max(valor_max_plot * 0.12, 20.0)

        fig_plot.update_layout(
            title=titulo_grafico_plot,
            xaxis_title="Fecha del Partido",
            yaxis_title=f"{metrica_nombre_plot} ({estadistico})",
            height=600,
            barmode='group',
            bargap=0.45,
            bargroupgap=0.12,
            hovermode='x unified',
            margin=dict(t=95),
            xaxis=dict(
                type='category',
                categoryorder='array',
                categoryarray=orden_labels_plot,
                tickangle=-45
            ),
            yaxis=dict(
                range=[min(0, valor_min_plot), valor_max_plot + margen_superior_plot]
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            showlegend=(nivel_analisis != 'Equipo')
        )
        return fig_plot
    
    # ========================================
    # GRÁFICO DE BARRAS
    # ========================================
    
    st.markdown(f"## 📊 {estadistico} de {metrica_nombre}")
    fig = crear_figura_plotly(df_grafico, metrica_nombre, mostrar_tendencia=mostrar_tendencia_lineal)
    
    st.plotly_chart(fig, use_container_width=True)

    # ========================================
    # TABLA DE DATOS
    # ========================================
    
    with st.expander("📋 Ver tabla de datos"):
        df_tabla = df_grafico.copy()
        df_tabla['fecha'] = df_tabla['fecha'].dt.strftime('%d/%m/%Y')
        df_tabla['minutaje'] = df_tabla['minutaje'].round(0).astype(int)
        df_tabla['valor'] = df_tabla['valor'].round(1)
        
        df_tabla = df_tabla[['fecha', 'nombre', 'valor', 'minutaje']]
        df_tabla.columns = ['Fecha', 'Nombre', f'{metrica_nombre} ({estadistico})', 'Minutos']
        
        st.dataframe(
            df_tabla,
            use_container_width=True,
            hide_index=True
        )

    return

    # ========================================
    # Exportación de informes eliminada de la interfaz.
    # ========================================
    st.markdown("---")
    st.subheader("📄 Informe PDF")
    st.caption("El informe usa los filtros actuales de partidos y tramo. Aquí puedes decidir qué bloques incluir.")

    incluir_bloque_equipo_pdf = st.checkbox(
        "Incluir bloque Equipo",
        key="incluir_bloque_equipo_pdf",
        value=(nivel_analisis == "Equipo")
    )

    metricas_equipo_pdf = []
    if incluir_bloque_equipo_pdf:
        todas_metricas_equipo_pdf = st.checkbox(
            "Seleccionar todas las métricas del bloque Equipo",
            key="todas_metricas_equipo_pdf",
            value=False
        )
        if todas_metricas_equipo_pdf:
            metricas_equipo_pdf = list(metricas_disponibles.keys())
            st.caption(f"Bloque Equipo: se incluirán todas las métricas ({len(metricas_equipo_pdf)}).")
        else:
            metricas_equipo_pdf = st.multiselect(
                "Métricas del bloque Equipo:",
                options=list(metricas_disponibles.keys()),
                default=[metrica_nombre],
                key="metricas_equipo_pdf",
                help="Métricas que se incluirán en la sección de equipo."
            )

    incluir_bloque_posiciones_pdf = st.checkbox(
        "Incluir bloque Posiciones",
        key="incluir_bloque_posiciones_pdf",
        value=(nivel_analisis == "Por posiciones")
    )

    posiciones_pdf_seleccionadas = []
    metricas_posiciones_pdf = []
    if incluir_bloque_posiciones_pdf:
        df_posiciones_pdf = obtener_df_con_posiciones(df_tramo)
        opciones_posiciones_pdf = ['Defensa', 'Centrocampista', 'Delantero']
        posiciones_pdf_seleccionadas = st.multiselect(
            "Posiciones a incluir en el bloque Posiciones:",
            options=opciones_posiciones_pdf,
            default=posiciones_seleccionadas if posiciones_seleccionadas else opciones_posiciones_pdf,
            key="posiciones_pdf_seleccionadas"
        )
        todas_metricas_posiciones_pdf = st.checkbox(
            "Seleccionar todas las métricas del bloque Posiciones",
            key="todas_metricas_posiciones_pdf",
            value=False
        )
        if todas_metricas_posiciones_pdf:
            metricas_posiciones_pdf = list(metricas_disponibles.keys())
            st.caption(f"Bloque Posiciones: se incluirán todas las métricas ({len(metricas_posiciones_pdf)}).")
        else:
            metricas_posiciones_pdf = st.multiselect(
                "Métricas del bloque Posiciones:",
                options=list(metricas_disponibles.keys()),
                default=[metrica_nombre],
                key="metricas_posiciones_pdf"
            )

    incluir_bloque_individual_pdf = st.checkbox(
        "Incluir bloque Individual",
        key="incluir_bloque_individual_pdf",
        value=(nivel_analisis == "Individual")
    )

    jugadores_pdf_seleccionados = []
    metricas_individual_pdf = []
    if incluir_bloque_individual_pdf:
        jugadores_pdf_disponibles = sorted(df_tramo['player'].dropna().astype(str).unique().tolist())
        jugadores_pdf_seleccionados = st.multiselect(
            "Jugadores a incluir en el bloque Individual:",
            options=jugadores_pdf_disponibles,
            default=jugadores_seleccionados if jugadores_seleccionados else jugadores_pdf_disponibles[:min(3, len(jugadores_pdf_disponibles))],
            key="jugadores_pdf_seleccionados"
        )
        todas_metricas_individual_pdf = st.checkbox(
            "Seleccionar todas las métricas del bloque Individual",
            key="todas_metricas_individual_pdf",
            value=False
        )
        if todas_metricas_individual_pdf:
            metricas_individual_pdf = list(metricas_disponibles.keys())
            st.caption(f"Bloque Individual: se incluirán todas las métricas ({len(metricas_individual_pdf)}).")
        else:
            metricas_individual_pdf = st.multiselect(
                "Métricas del bloque Individual:",
                options=list(metricas_disponibles.keys()),
                default=[metrica_nombre],
                key="metricas_individual_pdf"
            )

    mostrar_tendencia_pdf = st.checkbox(
        "Incluir líneas de tendencia en el PDF",
        key="mostrar_tendencia_pdf_equipo",
        value=False
    )

    incluir_tabla_tendencia_pdf = st.checkbox(
        "Incluir tabla de semáforo de tendencia en el PDF",
        key="incluir_tabla_tendencia_pdf_equipo",
        value=False
    )

    incluir_detalle_individual = st.checkbox(
        "Añadir detalle individual de jugadores al final del informe",
        key="incluir_detalle_individual_pdf",
        value=(nivel_analisis == "Individual")
    )

    incluir_glosario_pdf = st.checkbox(
        "Incluir glosario en el informe",
        key="incluir_glosario_pdf_equipo",
        value=True
    )

    jugadores_detalle_pdf = []
    if incluir_detalle_individual:
        if incluir_bloque_individual_pdf and len(jugadores_pdf_seleccionados) > 0:
            jugadores_detalle_pdf = jugadores_pdf_seleccionados.copy()
            st.caption(f"Detalle individual: {len(jugadores_detalle_pdf)} jugador(es) del bloque Individual.")
        elif nivel_analisis == "Individual":
            jugadores_detalle_pdf = jugadores_seleccionados.copy()
            st.caption(f"Detalle individual: {len(jugadores_detalle_pdf)} jugador(es) seleccionados en el análisis.")
        else:
            jugadores_detalle_pdf = sorted(df_tramo['player'].dropna().astype(str).unique().tolist())
            st.caption(f"Detalle individual: {len(jugadores_detalle_pdf)} jugador(es) según el filtro actual.")

    comentario_pdf = st.text_area(
        "Comentarios para el informe (opcional):",
        key="comentario_pdf_equipo",
        height=110,
        placeholder="Escribe aquí observaciones técnicas, contexto del partido o conclusiones..."
    )

    def construir_texto_filtro():
        if modo_partido == 'Partido Específico':
            fecha = info_filtro.get('partido_seleccionado')
            base = f"Partido específico: {fecha.strftime('%d/%m/%Y')}" if fecha is not None else "Partido específico"
            return f"{base} | Tramo: {filtro_parte}"
        if modo_partido == 'Últimos N partidos':
            n = info_filtro.get('n_partidos', 0)
            ini = info_filtro.get('fecha_inicio')
            fin = info_filtro.get('fecha_fin')
            if ini is not None and fin is not None:
                return f"Últimos {n} partidos ({ini.strftime('%d/%m/%Y')} - {fin.strftime('%d/%m/%Y')}) | Tramo: {filtro_parte}"
            return f"Últimos {n} partidos | Tramo: {filtro_parte}"

        ini = info_filtro.get('fecha_inicio')
        fin = info_filtro.get('fecha_fin')
        if ini is not None and fin is not None:
            return f"Rango de fechas: {ini.strftime('%d/%m/%Y')} - {fin.strftime('%d/%m/%Y')} | Tramo: {filtro_parte}"
        return f"Rango de fechas personalizado | Tramo: {filtro_parte}"

    def construir_texto_alcance():
        bloques = []
        if incluir_bloque_equipo_pdf:
            bloques.append("Equipo completo")
        if incluir_bloque_posiciones_pdf and len(posiciones_pdf_seleccionadas) > 0:
            bloques.append("Posiciones: " + ", ".join(posiciones_pdf_seleccionadas))
        if incluir_bloque_individual_pdf and len(jugadores_pdf_seleccionados) > 0:
            bloques.append("Jugadores: " + ", ".join(jugadores_pdf_seleccionados))

        if bloques:
            return " | ".join(bloques)

        if nivel_analisis == 'Equipo':
            return "Equipo completo"
        if nivel_analisis == 'Por posiciones':
            if len(posiciones_seleccionadas) == 1:
                jugadores = sorted(df_limpio['player'].unique().tolist())
                return f"Posición: {posiciones_seleccionadas[0]} | Jugadores: {', '.join(jugadores)}"
            return f"Posiciones: {', '.join(posiciones_seleccionadas)}"
        return f"Jugadores: {', '.join(jugadores_seleccionados)}"

    def construir_resumen_bloques_pdf():
        resumen = []
        if incluir_bloque_equipo_pdf:
            resumen.append({
                "bloque": "EQUIPO",
                "alcance": "Equipo completo",
                "metricas": "Todas las métricas" if len(metricas_equipo_pdf) == len(metricas_disponibles) else ", ".join(metricas_equipo_pdf),
            })
        if incluir_bloque_posiciones_pdf and len(posiciones_pdf_seleccionadas) > 0:
            resumen.append({
                "bloque": "POSICIONES",
                "alcance": ", ".join(posiciones_pdf_seleccionadas),
                "metricas": "Todas las métricas" if len(metricas_posiciones_pdf) == len(metricas_disponibles) else ", ".join(metricas_posiciones_pdf),
            })
        if incluir_bloque_individual_pdf and len(jugadores_pdf_seleccionados) > 0:
            resumen.append({
                "bloque": "JUGADORES",
                "alcance": ", ".join(jugadores_pdf_seleccionados),
                "metricas": "Todas las métricas" if len(metricas_individual_pdf) == len(metricas_disponibles) else ", ".join(metricas_individual_pdf),
            })
        return resumen

    def construir_periodo_corto():
        def extraer_jornada(texto):
            txt = str(texto).strip().lower()
            match = re.search(r'\bj\s*(\d+)\b', txt)
            if not match:
                match = re.search(r'jornada\s*(\d+)', txt)
            if not match:
                match = re.search(r'(\d+)', txt)
            return f"J{int(match.group(1))}" if match else None

        jornadas = []
        if 'session' in df_tramo.columns:
            for sesion in df_tramo['session'].dropna().tolist():
                jornada = extraer_jornada(sesion)
                if jornada and jornada not in jornadas:
                    jornadas.append(jornada)

        def extraer_num_jornada(texto):
            match = re.search(r'(\d+)', str(texto))
            return int(match.group(1)) if match else None

        if jornadas:
            jornadas_ordenadas = sorted(
                jornadas,
                key=lambda s: (extraer_num_jornada(s) is None, extraer_num_jornada(s) or 9999, str(s))
            )
            if len(jornadas_ordenadas) == 1:
                return jornadas_ordenadas[0]
            return f"{jornadas_ordenadas[0]}-{jornadas_ordenadas[-1]}"

        fechas = sorted(pd.to_datetime(df_tramo['date']).dropna().unique().tolist())
        if len(fechas) == 1:
            return pd.to_datetime(fechas[0]).strftime('%d-%m-%y')
        if len(fechas) > 1:
            return f"{pd.to_datetime(fechas[0]).strftime('%d-%m-%y')} - {pd.to_datetime(fechas[-1]).strftime('%d-%m-%y')}"
        return "Periodo"

    def construir_periodo_portada():
        periodo_corto = construir_periodo_corto()
        if re.fullmatch(r'J\d+', periodo_corto):
            return f"De jornada {periodo_corto} a jornada {periodo_corto}"
        if re.fullmatch(r'J\d+-J\d+', periodo_corto):
            j_ini, j_fin = periodo_corto.split('-')
            return f"De jornada {j_ini} a jornada {j_fin}"
        return periodo_corto

    def construir_nombre_archivo_pdf():
        def sanitizar(texto):
            txt = str(texto).strip()
            txt = unicodedata.normalize("NFKD", txt)
            txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
            txt = re.sub(r"[^A-Za-z0-9]+", "_", txt)
            return txt.strip("_") or "NA"

        bloques_activos = []
        if incluir_bloque_equipo_pdf:
            bloques_activos.append("Equipo")
        if incluir_bloque_posiciones_pdf:
            bloques_activos.append("Posiciones")
        if incluir_bloque_individual_pdf:
            bloques_activos.append("Individual")

        if len(bloques_activos) > 1:
            nivel_nombre = "Mixto"
            alcance_nombre = "Grupo"
        elif incluir_bloque_equipo_pdf:
            nivel_nombre = "Equipo"
            alcance_nombre = "Equipo"
        elif incluir_bloque_posiciones_pdf:
            nivel_nombre = "Por posiciones"
            alcance_nombre = posiciones_pdf_seleccionadas[0] if len(posiciones_pdf_seleccionadas) == 1 else "Grupo"
        elif incluir_bloque_individual_pdf:
            nivel_nombre = "Individual"
            alcance_nombre = jugadores_pdf_seleccionados[0] if len(jugadores_pdf_seleccionados) == 1 else "Grupo"
        else:
            nivel_nombre = nivel_analisis
            alcance_nombre = "Grupo"

        periodo_nombre = construir_periodo_corto()
        return f"InformeEquipo_{sanitizar(nivel_nombre)}_{sanitizar(alcance_nombre)}_{sanitizar(periodo_nombre)}.pdf"

    if st.button("📥 Generar informe PDF", type="primary", use_container_width=True):
        if not any([incluir_bloque_equipo_pdf, incluir_bloque_posiciones_pdf, incluir_bloque_individual_pdf]):
            st.warning("⚠️ Selecciona al menos un bloque para el informe.")
        elif incluir_bloque_equipo_pdf and len(metricas_equipo_pdf) == 0:
            st.warning("⚠️ Selecciona al menos una métrica para el bloque Equipo.")
        elif incluir_bloque_posiciones_pdf and (len(posiciones_pdf_seleccionadas) == 0 or len(metricas_posiciones_pdf) == 0):
            st.warning("⚠️ Selecciona posiciones y métricas para el bloque Posiciones.")
        elif incluir_bloque_individual_pdf and (len(jugadores_pdf_seleccionados) == 0 or len(metricas_individual_pdf) == 0):
            st.warning("⚠️ Selecciona jugadores y métricas para el bloque Individual.")
        elif incluir_detalle_individual and len(jugadores_detalle_pdf) == 0:
            st.warning("⚠️ Selecciona al menos un jugador para el detalle individual.")
        else:
            with st.spinner("Generando informe PDF..."):
                metricas_para_pdf = []

                def agregar_metricas_bloque(nombre_bloque, nivel_bloque, metricas_bloque, df_base_bloque, posiciones_bloque=None, jugadores_bloque=None):
                    for metrica_pdf_nombre in metricas_bloque:
                        metrica_pdf_col = METRICAS_DICT[metrica_pdf_nombre]
                        datos_pdf = construir_datos_grafico(
                            metrica_pdf_col,
                            nivel_analisis_local=nivel_bloque,
                            df_base_local=df_base_bloque,
                            posiciones_sel=posiciones_bloque,
                            jugadores_sel=jugadores_bloque,
                        )
                        if len(datos_pdf) == 0:
                            continue
                        df_grafico_pdf = preparar_df_grafico(datos_pdf)
                        metricas_para_pdf.append({
                            "bloque_nombre": nombre_bloque,
                            "nivel_analisis": nivel_bloque,
                            "metrica_nombre": metrica_pdf_nombre,
                            "df_grafico": df_grafico_pdf,
                            "plotly_fig": crear_figura_plotly(
                                df_grafico_pdf,
                                metrica_pdf_nombre,
                                mostrar_tendencia=mostrar_tendencia_pdf
                            ),
                            "mostrar_tendencia": mostrar_tendencia_pdf,
                            "incluir_tabla_tendencia": incluir_tabla_tendencia_pdf,
                            "filtro_parte": filtro_parte,
                        })

                if incluir_bloque_equipo_pdf:
                    agregar_metricas_bloque(
                        nombre_bloque="Equipo",
                        nivel_bloque="Equipo",
                        metricas_bloque=metricas_equipo_pdf,
                        df_base_bloque=df_tramo,
                    )

                if incluir_bloque_posiciones_pdf:
                    df_posiciones_bloque = obtener_df_con_posiciones(df_tramo)
                    df_posiciones_bloque = df_posiciones_bloque[df_posiciones_bloque['posicion'].isin(posiciones_pdf_seleccionadas)]
                    agregar_metricas_bloque(
                        nombre_bloque="Posiciones",
                        nivel_bloque="Por posiciones",
                        metricas_bloque=metricas_posiciones_pdf,
                        df_base_bloque=df_posiciones_bloque,
                        posiciones_bloque=posiciones_pdf_seleccionadas,
                    )

                if incluir_bloque_individual_pdf:
                    df_individual_bloque = df_tramo[df_tramo['player'].isin(jugadores_pdf_seleccionados)].copy()
                    agregar_metricas_bloque(
                        nombre_bloque="Individual",
                        nivel_bloque="Individual",
                        metricas_bloque=metricas_individual_pdf,
                        df_base_bloque=df_individual_bloque,
                        jugadores_bloque=jugadores_pdf_seleccionados,
                    )

                detalles_jugadores_pdf = []
                if incluir_detalle_individual:
                    metricas_detalle_individual = metricas_individual_pdf if len(metricas_individual_pdf) > 0 else metricas_equipo_pdf
                    for jugador in jugadores_detalle_pdf:
                        df_jugador = df_tramo[df_tramo['player'] == jugador].copy()
                        if len(df_jugador) == 0:
                            continue

                        minutos_jugador = (
                            pd.to_numeric(df_jugador['time'], errors='coerce').dropna()
                            if 'time' in df_jugador.columns else pd.Series(dtype=float)
                        )
                        min_max = float(minutos_jugador.max()) if len(minutos_jugador) > 0 else np.nan
                        min_prom = float(minutos_jugador.mean()) if len(minutos_jugador) > 0 else np.nan
                        min_min = float(minutos_jugador.min()) if len(minutos_jugador) > 0 else np.nan

                        tarjetas = []
                        for metrica_pdf_nombre in metricas_detalle_individual:
                            metrica_col_det = METRICAS_DICT[metrica_pdf_nombre]
                            if metrica_col_det not in df_jugador.columns:
                                continue
                            valores = pd.to_numeric(df_jugador[metrica_col_det], errors='coerce').dropna()
                            if len(valores) == 0:
                                continue

                            tarjetas.append({
                                "metrica": metrica_pdf_nombre,
                                "lineas": [
                                    f"Media: {valores.mean():.1f}",
                                    f"Mejor: {valores.max():.1f}",
                                    f"Peor: {valores.min():.1f}",
                                ]
                            })

                        if len(tarjetas) > 0:
                            if 'posicion' in df_jugador.columns and df_jugador['posicion'].notna().any():
                                posicion_j = str(df_jugador['posicion'].dropna().iloc[0])
                            elif 'position' in df_jugador.columns and df_jugador['position'].notna().any():
                                posicion_j = str(df_jugador['position'].dropna().iloc[0])
                            else:
                                posicion_j = "Sin posición"

                            detalles_jugadores_pdf.append({
                                "jugador": jugador,
                                "posicion": posicion_j,
                                "foto_path": obtener_foto_jugador(jugador),
                                "minutos_max": min_max,
                                "minutos_prom": min_prom,
                                "minutos_min": min_min,
                                "tarjetas": tarjetas
                            })

                if len(metricas_para_pdf) == 0:
                    st.error("❌ No se pudo generar el informe con la selección actual.")
                else:
                    bloques_activos = [b for b in ["Equipo" if incluir_bloque_equipo_pdf else None, "Posiciones" if incluir_bloque_posiciones_pdf else None, "Individual" if incluir_bloque_individual_pdf else None] if b]
                    nivel_informe_pdf = "Mixto" if len(bloques_activos) > 1 else bloques_activos[0]
                    output_path = generar_pdf_equipo(
                        metricas_pdf=metricas_para_pdf,
                        estadistico=estadistico,
                        nivel_analisis=nivel_informe_pdf,
                        filtro_texto=construir_texto_filtro(),
                        alcance_texto=construir_texto_alcance(),
                        comentario=comentario_pdf,
                        detalles_jugadores=detalles_jugadores_pdf,
                        periodo_portada=construir_periodo_portada(),
                        output_filename=construir_nombre_archivo_pdf(),
                        resumen_bloques=construir_resumen_bloques_pdf(),
                        incluir_glosario=incluir_glosario_pdf,
                    )
                    with open(output_path, "rb") as f:
                        pdf_bytes = f.read()

                    st.success("✅ Informe generado correctamente.")
                    st.download_button(
                        label="📄 Descargar informe PDF",
                        data=pdf_bytes,
                        file_name=Path(output_path).name,
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"download_pdf_equipo_{datetime.now().strftime('%H%M%S')}"
                    )


if __name__ == "__main__":
    main()
