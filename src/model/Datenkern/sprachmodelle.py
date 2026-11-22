"""Modellregister: alle verfügbaren Sprachmodelle – bei jedem Aufruf neu ermittelt.

Quellen:
  • Ollama (Adresse aus den Einstellungen bzw. HIPPOKRATES_OLLAMA_URL)
  • lokale Server mit OpenAI-kompatibler Schnittstelle: LM Studio, llama.cpp, Jan, GPT4All … werden
    auf ihren üblichen Ports gesucht (abschaltbar); weitere Adressen lassen sich eintragen
  • eigene Netze aus `netze/`, die als Chat-Modell (NetzChatModell) vorliegen

Modellkennungen: Ollama-Modelle tragen ihren Namen („qwen3.5:9b“, abwärtskompatibel zu älteren
Einstellungen), alle anderen „<quelle>::<name>“, z. B. „lmstudio::llama-3.1-8b“ oder „netz::mein-lm“.
"""
import ipaddress
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from . import db, netze, ollama, openai_kompatibel

TRENNER = "::"

# Rechner, auf dem die Modellserver laufen. In Docker ist das der Host (host.docker.internal).
MODELL_HOST = os.environ.get("HIPPOKRATES_MODELL_HOST", "localhost")

# Übliche Ports lokaler Server mit OpenAI-kompatibler Schnittstelle
BEKANNTE_SERVER = [
    ("lmstudio", "LM Studio", 1234),
    ("llamacpp", "llama.cpp / LocalAI", 8080),
    ("jan", "Jan", 1337),
    ("gpt4all", "GPT4All", 4891),
    ("textgen", "text-generation-webui", 5000),
    ("koboldcpp", "KoboldCpp", 5001),
]


def zerlegen(modell_id: str) -> tuple[str, str]:
    """'lmstudio::x' -> ('lmstudio', 'x');  'qwen3.5:9b' -> ('ollama', 'qwen3.5:9b')."""
    if TRENNER in modell_id:
        quelle, name = modell_id.split(TRENNER, 1)
        return quelle, name
    return "ollama", modell_id


def _schluessel(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower()) or "server"


def _standort(url: str) -> str:
    """lokal = dieser Rechner (bzw. der Docker-Host), netzwerk = anderer Rechner, cloud = Internetdienst."""
    host = (urlparse(url).hostname or "").lower()
    if host in ("localhost", "host.docker.internal", MODELL_HOST.lower()) or host.endswith(".localhost"):
        return "lokal"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        lan = "." not in host or host.endswith((".local", ".lan", ".home", ".internal", ".fritz.box"))
        return "netzwerk" if lan else "cloud"
    if ip.is_loopback:
        return "lokal"
    return "netzwerk" if ip.is_private or ip.is_link_local else "cloud"


def quellen(einst: dict) -> list[dict]:
    """Alle abzufragenden Quellen. `auto` = nur anzeigen, wenn erreichbar."""
    liste = [{"schluessel": "ollama", "name": "Ollama", "art": "ollama", "url": einst["ollama_url"], "auto": False}]
    eigene = einst.get("zusatz_server") or []
    belegt = {s["url"].rstrip("/") for s in eigene}
    if einst.get("server_suchen", True):
        for schluessel, name, port in BEKANNTE_SERVER:
            url = f"http://{MODELL_HOST}:{port}/v1"
            if url not in belegt:
                liste.append({"schluessel": schluessel, "name": name, "art": "openai", "url": url, "auto": True})
    vergeben = {q["schluessel"] for q in liste}
    for s in eigene:
        schluessel = _schluessel(s.get("name") or s["url"])
        while schluessel in vergeben:
            schluessel += "x"
        vergeben.add(schluessel)
        liste.append({"schluessel": schluessel, "name": s.get("name") or s["url"], "art": "openai",
                      "url": s["url"].rstrip("/"), "auto": False, "api_schluessel": s.get("api_schluessel", "")})
    return liste


def _abfragen(q: dict) -> tuple[dict, list[dict]]:
    status = {k: q[k] for k in ("schluessel", "name", "art", "url", "auto")}
    try:
        if q["art"] == "ollama":
            roh = ollama.modelle(q["url"])
        else:
            roh = openai_kompatibel.modelle(q["url"], timeout=1.5 if q["auto"] else 4,
                                            schluessel=q.get("api_schluessel", ""))
    except ollama.OllamaFehler as e:
        return {**status, "erreichbar": False, "fehler": str(e), "anzahl": 0}, []
    standort = _standort(q["url"])
    modelle = []
    for m in roh:
        cloud = m.get("cloud", False) or standort != "lokal"
        modelle.append({
            "id": m["name"] if q["art"] == "ollama" else f"{q['schluessel']}{TRENNER}{m['name']}",
            "name": m["name"], "quelle": q["schluessel"], "quelle_name": q["name"],
            "standort": "cloud" if m.get("cloud") else standort, "cloud": cloud,
            "embedding": m["embedding"], "faehigkeiten": m.get("faehigkeiten", []),
            "groesse": m.get("groesse", 0), "parameter": m.get("parameter", ""),
            "quantisierung": m.get("quantisierung", ""), "familie": m.get("familie", ""),
        })
    return {**status, "erreichbar": True, "fehler": "", "anzahl": len(modelle)}, modelle


def ermitteln(einst: dict | None = None) -> dict:
    """Fragt alle Quellen parallel ab. Nicht erreichbare automatisch gesuchte Server werden ausgeblendet."""
    einst = einst or db.einstellungen()
    qs = quellen(einst)
    with ThreadPoolExecutor(max_workers=len(qs)) as pool:
        ergebnisse = list(pool.map(_abfragen, qs))
    status, modelle = [], []
    for s, ms in ergebnisse:
        if s["auto"] and not s["erreichbar"]:
            continue
        status.append(s)
        modelle += ms
    eigene = netze.uebersicht()
    for c in eigene["chatmodelle"]:
        modelle.append({"id": f"netz{TRENNER}{c['name']}", "name": c["name"], "quelle": "netz",
                        "quelle_name": "Eigene Netze", "standort": "lokal", "cloud": False, "embedding": False,
                        "faehigkeiten": ["completion"], "groesse": 0, "parameter": "", "quantisierung": "",
                        "familie": "netzwerkzeug"})
    if eigene["chatmodelle"]:
        status.append({"schluessel": "netz", "name": "Eigene Netze", "art": "netz", "url": eigene["ordner"],
                       "auto": False, "erreichbar": True, "fehler": "", "anzahl": len(eigene["chatmodelle"])})
    return {"modelle": modelle, "quellen": status, "geprueft": db.jetzt()}


def lokale_chatmodelle(modelle: list[dict], ausgeschlossen: list[str] = ()) -> list[str]:
    """Für den Modus „alle lokalen Modelle“: jedes Chat-Modell auf diesem Rechner, größte zuerst."""
    raus = set(ausgeschlossen)
    passend = [m for m in modelle if not m["embedding"] and not m["cloud"] and m["id"] not in raus]
    return [m["id"] for m in sorted(passend, key=lambda m: (-m["groesse"], m["id"]))]


# ── Aufrufe ─────────────────────────────────────────────────────────────────────

def _server(einst: dict, quelle: str) -> dict:
    q = next((q for q in quellen(einst) if q["schluessel"] == quelle), None)
    if q is None:
        raise ollama.OllamaFehler(f"Modellquelle „{quelle}“ ist nicht (mehr) eingerichtet.")
    return q


def chat_json(einst: dict, modell_id: str, nachrichten: list[dict], schema: dict,
              abbruch: threading.Event | None = None, denken: bool = False) -> dict:
    quelle, name = zerlegen(modell_id)
    if quelle == "ollama":
        return ollama.chat_json(einst["ollama_url"], name, nachrichten, schema, abbruch, denken)
    if quelle == "netz":
        return netze.chat_json(name, nachrichten, abbruch)
    q = _server(einst, quelle)
    return openai_kompatibel.chat_json(q["url"], name, nachrichten, schema, abbruch, denken,
                                       q.get("api_schluessel", ""))


def embed(einst: dict, modell_id: str, texte: list[str]) -> list[list[float]]:
    quelle, name = zerlegen(modell_id)
    if quelle == "ollama":
        return ollama.embed(einst["ollama_url"], name, texte)
    q = _server(einst, quelle)
    return openai_kompatibel.embed(q["url"], name, texte, q.get("api_schluessel", ""))
