"""
CE Europa - Aplicación de Análisis GPS
Aplicación principal (Landing page)
v2.5.0 - Sistema de autenticación y carga desde Google Drive
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# Importar configuración
from config import PAGE_TITLE, PAGE_ICON, LAYOUT

# Importar utilidades
from utils import (
    render_sidebar,
    cargar_datos_desde_drive,
    cargar_plantilla_desde_drive,
    convertir_tiempo_a_minutos,
    mapear_datos_con_plantilla,
)
from utils.auth import mostrar_login, mostrar_info_usuario
from utils.drive_loader import obtener_escudo_path

# Asegurar que pandas no convierte datetime a string
pd.options.mode.copy_on_write = True


def cargar_datos_en_sesion():
    """
    Carga datos desde Drive y actualiza session_state.

    Returns:
        bool: True si la carga fue exitosa.
    """
    df = cargar_datos_desde_drive(equipo='europa')

    if df is None or len(df) == 0:
        return False

    plantilla = cargar_plantilla_desde_drive(equipo='europa')
    if plantilla is None or plantilla.empty:
        st.error("❌ No se pudo cargar la plantilla maestra para mapear los jugadores GPS")
        return False
    try:
        df = mapear_datos_con_plantilla(df, plantilla)
    except ValueError as error:
        st.error(f"❌ Estructura de plantilla no válida: {error}")
        return False
    if df.empty:
        st.error("❌ Ningún jugador GPS coincide con la plantilla maestra")
        return False

    # Normalizar columnas base para asegurar métricas derivadas.
    if 'time' in df.columns:
        if df['time'].dtype == 'object':
            time_limpio = (
                df['time']
                .astype(str)
                .str.replace("'", "", regex=False)
                .str.strip()
                .replace({'': pd.NA, 'nan': pd.NA, 'None': pd.NA})
            )
            df['time'] = time_limpio.apply(convertir_tiempo_a_minutos)
        df['time'] = pd.to_numeric(df['time'], errors='coerce')

    if 'hsr' in df.columns:
        df['hsr'] = pd.to_numeric(df['hsr'], errors='coerce')

    # Calcular HSR relativo si no viene en el dataset.
    if 'hsr' in df.columns and 'time' in df.columns:
        recalcular_hsr_rel = ('hsr_rel' not in df.columns)
        if not recalcular_hsr_rel:
            df['hsr_rel'] = pd.to_numeric(df['hsr_rel'], errors='coerce')
            recalcular_hsr_rel = df['hsr_rel'].isna().all()

        if recalcular_hsr_rel:
            df['hsr_rel'] = np.where(df['time'] > 0, df['hsr'] / df['time'], np.nan)

    # Asegurar consistencia de tipos antes de guardar en sesión
    df['date'] = pd.to_datetime(df['date'])

    st.session_state.df_procesado = df
    st.session_state.datos_cargados = True
    st.session_state.fecha_desde = pd.to_datetime(df['date'].min())
    st.session_state.fecha_hasta = pd.to_datetime(df['date'].max())
    st.session_state.partido_seleccionado = pd.to_datetime(df['date'].max())
    st.session_state.ultima_carga_drive = datetime.now().strftime('%d/%m/%Y %H:%M')

    return True


# Configuración de la página
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout=LAYOUT,
    initial_sidebar_state="collapsed"  # ← CAMBIADO de "expanded" a "collapsed"
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .subtitle {
        font-size: 1.5rem;
        color: #666;
        text-align: center;
        margin-bottom: 3rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .new-badge {
        background-color: #ff6b6b;
        color: white;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
        font-size: 0.8rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


def main():
    # ==========================================
    # PASO 1: OCULTAR SIDEBAR SI NO AUTENTICADO
    # ==========================================
    if not st.session_state.get('autenticado', False):
        st.markdown("""
            <style>
            [data-testid="stSidebar"] {
                display: none !important;
            }
            </style>
        """, unsafe_allow_html=True)
    
    # ==========================================
    # PASO 2: AUTENTICACIÓN
    # ==========================================
    if not mostrar_login():
        st.stop()  # Detener ejecución si no está autenticado
    
    # ==========================================
    # PASO 3: RENDERIZAR SIDEBAR (ahora sí está autenticado)
    # ==========================================
    render_sidebar()
    
    # Mostrar info del usuario
    mostrar_info_usuario()
    
    # ==========================================
    # INICIALIZAR SESSION STATE
    # ==========================================
    if 'datos_cargados' not in st.session_state:
        st.session_state.datos_cargados = False
    if 'carga_automatica_intentada' not in st.session_state:
        st.session_state.carga_automatica_intentada = False
    
    # Header
    st.markdown('<h1 class="main-header">⚽ CE Europa - Análisis GPS</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Sistema de análisis de datos físicos y rendimiento</p>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # ==========================================
    # CONTENIDO PRINCIPAL
    # ==========================================
    
    if not st.session_state.get('datos_cargados', False):
        # ========================================
        # PANTALLA DE BIENVENIDA + CARGA DE DATOS
        # ========================================
        
        st.subheader("📂 Carga de Datos")

        # Auto-carga una vez por sesión tras autenticación.
        if not st.session_state.get('carga_automatica_intentada', False):
            st.info("⏳ Cargando datos automáticamente desde Google Drive...")
            with st.spinner("Cargando datos desde Drive..."):
                try:
                    carga_ok = cargar_datos_en_sesion()
                    st.session_state.carga_automatica_intentada = True

                    if carga_ok:
                        st.success("✅ Datos cargados automáticamente")
                        st.rerun()
                    else:
                        st.warning("⚠️ No se pudo cargar automáticamente. Puedes intentarlo manualmente.")
                except Exception as e:
                    st.session_state.carga_automatica_intentada = True
                    st.error(f"❌ Error en carga automática: {str(e)}")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("""
            **Instrucciones:**
            1. La app intenta cargar automáticamente al iniciar sesión
            2. Si falla o quieres refrescar, usa el botón de carga manual
            3. Una vez cargados, podrás navegar a las otras páginas
            """)
        
        with col2:
            if st.button("📥 Cargar/Actualizar datos desde Google Drive", type="primary", use_container_width=True):
                with st.spinner("Cargando datos desde Drive..."):
                    try:
                        carga_ok = cargar_datos_en_sesion()
                        st.session_state.carga_automatica_intentada = True

                        if carga_ok:
                            st.success("✅ Datos cargados correctamente")
                            st.rerun()
                        else:
                            st.error("❌ No se encontraron datos")
                            
                    except Exception as e:
                        st.error(f"❌ Error al cargar datos: {str(e)}")
        
        st.markdown("---")
        
        # Información adicional
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            # Logo del CE Europa
            try:
                st.image(obtener_escudo_path(), width=400)
            except:
                st.info("⚽ CE Europa")
            
            st.markdown("""
            ### 👋 Bienvenido al Sistema de Análisis GPS
            
            Esta aplicación te permite analizar datos físicos de los partidos del CE Europa
            con herramientas avanzadas de visualización y análisis estadístico.
            
            #### 🚀 Para comenzar:
            
            1. **Espera** la carga automática inicial desde Google Drive
            2. Si hace falta, pulsa **Cargar/Actualizar datos** arriba
            3. **Navega** por las diferentes páginas del menú lateral
            
            #### 📊 Páginas disponibles:
            
            - **📊 Análisis de partidos:** Player Cards y análisis del partido
            - **📊 Estatus del Equipo:** <span class="new-badge">NUEVO</span> Vista panorámica con gráficos avanzados
            - **📍 GPS UBIKO:** <span class="new-badge">NUEVO</span> Control real de carga por jugador con CSV Ubiko
            
            ---
            
            **Nota:** Los datos se cargan automáticamente desde Google Drive
            """, unsafe_allow_html=True)
    
    else:
        # ========================================
        # PANTALLA DE DATOS CARGADOS
        # ========================================
        
        st.success("✅ **Datos cargados y listos**")
        
        df = st.session_state.df_procesado
        
        # Métricas principales
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "📁 Total Registros",
                len(df),
                help="Registros totales en el dataset (task='Total')"
            )
        
        with col2:
            st.metric(
                "👥 Jugadores",
                df['player'].nunique(),
                help="Jugadores únicos en el dataset"
            )
        
        with col3:
            st.metric(
                "⚽ Partidos",
                df['date'].nunique(),
                help="Partidos únicos en el dataset"
            )
        
        with col4:
            # CORREGIDO: Asegurar conversión a datetime
            fecha_min = pd.to_datetime(df['date'].min())
            fecha_max = pd.to_datetime(df['date'].max())
            dias = (fecha_max - fecha_min).days
            st.metric("📅 Rango", f"{dias} días")
        
        st.markdown("---")
        
        # Info detallada
        st.subheader("📊 Resumen del Dataset")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Fechas disponibles:**")
            # CORREGIDO: Asegurar conversión a datetime
            fecha_min = pd.to_datetime(df['date'].min())
            fecha_max = pd.to_datetime(df['date'].max())
            st.caption(f"Desde: {fecha_min.strftime('%d/%m/%Y')}")
            st.caption(f"Hasta: {fecha_max.strftime('%d/%m/%Y')}")
            
            st.markdown("**Jugadores registrados:**")
            # CORREGIDO: dropna().astype(str) para evitar errores con NaN
            jugadores = sorted(df['player'].dropna().astype(str).unique())
            st.caption(f"{len(jugadores)} jugadores totales")
        
        with col2:
            st.markdown("**Partidos disponibles:**")
            fechas_partidos = sorted(df['date'].unique())
            for fecha in fechas_partidos[-5:]:  # Últimos 5
                # CORREGIDO: Asegurar que fecha es datetime
                fecha_dt = pd.to_datetime(fecha)
                st.caption(f"📅 {fecha_dt.strftime('%d/%m/%Y')}")
            if len(fechas_partidos) > 5:
                st.caption(f"... y {len(fechas_partidos) - 5} más")
        
        st.markdown("---")
        
        # Instrucciones de uso
        st.markdown("""
        ### 🎯 Cómo usar la aplicación

        La herramienta está estructurada en dos grandes bloques de trabajo:

        #### 📋 Módulos disponibles:

        **A. 📋 Prescripción de la Carga (En desarrollo)**
        - Configuración de microciclos tipo (2 a 6 sesiones).
        - Asignación de % de carga por sesión y jugador (Return to Play, fatiga).
        - Control de ejecución y seguimiento semanal mediante sistema de alertas "semáforo".

        **B. 📊 Análisis de la Carga / Partidos**
        - Análisis panorámico del rendimiento del equipo en partidos.
        - Filtros simplificados por estadístico (Media, Máxima, Sumatorio) y tramos de partido.

        #### 💡 Características principales:
        - Mapeo de métricas clave: HSR, Sprint, HMLD y Max Speed.
        - Normalización automática de métricas a 75 minutos para jugadores con menor rodaje o suplentes.
        - Visualizaciones interactivas de carga y rendimiento.
        
        ---
        
        ### 📖 Métricas disponibles
        """, unsafe_allow_html=True)
        
        # Mostrar métricas disponibles en columnas
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Métricas de Distancia:**")
            for metrica in ['HSR', 'Distancia Total', 'Distancia a Sprint']:
                st.markdown(f"- ✅ {metrica}")
        
        with col2:
            st.markdown("**Métricas de Intensidad:**")
            for metrica in ['Sprints', 'Velocidad Máxima', 'Aceleraciones', 'Desaceleraciones']:
                st.markdown(f"- ✅ {metrica}")
        
        with col3:
            st.markdown("**Métricas Relativas:**")
            for metrica in ['HSR Relativo', 'Distancia por Minuto', 'HMLD', 'HMLD Relativo']:
                st.markdown(f"- ✅ {metrica}")
        
        st.markdown("---")
        
        # Navegación
        st.info("👈 **Ahora puedes navegar a las otras páginas usando el menú lateral**")
        
        # Vista previa de datos
        with st.expander("📋 Vista previa de datos"):
            st.dataframe(
                df.head(20),
                use_container_width=True
            )
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 2rem;'>
        <p><strong>CE Europa - Sistema de Análisis GPS</strong></p>
        <p>Desarrollado con ❤️ usando Streamlit</p>
        <p style='font-size: 0.8rem;'>v2.5.0 - Febrero 2025</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
