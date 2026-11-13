"""Rules for the match references of 'Prescripción de la carga'.

Run from the project folder with:  python -m unittest discover tests
The values reproduce real cases from the 2026/27 GPS exports.
"""

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.reference_engine import calculate_references  # noqa: E402


def matches(rows):
    """Build one row per player-match: (player, position, session, date, time, hsr, max_speed)."""
    return pd.DataFrame(
        rows,
        columns=["player", "position", "session", "date", "time", "hsr", "max_speed"],
    )


def by_player(references):
    return references.set_index("player")


class PeakReferenceTests(unittest.TestCase):
    def test_short_appearance_is_not_scaled_into_a_huge_peak(self):
        # Real bug: 604.5 m HSR in 7.7' was scaled to 75' -> 5,852 m.
        df = matches([
            ("Expósito", "Delantero", "J3 Hércules", "2026-09-12", 7.7, 604.5, 30.0),
            ("Expósito", "Delantero", "J1 Jaén", "2026-08-31", 106.2, 430.0, 31.0),
        ])
        ref = by_player(calculate_references(df, "hsr", "max", reference_date="2026-09-30"))
        self.assertAlmostEqual(ref.at["Expósito", "baseline_target"], 430.0)
        self.assertIn("J1 Jaén", ref.at["Expósito", "origin"])
        self.assertIn("106'", ref.at["Expósito", "origin"])

    def test_matches_between_60_and_75_minutes_are_scaled_to_75(self):
        df = matches([("Tito", "Defensa", "S30", "2026-08-20", 66.0, 374.0, 30.0)])
        ref = by_player(calculate_references(df, "hsr", "max", reference_date="2026-08-20"))
        self.assertAlmostEqual(ref.at["Tito", "baseline_target"], 374.0 * 75 / 66.0)

    def test_long_matches_are_never_scaled_down(self):
        # J5 recorded ~110' for everyone (recording window, not minutes played).
        df = matches([("Enol", "Defensa", "J5", "2026-09-27", 109.9, 1045.0, 32.0)])
        ref = by_player(calculate_references(df, "hsr", "max", reference_date="2026-09-27"))
        self.assertAlmostEqual(ref.at["Enol", "baseline_target"], 1045.0)

    def test_peak_is_all_time_best_and_updates_with_a_new_match(self):
        df = matches([
            ("Anglès", "Defensa", "J1 Jaén", "2026-08-31", 84.0, 938.0, 31.0),
            ("Anglès", "Defensa", "J4", "2026-09-20", 95.0, 700.0, 31.0),
        ])
        before = by_player(calculate_references(df, "hsr", "max", reference_date="2026-09-25"))
        self.assertAlmostEqual(before.at["Anglès", "baseline_target"], 938.0)

        new_best = matches([("Anglès", "Defensa", "J6", "2026-10-04", 96.0, 990.0, 31.0)])
        after = by_player(calculate_references(
            pd.concat([df, new_best]), "hsr", "max", reference_date="2026-10-04"
        ))
        self.assertAlmostEqual(after.at["Anglès", "baseline_target"], 990.0)

    def test_matches_after_the_md_date_are_ignored(self):
        df = matches([
            ("Anglès", "Defensa", "J1", "2026-08-31", 84.0, 600.0, 31.0),
            ("Anglès", "Defensa", "J6", "2026-10-04", 96.0, 990.0, 31.0),
        ])
        ref = by_player(calculate_references(df, "hsr", "max", reference_date="2026-09-01"))
        self.assertAlmostEqual(ref.at["Anglès", "baseline_target"], 600.0)

    def test_old_peak_is_flagged(self):
        df = matches([
            ("Padillo", "Medio", "S5", "2026-07-15", 80.0, 1000.0, 31.0),
            ("Padillo", "Medio", "J5", "2026-09-27", 95.0, 800.0, 31.0),
        ])
        ref = by_player(calculate_references(df, "hsr", "max", reference_date="2026-09-27"))
        self.assertTrue(ref.at["Padillo", "origin"].startswith("⚠️"))
        recent = by_player(calculate_references(df, "hsr", "max", reference_date="2026-08-01"))
        self.assertFalse(recent.at["Padillo", "origin"].startswith("⚠️"))


class AverageAndPercentileTests(unittest.TestCase):
    def test_last_n_averages_the_most_recent_valid_matches(self):
        df = matches([
            ("Gori", "Medio", "S5", "2026-07-15", 90.0, 1000.0, 30.0),  # oldest, left out
            ("Gori", "Medio", "J1", "2026-08-31", 90.0, 400.0, 30.0),
            ("Gori", "Medio", "J2", "2026-09-06", 20.0, 900.0, 30.0),   # < 60', not valid
            ("Gori", "Medio", "J3", "2026-09-12", 90.0, 500.0, 30.0),
            ("Gori", "Medio", "J4", "2026-09-19", 90.0, 600.0, 30.0),
            ("Gori", "Medio", "J5", "2026-09-27", 90.0, 700.0, 30.0),
        ])
        ref = by_player(calculate_references(df, "hsr", "last_n", reference_date="2026-09-30"))
        self.assertAlmostEqual(ref.at["Gori", "baseline_target"], (400 + 500 + 600 + 700) / 4)
        self.assertTrue(ref.at["Gori", "origin"].startswith("Últimos 4 partidos"))

    def test_last_n_with_fewer_matches_uses_what_there_is(self):
        df = matches([
            ("Enol", "Lateral", "J4", "2026-09-19", 90.0, 600.0, 30.0),
            ("Enol", "Lateral", "J5", "2026-09-27", 90.0, 800.0, 30.0),
        ])
        ref = by_player(calculate_references(df, "hsr", "last_n", reference_date="2026-09-30"))
        self.assertAlmostEqual(ref.at["Enol", "baseline_target"], 700.0)

    def test_mean_is_the_plain_average_of_the_given_matches(self):
        df = matches([
            ("Gori", "Medio", "S11", "2026-08-28", 90.0, 300.0, 30.0),
            ("Gori", "Medio", "J5", "2026-09-27", 90.0, 600.0, 30.0),
        ])
        ref = by_player(calculate_references(df, "hsr", "mean", reference_date="2026-09-27"))
        self.assertAlmostEqual(ref.at["Gori", "baseline_target"], 450.0)
        self.assertEqual(ref.at["Gori", "n_matches"], 2)

    def test_percentile_gives_recent_matches_more_weight(self):
        old_high = matches([
            ("Gori", "Medio", "S5", "2026-07-01", 90.0, 900.0, 30.0),
            ("Gori", "Medio", "J5", "2026-09-27", 90.0, 500.0, 30.0),
        ])
        recent_high = old_high.assign(hsr=[500.0, 900.0])
        p70_old = calculate_references(old_high, "hsr", "p70", reference_date="2026-09-27")
        p70_recent = calculate_references(recent_high, "hsr", "p70", reference_date="2026-09-27")
        self.assertGreater(
            p70_recent["baseline_target"].iloc[0], p70_old["baseline_target"].iloc[0]
        )

    def test_percentile_with_equal_weights_stays_between_the_values(self):
        df = matches([
            ("Gori", "Medio", "J1", "2026-09-27", 90.0, 400.0, 30.0),
            ("Gori", "Medio", "J2", "2026-09-27", 90.0, 600.0, 30.0),
        ])
        value = by_player(
            calculate_references(df, "hsr", "p70", reference_date="2026-09-27")
        ).at["Gori", "baseline_target"]
        self.assertTrue(400.0 <= value <= 600.0)


class FallbackTests(unittest.TestCase):
    def test_player_without_valid_matches_gets_position_average(self):
        df = matches([
            ("Teto Martín", "Medio", "J3", "2026-09-12", 22.0, 583.8, 30.0),  # < 60'
            ("Gori", "Medio", "J1", "2026-08-31", 90.0, 500.0, 30.0),
            ("Padillo", "Medio", "J1", "2026-08-31", 90.0, 600.0, 30.0),
            ("Mascaró", "Medio", "J1", "2026-08-31", 90.0, 1000.0, 30.0),
        ])
        ref = by_player(calculate_references(df, "hsr", "max", reference_date="2026-09-30"))
        self.assertAlmostEqual(ref.at["Teto Martín", "baseline_target"], 700.0)
        self.assertEqual(ref.at["Teto Martín", "source"], "position")
        self.assertIn("Media posición: Medio (3 jugadores)", ref.at["Teto Martín", "origin"])

    def test_squad_player_without_matches_is_listed(self):
        df = matches([("Gori", "Medio", "J1", "2026-08-31", 90.0, 500.0, 30.0)])
        squad = pd.DataFrame({"player": ["Gori", "Nuevo"], "position": ["Medio", "Medio"]})
        ref = by_player(calculate_references(
            df, "hsr", "max", reference_date="2026-09-30", players=squad
        ))
        self.assertAlmostEqual(ref.at["Nuevo", "baseline_target"], 500.0)

    def test_max_speed_uses_short_appearances_unscaled(self):
        df = matches([
            ("Santi", "Delantero", "J3", "2026-09-12", 10.2, 585.2, 33.8),
            ("Santi", "Delantero", "S33", "2026-08-25", 80.0, 560.0, 31.0),
        ])
        ref = by_player(calculate_references(df, "max_speed", "max", reference_date="2026-09-30"))
        self.assertAlmostEqual(ref.at["Santi", "baseline_target"], 33.8)


if __name__ == "__main__":
    unittest.main()
