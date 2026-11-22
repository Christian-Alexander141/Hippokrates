"""Eigene neuronale Netze (Bibliothek `netzwerkzeug`) für die Diagnose-Agenten.

Netze liegen als `.py`-Dateien im Ordner `netze/` (Umgebungsvariable HIPPOKRATES_NETZE) oder kommen
aus installierten Paketen. Sie werden bei jeder Abfrage neu gesucht; geänderte Dateien lädt
`netzwerkzeug.entdecken` neu. Werkzeug-Netze kann der Adminbereich für die Agenten freischalten,
Chat-Modell-Netze erscheinen in der Modellauswahl.
"""
import os
import threading
from pathlib import Path

from . import ollama

ORDNER = Path(os.environ.get("HIPPOKRATES_NETZE", Path(__file__).resolve().parents[3] / "netze"))

try:
    import netzwerkzeug
except ImportError:  # Bibliothek nicht installiert: Anwendung läuft ohne eigene Netze
    netzwerkzeug = None


def entdecken():
    if netzwerkzeug is None:
        return None
    return netzwerkzeug.entdecken(ORDNER)


def _schema(werkzeug) -> dict:
    """Flaches JSON-Schema der Eingaben – ohne Titel, damit es als Ollama-Format taugt."""
    roh = werkzeug.tool_call_schema.model_json_schema()
    eigenschaften = {k: {s: w for s, w in v.items() if s != "title"} for k, v in roh.get("properties", {}).items()}
    return {"type": "object", "properties": eigenschaften, "required": list(roh.get("required", eigenschaften))}


def uebersicht() -> dict:
    """Für die Oberfläche: alle gefundenen Netze mit Beschreibung, Eingaben und Ladefehlern."""
    if netzwerkzeug is None:
        return {"verfuegbar": False, "ordner": str(ORDNER), "werkzeuge": [], "chatmodelle": [],
                "fehler": ["Die Bibliothek „netzwerkzeug“ ist nicht installiert (pip install -e pakete/netzwerkzeug)."]}
    e = entdecken()
    werkzeuge = []
    for f in e.werkzeuge:
        meta = f.objekt.metadata or {}
        schema = _schema(f.objekt)
        werkzeuge.append({
            "name": f.name, "beschreibung": f.objekt.description, "quelle": f.quelle,
            "art": meta.get("art", "frei"), "klassen": meta.get("klassen", []), "ausgaben": meta.get("ausgaben", []),
            "version": meta.get("version", ""), "hinweis": meta.get("hinweis", ""),
            "eingaben": [{"name": k, "typ": v.get("type", ""), "beschreibung": v.get("description", "")}
                         for k, v in schema["properties"].items()],
        })
    chat = [{"name": f.name, "quelle": f.quelle} for f in e.chatmodelle]
    return {"verfuegbar": True, "ordner": str(ORDNER), "werkzeuge": werkzeuge, "chatmodelle": chat, "fehler": e.fehler}


def aktive(einst: dict) -> list:
    """Freigeschaltete Werkzeug-Netze, die gerade verfügbar sind."""
    gewuenscht = einst.get("netze_aktiv") or []
    if not gewuenscht or netzwerkzeug is None:
        return []
    e = entdecken()
    return [w for name in gewuenscht if (w := e.werkzeug(name)) is not None]


def planungsschema(werkzeuge: list) -> tuple[dict, str]:
    """JSON-Schema und Auftrag, mit dem ein Agent die Eingaben jedes Netzes aus der Akte überträgt."""
    eigenschaften, zeilen = {}, []
    for w in werkzeuge:
        s = _schema(w)
        eigenschaften[w.name] = {"type": "object",
                                 "properties": {"anwendbar": {"type": "boolean"}, **s["properties"]},
                                 "required": ["anwendbar", *s["required"]]}
        felder = "; ".join(f"{k}: {v.get('description') or v.get('type', '')}" for k, v in s["properties"].items())
        zeilen.append(f"  • {w.name} – {w.description} Eingaben: {felder}")
    auftrag = ("'netze': für jedes der folgenden neuronalen Netze ein Objekt. 'anwendbar' ist nur dann true, wenn alle "
               "Eingaben ausdrücklich in den Patientendaten stehen; übernimm die Werte unverändert (Einheiten "
               "umrechnen, aber nichts schätzen). Sonst 'anwendbar': false und beliebige Platzhalter.\n"
               + "\n".join(zeilen))
    return {"type": "object", "properties": eigenschaften, "required": list(eigenschaften)}, auftrag


def auswerten(werkzeug, argumente: dict) -> dict:
    """Ein Netz mit den vom Agenten übertragenen Eingaben auswerten -> Quelle für die Diagnose."""
    text, artefakt = netzwerkzeug.ausfuehren(werkzeug, argumente)
    if not artefakt:  # Validierungs- oder Laufzeitfehler: das Werkzeug liefert dann nur eine Meldung
        raise ValueError(text)
    return {"art": "netz", "id": f"{werkzeug.name}:{sorted(artefakt['eingabe'].items())}", "netz": werkzeug.name,
            "titel": f"Neuronales Netz „{werkzeug.name}“", "text": text, "eingabe": artefakt["eingabe"],
            "netz_art": artefakt["art"], "vorhersagen": artefakt["vorhersagen"], "hinweis": artefakt.get("hinweis", ""),
            "version": artefakt.get("version", "")}


# ── Netze als Chat-Modell (NetzChatModell) ─────────────────────────────────────

_chat_sperre = threading.Lock()


def chat_json(name: str, nachrichten: list[dict], abbruch: threading.Event | None = None) -> dict:
    modell = entdecken().chatmodell(name) if netzwerkzeug else None
    if modell is None:
        raise ollama.OllamaFehler(f"Eigenes Netz „{name}“ ist nicht (mehr) verfügbar.")
    if abbruch is not None and abbruch.is_set():
        raise ollama.Abgebrochen()
    with _chat_sperre:
        antwort = modell.invoke([(n["role"], n["content"]) for n in nachrichten])
    if abbruch is not None and abbruch.is_set():
        raise ollama.Abgebrochen()
    ergebnis = ollama._json_lesen(antwort.text)
    if not isinstance(ergebnis, dict):
        raise ollama.OllamaFehler(f"Netz „{name}“ lieferte kein gültiges JSON.")
    return ergebnis
