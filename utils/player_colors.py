"""Stable colors for player-specific visualizations."""

import colorsys
import hashlib
import unicodedata
from collections.abc import Iterable


def _player_key(player: object) -> str:
    value = unicodedata.normalize("NFKD", str(player).strip())
    return "".join(char for char in value if not unicodedata.combining(char)).casefold()


def build_player_color_map(players: Iterable[object]) -> dict[str, str]:
    """Return a deterministic, collision-free color for each player name."""
    keys = sorted({_player_key(player) for player in players} - {""})
    colors: dict[str, str] = {}
    used_colors: set[str] = set()

    for key in keys:
        attempt = 0
        while True:
            seed = key if attempt == 0 else f"{key}\0{attempt}"
            digest = hashlib.sha256(seed.encode("utf-8")).digest()
            hue = int.from_bytes(digest[:4], "big") / 2**32
            saturation = 0.68 + digest[4] / 255 * 0.18
            value = 0.82 + digest[5] / 255 * 0.16
            red, green, blue = colorsys.hsv_to_rgb(hue, saturation, value)
            color = "#{:02X}{:02X}{:02X}".format(
                round(red * 255),
                round(green * 255),
                round(blue * 255),
            )
            if color not in used_colors:
                colors[key] = color
                used_colors.add(color)
                break
            attempt += 1

    return colors


def get_player_color(color_map: dict[str, str], player: object) -> str:
    """Look up a player's color using the same normalization as the map builder."""
    return color_map[_player_key(player)]
