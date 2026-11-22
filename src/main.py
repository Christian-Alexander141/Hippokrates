"""Hippokrates – lokaler Server. Start:  .venv/bin/python src/main.py

Die Oberfläche ist eine React-Anwendung (Ordner frontend/). Der Server liefert ihren Build aus
frontend/dist aus; während der Entwicklung läuft stattdessen `npm run dev` mit Weiterleitung an /api.
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from model.Datenkern import abgleich, db, netze, rag, sprachmodelle

VERSION = "0.3.0"
OBERFLAECHE = Path(os.environ.get("HIPPOKRATES_OBERFLAECHE", Path(__file__).resolve().parents[1] / "frontend" / "dist"))
IN_DOCKER = os.environ.get("HIPPOKRATES_DOCKER") == "1"


@asynccontextmanager
async def lebenszyklus(app: FastAPI):
    db.initialisieren()
    yield


app = FastAPI(title="Hippokrates", version=VERSION, lifespan=lebenszyklus)


@app.get("/api/status")
def status():
    """Lebenszeichen für Docker-Healthcheck und Oberfläche – ohne Modellabfrage, daher schnell."""
    return {"ok": True, "version": VERSION, "docker": IN_DOCKER,
            "ollama_url_fest": bool(db.OLLAMA_URL_FEST), "modell_host": sprachmodelle.MODELL_HOST}


# ── Patienten ──────────────────────────────────────────────────────────────────

class Patient(BaseModel):
    name: str = Field(min_length=1)
    geburtsdatum: str = ""
    geschlecht: str = ""
    anamnese: str = ""
    befunde: str = ""
    vorerkrankungen: str = ""
    medikation: str = ""
    allergien: str = ""
    familienanamnese: str = ""
    sozialanamnese: str = ""
    ergaenzungen: str = ""


class Antwort(BaseModel):
    frage: str = Field(min_length=1)
    antwort: str = Field(min_length=1)


class Antworten(BaseModel):
    antworten: list[Antwort] = Field(min_length=1)


def _patient(patient_id: int) -> dict:
    with db.verbinden() as con:
        zeile = con.execute("SELECT * FROM patienten WHERE id=?", (patient_id,)).fetchone()
    if not zeile:
        raise HTTPException(404, "Patient nicht gefunden")
    return dict(zeile)


@app.get("/api/patienten")
def patienten_liste():
    return abgleich.uebersicht()


@app.post("/api/patienten")
def patient_anlegen(daten: Patient):
    werte = daten.model_dump()
    with db.verbinden() as con:
        patient_id = con.execute(
            f"INSERT INTO patienten ({', '.join(db.PATIENT_FELDER)}, geaendert) "
            f"VALUES ({', '.join('?' * len(db.PATIENT_FELDER))}, ?)",
            (*[werte[f] for f in db.PATIENT_FELDER], db.jetzt())).lastrowid
    patient = _patient(patient_id)
    return {"patient": patient, "abgleich_gestartet": abgleich.bei_aenderung_starten(patient)}


@app.get("/api/patienten/{patient_id}")
def patient_lesen(patient_id: int):
    return _patient(patient_id)


@app.put("/api/patienten/{patient_id}")
def patient_aendern(patient_id: int, daten: Patient):
    _patient(patient_id)
    werte = daten.model_dump()
    with db.verbinden() as con:
        con.execute(f"UPDATE patienten SET {', '.join(f'{f}=?' for f in db.PATIENT_FELDER)}, geaendert=? WHERE id=?",
                    (*[werte[f] for f in db.PATIENT_FELDER], db.jetzt(), patient_id))
    patient = _patient(patient_id)
    return {"patient": patient, "abgleich_gestartet": abgleich.bei_aenderung_starten(patient)}


@app.delete("/api/patienten/{patient_id}")
def patient_loeschen(patient_id: int):
    _patient(patient_id)
    abgleich.abbrechen(patient_id)
    with db.verbinden() as con:
        con.execute("DELETE FROM patienten WHERE id=?", (patient_id,))
    return {"ok": True}


@app.get("/api/patienten/{patient_id}/abgleich")
def abgleich_lesen(patient_id: int):
    patient = _patient(patient_id)
    return {"patient": {**patient, "alter": abgleich.alter(patient["geburtsdatum"]),
                        "hat_daten": abgleich.hat_klinische_daten(patient)},
            **abgleich.stand(patient)}


@app.post("/api/patienten/{patient_id}/abgleich")
def abgleich_neu(patient_id: int):
    patient = _patient(patient_id)
    if not abgleich.hat_klinische_daten(patient):
        raise HTTPException(400, "Für diesen Patienten sind noch keine klinischen Angaben gespeichert.")
    return {"lauf_id": abgleich.starten(patient)}


@app.post("/api/patienten/{patient_id}/antworten")
def rueckfragen_beantworten(patient_id: int, daten: Antworten):
    """Antworten auf Rückfragen in der Patientenakte ergänzen und sofort neu abgleichen."""
    patient = _patient(patient_id)
    neu = "\n".join(f"Rückfrage: {a.frage.strip()}\nAntwort: {a.antwort.strip()}" for a in daten.antworten)
    ergaenzungen = "\n\n".join(t for t in (patient["ergaenzungen"].strip(), neu) if t)
    with db.verbinden() as con:
        con.execute("UPDATE patienten SET ergaenzungen=?, geaendert=? WHERE id=?",
                    (ergaenzungen, db.jetzt(), patient_id))
    return {"lauf_id": abgleich.starten(_patient(patient_id))}


# ── Einstellungen (Adminbereich und Technik) ───────────────────────────────────

class Server(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    url: str = Field(pattern=r"^https?://")
    api_schluessel: str = ""


class Einstellungen(BaseModel):
    """Alle Felder optional: Adminbereich und Technik speichern jeweils nur ihre eigenen Werte."""
    ollama_url: str | None = Field(None, pattern=r"^https?://")
    agenten: list[str] | None = Field(None, max_length=24)
    agenten_modus: str | None = Field(None, pattern="^(auswahl|alle)$")
    ausgeschlossene_modelle: list[str] | None = None
    server_suchen: bool | None = None
    zusatz_server: list[Server] | None = Field(None, max_length=10)
    embedding_modell: str | None = None
    top_k: int | None = Field(None, ge=1, le=10)
    parallel: int | None = Field(None, ge=1, le=12)
    icd_abgleich: bool | None = None
    denken: bool | None = None
    max_diagnosen: int | None = Field(None, ge=1, le=10)
    deaktivierte_buecher: list[str] | None = None
    internet: bool | None = None
    rueckfragen: bool | None = None
    auto_abgleich: bool | None = None
    einzelnennungen_einklappen: bool | None = None
    netze_aktiv: list[str] | None = None


def _umgebung() -> dict:
    return {"ollama_url_fest": bool(db.OLLAMA_URL_FEST), "docker": IN_DOCKER, "modell_host": sprachmodelle.MODELL_HOST}


@app.get("/api/modelle")
def modelle_lesen():
    """Alle verfügbaren Sprachmodelle – bei jedem Aufruf frisch bei Ollama und den lokalen Servern abgefragt."""
    return sprachmodelle.ermitteln(db.einstellungen())


@app.get("/api/einstellungen")
def einstellungen_lesen():
    einst = abgleich.aktuelle_einstellungen()
    verfuegbar = sprachmodelle.ermitteln(einst)
    ollama_quelle = next((q for q in verfuegbar["quellen"] if q["art"] == "ollama"), None)
    return {"einstellungen": einst, **verfuegbar, "ollama_fehler": ollama_quelle["fehler"] if ollama_quelle else "",
            "umgebung": _umgebung()}


@app.patch("/api/einstellungen")
def einstellungen_aendern(daten: Einstellungen):
    aenderungen = daten.model_dump(exclude_none=True)
    if "agenten" in aenderungen:
        if any(not m for m in aenderungen["agenten"]):
            raise HTTPException(400, "Bitte für jeden Agenten ein Sprachmodell auswählen.")
        if len(set(aenderungen["agenten"])) != len(aenderungen["agenten"]):
            # Dasselbe Modell mehrfach würde sich selbst zustimmen und den Konsens verfälschen.
            raise HTTPException(400, "Jedes Sprachmodell darf nur einem Agenten zugewiesen werden.")
    if "ollama_url" in aenderungen and db.OLLAMA_URL_FEST:
        raise HTTPException(400, "Die Ollama-Adresse ist über HIPPOKRATES_OLLAMA_URL fest vorgegeben.")
    abgleich.aktuelle_einstellungen()  # Vorbelegung festschreiben, bevor einzelne Werte geändert werden
    alt, neu = db.einstellungen_aendern(aenderungen)
    if neu["embedding_modell"] != alt["embedding_modell"]:
        rag.indexieren_starten()  # Vektoren verschiedener Embedding-Modelle sind nicht vergleichbar
    return {"einstellungen": neu}


# ── Eigene neuronale Netze ─────────────────────────────────────────────────────

@app.get("/api/netze")
def netze_lesen():
    """Netze aus dem Ordner netze/ und installierten Paketen – bei jedem Aufruf neu gesucht."""
    return netze.uebersicht()


# ── Fachbibliothek ─────────────────────────────────────────────────────────────

def _bibliotheksdatei(name: str) -> Path:
    pfad = db.BIBLIOTHEK_PFAD / Path(name).name
    if not Path(name).name or pfad.suffix.lower() not in rag.ERLAUBTE_ENDUNGEN:
        raise HTTPException(400, "Erlaubt sind PDF-, TXT- und MD-Dateien.")
    return pfad


@app.get("/api/bibliothek")
def bibliothek_lesen():
    return {"dateien": rag.dateien(), "status": rag.status, "ordner": str(db.BIBLIOTHEK_PFAD),
            "embedding_modell": db.einstellungen()["embedding_modell"]}


@app.post("/api/bibliothek/datei")
async def bibliothek_hochladen(name: str, request: Request):
    pfad = _bibliotheksdatei(name)
    pfad.write_bytes(await request.body())
    rag.indexieren_starten()
    return {"ok": True}


@app.delete("/api/bibliothek/datei")
def bibliothek_loeschen(name: str):
    pfad = _bibliotheksdatei(name)
    if not pfad.is_file():
        raise HTTPException(404, "Datei nicht gefunden")
    pfad.unlink()
    aus = db.einstellungen()["deaktivierte_buecher"]
    if pfad.name in aus:  # ein später erneut hochgeladenes Buch soll wieder berücksichtigt werden
        db.einstellungen_aendern({"deaktivierte_buecher": [n for n in aus if n != pfad.name]})
    rag.indexieren_starten()
    return {"ok": True}


@app.post("/api/bibliothek/indexieren")
def bibliothek_indexieren():
    return {"gestartet": rag.indexieren_starten()}


# ── Oberfläche (React-Build) ───────────────────────────────────────────────────

if (OBERFLAECHE / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=OBERFLAECHE / "assets"), name="assets")


@app.get("/{pfad:path}", include_in_schema=False)
def oberflaeche(pfad: str):
    """Alle übrigen Pfade gehören der React-Anwendung (clientseitiges Routing)."""
    if pfad.startswith("api/"):
        raise HTTPException(404, "Unbekannte Schnittstelle")
    datei = (OBERFLAECHE / pfad).resolve()
    if pfad and datei.is_file() and datei.is_relative_to(OBERFLAECHE.resolve()):
        return FileResponse(datei)
    index = OBERFLAECHE / "index.html"
    if not index.is_file():
        return HTMLResponse(
            "<h1>Oberfläche nicht gebaut</h1><p>Bitte im Ordner <code>frontend</code> "
            "<code>npm install</code> und <code>npm run build</code> ausführen – oder für die Entwicklung "
            "<code>npm run dev</code> starten und <a href='http://localhost:5173'>localhost:5173</a> öffnen.</p>",
            status_code=503)
    return FileResponse(index, headers={"Cache-Control": "no-store"})


if __name__ == "__main__":
    import uvicorn
    # Standard: nur lokal erreichbar, denn die Anwendung hat keine Benutzeranmeldung. Im Docker-Container
    # muss sie auf 0.0.0.0 lauschen; docker-compose.yml veröffentlicht den Port dann nur auf 127.0.0.1.
    uvicorn.run(app, host=os.environ.get("HIPPOKRATES_HOST", "127.0.0.1"),
                port=int(os.environ.get("HIPPOKRATES_PORT", "8000")))
