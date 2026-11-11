"""Lokale, dauerhafte Speicherung (SQLite) für Patienten, Einstellungen, Abgleiche und Bibliotheksindex."""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

# Alle Laufzeitdaten liegen außerhalb von src/ und sind per .gitignore vom Repository ausgeschlossen.
DATEN_PFAD = Path(os.environ.get("HIPPOKRATES_DATEN", Path(__file__).resolve().parents[3] / "daten"))
DB_PFAD = DATEN_PFAD / "hippokrates.db"
BIBLIOTHEK_PFAD = DATEN_PFAD / "bibliothek"

# Felder, die an die Agenten gehen. Jede Änderung daran löst einen neuen Abgleich aus.
KLINISCHE_FELDER = {
    "anamnese": "Aktuelle Beschwerden / Anamnese",
    "befunde": "Befunde und Laborwerte",
    "vorerkrankungen": "Vorerkrankungen",
    "medikation": "Dauermedikation",
    "allergien": "Allergien und Unverträglichkeiten",
    "familienanamnese": "Familienanamnese",
    "sozialanamnese": "Sozialanamnese / Risikofaktoren",
    "ergaenzungen": "Ergänzungen und Antworten auf Rückfragen",
}
PATIENT_FELDER = ["name", "geburtsdatum", "geschlecht", *KLINISCHE_FELDER]

STANDARD_EINSTELLUNGEN = {
    # ── Technik ──
    "ollama_url": "http://localhost:11434",
    "agenten": None,  # Liste von Modellnamen; None = noch nie festgelegt
    "embedding_modell": "",
    "top_k": 4,  # Literaturstellen je Suchanfrage
    "parallel": 1,  # gleichzeitig laufende Agenten
    "icd_abgleich": True,  # Diagnosen mit gleicher ICD-10-Kategorie zusammenfassen
    "denken": False,  # Denkphase von Thinking-Modellen zulassen (gründlicher, aber deutlich langsamer)
    # ── Adminbereich (fachliche Vorgaben) ──
    "max_diagnosen": 5,  # Diagnosen je Agent
    "deaktivierte_buecher": [],  # Dateinamen der Fachbücher, die nicht berücksichtigt werden
    "internet": False,  # zusätzliche Recherche in PubMed-Abstracts (Europe PMC)
    "rueckfragen": True,  # Agenten dürfen Fragen zu fehlenden Angaben stellen
    "auto_abgleich": True,  # Änderungen an den Patientendaten starten sofort einen neuen Abgleich
    "einzelnennungen_einklappen": True,  # Diagnosen, die nur ein Agent nennt, eingeklappt zeigen
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS patienten (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    geburtsdatum TEXT NOT NULL DEFAULT '',
    geschlecht TEXT NOT NULL DEFAULT '',
    anamnese TEXT NOT NULL DEFAULT '',
    vorerkrankungen TEXT NOT NULL DEFAULT '',
    medikation TEXT NOT NULL DEFAULT '',
    allergien TEXT NOT NULL DEFAULT '',
    familienanamnese TEXT NOT NULL DEFAULT '',
    sozialanamnese TEXT NOT NULL DEFAULT '',
    befunde TEXT NOT NULL DEFAULT '',
    ergaenzungen TEXT NOT NULL DEFAULT '',
    geaendert TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS einstellungen (id INTEGER PRIMARY KEY CHECK (id = 1), wert TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS laeufe (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patienten(id) ON DELETE CASCADE,
    daten_hash TEXT NOT NULL,
    status TEXT NOT NULL,           -- laufend | fertig | fehler | abgebrochen
    meldung TEXT NOT NULL DEFAULT '',
    gestartet TEXT NOT NULL,
    beendet TEXT,
    konsens TEXT,
    rahmen TEXT                     -- Vorgaben, unter denen der Abgleich lief (Modelle, Bücher, Internet …)
);
CREATE TABLE IF NOT EXISTS agenten (
    id INTEGER PRIMARY KEY,
    lauf_id INTEGER NOT NULL REFERENCES laeufe(id) ON DELETE CASCADE,
    nr INTEGER NOT NULL,
    modell TEXT NOT NULL,
    status TEXT NOT NULL,           -- wartend | laufend | fertig | fehler | abgebrochen
    schritt TEXT NOT NULL DEFAULT '',
    suchanfragen TEXT,
    quellen TEXT,
    diagnosen TEXT,
    rueckfragen TEXT,
    hinweise TEXT,
    fehler TEXT,
    dauer REAL
);
CREATE TABLE IF NOT EXISTS bib_dateien (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    sha TEXT NOT NULL,
    modell TEXT NOT NULL,
    abschnitte INTEGER NOT NULL,
    indexiert TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bib_abschnitte (
    id INTEGER PRIMARY KEY,
    datei_id INTEGER NOT NULL REFERENCES bib_dateien(id) ON DELETE CASCADE,
    seite INTEGER,
    text TEXT NOT NULL,
    embedding BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_laeufe_patient ON laeufe(patient_id, id);
CREATE INDEX IF NOT EXISTS idx_agenten_lauf ON agenten(lauf_id);
CREATE INDEX IF NOT EXISTS idx_abschnitte_datei ON bib_abschnitte(datei_id);
"""

# Spalten, die nach der ersten Version hinzukamen – bestehende Datenbanken werden beim Start ergänzt.
_NACHTRAEGLICH = [
    ("patienten", "ergaenzungen", "TEXT NOT NULL DEFAULT ''"),
    ("laeufe", "rahmen", "TEXT"),
    ("agenten", "rueckfragen", "TEXT"),
    ("agenten", "hinweise", "TEXT"),
]

_einstellungen_sperre = threading.Lock()


def jetzt() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def verbinden():
    con = sqlite3.connect(DB_PFAD, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def initialisieren() -> None:
    BIBLIOTHEK_PFAD.mkdir(parents=True, exist_ok=True)
    with verbinden() as con:
        con.execute("PRAGMA journal_mode = WAL")
        con.executescript(_SCHEMA)
        for tabelle, spalte, definition in _NACHTRAEGLICH:
            if spalte not in {z["name"] for z in con.execute(f"PRAGMA table_info({tabelle})")}:
                con.execute(f"ALTER TABLE {tabelle} ADD COLUMN {spalte} {definition}")
        # Abgleiche, die ein Neustart unterbrochen hat, laufen nicht mehr weiter.
        con.execute(
            "UPDATE laeufe SET status='abgebrochen', meldung='Durch Neustart unterbrochen', beendet=? "
            "WHERE status='laufend'",
            (jetzt(),),
        )
        con.execute("UPDATE agenten SET status='abgebrochen' WHERE status IN ('wartend','laufend')")


def einstellungen() -> dict:
    with verbinden() as con:
        zeile = con.execute("SELECT wert FROM einstellungen WHERE id=1").fetchone()
    return {**STANDARD_EINSTELLUNGEN, **(json.loads(zeile["wert"]) if zeile else {})}


def einstellungen_speichern(werte: dict) -> None:
    with verbinden() as con:
        con.execute(
            "INSERT INTO einstellungen (id, wert) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET wert=excluded.wert",
            (json.dumps(werte),),
        )


def einstellungen_aendern(aenderungen: dict) -> tuple[dict, dict]:
    """Übernimmt einzelne Werte, ohne gleichzeitige Änderungen anderer Werte zu überschreiben. -> (alt, neu)"""
    with _einstellungen_sperre:
        alt = einstellungen()
        neu = {**alt, **aenderungen}
        einstellungen_speichern(neu)
    return alt, neu
