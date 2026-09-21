"""
Módulo para carga de datos CSV
"""

import pandas as pd
import streamlit as st
import glob
from pathlib import Path
import re
import unicodedata


def normalizar_nombre_jugador(valor):
    """Return a stable key for matching roster and GPS player names."""
    if pd.isna(valor):
        return ""
    texto = str(valor).replace("\ufeff", "").replace("\u200b", "")
    texto = "".join(
        caracter for caracter in texto
        if unicodedata.category(caracter) not in {"Cc", "Cf"}
    )
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto.casefold()


def limpiar_texto(valor):
    """Trim text fields and remove invisible characters from imported files."""
    if pd.isna(valor):
        return ""
    texto = str(valor).replace("\ufeff", "").replace("\u200b", "")
    texto = "".join(
        caracter for caracter in texto
        if unicodedata.category(caracter) not in {"Cc", "Cf"}
    )
    return re.sub(r"\s+", " ", texto).strip()


def mapear_datos_con_plantilla(df_gps, df_plantilla, columna_jugador="player"):
    """
    Keep only roster players and apply the roster display name and position.

    The roster's ``Jugador GPS`` is the only join key. Matching is
    case-insensitive and ignores invisible characters and whitespace
    differences.
    """
    if df_gps is None or df_plantilla is None:
        return pd.DataFrame() if df_gps is None else df_gps.iloc[0:0].copy()
    if columna_jugador not in df_gps.columns:
        raise ValueError(f"Falta la columna de jugador '{columna_jugador}' en los datos GPS")

    required = {"Jugador", "Posición", "Jugador GPS"}
    missing = required - set(df_plantilla.columns)
    if missing:
        raise ValueError(f"Faltan columnas de plantilla: {sorted(missing)}")

    gps = df_gps.copy()
    roster = df_plantilla[list(required)].copy()
    # A frame loaded by the main app already carries the bridge key. Reusing
    # it makes this function safe when UBIKO prepares that same frame again.
    bridge_column = "Jugador GPS" if "Jugador GPS" in gps.columns else columna_jugador
    gps["_player_key"] = gps[bridge_column].map(normalizar_nombre_jugador)
    roster["_player_key"] = roster["Jugador GPS"].map(normalizar_nombre_jugador)
    roster["Jugador"] = roster["Jugador"].map(limpiar_texto)
    roster["Posición"] = roster["Posición"].map(limpiar_texto)
    roster["Jugador GPS"] = roster["Jugador GPS"].map(limpiar_texto)
    roster = roster[roster["_player_key"].ne("")].drop_duplicates(
        subset="_player_key", keep="first"
    )

    roster_for_merge = roster[["_player_key", "Jugador", "Posición", "Jugador GPS"]]
    if "Jugador GPS" in gps.columns:
        roster_for_merge = roster_for_merge.rename(columns={"Jugador GPS": "_roster_gps"})

    mapped = gps.merge(
        roster_for_merge,
        on="_player_key",
        how="inner",
        validate="many_to_one",
    )
    mapped[columna_jugador] = mapped["Jugador"]
    mapped["position"] = mapped["Posición"]
    if "_roster_gps" in mapped.columns:
        mapped["Jugador GPS"] = mapped["_roster_gps"]
        mapped = mapped.drop(columns=["_roster_gps"])
    return mapped.drop(columns=["_player_key", "Jugador", "Posición"])


@st.cache_data
def cargar_datos_csv(carpeta_csv):
    """
    Carga todos los archivos CSV de la carpeta
    
    Args:
        carpeta_csv (str): Ruta a la carpeta con archivos CSV
        
    Returns:
        pd.DataFrame: DataFrame concatenado con todos los datos
    """
    carpeta = Path(carpeta_csv)
    archivos = sorted(
        path for path in carpeta.rglob("*")
        if path.is_file() and path.suffix.casefold() == ".csv"
    )
    
    if not archivos:
        return None
    
    dfs = []
    archivos_procesados = 0
    archivos_con_error = 0
    
    for archivo in archivos:
        try:
            # Leer CSV con formato europeo (decimal=',', thousands='.')
            try:
                df = pd.read_csv(
                    archivo,
                    sep=';',
                    decimal=',',
                    thousands='.',
                    encoding='utf-8-sig',
                )
            except (UnicodeDecodeError, pd.errors.ParserError):
                df = pd.read_csv(
                    archivo,
                    sep=None,
                    engine='python',
                    decimal=',',
                    thousands='.',
                    encoding='latin1',
                )
            df.columns = [limpiar_texto(columna) for columna in df.columns]
            if 'player' in df.columns:
                df['player'] = df['player'].map(limpiar_texto)
            dfs.append(df)
            archivos_procesados += 1
            
        except Exception as e:
            archivos_con_error += 1
            st.warning(f"⚠️ Error leyendo {Path(archivo).name}: {str(e)}")
    
    if dfs:
        df_completo = pd.concat(dfs, ignore_index=True)
        
        # Mensaje informativo
        if archivos_procesados > 0:
            st.success(f"✅ {archivos_procesados} archivos cargados correctamente")
        if archivos_con_error > 0:
            st.warning(f"⚠️ {archivos_con_error} archivos con errores")
            
        return df_completo
    
    return None


def validar_columnas(df, columnas_requeridas):
    """
    Valida que el DataFrame tenga las columnas requeridas
    
    Args:
        df (pd.DataFrame): DataFrame a validar
        columnas_requeridas (list): Lista de columnas requeridas
        
    Returns:
        tuple: (bool, list) - (es_valido, columnas_faltantes)
    """
    columnas_presentes = set(df.columns)
    columnas_requeridas_set = set(columnas_requeridas)
    columnas_faltantes = columnas_requeridas_set - columnas_presentes
    
    es_valido = len(columnas_faltantes) == 0
    
    return es_valido, list(columnas_faltantes)


def obtener_info_dataset(df):
    """
    Obtiene información básica del dataset
    
    Args:
        df (pd.DataFrame): DataFrame a analizar
        
    Returns:
        dict: Diccionario con información del dataset
    """
    info = {
        'total_registros': len(df),
        'jugadores_unicos': df['player'].nunique() if 'player' in df.columns else 0,
        'partidos_unicos': df['date'].nunique() if 'date' in df.columns else 0,
        'fecha_min': df['date'].min() if 'date' in df.columns else None,
        'fecha_max': df['date'].max() if 'date' in df.columns else None,
        'columnas': list(df.columns),
        'memoria_mb': df.memory_usage(deep=True).sum() / 1024**2
    }
    
    return info
