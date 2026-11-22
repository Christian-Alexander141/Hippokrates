"""Aufruf:  python -m unittest discover pakete/netzwerkzeug/tests"""
import os
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any

import numpy as np
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import BaseModel, Field

from netzwerkzeug import NetzChatModell, NetzErgebnis, als_werkzeug, ausfuehren, entdecken, netz_werkzeug


class Blutbild(BaseModel):
    hb: float = Field(description="Hb in g/dl")
    mcv: float = Field(description="MCV in fl")
    weiblich: bool = Field(description="weiblich?")


def regelnetz(x: np.ndarray) -> np.ndarray:
    """Stellvertreter für ein trainiertes Netz: liefert Logits für [keine, mikro, makro]."""
    hb, mcv, _ = x[0]
    if hb >= 12:
        return np.array([[4.0, 0.0, 0.0]])
    return np.array([[0.0, 4.0, 0.0]]) if mcv < 80 else np.array([[0.0, 0.0, 4.0]])


KLASSEN = ["keine Anämie", "mikrozytäre Anämie", "makrozytäre Anämie"]


def werkzeug(**optionen):
    return als_werkzeug(regelnetz, name="anaemie", beschreibung="Anämieform aus Hb und MCV", eingabe=Blutbild,
                        klassen=KLASSEN, **optionen)


class Skriptmodell(BaseChatModel):
    """Chat-Modell mit festem Drehbuch – prüft den Agentenablauf ohne echtes Sprachmodell."""
    antworten: list[AIMessage]
    gesehen: list[Any] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "skript"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.gesehen.append(messages)
        return ChatResult(generations=[ChatGeneration(message=self.antworten[len(self.gesehen) - 1])])


class Werkzeug(unittest.TestCase):
    def test_klassifikation_text_und_artefakt(self):
        text, artefakt = ausfuehren(werkzeug(), {"hb": 9.5, "mcv": 70, "weiblich": True})
        self.assertIn("mikrozytäre Anämie", text.splitlines()[1])
        self.assertEqual(artefakt["art"], "klassifikation")
        self.assertEqual(artefakt["vorhersagen"][0]["bezeichnung"], "mikrozytäre Anämie")
        self.assertAlmostEqual(sum(v["wert"] for v in artefakt["vorhersagen"]), 1.0, places=5)
        self.assertEqual(artefakt["eingabe"], {"hb": 9.5, "mcv": 70.0, "weiblich": True})

    def test_ungueltige_eingabe_wird_zur_meldung(self):
        text, _ = ausfuehren(werkzeug(), {"hb": "viel", "mcv": 70, "weiblich": True})
        self.assertIn("Ungültige Eingabe", text)

    def test_metadaten_und_schema(self):
        w = werkzeug(version="1.2", hinweis="Test")
        self.assertTrue(w.metadata["netzwerkzeug"])
        self.assertEqual(w.metadata["klassen"], KLASSEN)
        self.assertEqual(set(w.tool_call_schema.model_json_schema()["properties"]), {"hb", "mcv", "weiblich"})
        self.assertIn("Version 1.2", ausfuehren(w, {"hb": 13, "mcv": 90, "weiblich": False})[0])

    def test_laden_erst_beim_ersten_aufruf(self):
        geladen = []
        w = als_werkzeug(laden=lambda: geladen.append(1) or regelnetz, name="faul", beschreibung="x",
                         eingabe=Blutbild, klassen=KLASSEN)
        self.assertEqual(geladen, [])
        ausfuehren(w, {"hb": 13, "mcv": 90, "weiblich": False})
        ausfuehren(w, {"hb": 13, "mcv": 90, "weiblich": False})
        self.assertEqual(geladen, [1])

    def test_regression_mit_einheiten(self):
        w = als_werkzeug(lambda x: np.array([[x[0, 0] * 2, 0.5]]), name="reg", beschreibung="x", eingabe=Blutbild,
                         ausgaben=["Risiko-Score", "Anteil"], einheiten=["Punkte", ""])
        text, a = ausfuehren(w, {"hb": 3, "mcv": 1, "weiblich": False})
        self.assertEqual([(v["bezeichnung"], v["wert"]) for v in a["vorhersagen"]], [("Risiko-Score", 6.0), ("Anteil", 0.5)])
        self.assertIn("6 Punkte", text)

    def test_sigmoid_ausgabe_bei_zwei_klassen(self):
        w = als_werkzeug(lambda x: np.array([[0.8]]), name="bin", beschreibung="x", eingabe=Blutbild,
                         klassen=["negativ", "positiv"])
        _, a = ausfuehren(w, {"hb": 1, "mcv": 1, "weiblich": True})
        self.assertEqual(a["vorhersagen"][0]["bezeichnung"], "positiv")
        self.assertAlmostEqual(a["vorhersagen"][0]["wert"], 0.8)

    def test_sklearn_und_onnx_adapter(self):
        class Sklearn:
            def predict_proba(self, x):
                return np.array([[0.1, 0.7, 0.2]])

        class Eingang:
            name, type = "eingabe", "tensor(float)"

        class Onnx:
            def get_inputs(self):
                return [Eingang()]

            def run(self, _, feed):
                assert feed["eingabe"].dtype == np.float32
                return [np.array([[0.0, 0.0, 5.0]])]

        for netz, erwartet in ((Sklearn(), "mikrozytäre Anämie"), (Onnx(), "makrozytäre Anämie")):
            w = als_werkzeug(netz, name="a", beschreibung="x", eingabe=Blutbild, klassen=KLASSEN)
            self.assertEqual(ausfuehren(w, {"hb": 1, "mcv": 1, "weiblich": True})[1]["vorhersagen"][0]["bezeichnung"],
                             erwartet)

    def test_dekorator_mit_eigenem_ergebnis(self):
        @netz_werkzeug
        def bmi(daten: Blutbild) -> NetzErgebnis:
            """Gibt einen festen Text zurück."""
            return NetzErgebnis("", "frei", text=f"Hb war {daten.hb}")

        self.assertEqual(bmi.name, "bmi")
        self.assertEqual(bmi.description, "Gibt einen festen Text zurück.")
        self.assertIn("Hb war 11.0", ausfuehren(bmi, {"hb": 11, "mcv": 1, "weiblich": True})[0])

    def test_fehlender_parameter_typ(self):
        with self.assertRaises(TypeError):
            netz_werkzeug(lambda daten: 1, beschreibung="x")


class CreateAgent(unittest.TestCase):
    def test_agent_ruft_netz_als_werkzeug_auf(self):
        from langchain.agents import create_agent

        modell = Skriptmodell(antworten=[
            AIMessage(content="", tool_calls=[{"name": "anaemie", "args": {"hb": 9.8, "mcv": 72, "weiblich": True},
                                               "id": "c1", "type": "tool_call"}]),
            AIMessage(content="Mikrozytäre Anämie, am ehesten Eisenmangel."),
        ])
        agent = create_agent(modell, tools=[werkzeug()])
        ergebnis = agent.invoke({"messages": [HumanMessage("Hb 9,8 g/dl, MCV 72 fl, Patientin")]})
        tool = next(m for m in ergebnis["messages"] if isinstance(m, ToolMessage))
        self.assertIn("mikrozytäre Anämie", tool.content)
        self.assertEqual(tool.artifact["vorhersagen"][0]["bezeichnung"], "mikrozytäre Anämie")
        self.assertEqual(ergebnis["messages"][-1].content, "Mikrozytäre Anämie, am ehesten Eisenmangel.")

    def test_middleware_schreibt_ergebnis_in_systemprompt(self):
        from langchain.agents import create_agent

        from netzwerkzeug import NetzMiddleware

        modell = Skriptmodell(antworten=[AIMessage(content="ok")])
        middleware = NetzMiddleware([werkzeug()], eingaben=lambda state, runtime: {
            "anaemie": Blutbild(hb=8.9, mcv=110, weiblich=False)})
        agent = create_agent(modell, system_prompt="Du bist hilfreich.", middleware=[middleware])
        ergebnis = agent.invoke({"messages": [HumanMessage("Bitte einordnen")]})
        system = modell.gesehen[0][0]
        self.assertEqual(system.type, "system")
        self.assertTrue(system.text.startswith("Du bist hilfreich."))
        self.assertIn("makrozytäre Anämie", system.text)
        self.assertEqual(ergebnis["netz_befunde"][0]["artefakt"]["vorhersagen"][0]["bezeichnung"], "makrozytäre Anämie")

    def test_eigenes_generatives_netz_als_agentenmodell(self):
        from langchain.agents import create_agent

        prompts: list[str] = []
        drehbuch = iter(['{"werkzeug": "anaemie", "argumente": {"hb": 10, "mcv": 75, "weiblich": true}}',
                         '{"antwort": "Das Netz sieht eine mikrozytäre Anämie."}'])

        def erzeuge(prompt: str, **_) -> str:
            prompts.append(prompt)
            return next(drehbuch)

        agent = create_agent(NetzChatModell(erzeuge=erzeuge, modellname="mini-lm"), tools=[werkzeug()])
        ergebnis = agent.invoke({"messages": [HumanMessage("Hb 10, MCV 75, weiblich")]})
        self.assertIn("Verfügbare Werkzeuge", prompts[0])
        self.assertIn("anaemie", prompts[0])
        self.assertIn("Ergebnis von anaemie", prompts[1])
        self.assertEqual(ergebnis["messages"][-1].content, "Das Netz sieht eine mikrozytäre Anämie.")


class Entdecken(unittest.TestCase):
    def test_ordner_mit_neuladen_und_fehlern(self):
        with tempfile.TemporaryDirectory() as ordner:
            datei = Path(ordner) / "mein_netz.py"
            vorlage = ("from pydantic import BaseModel\nfrom netzwerkzeug import als_werkzeug\n"
                       "class E(BaseModel):\n    x: float\n"
                       "w = als_werkzeug(lambda x: x, name='{name}', beschreibung='b', eingabe=E)\n")
            datei.write_text(vorlage.format(name="netz_eins"))
            (Path(ordner) / "kaputt.py").write_text("raise RuntimeError('absichtlich')\n")
            (Path(ordner) / "_privat.py").write_text("raise RuntimeError('wird ignoriert')\n")
            e = entdecken(ordner, pakete=False)
            self.assertEqual([f.name for f in e.werkzeuge], ["netz_eins"])
            self.assertEqual(len(e.fehler), 1)
            self.assertIn("kaputt.py", e.fehler[0])

            datei.write_text(vorlage.format(name="netz_zwei"))
            neu = time.time() + 5
            os.utime(datei, (neu, neu))
            self.assertEqual([f.name for f in entdecken(ordner, pakete=False).werkzeuge], ["netz_zwei"])


if __name__ == "__main__":
    unittest.main()
