"""
Módulo para procesamiento de datos
"""

import pandas as pd
import numpy as np


def convertir_tiempo_a_minutos(tiempo_str):
    """
    Convierte tiempo en formato MM:SS a minutos decimales
    
    Args:
        tiempo_str: Tiempo en formato MM:SS o decimal
        
    Returns:
        float: Tiempo en minutos decimales
    """
    try:
        if pd.isna(tiempo_str):
            return np.nan
        
        # Si ya es float, devolver
        if isinstance(tiempo_str, (int, float)):
            return float(tiempo_str)
        
        tiempo_str = str(tiempo_str).strip()
        partes = tiempo_str.split(':')
        
        if len(partes) == 2:
            # Formato MM:SS
            minutos = float(partes[0])
            segundos = float(partes[1])
            return minutos + (segundos / 60)
        elif len(partes) == 3:
            # Formato HH:MM:SS
            horas = float(partes[0])
            minutos = float(partes[1])
            segundos = float(partes[2])
            return (horas * 60) + minutos + (segundos / 60)
        else:
            # Ya es decimal
            return float(tiempo_str)
    except:
        return np.nan


def procesar_datos(df):
    """
    Procesa los datos de partidos: conserva sus tareas Total y por tramos,
    convierte tiempo y calcula métricas.
    
    Args:
        df (pd.DataFrame): DataFrame crudo
        
    Returns:
        pd.DataFrame: DataFrame procesado
    """
    from utils.filtros import filtrar_solo_partidos

    df = filtrar_solo_partidos(df)

    # Filtrar solo registros con jugador
    df = df[df['player'].notna()].copy()
    
    # Convertir tiempo a minutos decimales
    if df['time'].dtype == 'object':
        df['time'] = df['time'].apply(convertir_tiempo_a_minutos)
    
    # Calcular HSR relativo si no existe o está vacío
    if 'hsr_rel' not in df.columns or df['hsr_rel'].isna().all():
        df['hsr_rel'] = np.where(df['time'] > 0, df['hsr'] / df['time'], 0)
    
    # Calcular HMLD relativo si no existe o está vacío
    if 'hmld_relative' not in df.columns or df['hmld_relative'].isna().all():
        df['hmld_relative'] = np.where(df['time'] > 0, df['hmld'] / df['time'], 0)
    
    # Convertir date a datetime
    df['date'] = pd.to_datetime(df['date'], format='%m/%d/%Y', errors='coerce')
    
    return df


def filtrar_por_fechas(df, fecha_desde, fecha_hasta):
    """
    Filtra el DataFrame por rango de fechas
    Convierte fechas a datetime si son strings
    """
    import pandas as pd
    
    # Asegurar que las fechas son datetime
    if isinstance(fecha_desde, str):
        fecha_desde = pd.to_datetime(fecha_desde)
    if isinstance(fecha_hasta, str):
        fecha_hasta = pd.to_datetime(fecha_hasta)
    
    # Asegurar que df['date'] es datetime
    if df['date'].dtype == 'object':
        df['date'] = pd.to_datetime(df['date'])
    
    df_filtrado = df[(df['date'] >= fecha_desde) & (df['date'] <= fecha_hasta)].copy()
    return df_filtrado


def obtener_partidos_disponibles(df):
    """
    Obtiene lista de partidos disponibles en el DataFrame
    
    Args:
        df (pd.DataFrame): DataFrame con datos
        
    Returns:
        pd.DataFrame: DataFrame con partidos únicos (date, session)
    """
    partidos = df.groupby('date').agg({
        'session': 'first'
    }).reset_index()
    
    partidos = partidos.sort_values('date')
    
    # Crear etiqueta descriptiva
    partidos['label'] = partidos.apply(
        lambda x: f"{x['session']} - {x['date'].strftime('%d/%m/%Y')}", 
        axis=1
    )
    
    return partidos


def filtrar_por_partido(df, fecha_partido):
    """
    Filtra datos de un partido específico
    
    Args:
        df (pd.DataFrame): DataFrame con datos
        fecha_partido (datetime): Fecha del partido
        
    Returns:
        pd.DataFrame: DataFrame con datos del partido
    """
    df_partido = df[df['date'] == fecha_partido].copy()
    return df_partido


def limpiar_datos(df):
    """
    Limpia el DataFrame eliminando duplicados y valores inválidos
    
    Args:
        df (pd.DataFrame): DataFrame a limpiar
        
    Returns:
        pd.DataFrame: DataFrame limpio
    """
    # Eliminar duplicados
    df = df.drop_duplicates(subset=['date', 'player'], keep='first')
    
    # Eliminar registros con time = 0 o negativo
    df = df[df['time'] > 0].copy()
    
    return df
