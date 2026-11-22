"""Schlanker Client für die lokale Ollama-HTTP-API (nur Standardbibliothek)."""
import json
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor


ZEITLIMIT = 600  # Sekunden je Modellanfrage


class OllamaFehler(RuntimeError):
    pass


class Abgebrochen(Exception):
    """Der Abgleich wurde durch einen neueren ersetzt."""


def _anfrage(url: str, pfad: str, daten: dict | None = None, timeout: float = 900):
    req = urllib.request.Request(
        url.rstrip("/") + pfad,
        data=json.dumps(daten).encode() if daten is not None else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")
        try:
            text = json.loads(text).get("error", text)
        except ValueError:
            pass
        raise OllamaFehler(f"Ollama meldet Fehler {e.code}: {text[:300]}") from None
    except (urllib.error.URLError, OSError) as e:
        raise OllamaFehler(f"Ollama unter {url} nicht erreichbar: {e}") from None


_faehigkeiten: dict[str, list[str]] = {}  # digest -> Fähigkeiten laut /api/show (ändert sich nur mit dem Modell)


def _faehigkeiten_lesen(url: str, name: str, digest: str) -> list[str] | None:
    if digest and digest in _faehigkeiten:
        return _faehigkeiten[digest]
    try:
        with _anfrage(url, "/api/show", {"model": name}, timeout=5) as antwort:
            werte = list(json.load(antwort).get("capabilities") or [])
    except OllamaFehler:
        return None  # ältere Ollama-Versionen oder Zeitüberschreitung: Namensheuristik genügt
    if digest:
        _faehigkeiten[digest] = werte
    return werte


def modelle(url: str) -> list[dict]:
    """Installierte Modelle – bei jedem Aufruf neu von Ollama abgefragt.

    `cloud` = Anfragen verlassen den Rechner, `embedding` = kein Chat-Modell. Die Fähigkeiten
    (completion, tools, thinking, vision, embedding) stammen aus /api/show.
    """
    with _anfrage(url, "/api/tags", timeout=10) as antwort:
        eintraege = json.load(antwort).get("models", [])
    with ThreadPoolExecutor(max_workers=8) as pool:
        faehigkeiten = list(pool.map(lambda m: _faehigkeiten_lesen(url, m["name"], m.get("digest", "")), eintraege))
    liste = []
    for m, faehig in zip(eintraege, faehigkeiten):
        name = m["name"]
        details = m.get("details") or {}
        familien = " ".join(details.get("families") or []).lower()
        embedding = "embedding" in faehig if faehig else ("embed" in name.lower() or "bert" in familien)
        liste.append({
            "name": name,
            "cloud": bool(m.get("remote_host")) or "cloud" in name.split(":")[-1],
            "embedding": embedding,
            "faehigkeiten": faehig or (["embedding"] if embedding else ["completion"]),
            "groesse": m.get("size") or 0,
            "parameter": details.get("parameter_size") or "",
            "quantisierung": details.get("quantization_level") or "",
            "familie": details.get("family") or "",
            "geaendert": m.get("modified_at") or "",
        })
    return sorted(liste, key=lambda m: m["name"])


def chat_json(url: str, modell: str, nachrichten: list[dict], schema: dict,
              abbruch: threading.Event | None = None, denken: bool = False) -> dict:
    """Chat-Anfrage mit JSON-Schema. Bricht die Generierung ab, sobald `abbruch` gesetzt ist.

    `denken=False` schaltet bei Thinking-Modellen (z. B. qwen3) die vorgeschaltete Denkphase ab,
    die auf kleiner Hardware viele Minuten dauern kann. Antwortlänge und Laufzeit sind begrenzt,
    damit ein hängendes Modell nur den eigenen Agenten ausfallen lässt. Liefert das Modell kein
    gültiges JSON (kleine Modelle geraten gelegentlich in Wiederholungsschleifen), folgt ein
    zweiter Versuch mit anderem Seed.
    """
    frist = time.monotonic() + ZEITLIMIT
    fehler = None
    for versuch in range(2):
        text, grund = _chat_text(url, modell, nachrichten, schema, abbruch, denken, versuch, frist)
        ergebnis = _json_lesen(text)
        if isinstance(ergebnis, dict):
            return ergebnis
        fehler = (f"{modell}: Antwort nach {len(text)} Zeichen abgeschnitten (Längenlimit erreicht, vermutlich "
                  f"Wiederholungsschleife)" if grund == "length"
                  else f"{modell} lieferte kein gültiges JSON (…{text[-120:]!r})")
    raise OllamaFehler(fehler + " – auch im zweiten Versuch.")


def _json_lesen(text: str):
    """JSON-Objekt aus der Modellantwort lesen. Text davor oder danach (Markdown, Erklärungen) wird
    ignoriert; fehlen am Ende schließende Klammern – kleine Modelle hören gern kurz vorher auf –,
    werden sie ergänzt."""
    start = text.find("{")
    if start < 0:
        return None
    kern = text[start:].rstrip().removesuffix("```").rstrip()
    for ende in ("", "}", "]}", "\"]}", "}]}", "\"}]}", "\"}"):
        try:
            return json.JSONDecoder().raw_decode(kern + ende)[0]
        except ValueError:
            continue
    return None


def _chat_text(url, modell, nachrichten, schema, abbruch, denken, seed, frist) -> tuple[str, str]:
    antwort = _anfrage(url, "/api/chat", {
        "model": modell,
        "messages": nachrichten,
        "format": schema,
        "stream": True,
        "think": denken,
        "options": {"temperature": 0, "seed": seed, "num_ctx": 8192, "num_predict": 8000 if denken else 3000,
                    "repeat_penalty": 1.1},
    })
    teile, grund = [], ""
    try:
        with antwort:  # Schließen der Verbindung beendet die Generierung in Ollama
            for zeile in antwort:
                if abbruch is not None and abbruch.is_set():
                    raise Abgebrochen()
                if time.monotonic() > frist:
                    raise OllamaFehler(f"{modell}: Zeitlimit von {ZEITLIMIT // 60} Minuten überschritten")
                if not zeile.strip():
                    continue
                d = json.loads(zeile)
                if d.get("error"):
                    raise OllamaFehler(f"{modell}: {d['error']}")
                teile.append((d.get("message") or {}).get("content") or "")
                if d.get("done"):
                    grund = d.get("done_reason") or ""
                    break
    except OSError as e:
        raise OllamaFehler(f"{modell}: Verbindung zu Ollama abgebrochen ({e})") from None
    return "".join(teile), grund


def embed(url: str, modell: str, texte: list[str]) -> list[list[float]]:
    vektoren: list[list[float]] = []
    for i in range(0, len(texte), 16):
        with _anfrage(url, "/api/embed", {"model": modell, "input": texte[i:i + 16]}) as antwort:
            vektoren.extend(json.load(antwort)["embeddings"])
    return vektoren
