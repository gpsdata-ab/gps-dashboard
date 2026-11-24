"""Manual match references typed by the staff, saved in Google Drive.

The values live in ``europa/prescripcion_carga/referencias_manuales.csv``
(one row per player and metric), so they survive app restarts and are
shared by the whole staff. The file can be opened in Drive or Excel.
"""

from __future__ import annotations

import io
from datetime import date

import pandas as pd

from .drive_loader import FOLDER_IDS, autenticar_google_drive

FOLDER_NAME = "prescripcion_carga"
FILE_NAME = "referencias_manuales.csv"
COLUMNS = ["jugador", "metrica", "valor", "fecha", "usuario"]
_FOLDER_MIME = "application/vnd.google-apps.folder"


class ManualReferencesError(RuntimeError):
    """Google Drive could not be read or written."""


# --- table helpers (no Drive access) -----------------------------------------

def empty_table() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)


def parse_csv(text: str) -> pd.DataFrame:
    """Read the CSV stored in Drive (';' separated, decimal comma)."""
    if not text or not text.strip():
        return empty_table()
    table = pd.read_csv(io.StringIO(text), sep=";", decimal=",", dtype=str)
    for column in COLUMNS:
        if column not in table.columns:
            table[column] = ""
    table = table[COLUMNS].fillna("")
    table["valor"] = pd.to_numeric(
        table["valor"].str.replace(",", ".", regex=False), errors="coerce"
    )
    table = table[table["jugador"].str.strip().ne("") & table["valor"].notna()]
    return table.reset_index(drop=True)


def to_csv_text(table: pd.DataFrame) -> str:
    ordered = table[COLUMNS].sort_values(["metrica", "jugador"])
    return ordered.to_csv(sep=";", decimal=",", index=False)


def apply_changes(
    table: pd.DataFrame,
    metric: str,
    changes: dict[str, float | None],
    user: str,
    today: date | None = None,
) -> pd.DataFrame:
    """Set (value) or remove (None) one metric's manual value for some players."""
    today = today or date.today()
    keep = ~((table["metrica"] == metric) & table["jugador"].isin(changes))
    new_rows = pd.DataFrame(
        [
            {
                "jugador": player,
                "metrica": metric,
                "valor": float(value),
                "fecha": today.strftime("%d/%m/%Y"),
                "usuario": user,
            }
            for player, value in changes.items()
            if value is not None and pd.notna(value)
        ],
        columns=COLUMNS,
    )
    frames = [frame for frame in (table[keep], new_rows) if not frame.empty]
    if not frames:
        return empty_table()
    return pd.concat(frames, ignore_index=True)[COLUMNS]


def values_for_metric(table: pd.DataFrame, metric: str) -> dict[str, dict]:
    """{player: {'valor', 'fecha', 'usuario'}} for one metric."""
    rows = table[table["metrica"] == metric]
    return {
        row["jugador"]: {"valor": float(row["valor"]), "fecha": row["fecha"], "usuario": row["usuario"]}
        for _, row in rows.iterrows()
    }


# --- Google Drive --------------------------------------------------------------

def _quote(text: str) -> str:
    return text.replace("\\", "\\\\").replace("'", "\\'")


def _find(drive, parent_id: str, title: str, mime: str | None = None):
    query = f"'{parent_id}' in parents and title = '{_quote(title)}' and trashed = false"
    if mime:
        query += f" and mimeType = '{mime}'"
    found = drive.ListFile({"q": query}).GetList()
    return found[0] if found else None


def _get_file(drive):
    """Return the Drive CSV, creating the folder and the file if missing."""
    parent_id = FOLDER_IDS["europa"]
    folder = _find(drive, parent_id, FOLDER_NAME, _FOLDER_MIME)
    if folder is None:
        folder = drive.CreateFile(
            {"title": FOLDER_NAME, "mimeType": _FOLDER_MIME, "parents": [{"id": parent_id}]}
        )
        folder.Upload()
    csv_file = _find(drive, folder["id"], FILE_NAME)
    if csv_file is None:
        # Service accounts cannot own files in a personal Drive (no storage
        # quota), so the file may have to be uploaded once by a person.
        try:
            csv_file = drive.CreateFile(
                {"title": FILE_NAME, "mimeType": "text/csv", "parents": [{"id": folder["id"]}]}
            )
            csv_file.SetContentString(to_csv_text(empty_table()), encoding="utf-8")
            csv_file.Upload()
        except Exception as error:
            raise ManualReferencesError(
                f"Falta el archivo '{FILE_NAME}' en la carpeta de Google Drive "
                f"'europa/{FOLDER_NAME}'. Súbelo una vez (puede estar vacío) y "
                "vuelve a cargar la página."
            ) from error
    return csv_file


def _connect():
    drive = autenticar_google_drive(mostrar_mensajes=False)
    if drive is None:
        raise ManualReferencesError("No se pudo conectar con Google Drive.")
    return drive


def load_table() -> pd.DataFrame:
    """Read every saved manual reference from Drive."""
    try:
        csv_file = _get_file(_connect())
        return parse_csv(csv_file.GetContentString(encoding="utf-8", remove_bom=True))
    except ManualReferencesError:
        raise
    except Exception as error:  # Drive/network errors
        raise ManualReferencesError(str(error)) from error


def save_changes(metric: str, changes: dict[str, float | None], user: str) -> pd.DataFrame:
    """Apply changes on top of the latest Drive version and save it.

    The file is read again right before writing, so values saved meanwhile
    by other staff members are kept. Returns the saved table.
    """
    try:
        csv_file = _get_file(_connect())
        latest = parse_csv(csv_file.GetContentString(encoding="utf-8", remove_bom=True))
        updated = apply_changes(latest, metric, changes, user)
        csv_file.SetContentString(to_csv_text(updated), encoding="utf-8")
        csv_file.Upload()
        return updated
    except ManualReferencesError:
        raise
    except Exception as error:  # Drive/network errors
        raise ManualReferencesError(str(error)) from error
