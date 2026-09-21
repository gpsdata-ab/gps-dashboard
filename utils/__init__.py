"""
Módulo de utilidades para la aplicación CE Europa GPS
"""

from .data_loader import cargar_datos_csv, validar_columnas, mapear_datos_con_plantilla
from .drive_loader import cargar_datos_desde_drive, cargar_plantilla_desde_drive, obtener_info_dataset
from .data_processor import (
    procesar_datos, 
    convertir_tiempo_a_minutos,
    filtrar_por_fechas,
    obtener_partidos_disponibles,
    filtrar_por_partido,
    limpiar_datos
)
from .calculations import (
    calcular_referencias_normalizadas,
    normalizar_a_94min,
    calcular_estadisticas_partido,
    obtener_referencia_metrica,
    calcular_evolucion_temporal,
    calcular_z_score,
    clasificar_rendimiento
)
from .visualizations import (
    crear_player_card,
    crear_dashboard_player_cards,
    calcular_promedio_ultimos_partidos,
    obtener_foto_jugador
)
from .sidebar import render_sidebar

from .plantilla import (
    cargar_plantilla_europa,
    mapear_posicion,
    obtener_info_jugador,
    obtener_jugadores_por_posicion,
    verificar_plantilla
)

from .pdf_evolucion_individual import generar_pdf_evolucion_individual

from .auth import (
    mostrar_login,
    cerrar_sesion,
    mostrar_info_usuario
)

from .filtros import render_filtro_partidos

# ← ELIMINADA LÍNEA: from utils.proteccion import inicializar_pagina

__all__ = [
    # data_loader
    'validar_columnas',
    'cargar_datos_csv',
    'mapear_datos_con_plantilla',
    'obtener_info_dataset',
    # drive_loader
    'cargar_datos_desde_drive',
    'cargar_plantilla_desde_drive',
    # data_processor
    'procesar_datos',
    'convertir_tiempo_a_minutos',
    'filtrar_por_fechas',
    'obtener_partidos_disponibles',
    'filtrar_por_partido',
    'limpiar_datos',
    # calculations
    'calcular_referencias_normalizadas',
    'normalizar_a_94min',
    'calcular_estadisticas_partido',
    'obtener_referencia_metrica',
    'calcular_evolucion_temporal',
    'calcular_z_score',
    'clasificar_rendimiento',
    # visualizations
    'crear_player_card',
    'crear_dashboard_player_cards',
    'calcular_promedio_ultimos_partidos',
    'obtener_foto_jugador',
    # sidebar
    'render_sidebar',
    # filtros
    'render_filtro_partidos',
    # plantilla
    'cargar_plantilla_europa',
    'mapear_posicion',
    'obtener_info_jugador',
    'obtener_jugadores_por_posicion',
    'verificar_plantilla',
    # auth
    'mostrar_login',
    'cerrar_sesion',
    'mostrar_info_usuario',
    # pdf
    'generar_pdf_evolucion_individual'
]
