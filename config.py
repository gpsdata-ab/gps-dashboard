"""
Configuración centralizada de la aplicación
"""

from pathlib import Path

# Rutas
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
UTILS_DIR = BASE_DIR / "utils"

# Configuración de datos
COLUMNAS_REQUERIDAS = [
    'session', 'task', 'date', 'position', 'dorsal', 'player', 'time',
    'total_distance', 'minute_distance', 'max_speed', 'hsr', 'hsr_rel',
    'distance_vrange6', 'sprints', 'num_acc_expl', 'num_dec_expl',
    'hmld', 'hmld_relative'
]

# Métricas disponibles para análisis
METRICAS_DICT = {
    'HSR': 'hsr',
    'HSR Relativo': 'hsr_rel',
    'Distancia Total': 'total_distance',
    'Distancia por Minuto': 'minute_distance',
    'Velocidad Máxima': 'max_speed',
    'Distancia a Sprint': 'distance_vrange6',
    'Sprints': 'sprints',
    'Aceleraciones': 'num_acc_expl',
    'Deceleraciones': 'num_dec_expl',
    'HMLD': 'hmld',
    'HMLD Relativo': 'hmld_relative'
}

# Métricas acumulativas (se normalizan a 94 min)
METRICAS_ACUMULATIVAS = [
    'total_distance', 'hsr', 'distance_vrange6', 'sprints',
    'num_acc_expl', 'num_dec_expl', 'hmld'
]

# Métricas relativas (NO se normalizan)
METRICAS_RELATIVAS = [
    'minute_distance', 'max_speed', 'hsr_rel', 'hmld_relative'
]

# Parámetros de normalización
MINUTOS_NORMALIZACION = 94
MINUTOS_MINIMOS = 60  # Mínimo de minutos para incluir en referencias

# Referencias de partido de "Prescripción de la carga" (partido = 100%).
# Se pueden ajustar aquí sin tocar el resto del código.
REFERENCIA_MINUTOS = 75            # Minutaje al que se lleva cada partido (60'-75' se escalan a 75')
REFERENCIA_MINUTOS_MINIMOS = 60    # Partidos con menos minutos no cuentan (salvo Max speed)
REFERENCIA_VIDA_MEDIA_DIAS = 30    # Percentil 70: un partido de hace 30 días pesa la mitad
REFERENCIA_PICO_ANTIGUO_DIAS = 60  # Pico máximo más antiguo que esto se marca con ⚠️
REFERENCIA_ULTIMOS_PARTIDOS = 4    # Partidos de "Promedio (últimos N partidos)"

# Configuración de Streamlit
PAGE_TITLE = "CE Europa - Análisis GPS"
PAGE_ICON = "⚽"
LAYOUT = "wide"

# Colores para gráficos
COLORES = {
    'primario': '#1f77b4',      # Azul
    'secundario': '#ff7f0e',    # Naranja
    'referencia': '#d62728',    # Rojo
    'exito': '#2ca02c',         # Verde
    'advertencia': '#ff7f0e'    # Naranja
}
