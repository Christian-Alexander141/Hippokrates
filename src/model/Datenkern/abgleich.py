"""Ablaufsteuerung: startet für einen Patienten alle Agenten und gleicht ihre Diagnosen anschließend ab."""
import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from . import agent, db, konsens, ollama, rag

_sperre = threading.Lock()
_abbrueche: dict[int, threading.Event] = {}  # patient_id -> Abbruchsignal des aktiven Abgleichs
_einzeln = threading.Lock()  # nur ein Abgleich gleichzeitig, damit sich Patienten nicht die GPU streitig machen


def aktuelle_einstellungen() -> dict:
    """Einstellungen; beim allerersten Aufruf werden bis zu drei lokale Modelle als Agenten vorbelegt."""
    einst = db.einstellungen()
    if einst["agenten"] is None or not einst["embedding_modell"]:
        try:
            modelle = ollama.modelle(einst["ollama_url"])
        except ollama.OllamaFehler:
            return {**einst, "agenten": einst["agenten"] or []}
        lokal = [m for m in modelle if not m["cloud"]]
        vorbelegung = {}
        if einst["agenten"] is None:
            chat = sorted((m for m in lokal if not m["embedding"]), key=lambda m: -m["groesse"])
            vorbelegung["agenten"] = [m["name"] for m in chat[:3]]
        if not einst["embedding_modell"]:
            vorbelegung["embedding_modell"] = next((m["name"] for m in lokal if m["embedding"]), "")
        _, einst = db.einstellungen_aendern(vorbelegung)
    return einst


def alter(geburtsdatum: str) -> int | None:
    try:
        geb, heute = date.fromisoformat(geburtsdatum), date.today()
    except ValueError:
        return None
    return heute.year - geb.year - ((heute.month, heute.day) < (geb.month, geb.day))


def patiententext(patient: dict) -> str:
    """Was die Agenten sehen. Der Name wird bewusst nicht weitergegeben."""
    kopf = []
    if (jahre := alter(patient["geburtsdatum"])) is not None:
        kopf.append(f"Alter: {jahre} Jahre")
    if patient["geschlecht"]:
        kopf.append(f"Geschlecht: {patient['geschlecht']}")
    teile = ["; ".join(kopf)] if kopf else []
    teile += [f"{titel}: {patient[feld].strip()}" for feld, titel in db.KLINISCHE_FELDER.items()
              if patient[feld].strip()]
    return "\n".join(teile)


def daten_hash(patient: dict) -> str:
    felder = ["geburtsdatum", "geschlecht", *db.KLINISCHE_FELDER]
    return hashlib.sha256(json.dumps([patient[f].strip() for f in felder]).encode()).hexdigest()


def hat_klinische_daten(patient: dict) -> bool:
    return any(patient[f].strip() for f in db.KLINISCHE_FELDER)


def bei_aenderung_starten(patient: dict) -> bool:
    """Startet einen Abgleich, wenn sich die klinischen Daten seit dem letzten Abgleich geändert haben
    und der automatische Abgleich im Adminbereich eingeschaltet ist."""
    if not hat_klinische_daten(patient) or not db.einstellungen()["auto_abgleich"]:
        return False
    with db.verbinden() as con:
        letzter = con.execute("SELECT daten_hash, status FROM laeufe WHERE patient_id=? ORDER BY id DESC LIMIT 1",
                              (patient["id"],)).fetchone()
    if letzter and letzter["daten_hash"] == daten_hash(patient) and letzter["status"] in ("laufend", "fertig"):
        return False
    starten(patient)
    return True


def abbrechen(patient_id: int) -> None:
    with _sperre:
        signal = _abbrueche.pop(patient_id, None)
    if signal:
        signal.set()


def _rahmen(einst: dict) -> dict:
    """Vorgaben, unter denen ein Abgleich läuft – wird mit dem Ergebnis gespeichert."""
    return {
        "agenten": einst["agenten"],
        "buecher": rag.aktive_buecher(einst),
        "internet": einst["internet"],
        "rueckfragen": einst["rueckfragen"],
        "max_diagnosen": einst["max_diagnosen"],
    }


def starten(patient: dict) -> int:
    einst = aktuelle_einstellungen()
    modelle = einst["agenten"]
    signal = threading.Event()
    with _sperre:
        alt = _abbrueche.get(patient["id"])
        if alt:
            alt.set()  # ein neuerer Datenstand ersetzt den laufenden Abgleich
        _abbrueche[patient["id"]] = signal
        with db.verbinden() as con:
            con.execute("UPDATE laeufe SET status='abgebrochen', meldung='Durch neueren Abgleich ersetzt', beendet=? "
                        "WHERE patient_id=? AND status='laufend'", (db.jetzt(), patient["id"]))
            lauf_id = con.execute(
                "INSERT INTO laeufe (patient_id, daten_hash, status, gestartet, rahmen) VALUES (?,?,?,?,?)",
                (patient["id"], daten_hash(patient), "laufend", db.jetzt(), json.dumps(_rahmen(einst)))).lastrowid
            con.executemany("INSERT INTO agenten (lauf_id, nr, modell, status) VALUES (?,?,?,'wartend')",
                            [(lauf_id, nr, m) for nr, m in enumerate(modelle, 1)])
    threading.Thread(target=_lauf, args=(lauf_id, patient["id"], patiententext(patient), einst, signal),
                     daemon=True).start()
    return lauf_id


def _agent_setzen(lauf_id: int, nr: int, **werte) -> None:
    with db.verbinden() as con:
        con.execute(f"UPDATE agenten SET {', '.join(f'{k}=?' for k in werte)} WHERE lauf_id=? AND nr=?",
                    (*werte.values(), lauf_id, nr))


def _ein_agent(lauf_id: int, nr: int, modell: str, text: str, einst: dict, signal: threading.Event) -> dict | None:
    if signal.is_set():
        _agent_setzen(lauf_id, nr, status="abgebrochen", schritt="")
        return None
    beginn = time.monotonic()
    _agent_setzen(lauf_id, nr, status="laufend", schritt="startet")
    try:
        ergebnis = agent.ausfuehren(modell, text, einst, signal,
                                    lambda schritt: _agent_setzen(lauf_id, nr, schritt=schritt))
    except ollama.Abgebrochen:
        _agent_setzen(lauf_id, nr, status="abgebrochen", schritt="")
        return None
    except Exception as e:  # ein ausgefallener Agent darf die übrigen nicht mitreißen
        _agent_setzen(lauf_id, nr, status="fehler", schritt="", fehler=str(e), dauer=time.monotonic() - beginn)
        return None
    _agent_setzen(lauf_id, nr, status="fertig", schritt="", dauer=time.monotonic() - beginn,
                  **{k: json.dumps(ergebnis[k]) for k in ("suchanfragen", "quellen", "diagnosen", "rueckfragen",
                                                           "hinweise")})
    return {"nr": nr, "modell": modell, "diagnosen": ergebnis["diagnosen"]}


def _lauf(lauf_id: int, patient_id: int, text: str, einst: dict, signal: threading.Event) -> None:
    status, meldung, rangliste = "fehler", "", None
    try:
        with _einzeln:
            modelle = einst["agenten"]
            if not modelle:
                meldung = "Keine Agenten konfiguriert – bitte unter „Technik“ Sprachmodelle auswählen."
            else:
                with ThreadPoolExecutor(max_workers=max(1, einst["parallel"])) as pool:
                    ergebnisse = list(pool.map(
                        lambda paar: _ein_agent(lauf_id, paar[0], paar[1], text, einst, signal),
                        enumerate(modelle, 1)))
                erfolgreich = [e for e in ergebnisse if e]
                if signal.is_set():
                    status, meldung = "abgebrochen", "Durch neueren Abgleich ersetzt"
                elif not erfolgreich:
                    meldung = "Kein Agent hat ein Ergebnis geliefert."
                else:
                    rangliste = konsens.konsens(erfolgreich, einst["icd_abgleich"])
                    status = "fertig"
                    if len(erfolgreich) < len(modelle):
                        meldung = f"{len(modelle) - len(erfolgreich)} von {len(modelle)} Agenten sind ausgefallen."
    except Exception as e:
        meldung = f"Interner Fehler: {e}"
    finally:
        with db.verbinden() as con:
            con.execute("UPDATE laeufe SET status=?, meldung=?, beendet=?, konsens=? WHERE id=? AND status='laufend'",
                        (status, meldung, db.jetzt(), json.dumps(rangliste) if rangliste is not None else None,
                         lauf_id))
            con.execute("UPDATE agenten SET status='abgebrochen', schritt='' "
                        "WHERE lauf_id=? AND status IN ('wartend','laufend')", (lauf_id,))
        with _sperre:
            if _abbrueche.get(patient_id) is signal:
                del _abbrueche[patient_id]


# ── Lesen ─────────────────────────────────────────────────────────────────────

def _lauf_lesen(con, lauf) -> dict:
    agenten = []
    for a in con.execute("SELECT * FROM agenten WHERE lauf_id=? ORDER BY nr", (lauf["id"],)):
        eintrag = dict(a)
        for feld in ("suchanfragen", "quellen", "diagnosen", "rueckfragen", "hinweise"):
            eintrag[feld] = json.loads(a[feld]) if a[feld] else []
        # Abgleiche aus der ersten Version speicherten Suchanfragen als reine Texte
        eintrag["suchanfragen"] = [s if isinstance(s, dict) else {"art": "buch", "text": s}
                                   for s in eintrag["suchanfragen"]]
        for q in eintrag["quellen"]:
            q.setdefault("art", "buch")
        agenten.append(eintrag)
    ergebnis = dict(lauf)
    ergebnis["konsens"] = json.loads(lauf["konsens"]) if lauf["konsens"] else []
    ergebnis["rahmen"] = json.loads(lauf["rahmen"]) if lauf["rahmen"] else None
    ergebnis["agenten"] = agenten
    ergebnis["rueckfragen"] = konsens.rueckfragen_buendeln([a for a in agenten if a["status"] == "fertig"])
    return ergebnis


def stand(patient: dict) -> dict:
    """Neuester Abgleich (ggf. laufend) und neuestes fertiges Ergebnis eines Patienten."""
    with db.verbinden() as con:
        letzter = con.execute("SELECT * FROM laeufe WHERE patient_id=? ORDER BY id DESC LIMIT 1",
                              (patient["id"],)).fetchone()
        fertig = letzter if letzter and letzter["status"] == "fertig" else con.execute(
            "SELECT * FROM laeufe WHERE patient_id=? AND status='fertig' ORDER BY id DESC LIMIT 1",
            (patient["id"],)).fetchone()
        lauf = _lauf_lesen(con, letzter) if letzter else None
        ergebnis = lauf if fertig is letzter else (_lauf_lesen(con, fertig) if fertig else None)
    h = daten_hash(patient)
    for eintrag in (lauf, ergebnis):
        if eintrag:
            eintrag["aktuell"] = eintrag["daten_hash"] == h
    return {"lauf": lauf, "ergebnis": ergebnis}


def uebersicht() -> list[dict]:
    """Alle Patienten mit Abgleichstatus und führender Diagnose – für Patientenliste und Übersicht."""
    with db.verbinden() as con:
        patienten = [dict(z) for z in con.execute("SELECT * FROM patienten ORDER BY name COLLATE NOCASE")]
        letzte = {z["patient_id"]: z for z in con.execute(
            "SELECT patient_id, status, daten_hash FROM laeufe WHERE id IN (SELECT MAX(id) FROM laeufe GROUP BY patient_id)")}
        fertige = {z["patient_id"]: z for z in con.execute(
            "SELECT patient_id, konsens, daten_hash, beendet FROM laeufe "
            "WHERE id IN (SELECT MAX(id) FROM laeufe WHERE status='fertig' GROUP BY patient_id)")}
    liste = []
    for p in patienten:
        h, letzter, fertig = daten_hash(p), letzte.get(p["id"]), fertige.get(p["id"])
        if letzter is None:
            zustand = "ohne" if hat_klinische_daten(p) else "leer"
        elif letzter["status"] == "laufend":
            zustand = "laufend"
        elif letzter["status"] == "fertig":
            zustand = "aktuell" if letzter["daten_hash"] == h else "veraltet"
        else:
            zustand = letzter["status"]  # fehler | abgebrochen
        rangliste = json.loads(fertig["konsens"] or "[]") if fertig else []
        liste.append({
            "id": p["id"], "name": p["name"], "geburtsdatum": p["geburtsdatum"], "geschlecht": p["geschlecht"],
            "alter": alter(p["geburtsdatum"]), "geaendert": p["geaendert"], "zustand": zustand,
            "abgeglichen": fertig["beendet"] if fertig else None,
            "diagnosen": [{k: g[k] for k in ("name", "icd10", "stimmen", "agenten_gesamt")} for g in rangliste[:3]],
        })
    return liste
