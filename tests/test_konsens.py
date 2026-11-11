"""Aufruf:  .venv/bin/python -m unittest discover tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from model.Datenkern.konsens import icd_kategorie, konsens, namensschluessel, rueckfragen_buendeln  # noqa: E402


def d(name, icd=""):
    return {"name": name, "icd10": icd, "begruendung": "", "quellen": []}


class Namensschluessel(unittest.TestCase):
    def test_schreibvarianten(self):
        self.assertEqual(namensschluessel("Akute Appendicitis"), namensschluessel("appendizitis, akute"))
        self.assertEqual(namensschluessel("V. a. Skorbut (Vitamin-C-Mangel)"), namensschluessel("Skorbut"))
        self.assertEqual(namensschluessel("Diabetes mellitus Typ II"), namensschluessel("Diabetes mellitus Typ 2"))
        self.assertEqual(namensschluessel("Ösophagus-Carcinom"), namensschluessel("Oesophagus Karzinom"))

    def test_verschiedene_bleiben_verschieden(self):
        self.assertNotEqual(namensschluessel("Morbus Crohn"), namensschluessel("Colitis ulcerosa"))

    def test_icd(self):
        self.assertEqual(icd_kategorie("k35.80"), "K35")
        self.assertEqual(icd_kategorie("unbekannt"), "")


class Konsens(unittest.TestCase):
    agenten = [
        {"nr": 1, "modell": "a", "diagnosen": [d("Akute Appendizitis", "K35.8"), d("Gastroenteritis", "A09.9")]},
        {"nr": 2, "modell": "b", "diagnosen": [d("Morbus Crohn", "K50.9"), d("Appendicitis", "K35.80")]},
        {"nr": 3, "modell": "c", "diagnosen": [d("Blinddarmentzündung", "K35.3"), d("Morbus Crohn")]},
    ]

    def test_haeufige_zuerst(self):
        r = konsens(self.agenten)
        self.assertEqual([(g["stimmen"], g["icd10"][:3]) for g in r], [(3, "K35"), (2, "K50"), (1, "A09")])
        self.assertEqual(r[0]["agenten_gesamt"], 3)

    def test_ohne_icd_nur_namen(self):
        r = konsens(self.agenten, icd_abgleich=False)
        self.assertEqual([g["stimmen"] for g in r], [2, 1, 1, 1, 1])  # nur Morbus Crohn stimmt dem Namen nach überein

    def test_gleichstand_nach_rang_dann_name(self):
        r = konsens([{"nr": 1, "modell": "a", "diagnosen": [d("Zoster"), d("Asthma"), d("Gicht")]}])
        self.assertEqual([g["name"] for g in r], ["Zoster", "Asthma", "Gicht"])

    def test_agent_zaehlt_nur_einmal(self):
        r = konsens([{"nr": 1, "modell": "a", "diagnosen": [d("Skorbut"), d("V. a. Skorbut")]}])
        self.assertEqual((len(r), r[0]["stimmen"], r[0]["mittlerer_rang"]), (1, 1, 1.0))

    def test_deterministisch_unabhaengig_von_reihenfolge(self):
        self.assertEqual(konsens(self.agenten), konsens(list(reversed(self.agenten))))

    def test_rueckfragen_gebuendelt(self):
        r = rueckfragen_buendeln([
            {"nr": 2, "rueckfragen": ["Seit wann bestehen die Beschwerden?", "Fieber?"]},
            {"nr": 1, "rueckfragen": ["Raucht der Patient?", "seit wann bestehen die Beschwerden"]},
        ])
        self.assertEqual([(g["frage"], g["agenten"]) for g in r], [
            ("seit wann bestehen die Beschwerden", [1, 2]), ("Raucht der Patient?", [1]), ("Fieber?", [2])])


if __name__ == "__main__":
    unittest.main()
