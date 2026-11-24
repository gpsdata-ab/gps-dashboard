"""Manual references saved in Google Drive (table logic only, no Drive access).

Run from the project folder with:  python -m unittest discover tests
"""

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils import manual_references as mr  # noqa: E402

TODAY = date(2026, 11, 18)


class ManualReferenceTableTests(unittest.TestCase):
    def test_csv_round_trip_keeps_accents_and_decimals(self):
        table = mr.apply_changes(mr.empty_table(), "hsr", {"Teto Martín": 650.5}, "Alex", TODAY)
        text = mr.to_csv_text(table)
        self.assertIn("Teto Martín;hsr;650,5;18/11/2026;Alex", text)
        back = mr.parse_csv(text)
        self.assertEqual(mr.values_for_metric(back, "hsr")["Teto Martín"]["valor"], 650.5)

    def test_empty_or_header_only_file_is_an_empty_table(self):
        self.assertTrue(mr.parse_csv("").empty)
        self.assertTrue(mr.parse_csv(mr.to_csv_text(mr.empty_table())).empty)

    def test_new_value_replaces_the_old_one_for_the_same_metric(self):
        table = mr.apply_changes(mr.empty_table(), "hsr", {"Joel": 500.0}, "Alex", TODAY)
        table = mr.apply_changes(table, "hsr", {"Joel": 550.0}, "Jorge", TODAY)
        values = mr.values_for_metric(table, "hsr")
        self.assertEqual(len(table), 1)
        self.assertEqual(values["Joel"], {"valor": 550.0, "fecha": "18/11/2026", "usuario": "Jorge"})

    def test_deleting_a_value_only_touches_that_player_and_metric(self):
        table = mr.apply_changes(
            mr.empty_table(), "hsr", {"Joel": 500.0, "Youssef": 700.0}, "Alex", TODAY
        )
        table = mr.apply_changes(table, "max_speed", {"Joel": 31.5}, "Alex", TODAY)
        table = mr.apply_changes(table, "hsr", {"Joel": None}, "Alex", TODAY)
        self.assertEqual(set(mr.values_for_metric(table, "hsr")), {"Youssef"})
        self.assertEqual(mr.values_for_metric(table, "max_speed")["Joel"]["valor"], 31.5)

    def test_values_typed_in_excel_with_extra_columns_are_read(self):
        text = "jugador;metrica;valor;fecha;usuario;nota\nJoel;hsr;612,3;18/11/2026;Alex;RTP\n;hsr;1;;;\n"
        values = mr.values_for_metric(mr.parse_csv(text), "hsr")
        self.assertEqual(values, {"Joel": {"valor": 612.3, "fecha": "18/11/2026", "usuario": "Alex"}})


if __name__ == "__main__":
    unittest.main()
