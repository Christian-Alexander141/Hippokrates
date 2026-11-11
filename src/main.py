"""Hippokrates – lokaler Server. Start:  .venv/bin/python src/main.py"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from model.Datenkern import abgleich, db, ollama, rag

OBERFLAECHE = Path(__file__).parent / "Index" / "index.html"


@asynccontextmanager
async def lebenszyklus(app: FastAPI):
    db.initialisieren()
    yield


app = FastAPI(title="Hippokrates", lifespan=lebenszyklus)


@app.get("/", include_in_schema=False)
def oberflaeche():
    return FileResponse(OBERFLAECHE, headers={"Cache-Control": "no-store"})


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

class Einstellungen(BaseModel):
    """Alle Felder optional: Adminbereich und Technik speichern jeweils nur ihre eigenen Werte."""
    ollama_url: str | None = Field(None, min_length=1)
    agenten: list[str] | None = Field(None, min_length=1, max_length=12)
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


@app.get("/api/einstellungen")
def einstellungen_lesen():
    einst = abgleich.aktuelle_einstellungen()
    try:
        modelle, fehler = ollama.modelle(einst["ollama_url"]), ""
    except ollama.OllamaFehler as e:
        modelle, fehler = [], str(e)
    return {"einstellungen": einst, "modelle": modelle, "ollama_fehler": fehler}


@app.patch("/api/einstellungen")
def einstellungen_aendern(daten: Einstellungen):
    aenderungen = daten.model_dump(exclude_none=True)
    if "agenten" in aenderungen:
        if any(not m for m in aenderungen["agenten"]):
            raise HTTPException(400, "Bitte für jeden Agenten ein Sprachmodell auswählen.")
        if len(set(aenderungen["agenten"])) != len(aenderungen["agenten"]):
            # Dasselbe Modell mehrfach würde sich selbst zustimmen und den Konsens verfälschen.
            raise HTTPException(400, "Jedes Sprachmodell darf nur einem Agenten zugewiesen werden.")
    abgleich.aktuelle_einstellungen()  # Vorbelegung festschreiben, bevor einzelne Werte geändert werden
    alt, neu = db.einstellungen_aendern(aenderungen)
    if neu["embedding_modell"] != alt["embedding_modell"]:
        rag.indexieren_starten()  # Vektoren verschiedener Embedding-Modelle sind nicht vergleichbar
    return {"einstellungen": neu}


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


if __name__ == "__main__":
    import uvicorn
    # Nur lokal erreichbar: Die Anwendung hat keine Benutzeranmeldung.
    uvicorn.run(app, host="127.0.0.1", port=8000)
