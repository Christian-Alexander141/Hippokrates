"""Aufruf:  .venv/bin/python -m unittest discover tests"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("HIPPOKRATES_DATEN", tempfile.mkdtemp(prefix="hippokrates-test-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from model.Datenkern import abgleich, db, sprachmodelle  # noqa: E402


def modell(id_, groesse=1, embedding=False, cloud=False):
    return {"id": id_, "name": id_, "quelle": "ollama", "quelle_name": "Ollama", "standort": "cloud" if cloud else "lokal",
            "cloud": cloud, "embedding": embedding, "faehigkeiten": [], "groesse": groesse, "parameter": "",
            "quantisierung": "", "familie": ""}


class Kennungen(unittest.TestCase):
    def test_zerlegen(self):
        self.assertEqual(sprachmodelle.zerlegen("qwen3.5:9b"), ("ollama", "qwen3.5:9b"))
        self.assertEqual(sprachmodelle.zerlegen("hf.co/nutzer/modell:Q4"), ("ollama", "hf.co/nutzer/modell:Q4"))
        self.assertEqual(sprachmodelle.zerlegen("lmstudio::llama-3.1-8b"), ("lmstudio", "llama-3.1-8b"))
        self.assertEqual(sprachmodelle.zerlegen("netz::mein-lm"), ("netz", "mein-lm"))

    def test_standort(self):
        s = sprachmodelle._standort
        self.assertEqual(s("http://localhost:1234/v1"), "lokal")
        self.assertEqual(s("http://127.0.0.1:8080/v1"), "lokal")
        self.assertEqual(s("http://host.docker.internal:11434"), "lokal")
        self.assertEqual(s("http://192.168.1.20:8000/v1"), "netzwerk")
        self.assertEqual(s("http://gpu-server:8000/v1"), "netzwerk")
        self.assertEqual(s("https://api.example.com/v1"), "cloud")


class Auswahl(unittest.TestCase):
    verfuegbar = [modell("klein", 2), modell("gross", 9), modell("embed", 1, embedding=True),
                  modell("fern-cloud", 0, cloud=True), modell("mittel", 5)]

    def test_alle_lokalen_ohne_cloud_embedding_und_ausgeschlossene(self):
        self.assertEqual(sprachmodelle.lokale_chatmodelle(self.verfuegbar), ["gross", "mittel", "klein"])
        self.assertEqual(sprachmodelle.lokale_chatmodelle(self.verfuegbar, ["mittel"]), ["gross", "klein"])

    def test_aufloesen_prueft_jedes_mal_die_verfuegbarkeit(self):
        einst = {**db.STANDARD_EINSTELLUNGEN, "agenten": ["gross", "weg", "klein"]}
        with mock.patch.object(sprachmodelle, "ermitteln", return_value={"modelle": self.verfuegbar}) as m:
            modelle, fehlend = abgleich.agenten_aufloesen(einst)
            self.assertEqual((modelle, fehlend), (["gross", "weg", "klein"], {"weg"}))
            modelle, fehlend = abgleich.agenten_aufloesen({**einst, "agenten_modus": "alle", "ausgeschlossene_modelle": ["klein"]})
            self.assertEqual((modelle, fehlend), (["gross", "mittel"], set()))
            self.assertEqual(m.call_count, 2)

    def test_quellen_mit_suche_und_zusatzserver(self):
        einst = {**db.STANDARD_EINSTELLUNGEN, "zusatz_server": [{"name": "LM Studio", "url": "http://localhost:1234/v1"}]}
        qs = sprachmodelle.quellen(einst)
        self.assertEqual(qs[0]["art"], "ollama")
        # Der eingetragene Server ersetzt die automatische Suche auf demselben Port und bekommt einen eigenen Schlüssel
        self.assertEqual(sum(q["url"] == "http://localhost:1234/v1" for q in qs), 1)
        self.assertEqual(len({q["schluessel"] for q in qs}), len(qs))
        self.assertEqual(len(sprachmodelle.quellen({**einst, "server_suchen": False})), 2)


class FesteOllamaAdresse(unittest.TestCase):
    def test_wird_nicht_gespeichert(self):
        db.initialisieren()
        with mock.patch.object(db, "OLLAMA_URL_FEST", "http://host.docker.internal:11434"):
            _, neu = db.einstellungen_aendern({"ollama_url": "http://anders:1", "top_k": 7})
            self.assertEqual(neu["ollama_url"], "http://host.docker.internal:11434")
        gespeichert = db.einstellungen()
        self.assertEqual(gespeichert["ollama_url"], db.STANDARD_EINSTELLUNGEN["ollama_url"])
        self.assertEqual(gespeichert["top_k"], 7)


if __name__ == "__main__":
    unittest.main()
