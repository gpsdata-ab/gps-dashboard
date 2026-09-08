"""
Página Individual - Análisis por Jugador
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path
import os

# Añadir directorio raíz al path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from config import PAGE_TITLE, PAGE_ICON, LAYOUT, METRICAS_DICT, COLORES
from utils import (calcular_referencias_normalizadas, filtrar_por_fechas,
                   filtrar_por_partido, obtener_referencia_metrica,
                   calcular_z_score, clasificar_rendimiento, render_sidebar)
from utils.filtros import render_filtro_partidos

# Configuración
st.set_page_config(
    page_title=f"{PAGE_TITLE} - Individual",
    page_icon=PAGE_ICON,
    layout=LAYOUT,
    initial_sidebar_state="collapsed"
)

def main():
    # ==========================================
    # VERIFICAR AUTENTICACIÓN
    # ==========================================
    if not st.session_state.get('autenticado', False):
        st.warning("⚠️ Por favor, inicia sesión desde la página principal")
        st.info("👉 Ve a la app principal para iniciar sesión")
        st.stop()
    
    # ==========================================
    # RENDERIZAR SIDEBAR
    # ==========================================
    render_sidebar()
    
    st.title("👤 Análisis Individual")
    
    # ==========================================
    # VERIFICAR DATOS CARGADOS
    # ==========================================
    if not st.session_state.get('datos_cargados', False):
        st.warning("⚠️ No hay datos cargados")
        st.info("💡 Ve a la página principal y carga los datos desde Google Drive")
        st.stop()
    
    # ==========================================
    # OBTENER DATOS DE FORMA SEGURA
    # ==========================================
    df = st.session_state.get('df_procesado')
    
    if df is None or len(df) == 0:
        st.error("⚠️ Error: datos no disponibles")
        st.stop()
    
    # ========================================
    # SISTEMA DE FILTROS DE PARTIDOS
    # ========================================
    
    # Renderizar filtros (retorna: df_filtrado, modo_partido, info_dict)
    df_filtrado, modo_partido, info_dict = render_filtro_partidos(
        df=df,
        titulo="🎯 Filtros de Análisis"
    )
    
    # Verificar que hay datos filtrados
    if df_filtrado is None or len(df_filtrado) == 0:
        st.error("❌ No hay datos en el rango seleccionado")
        st.stop()
    
    st.markdown("---")
    
    # ========================================
    # SELECTOR DE MÉTRICA
    # ========================================
    
    st.markdown("### 📊 Configuración de Análisis")
    metrica_nombre = st.selectbox(
        "Selecciona la métrica a analizar:",
        options=list(METRICAS_DICT.keys()),
        key='metrica_individual'
    )
    metrica_col = METRICAS_DICT[metrica_nombre]
    
    st.markdown("---")

    # ========================================
    # CALCULAR REFERENCIAS CON DATOS FILTRADOS
    # ========================================
    
    df_referencias = calcular_referencias_normalizadas(df_filtrado)
    
    # ========================================
    # TABS
    # ========================================
    
    # Tabs
    tab1, tab2 = st.tabs(["📈 Evolución Individual", "🎯 Comparativa"])
    
    # TAB 1: EVOLUCIÓN INDIVIDUAL
    with tab1:
        st.subheader("📈 Evolución Individual")
        
        # Selector de jugador y estadísticas (con foto)
        col_foto, col_jug, col_stat_jug, col_stat_pos = st.columns([0.5, 2, 1, 1])
        
        with col_jug:
            jugadores = sorted(df_filtrado['player'].dropna().astype(str).unique())
            jugador_seleccionado = st.selectbox(
                "👤 Seleccionar jugador:",
                options=jugadores,
                key='jugador_evolucion'
            )
        
        with col_stat_jug:
            estadistica_jugador = st.selectbox(
                "📊 Línea jugador:",
                options=['Media', 'Mediana', 'P70', 'P75', 'P80', 'P85', 'P90', 'P95'],
                index=0,
                key='stat_jugador',
                help="Estadística acumulada del jugador"
            )
        
        with col_stat_pos:
            estadistica_posicion = st.selectbox(
                "📍 Línea posición:",
                options=['Media', 'Mediana', 'P70', 'P75', 'P80', 'P85', 'P90', 'P95'],
                index=0,
                key='stat_posicion',
                help="Estadística acumulada de jugadores de su posición"
            )
        
        # Mostrar foto del jugador seleccionado
        with col_foto:
            from utils.visualizations import obtener_foto_jugador
            foto_path = obtener_foto_jugador(jugador_seleccionado)
            st.image(foto_path, use_container_width=True)
        
        # Detectar posición del jugador desde plantilla
        try:
            from utils import cargar_plantilla_europa, mapear_posicion
            df_plantilla = cargar_plantilla_europa()
            posicion_jugador = mapear_posicion(jugador_seleccionado, df_plantilla)
        except:
            posicion_jugador = 'Sin posición'
            df_plantilla = None
        
        # CRÍTICO: Filtrar datos del jugador Y eliminar duplicados
        df_jugador = df_filtrado[df_filtrado['player'] == jugador_seleccionado].copy()
        
        # Eliminar duplicados por fecha (tomar el registro con más minutos jugados)
        df_jugador = df_jugador.sort_values('time', ascending=False).drop_duplicates(subset=['date'], keep='first')
        df_jugador = df_jugador.sort_values('date')
        
        if len(df_jugador) > 0:
            # Métricas del jugador
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Posición", posicion_jugador)
            with col2:
                # Verificar que la métrica existe
                if metrica_col in df_jugador.columns:
                    st.metric(f"Media {metrica_nombre}", f"{df_jugador[metrica_col].mean():.2f}")
                else:
                    st.metric(f"Media {metrica_nombre}", "N/A")
            with col3:
                if metrica_col in df_jugador.columns:
                    st.metric(f"Mejor", f"{df_jugador[metrica_col].max():.2f}")
                else:
                    st.metric(f"Mejor", "N/A")
            with col4:
                if df_referencias is not None and metrica_col in df_jugador.columns:
                    ref = obtener_referencia_metrica(df_referencias, metrica_col)
                    if ref is not None and isinstance(ref, dict) and 'Media' in ref:
                        dif = df_jugador[metrica_col].mean() - ref['Media']
                        st.metric("vs Ref. Equipo", f"{dif:+.2f}", 
                                 delta=f"{(dif/ref['Media']*100):+.1f}%")
            
            st.markdown("---")
            
            # CRÍTICO: Verificar que la métrica existe antes de continuar
            if metrica_col not in df_jugador.columns:
                st.error(f"❌ La métrica '{metrica_nombre}' no existe en los datos. Esta métrica puede ser calculada y no estar disponible en el conjunto de datos filtrado.")
                st.stop()
            
            # ========================================
            # PREPARAR DATOS PARA GRÁFICO
            # ========================================
            
            # CRÍTICO: Obtener TODOS los partidos únicos del rango filtrado
            todos_partidos = df_filtrado[['date', 'session']].drop_duplicates().sort_values('date')
            
            # Crear DataFrame completo con todos los partidos
            df_completo = todos_partidos.copy()
            df_completo['jugador'] = jugador_seleccionado
            
            # Merge con datos del jugador (solo columnas que existen)
            merge_cols = ['date', metrica_col, 'time']
            # Filtrar solo columnas que existen
            merge_cols = [col for col in merge_cols if col in df_jugador.columns]
            
            df_completo = df_completo.merge(
                df_jugador[merge_cols],
                on='date',
                how='left'
            )
            
            # ========================================
            # CALCULAR ESTADÍSTICA ACUMULADA DEL JUGADOR
            # ========================================
            
            df_completo['valor_acum_jugador'] = None
            
            valores_jugados = []
            for idx, row in df_completo.iterrows():
                if pd.notna(row.get(metrica_col)):
                    valores_jugados.append(row[metrica_col])
                
                if len(valores_jugados) > 0:
                    if estadistica_jugador == 'Media':
                        val = pd.Series(valores_jugados).mean()
                    elif estadistica_jugador == 'Mediana':
                        val = pd.Series(valores_jugados).median()
                    elif estadistica_jugador == 'P70':
                        val = pd.Series(valores_jugados).quantile(0.70)
                    elif estadistica_jugador == 'P75':
                        val = pd.Series(valores_jugados).quantile(0.75)
                    elif estadistica_jugador == 'P80':
                        val = pd.Series(valores_jugados).quantile(0.80)
                    elif estadistica_jugador == 'P85':
                        val = pd.Series(valores_jugados).quantile(0.85)
                    elif estadistica_jugador == 'P90':
                        val = pd.Series(valores_jugados).quantile(0.90)
                    elif estadistica_jugador == 'P95':
                        val = pd.Series(valores_jugados).quantile(0.95)
                    
                    df_completo.at[idx, 'valor_acum_jugador'] = val
            
            # ========================================
            # CALCULAR ESTADÍSTICA ACUMULADA DE LA POSICIÓN
            # ========================================
            
            df_completo['valor_acum_posicion'] = None
            
            if posicion_jugador not in ['Sin posición', None, ''] and df_plantilla is not None:
                try:
                    jugadores_posicion = df_plantilla[
                        df_plantilla['Posición'] == posicion_jugador
                    ]['Jugador GPS'].tolist()
                    
                    df_posicion = df_filtrado[df_filtrado['player'].isin(jugadores_posicion)].copy()
                    
                    # Eliminar duplicados por jugador y fecha
                    df_posicion = df_posicion.sort_values('time', ascending=False).drop_duplicates(subset=['player', 'date'], keep='first')
                    
                    if len(df_posicion) > 0 and metrica_col in df_posicion.columns:
                        for fecha in todos_partidos['date']:
                            df_hasta_fecha = df_posicion[df_posicion['date'] <= fecha]
                            
                            if len(df_hasta_fecha) > 0:
                                valores = df_hasta_fecha[metrica_col].dropna()
                                
                                if len(valores) > 0:
                                    if estadistica_posicion == 'Media':
                                        valor_pos = valores.mean()
                                    elif estadistica_posicion == 'Mediana':
                                        valor_pos = valores.median()
                                    elif estadistica_posicion == 'P70':
                                        valor_pos = valores.quantile(0.70)
                                    elif estadistica_posicion == 'P75':
                                        valor_pos = valores.quantile(0.75)
                                    elif estadistica_posicion == 'P80':
                                        valor_pos = valores.quantile(0.80)
                                    elif estadistica_posicion == 'P85':
                                        valor_pos = valores.quantile(0.85)
                                    elif estadistica_posicion == 'P90':
                                        valor_pos = valores.quantile(0.90)
                                    elif estadistica_posicion == 'P95':
                                        valor_pos = valores.quantile(0.95)
                                    else:
                                        valor_pos = valores.mean()
                                    
                                    df_completo.loc[df_completo['date'] == fecha, 'valor_acum_posicion'] = valor_pos
                except Exception as e:
                    st.warning(f"⚠️ No se pudo calcular estadística de posición: {e}")
            
            # ========================================
            # CREAR GRÁFICO COMBINADO
            # ========================================
            
            fig = go.Figure()
            
            # 1. BARRAS - Solo partidos donde jugó
            df_jugo = df_completo[df_completo[metrica_col].notna()].copy()
            
            if len(df_jugo) > 0:
                texto_barras = [f"{int(t)}'" for t in df_jugo['time']] if 'time' in df_jugo.columns else [""] * len(df_jugo)
                
                fig.add_trace(go.Bar(
                    x=df_jugo['date'],
                    y=df_jugo[metrica_col],
                    name=f'{metrica_nombre} (real)',
                    marker_color=COLORES['primario'],
                    text=texto_barras,
                    textposition='outside',
                    textfont=dict(size=10),
                    hovertemplate='<b>%{x|%d/%m/%Y}</b><br>' +
                                  f'{metrica_nombre}: %{{y:.1f}}<br>' +
                                  'Minutos: %{text}<extra></extra>',
                    opacity=0.7
                ))
            
            # 2. LÍNEA ACUMULADA DEL JUGADOR
            df_con_acum_jug = df_completo[df_completo['valor_acum_jugador'].notna()].copy()
            
            if len(df_con_acum_jug) > 0:
                fig.add_trace(go.Scatter(
                    x=df_con_acum_jug['date'],
                    y=df_con_acum_jug['valor_acum_jugador'],
                    mode='lines+markers',
                    name=f'{estadistica_jugador} {jugador_seleccionado}',
                    line=dict(color='#ef4444', width=3, dash='solid'),
                    marker=dict(size=8, symbol='circle'),
                    hovertemplate='<b>%{x|%d/%m/%Y}</b><br>' +
                                  f'{estadistica_jugador}: %{{y:.1f}}<extra></extra>'
                ))
            
            # 3. LÍNEA ACUMULADA DE LA POSICIÓN
            df_con_acum_pos = df_completo[df_completo['valor_acum_posicion'].notna()].copy()
            
            if len(df_con_acum_pos) > 0:
                fig.add_trace(go.Scatter(
                    x=df_con_acum_pos['date'],
                    y=df_con_acum_pos['valor_acum_posicion'],
                    mode='lines',
                    name=f'{estadistica_posicion} {posicion_jugador}s',
                    line=dict(color='#ef4444', width=2, dash='dash'),
                    hovertemplate='<b>%{x|%d/%m/%Y}</b><br>' +
                                  f'{estadistica_posicion} {posicion_jugador}s: %{{y:.1f}}<extra></extra>'
                ))
            
            fig.update_layout(
                title=f"Evolución de {metrica_nombre} - {jugador_seleccionado} ({posicion_jugador})",
                xaxis_title="Fecha del partido",
                yaxis_title=metrica_nombre,
                height=550,
                hovermode='x unified',
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                xaxis=dict(
                    tickformat='%d/%m',
                    tickangle=-45
                )
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # ========================================
            # EXPORTAR A PDF
            # ========================================
            
            st.markdown("---")
            st.subheader("📄 Exportar Informe a PDF")
            
            col_pdf1, col_pdf2, col_pdf3 = st.columns([2, 2, 1])
            
            with col_pdf1:
                # CRÍTICO: Solo mostrar métricas que existen en los datos
                metricas_disponibles = [m for m in METRICAS_DICT.keys() if METRICAS_DICT[m] in df_filtrado.columns]
                
                metricas_pdf = st.multiselect(
                    "Métricas a incluir:",
                    options=metricas_disponibles,
                    default=[metrica_nombre] if metrica_nombre in metricas_disponibles else metricas_disponibles[:1],
                    key='metricas_pdf',
                    help="Solo métricas disponibles en los datos filtrados"
                )
            
            with col_pdf2:
                modo_jugadores_pdf = st.radio(
                    "Jugadores:",
                    options=['Solo jugador actual', 'Selección múltiple'],
                    key='modo_jugadores_pdf',
                    horizontal=True
                )
                
                if modo_jugadores_pdf == 'Selección múltiple':
                    jugadores_pdf = st.multiselect(
                        "Seleccionar jugadores:",
                        options=jugadores,
                        default=[jugador_seleccionado],
                        key='jugadores_pdf',
                        help="Máximo 5 jugadores"
                    )
                else:
                    jugadores_pdf = [jugador_seleccionado]
            
            with col_pdf3:
                st.write("")
                st.write("")
                if st.button("🔽 Generar PDF", type="primary", use_container_width=True):
                    if len(metricas_pdf) == 0:
                        st.error("⚠️ Selecciona al menos 1 métrica")
                    elif len(jugadores_pdf) == 0:
                        st.error("⚠️ Selecciona al menos 1 jugador")
                    else:
                        with st.spinner("Generando PDF..."):
                            try:
                                jugadores_datos = []
                                
                                for jugador in jugadores_pdf:
                                    # Filtrar y limpiar datos del jugador
                                    df_jugador_pdf = df_filtrado[df_filtrado['player'] == jugador].copy()
                                    df_jugador_pdf = df_jugador_pdf.sort_values('time', ascending=False).drop_duplicates(subset=['date'], keep='first')
                                    
                                    posicion_pdf = mapear_posicion(jugador, df_plantilla) if df_plantilla is not None else 'Sin posición'
                                    
                                    # Calcular stats para cada métrica
                                    stats_jugador = {}
                                    for metrica_nombre_pdf in metricas_pdf:
                                        metrica_col_pdf = METRICAS_DICT[metrica_nombre_pdf]
                                        
                                        # Verificar que existe
                                        if metrica_col_pdf not in df_jugador_pdf.columns:
                                            continue
                                        
                                        media_val = df_jugador_pdf[metrica_col_pdf].mean()
                                        mejor_val = df_jugador_pdf[metrica_col_pdf].max()
                                        peor_val = df_jugador_pdf[metrica_col_pdf].min()
                                        
                                        vs_ref = 0
                                        if df_referencias is not None:
                                            ref = obtener_referencia_metrica(df_referencias, metrica_col_pdf)
                                            if ref is not None and isinstance(ref, dict) and 'Media' in ref:
                                                vs_ref = media_val - ref['Media']
                                        
                                        stats_jugador[metrica_col_pdf] = {
                                            'media': media_val,
                                            'mejor': mejor_val,
                                            'peor': peor_val,
                                            'vs_ref': vs_ref
                                        }
                                    
                                    # Preparar df_completo por métrica
                                    df_completos_por_metrica = {}
                                    
                                    for metrica_nombre_pdf in metricas_pdf:
                                        metrica_col_pdf = METRICAS_DICT[metrica_nombre_pdf]
                                        
                                        # Verificar que existe
                                        if metrica_col_pdf not in df_filtrado.columns:
                                            continue
                                        
                                        todos_partidos_pdf = df_filtrado[['date', 'session']].drop_duplicates().sort_values('date')
                                        df_completo_metrica = todos_partidos_pdf.copy()
                                        df_completo_metrica['jugador'] = jugador
                                        
                                        merge_cols = ['date', metrica_col_pdf, 'time']
                                        merge_cols = [col for col in merge_cols if col in df_jugador_pdf.columns]
                                        
                                        df_completo_metrica = df_completo_metrica.merge(
                                            df_jugador_pdf[merge_cols],
                                            on='date',
                                            how='left'
                                        )
                                        
                                        df_completo_metrica['valor_acum_jugador'] = None
                                        valores_jugados_pdf = []
                                        
                                        for idx, row in df_completo_metrica.iterrows():
                                            if pd.notna(row.get(metrica_col_pdf)):
                                                valores_jugados_pdf.append(row[metrica_col_pdf])
                                            
                                            if len(valores_jugados_pdf) > 0:
                                                if estadistica_jugador == 'Media':
                                                    val = pd.Series(valores_jugados_pdf).mean()
                                                elif estadistica_jugador == 'Mediana':
                                                    val = pd.Series(valores_jugados_pdf).median()
                                                elif estadistica_jugador == 'P70':
                                                    val = pd.Series(valores_jugados_pdf).quantile(0.70)
                                                elif estadistica_jugador == 'P75':
                                                    val = pd.Series(valores_jugados_pdf).quantile(0.75)
                                                elif estadistica_jugador == 'P80':
                                                    val = pd.Series(valores_jugados_pdf).quantile(0.80)
                                                elif estadistica_jugador == 'P85':
                                                    val = pd.Series(valores_jugados_pdf).quantile(0.85)
                                                elif estadistica_jugador == 'P90':
                                                    val = pd.Series(valores_jugados_pdf).quantile(0.90)
                                                elif estadistica_jugador == 'P95':
                                                    val = pd.Series(valores_jugados_pdf).quantile(0.95)
                                                
                                                df_completo_metrica.at[idx, 'valor_acum_jugador'] = val
                                        
                                        df_completo_metrica['valor_acum_posicion'] = None
                                        
                                        if posicion_pdf not in ['Sin posición', None, ''] and df_plantilla is not None:
                                            try:
                                                jugadores_posicion_pdf = df_plantilla[
                                                    df_plantilla['Posición'] == posicion_pdf
                                                ]['Jugador GPS'].tolist()
                                                
                                                df_posicion_pdf = df_filtrado[df_filtrado['player'].isin(jugadores_posicion_pdf)].copy()
                                                df_posicion_pdf = df_posicion_pdf.sort_values('time', ascending=False).drop_duplicates(subset=['player', 'date'], keep='first')
                                                
                                                if len(df_posicion_pdf) > 0 and metrica_col_pdf in df_posicion_pdf.columns:
                                                    for fecha in todos_partidos_pdf['date']:
                                                        df_hasta_fecha_pdf = df_posicion_pdf[df_posicion_pdf['date'] <= fecha]
                                                        
                                                        if len(df_hasta_fecha_pdf) > 0:
                                                            valores_pos = df_hasta_fecha_pdf[metrica_col_pdf].dropna()
                                                            
                                                            if len(valores_pos) > 0:
                                                                if estadistica_posicion == 'Media':
                                                                    valor_pos_pdf = valores_pos.mean()
                                                                elif estadistica_posicion == 'Mediana':
                                                                    valor_pos_pdf = valores_pos.median()
                                                                elif estadistica_posicion == 'P70':
                                                                    valor_pos_pdf = valores_pos.quantile(0.70)
                                                                elif estadistica_posicion == 'P75':
                                                                    valor_pos_pdf = valores_pos.quantile(0.75)
                                                                elif estadistica_posicion == 'P80':
                                                                    valor_pos_pdf = valores_pos.quantile(0.80)
                                                                elif estadistica_posicion == 'P85':
                                                                    valor_pos_pdf = valores_pos.quantile(0.85)
                                                                elif estadistica_posicion == 'P90':
                                                                    valor_pos_pdf = valores_pos.quantile(0.90)
                                                                elif estadistica_posicion == 'P95':
                                                                    valor_pos_pdf = valores_pos.quantile(0.95)
                                                                
                                                                df_completo_metrica.loc[df_completo_metrica['date'] == fecha, 'valor_acum_posicion'] = valor_pos_pdf
                                            except:
                                                pass
                                        
                                        df_completos_por_metrica[metrica_col_pdf] = df_completo_metrica
                                    
                                    from utils.visualizations import obtener_foto_jugador
                                    foto_path_pdf = obtener_foto_jugador(jugador)
                                    
                                    jugadores_datos.append({
                                        'nombre': jugador,
                                        'posicion': posicion_pdf,
                                        'foto_path': foto_path_pdf,
                                        'stats': stats_jugador,
                                        'df_completos_por_metrica': df_completos_por_metrica
                                    })
                                
                                from utils.pdf_evolucion_individual import generar_pdf_evolucion_individual
                                
                                pdf_path = generar_pdf_evolucion_individual(
                                    jugadores_datos=jugadores_datos,
                                    metricas_seleccionadas=[METRICAS_DICT[m] for m in metricas_pdf],
                                    estadistica_jugador=estadistica_jugador,
                                    estadistica_posicion=estadistica_posicion,
                                    fecha_desde=info_dict.get('fecha_inicio'),
                                    fecha_hasta=info_dict.get('fecha_fin'),
                                    df_rango=df_filtrado,
                                    METRICAS_DICT=METRICAS_DICT,
                                    COLORES=COLORES
                                )
                                
                                st.success("✅ PDF generado correctamente!")
                                
                                with open(pdf_path, 'rb') as f:
                                    st.download_button(
                                        label="📥 Descargar PDF",
                                        data=f,
                                        file_name=os.path.basename(pdf_path),
                                        mime='application/pdf'
                                    )
                                
                            except Exception as e:
                                st.error(f"❌ Error al generar PDF: {str(e)}")
                                import traceback
                                st.code(traceback.format_exc())

            # Info adicional
            partidos_totales = len(todos_partidos)
            partidos_jugados = len(df_jugador)
            partidos_no_jugados = partidos_totales - partidos_jugados
            
            info_text = f"ℹ️ **{jugador_seleccionado}** ({posicion_jugador}) jugó **{partidos_jugados} de {partidos_totales}** partidos. "
            
            if partidos_no_jugados > 0:
                info_text += f"En los **{partidos_no_jugados} partidos** donde no jugó, su línea mantiene el valor anterior."
            
            st.info(info_text)
            
            # Tabla de evolución
            with st.expander("📋 Ver tabla de evolución completa"):
                df_tabla_evol = df_completo[['date', 'session', 'time', metrica_col, 
                                             'valor_acum_jugador', 'valor_acum_posicion']].copy()
                df_tabla_evol['date'] = df_tabla_evol['date'].dt.strftime('%d/%m/%Y')
                df_tabla_evol['time'] = df_tabla_evol['time'].apply(
                    lambda x: f"{x:.0f}" if pd.notna(x) else "-"
                ) if 'time' in df_tabla_evol.columns else "-"
                df_tabla_evol[metrica_col] = df_tabla_evol[metrica_col].apply(
                    lambda x: f"{x:.1f}" if pd.notna(x) else "-"
                )
                df_tabla_evol['valor_acum_jugador'] = df_tabla_evol['valor_acum_jugador'].apply(
                    lambda x: f"{x:.2f}" if pd.notna(x) else "-"
                )
                df_tabla_evol['valor_acum_posicion'] = df_tabla_evol['valor_acum_posicion'].apply(
                    lambda x: f"{x:.2f}" if pd.notna(x) else "-"
                )
                
                df_tabla_evol.columns = ['Fecha', 'Partido', 'Min', metrica_nombre, 
                                         f'{estadistica_jugador} Jugador', 
                                         f'{estadistica_posicion} {posicion_jugador}s']
                
                st.dataframe(
                    df_tabla_evol,
                    use_container_width=True,
                    height=400
                )
        else:
            st.warning(f"⚠️ No hay datos para {jugador_seleccionado} en el rango seleccionado")
    
    # TAB 2: COMPARATIVA
    with tab2:
        st.subheader("🎯 Comparativa entre Jugadores")
        
        jugadores = sorted(df_filtrado['player'].dropna().astype(str).unique())
        jugadores_comparar = st.multiselect(
            "Seleccionar jugadores a comparar (máx. 5):",
            options=jugadores,
            default=jugadores[:min(3, len(jugadores))],
            max_selections=5
        )
        
        if len(jugadores_comparar) > 0:
            # Verificar que la métrica existe
            if metrica_col not in df_filtrado.columns:
                st.error(f"❌ La métrica '{metrica_nombre}' no existe en los datos filtrados.")
                st.stop()
            
            # Gráfico comparativo
            fig = go.Figure()

            for jugador in jugadores_comparar:
                df_jug = df_filtrado[df_filtrado['player'] == jugador].copy()
                # Eliminar duplicados
                df_jug = df_jug.sort_values('time', ascending=False).drop_duplicates(subset=['date'], keep='first')
                df_jug = df_jug.sort_values('date')
                
                fig.add_trace(go.Bar(
                    x=df_jug['date'],
                    y=df_jug[metrica_col],
                    name=jugador,
                    text=[f"{v:.0f}" for v in df_jug[metrica_col]],
                    textposition='outside',
                    hovertemplate='<b>%{x|%d/%m/%Y}</b><br>' +
                                f'{metrica_nombre}: %{{y:.1f}}<br>' +
                                '<extra></extra>'
                ))

            if df_referencias is not None:
                ref = obtener_referencia_metrica(df_referencias, metrica_col)
                if ref is not None and 'Media' in ref:
                    fig.add_hline(
                        y=ref['Media'],
                        line_dash="dash",
                        line_color=COLORES['referencia'],
                        annotation_text="Ref. 94min"
                    )

            fig.update_traces(
                textfont=dict(size=22, color='black', family='Arial Black'),
                textposition='outside',
                selector=dict(type='bar')
            )

            fig.update_layout(
                title=f"Comparativa de {metrica_nombre}",
                xaxis_title="Fecha",
                yaxis_title=metrica_nombre,
                height=650,
                hovermode='x unified',
                barmode='group'
            )

            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            st.subheader("📊 Estadísticas Comparativas")
            
            comparativa_stats = []
            for jugador in jugadores_comparar:
                df_jug = df_filtrado[df_filtrado['player'] == jugador].copy()
                df_jug = df_jug.drop_duplicates(subset=['date'], keep='first')
                
                stats = {
                    'Jugador': jugador,
                    'Partidos': len(df_jug),
                    f'Media {metrica_nombre}': df_jug[metrica_col].mean(),
                    f'Mejor': df_jug[metrica_col].max(),
                    f'Peor': df_jug[metrica_col].min()
                }
                
                comparativa_stats.append(stats)
            
            df_comp_stats = pd.DataFrame(comparativa_stats)
            
            st.dataframe(
                df_comp_stats.style.format({
                    f'Media {metrica_nombre}': '{:.2f}',
                    'Mejor': '{:.2f}',
                    'Peor': '{:.2f}'
                }),
                use_container_width=True
            )
        else:
            st.info("👆 Selecciona jugadores para comparar")


if __name__ == "__main__":
    main()