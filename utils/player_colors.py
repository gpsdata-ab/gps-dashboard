"""Clearly distinguishable colors for player-specific visualizations.

Colors are assigned per chart, to the players actually shown, from a
high-contrast categorical palette. The first ten players get ten clearly
different colors; beyond that the palette repeats with a hatch pattern so
every bar remains identifiable.
"""

import unicodedata
from collections.abc import Iterable

# D3 / Tableau "category10": ten saturated hues designed to be told apart
# on a white background, in this order.
DISTINCT_PALETTE = [
    "#1F77B4",  # azul
    "#FF7F0E",  # naranja
    "#2CA02C",  # verde
    "#D62728",  # rojo
    "#9467BD",  # morado
    "#8C564B",  # marrón
    "#E377C2",  # rosa
    "#7F7F7F",  # gris
    "#BCBD22",  # oliva
    "#17BECF",  # cian
]
# Pattern used for each pass over the palette ("" = solid bar).
OVERFLOW_PATTERNS = ["", "/", "x", ".", "+", "\\"]


def _player_key(player: object) -> str:
    value = unicodedata.normalize("NFKD", str(player).strip())
    return "".join(char for char in value if not unicodedata.combining(char)).casefold()


def build_player_style_map(players: Iterable[object]) -> dict[str, tuple[str, str]]:
    """Return a distinct ``(color, pattern)`` per player, in the given order.

    Pass only the players that appear in the chart so the palette is spent
    on them; duplicates and empty names are ignored.
    """
    styles: dict[str, tuple[str, str]] = {}
    for player in players:
        key = _player_key(player)
        if not key or key in styles:
            continue
        index = len(styles)
        color = DISTINCT_PALETTE[index % len(DISTINCT_PALETTE)]
        pattern = OVERFLOW_PATTERNS[
            (index // len(DISTINCT_PALETTE)) % len(OVERFLOW_PATTERNS)
        ]
        styles[key] = (color, pattern)
    return styles


def get_player_style(style_map: dict[str, tuple[str, str]], player: object) -> tuple[str, str]:
    """Look up a player's ``(color, pattern)`` using the map's normalization."""
    return style_map[_player_key(player)]
