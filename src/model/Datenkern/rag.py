"""Lokale Literaturbibliothek: Indexierung (PDF/TXT/MD) und semantische Suche für die Agenten.

Die Embeddings erzeugt ein lokales Ollama-Modell; Vektoren und Textabschnitte liegen in SQLite.
"""
import hashlib
import re
import threading
from pathlib import Path

import numpy as np

from . import db, ollama

ERLAUBTE_ENDUNGEN = {".pdf", ".txt", ".md"}

status = {"laeuft": False, "datei": "", "fertig": 0, "gesamt": 0, "fehler": []}
_index_sperre = threading.Lock()
_erneut = False  # während der Indexierung kam eine weitere Änderung hinzu
_cache: tuple[str, np.ndarray, np.ndarray, list[str]] | None = None  # (modell, ids, matrix, dateinamen)


def _seiten(pfad: Path) -> list[tuple[int | None, str]]:
    if pfad.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        return [(nr, seite.extract_text() or "") for nr, seite in enumerate(PdfReader(pfad).pages, 1)]
    return [(None, pfad.read_text(encoding="utf-8", errors="replace"))]


def _abschnitte(text: str, groesse: int = 1200, ueberlapp: int = 200) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text).strip()
    stuecke, start = [], 0
    while start < len(text):
        ende = min(start + groesse, len(text))
        if ende < len(text):  # möglichst an Absatz- oder Satzende trennen
            schnitt = max(text.rfind("\n", start + groesse // 2, ende), text.rfind(". ", start + groesse // 2, ende))
            if schnitt > 0:
                ende = schnitt + 1
        stuecke.append(text[start:ende].strip())
        if ende >= len(text):
            break
        start = ende - ueberlapp
    return [s for s in stuecke if len(s) > 40]


def _normiert(vektoren) -> np.ndarray:
    m = np.asarray(vektoren, dtype=np.float32)
    return m / np.maximum(np.linalg.norm(m, axis=-1, keepdims=True), 1e-12)


def dateien() -> list[dict]:
    """Dateien im Bibliotheksordner samt Indexstand."""
    with db.verbinden() as con:
        indexiert = {z["name"]: dict(z) for z in con.execute("SELECT * FROM bib_dateien")}
    einst = db.einstellungen()
    aus = set(einst["deaktivierte_buecher"])
    liste = []
    for pfad in sorted(db.BIBLIOTHEK_PFAD.iterdir(), key=lambda p: p.name.lower()):
        if pfad.is_file() and pfad.suffix.lower() in ERLAUBTE_ENDUNGEN:
            eintrag = indexiert.get(pfad.name)
            fehler = next((f.split(": ", 1)[1] for f in status["fehler"] if f.startswith(pfad.name + ": ")), "")
            liste.append({
                "name": pfad.name,
                "groesse": pfad.stat().st_size,
                "abschnitte": eintrag["abschnitte"] if eintrag else 0,
                "indexiert": bool(eintrag) and eintrag["modell"] == einst["embedding_modell"],
                "aktiv": pfad.name not in aus,
                "fehler": fehler,
            })
    return liste


def indexieren_starten() -> bool:
    """Gleicht den Index im Hintergrund mit dem Bibliotheksordner ab. False, wenn bereits ein Lauf aktiv ist."""
    global _erneut
    if not _index_sperre.acquire(blocking=False):
        _erneut = True
        return False
    status.update(laeuft=True, datei="", fertig=0, gesamt=0, fehler=[])
    threading.Thread(target=_indexieren, daemon=True).start()
    return True


def _indexieren() -> None:
    global _cache, _erneut
    try:
        einst = db.einstellungen()
        modell = einst["embedding_modell"]
        if not modell:
            status["fehler"].append("Kein Embedding-Modell in den Einstellungen gewählt.")
            return
        pfade = [p for p in sorted(db.BIBLIOTHEK_PFAD.iterdir())
                 if p.is_file() and p.suffix.lower() in ERLAUBTE_ENDUNGEN]
        status["gesamt"] = len(pfade)
        with db.verbinden() as con:
            bekannt = {z["name"]: z for z in con.execute("SELECT * FROM bib_dateien")}
            for name in set(bekannt) - {p.name for p in pfade}:  # gelöschte Dateien aus dem Index nehmen
                con.execute("DELETE FROM bib_dateien WHERE name=?", (name,))
        for pfad in pfade:
            status["datei"] = pfad.name
            try:
                sha = hashlib.sha256(pfad.read_bytes()).hexdigest()
                alt = bekannt.get(pfad.name)
                if not (alt and alt["sha"] == sha and alt["modell"] == modell):
                    stuecke = [(seite, s) for seite, text in _seiten(pfad) for s in _abschnitte(text)]
                    if not stuecke:
                        raise ValueError("kein Text extrahierbar (gescanntes PDF ohne Textebene?)")
                    vektoren = _normiert(ollama.embed(einst["ollama_url"], modell, [s for _, s in stuecke]))
                    with db.verbinden() as con:
                        con.execute("DELETE FROM bib_dateien WHERE name=?", (pfad.name,))
                        datei_id = con.execute(
                            "INSERT INTO bib_dateien (name, sha, modell, abschnitte, indexiert) VALUES (?,?,?,?,?)",
                            (pfad.name, sha, modell, len(stuecke), db.jetzt()),
                        ).lastrowid
                        con.executemany(
                            "INSERT INTO bib_abschnitte (datei_id, seite, text, embedding) VALUES (?,?,?,?)",
                            [(datei_id, seite, s, v.tobytes()) for (seite, s), v in zip(stuecke, vektoren)],
                        )
            except Exception as e:  # eine defekte Datei darf den Rest nicht aufhalten
                status["fehler"].append(f"{pfad.name}: {e}")
            status["fertig"] += 1
    except Exception as e:
        status["fehler"].append(str(e))
    finally:
        _cache = None
        status.update(laeuft=False, datei="")
        _index_sperre.release()
        if _erneut:
            _erneut = False
            indexieren_starten()


def _matrix(modell: str) -> tuple[np.ndarray, np.ndarray, list[str]]:
    global _cache
    cache = _cache
    if cache is None or cache[0] != modell:
        with db.verbinden() as con:
            zeilen = con.execute(
                "SELECT a.id, a.embedding, d.name FROM bib_abschnitte a JOIN bib_dateien d ON d.id = a.datei_id "
                "WHERE d.modell = ? ORDER BY a.id", (modell,),
            ).fetchall()
        ids = np.array([z["id"] for z in zeilen], dtype=np.int64)
        matrix = (np.vstack([np.frombuffer(z["embedding"], dtype=np.float32) for z in zeilen])
                  if zeilen else np.zeros((0, 1), dtype=np.float32))
        cache = _cache = (modell, ids, matrix, [z["name"] for z in zeilen])
    return cache[1], cache[2], cache[3]


def aktive_buecher(einst: dict) -> list[str]:
    """Indexierte Fachbücher, die laut Adminbereich berücksichtigt werden."""
    if not einst["embedding_modell"]:
        return []
    aus = set(einst["deaktivierte_buecher"])
    with db.verbinden() as con:
        namen = [z["name"] for z in con.execute(
            "SELECT name FROM bib_dateien WHERE modell=? ORDER BY name COLLATE NOCASE", (einst["embedding_modell"],))]
    return [n for n in namen if n not in aus]


def suche(anfrage: str, k: int, einst: dict) -> list[dict]:
    """Die k ähnlichsten Abschnitte aus den berücksichtigten Fachbüchern (Kosinus-Ähnlichkeit)."""
    modell = einst["embedding_modell"]
    if not modell:
        return []
    ids, matrix, namen = _matrix(modell)
    aus = set(einst["deaktivierte_buecher"])
    erlaubt = np.array([n not in aus for n in namen], dtype=bool)
    if not erlaubt.any():
        return []
    q = _normiert(ollama.embed(einst["ollama_url"], modell, [anfrage]))[0]
    werte = np.where(erlaubt, matrix @ q, -np.inf)
    # stabile Sortierung: bei gleicher Ähnlichkeit entscheidet die Abschnitts-ID
    beste = [i for i in np.lexsort((ids, -werte))[:k] if erlaubt[i]]
    treffer_ids = [int(ids[i]) for i in beste]
    with db.verbinden() as con:
        zeilen = {z["id"]: z for z in con.execute(
            "SELECT a.id, a.seite, a.text, d.name FROM bib_abschnitte a JOIN bib_dateien d ON d.id = a.datei_id "
            f"WHERE a.id IN ({','.join('?' * len(treffer_ids))})", treffer_ids)}
    return [{"id": i, "datei": zeilen[i]["name"], "seite": zeilen[i]["seite"], "text": zeilen[i]["text"],
             "aehnlichkeit": round(float(werte[pos]), 4)}
            for i, pos in zip(treffer_ids, beste) if i in zeilen]
