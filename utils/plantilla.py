"""
Módulo de Plantilla - Gestión de datos del Excel de plantilla
Carga información de jugadores (posición, fecha nacimiento, etc.)
"""

import pandas as pd
from pathlib import Path
import re
import unicodedata
import warnings


# Ruta al archivo Excel de plantilla
RUTA_PLANTILLA = 'assets/jugadores/Plantillas CE Europa.XLSX'
HOJA_PLANTILLA = 'First Team'


def _normalizar_texto(valor):
    """Normaliza espacios, mayúsculas y acentos for lookup comparisons."""
    texto = str(valor).strip()
    texto = re.sub(r"\s+", " ", texto)
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(
        caracter for caracter in texto if not unicodedata.combining(caracter)
    ).casefold()


def _limpiar_campo(valor):
    """Trim a text field and collapse accidental repeated whitespace."""
    if pd.isna(valor):
        return ""
    texto = str(valor).replace("\ufeff", "").replace("\u200b", "")
    texto = "".join(
        caracter for caracter in texto
        if unicodedata.category(caracter) not in {"Cc", "Cf"}
    )
    return re.sub(r"\s+", " ", texto).strip()


def cargar_plantilla_europa():
    """
    Carga el archivo Excel con la plantilla del First Team
    
    Returns:
        pd.DataFrame: DataFrame con columnas:
            - Jugador: Nombre completo
            - Posición: Defensa, Centrocampista, Delantero
            - F. Nacimiento: Fecha de nacimiento
            - Jugador GPS: Nombre usado en archivos GPS
            
    Raises:
        FileNotFoundError: Si no existe el archivo
        ValueError: Si la hoja no existe o faltan columnas
    """
    ruta = Path(RUTA_PLANTILLA)
    
    if not ruta.exists():
        raise FileNotFoundError(f"No se encuentra el archivo de plantilla: {RUTA_PLANTILLA}")
    
    try:
        # Leer Excel
        df = pd.read_excel(ruta, sheet_name=HOJA_PLANTILLA)
        
        # Verificar columnas requeridas
        columnas_requeridas = ['Jugador', 'Posición', 'F. Nacimiento', 'Jugador GPS']
        
        for col in columnas_requeridas:
            if col not in df.columns:
                raise ValueError(f"Falta la columna '{col}' en la hoja '{HOJA_PLANTILLA}'")
        
        # Limpiar datos
        df = df.dropna(subset=['Jugador GPS'])  # Eliminar filas sin nombre GPS
        df['Jugador GPS'] = df['Jugador GPS'].map(_limpiar_campo)
        df['Jugador'] = df['Jugador'].map(_limpiar_campo)
        df['Posición'] = df['Posición'].map(_limpiar_campo)
        
        # Verificar que Jugador GPS no tenga duplicados
        duplicados = df[df['Jugador GPS'].duplicated()]['Jugador GPS'].tolist()
        if duplicados:
            warnings.warn(
                f"Duplicate GPS player names in plantilla: {duplicados}",
                RuntimeWarning,
                stacklevel=2,
            )
        
        return df
        
    except Exception as e:
        raise ValueError(f"Error al leer el archivo Excel: {e}")


def mapear_posicion(nombre_gps, df_plantilla):
    """
    Busca la posición de un jugador por su nombre GPS
    
    Args:
        nombre_gps (str): Nombre del jugador en archivos GPS (ej: 'Adnane', 'Sgro')
        df_plantilla (pd.DataFrame): DataFrame con la plantilla cargada
        
    Returns:
        str: Posición del jugador ('Defensa', 'Centrocampista', 'Delantero')
             o 'Sin posición' si no se encuentra
    
    Examples:
        >>> df = cargar_plantilla_europa()
        >>> mapear_posicion('Adnane', df)
        'Centrocampista'
        >>> mapear_posicion('Sgro', df)
        'Defensa'
    """
    if df_plantilla is None or len(df_plantilla) == 0:
        return 'Sin posición'
    
    nombre_normalizado = _normalizar_texto(nombre_gps)
    if not nombre_normalizado:
        return 'Sin posición'
    name_columns = [
        column for column in ('Jugador GPS', 'Jugador')
        if column in df_plantilla.columns
    ]

    for name_column in name_columns:
        nombres_normalizados = df_plantilla[name_column].map(_normalizar_texto)
        match = df_plantilla[nombres_normalizados == nombre_normalizado]
        if len(match) > 0:
            return _limpiar_campo(match['Posición'].iloc[0])

    # Admitir diferencias entre nombres completos y alias GPS, sin permitir
    # coincidencias de una o dos letras.
    if len(nombre_normalizado) >= 3:
        candidate_frames = []
        for name_column in name_columns:
            nombres_normalizados = df_plantilla[name_column].map(_normalizar_texto)
            candidatos = df_plantilla[
                nombres_normalizados.map(
                    lambda candidato: (
                        nombre_normalizado in candidato
                        or candidato in nombre_normalizado
                    )
                )
            ].copy()
            if not candidatos.empty:
                candidatos["_match_length"] = candidatos[name_column].map(
                    lambda candidato: len(_normalizar_texto(candidato))
                )
                candidate_frames.append(candidatos)

        if candidate_frames:
            candidatos = pd.concat(candidate_frames).drop_duplicates()
            mejor_match = candidatos.sort_values(
                "_match_length",
                ascending=False,
            ).iloc[0]
            return _limpiar_campo(mejor_match['Posición'])
    
    return 'Sin posición'


def obtener_info_jugador(nombre_gps, df_plantilla):
    """
    Obtiene toda la información de un jugador
    
    Args:
        nombre_gps (str): Nombre del jugador en archivos GPS
        df_plantilla (pd.DataFrame): DataFrame con la plantilla
        
    Returns:
        dict: Diccionario con info del jugador o None si no existe
            {
                'nombre_completo': str,
                'posicion': str,
                'fecha_nacimiento': datetime,
                'edad': int
            }
    """
    if df_plantilla is None or len(df_plantilla) == 0:
        return None
    
    match = df_plantilla[df_plantilla['Jugador GPS'] == nombre_gps]
    
    if len(match) == 0:
        return None
    
    jugador = match.iloc[0]
    
    # Calcular edad
    try:
        fecha_nac = pd.to_datetime(jugador['F. Nacimiento'])
        hoy = pd.Timestamp.now()
        edad = (hoy - fecha_nac).days // 365
    except:
        edad = None
    
    return {
        'nombre_completo': jugador['Jugador'],
        'posicion': jugador['Posición'],
        'fecha_nacimiento': jugador['F. Nacimiento'],
        'edad': edad
    }


def obtener_jugadores_por_posicion(df_plantilla, posicion):
    """
    Obtiene lista de jugadores de una posición específica
    
    Args:
        df_plantilla (pd.DataFrame): DataFrame con la plantilla
        posicion (str): 'Defensa', 'Centrocampista', o 'Delantero'
        
    Returns:
        list: Lista de nombres GPS de jugadores de esa posición
    """
    if df_plantilla is None or len(df_plantilla) == 0:
        return []
    
    jugadores = df_plantilla[df_plantilla['Posición'] == posicion]['Jugador GPS'].tolist()
    
    return jugadores


def verificar_plantilla():
    """
    Verifica que la plantilla se pueda cargar correctamente
    
    Returns:
        tuple: (bool, str) - (éxito, mensaje)
    """
    try:
        df = cargar_plantilla_europa()
        
        # Contar por posición
        stats = df['Posición'].value_counts()
        
        mensaje = f"✅ Plantilla cargada correctamente:\n"
        mensaje += f"  - Total jugadores: {len(df)}\n"
        
        for posicion, count in stats.items():
            mensaje += f"  - {posicion}: {count} jugadores\n"
        
        # Verificar duplicados
        duplicados = df[df['Jugador GPS'].duplicated()]['Jugador GPS'].tolist()
        if duplicados:
            mensaje += f"\n⚠️ Duplicados encontrados: {', '.join(duplicados)}"
        
        return True, mensaje
        
    except Exception as e:
        return False, f"❌ Error: {e}"


if __name__ == "__main__":
    # Test del módulo
    print("Verificando plantilla...")
    exito, mensaje = verificar_plantilla()
    print(mensaje)
    
    if exito:
        df = cargar_plantilla_europa()
        print("\n" + "="*50)
        print("Ejemplo de uso:")
        print("="*50)
        
        # Probar con algunos jugadores
        jugadores_test = ['Adnane', 'Sgro', 'Pla', 'Khalid']
        
        for jugador in jugadores_test:
            posicion = mapear_posicion(jugador, df)
            info = obtener_info_jugador(jugador, df)
            
            print(f"\n{jugador}:")
            print(f"  Posición: {posicion}")
            if info:
                print(f"  Nombre completo: {info['nombre_completo']}")
                if info['edad']:
                    print(f"  Edad: {info['edad']} años")