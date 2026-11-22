"""Client für lokale Modellserver mit OpenAI-kompatibler Schnittstelle (nur Standardbibliothek).

Dazu gehören LM Studio, llama.cpp-Server, LocalAI, Jan, GPT4All, KoboldCpp, text-generation-webui
und vLLM. Strukturierte Antworten werden per `response_format: json_schema` angefordert; Server, die
das nicht kennen, bekommen `json_object` bzw. nur die Anweisung im Prompt.
"""
import json
import re
import threading
import time
import urllib.error
import urllib.request

from .ollama import Abgebrochen, OllamaFehler, ZEITLIMIT, _json_lesen


class ServerFehler(OllamaFehler):
    """Erbt von OllamaFehler, damit Agenten und Abgleich alle Modellfehler gleich behandeln."""


def _anfrage(basis: str, pfad: str, daten: dict | None = None, timeout: float = 900, schluessel: str = ""):
    kopf = {"Content-Type": "application/json"}
    if schluessel:
        kopf["Authorization"] = f"Bearer {schluessel}"
    req = urllib.request.Request(basis.rstrip("/") + pfad,
                                 data=json.dumps(daten).encode() if daten is not None else None, headers=kopf)
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")
        try:
            fehler = json.loads(text).get("error", text)
            text = fehler.get("message", text) if isinstance(fehler, dict) else fehler
        except (ValueError, AttributeError):
            pass
        raise ServerFehler(f"Server {basis} meldet Fehler {e.code}: {str(text)[:300]}") from None
    except (urllib.error.URLError, OSError) as e:
        raise ServerFehler(f"Server {basis} nicht erreichbar: {getattr(e, 'reason', e)}") from None


def modelle(basis: str, timeout: float = 2, schluessel: str = "") -> list[dict]:
    with _anfrage(basis, "/models", timeout=timeout, schluessel=schluessel) as antwort:
        daten = json.load(antwort)
    liste = []
    for m in daten.get("data") or daten.get("models") or []:
        name = m.get("id") or m.get("name")
        if not name:
            continue
        typ = str(m.get("type") or m.get("object") or "").lower()
        embedding = "embed" in name.lower() or "embedding" in typ
        # Ollama-Cloud-Modelle tauchen auch über Ollamas OpenAI-Schnittstelle auf („…-cloud“ bzw. „…:cloud“)
        cloud = bool(re.search(r"[-:]cloud$", name))
        liste.append({"name": name, "embedding": embedding, "cloud": cloud,
                      "faehigkeiten": ["embedding"] if embedding else ["completion"]})
    return sorted(liste, key=lambda m: m["name"])


def chat_json(basis: str, modell: str, nachrichten: list[dict], schema: dict,
              abbruch: threading.Event | None = None, denken: bool = False, schluessel: str = "") -> dict:
    """Wie `ollama.chat_json`: JSON-Antwort nach Schema, abbrechbar, mit zweitem Versuch."""
    frist = time.monotonic() + ZEITLIMIT
    formate = [{"type": "json_schema", "json_schema": {"name": "antwort", "schema": schema, "strict": False}},
               {"type": "json_object"}, None]
    fehler = ""
    versuch = 0
    while formate and versuch < 3:
        format_ = formate[0]
        try:
            text, grund = _chat_text(basis, modell, nachrichten, format_, abbruch, versuch, frist, schluessel)
        except ServerFehler as e:
            # 400 = Server kennt das Antwortformat nicht -> einfacheres Format probieren
            if " 400" in str(e) or " 422" in str(e) or "response_format" in str(e):
                formate.pop(0)
                fehler = str(e)
                continue
            raise
        ergebnis = _json_lesen(text)
        if isinstance(ergebnis, dict):
            return ergebnis
        fehler = (f"{modell}: Antwort abgeschnitten (Längenlimit)" if grund == "length"
                  else f"{modell} lieferte kein gültiges JSON (…{text[-120:]!r})")
        versuch += 1
    raise ServerFehler(fehler or f"{modell}: keine verwertbare Antwort")


def _chat_text(basis, modell, nachrichten, format_, abbruch, seed, frist, schluessel) -> tuple[str, str]:
    daten = {"model": modell, "messages": nachrichten, "stream": True, "temperature": 0, "seed": seed,
             "max_tokens": 3000}
    if format_:
        daten["response_format"] = format_
    antwort = _anfrage(basis, "/chat/completions", daten, schluessel=schluessel)
    teile, grund = [], ""
    try:
        with antwort:  # Schließen der Verbindung beendet die Generierung
            for zeile in antwort:
                if abbruch is not None and abbruch.is_set():
                    raise Abgebrochen()
                if time.monotonic() > frist:
                    raise ServerFehler(f"{modell}: Zeitlimit von {ZEITLIMIT // 60} Minuten überschritten")
                zeile = zeile.decode(errors="replace").strip()
                if not zeile.startswith("data:"):
                    continue
                inhalt = zeile[5:].strip()
                if inhalt == "[DONE]":
                    break
                d = json.loads(inhalt)
                if d.get("error"):
                    raise ServerFehler(f"{modell}: {d['error']}")
                for wahl in d.get("choices") or []:
                    teile.append((wahl.get("delta") or {}).get("content") or "")
                    grund = wahl.get("finish_reason") or grund
    except OSError as e:
        raise ServerFehler(f"{modell}: Verbindung abgebrochen ({e})") from None
    return "".join(teile), grund


def embed(basis: str, modell: str, texte: list[str], schluessel: str = "") -> list[list[float]]:
    vektoren: list[list[float]] = []
    for i in range(0, len(texte), 16):
        with _anfrage(basis, "/embeddings", {"model": modell, "input": texte[i:i + 16]},
                      schluessel=schluessel) as antwort:
            daten = sorted(json.load(antwort)["data"], key=lambda d: d.get("index", 0))
        vektoren.extend(d["embedding"] for d in daten)
    return vektoren
