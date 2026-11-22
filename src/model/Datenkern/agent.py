"""Ein Diagnose-Agent: recherchiert eigenständig und liefert strukturierte Differentialdiagnosen.

Jeder Agent arbeitet nur mit den Patientendaten und seinen eigenen Rechercheergebnissen –
er sieht weder die Suchanfragen noch die Diagnosen der anderen Agenten.

Schritte (Schlüssel für die Fortschrittsanzeige):
  plant       – formuliert Suchanfragen für Fachbibliothek und ggf. PubMed
  bibliothek  – durchsucht die berücksichtigten Fachbücher
  internet    – sucht in PubMed-Abstracts (nur wenn im Adminbereich erlaubt)
  netze       – wertet freigeschaltete eigene neuronale Netze aus (Bibliothek netzwerkzeug)
  diagnose    – erstellt die Differentialdiagnosen und ggf. Rückfragen

Die eigenen Netze werden wie Werkzeuge eines LangChain-Agenten genutzt: Der Agent überträgt in der
Planungsphase die Eingaben aus der Akte (Schema = Eingabemodell des Netzes), das Netz rechnet
deterministisch, sein Ergebnis geht als zitierbare Quelle in die Diagnose ein. Dieser feste Ablauf
funktioniert auch mit kleinen Modellen ohne zuverlässige Werkzeugaufrufe.
"""
import json
import threading
from typing import Callable

from . import netze, ollama, rag, sprachmodelle, web

MAX_SUCHANFRAGEN = 4
MAX_WEBANFRAGEN = 2
MAX_QUELLEN = 8
MAX_WEBQUELLEN = 4
MAX_RUECKFRAGEN = 3

_SYSTEM = (
    "Du bist ein medizinischer Assistent für Differentialdiagnostik und unterstützt ärztliches Fachpersonal. "
    "Du arbeitest sorgfältig, stützt dich auf die Patientendaten und die bereitgestellte Fachliteratur "
    "und antwortest auf Deutsch – ausschließlich mit einem JSON-Objekt, ohne Erklärtext und ohne Markdown."
)



def _textliste(n: int, laenge: int = 200) -> dict:
    """Begrenzte Liste – verhindert, dass kleine Modelle endlos weitere Einträge erzeugen."""
    return {"type": "array", "items": {"type": "string", "maxLength": laenge}, "maxItems": n}


def _liste(werte, n: int) -> list[str]:
    ergebnis: list[str] = []
    for w in werte if isinstance(werte, list) else []:
        w = str(w).strip()
        if w and w not in ergebnis:
            ergebnis.append(w)
    return ergebnis[:n]


def _pruefen(abbruch: threading.Event) -> None:
    if abbruch.is_set():
        raise ollama.Abgebrochen()


def _quellenkopf(q: dict) -> str:
    if q["art"] == "netz":
        return f"[{q['nr']}] {q['titel']}"
    if q["art"] == "web":
        return f"[{q['nr']}] PubMed: {q['titel']} ({q['fundstelle']})"
    return f"[{q['nr']}] Fachbuch „{q['datei']}“" + (f", S. {q['seite']}" if q["seite"] else "")


def ausfuehren(modell: str, patiententext: str, einst: dict, abbruch: threading.Event,
               fortschritt: Callable[[str], None]) -> dict:
    denken = einst["denken"]
    bibliothek = bool(rag.aktive_buecher(einst))
    internet = bool(einst["internet"])
    netz_werkzeuge = netze.aktive(einst)
    netz_eingaben: dict[str, dict] = {}
    buch_anfragen: list[str] = []
    web_anfragen: list[str] = []
    quellen: list[dict] = []
    hinweise: list[str] = []

    # ── 1. Recherche planen ──
    if bibliothek or internet or netz_werkzeuge:
        fortschritt("plant")
        eigenschaften, auftraege, beispiel = {}, [], {}
        if bibliothek:
            eigenschaften["suchanfragen"] = _textliste(MAX_SUCHANFRAGEN, 150)
            beispiel["suchanfragen"] = ["...", "..."]
            auftraege.append(f"'suchanfragen': bis zu {MAX_SUCHANFRAGEN} kurze, gezielte Suchanfragen für die "
                             "Fachbibliothek (Symptomkombinationen, Verdachtsdiagnosen, auffällige Befunde).")
        if internet:
            eigenschaften["pubmed"] = _textliste(MAX_WEBANFRAGEN, 120)
            beispiel["pubmed"] = ["..."]
            auftraege.append(f"'pubmed': bis zu {MAX_WEBANFRAGEN} englische Suchbegriffe für PubMed aus "
                             "medizinischen Fachtermini (z. B. \"scurvy gingival bleeding\"). Keine Namen, "
                             "keine persönlichen Angaben.")
        if netz_werkzeuge:
            eigenschaften["netze"], auftrag = netze.planungsschema(netz_werkzeuge)
            beispiel["netze"] = {w.name: {"anwendbar": True, "...": "..."} for w in netz_werkzeuge}
            auftraege.append(auftrag)
        antwort = sprachmodelle.chat_json(einst, modell, [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": (
                f"Patientendaten:\n{patiententext}\n\n"
                "Du recherchierst die Differentialdiagnosen dieses Falls. Formuliere dazu:\n- "
                + "\n- ".join(auftraege)
                + f"\n\nAntworte nur mit JSON in genau dieser Form: {json.dumps(beispiel, ensure_ascii=False)}"
            )},
        ], {"type": "object", "properties": eigenschaften, "required": list(eigenschaften)}, abbruch, denken)
        buch_anfragen = _liste(antwort.get("suchanfragen"), MAX_SUCHANFRAGEN) if bibliothek else []
        web_anfragen = _liste(antwort.get("pubmed"), MAX_WEBANFRAGEN) if internet else []
        geplant = antwort.get("netze") if isinstance(antwort.get("netze"), dict) else {}
        for w in netz_werkzeuge:
            eintrag = geplant.get(w.name)
            if isinstance(eintrag, dict) and eintrag.get("anwendbar") is True:
                netz_eingaben[w.name] = {k: v for k, v in eintrag.items() if k != "anwendbar"}

    # ── 2. Fachbibliothek ──
    if buch_anfragen:
        fortschritt("bibliothek")
        treffer: dict[int, dict] = {}
        for anfrage in buch_anfragen:
            _pruefen(abbruch)
            for t in rag.suche(anfrage, einst["top_k"], einst):
                if t["id"] not in treffer or t["aehnlichkeit"] > treffer[t["id"]]["aehnlichkeit"]:
                    treffer[t["id"]] = t
        quellen = [{"art": "buch", **t}
                   for t in sorted(treffer.values(), key=lambda t: (-t["aehnlichkeit"], t["id"]))[:MAX_QUELLEN]]

    # ── 3. PubMed ──
    if web_anfragen:
        fortschritt("internet")
        gesehen: set[str] = set()
        for anfrage in web_anfragen:
            _pruefen(abbruch)
            try:
                ergebnisse = web.suche(anfrage, MAX_WEBQUELLEN // MAX_WEBANFRAGEN)
            except web.WebFehler as e:
                hinweise.append(f"PubMed-Suche „{anfrage}“ fehlgeschlagen: {e}")
                continue
            for t in ergebnisse:
                if t["id"] not in gesehen:
                    gesehen.add(t["id"])
                    quellen.append({"art": "web", **t})
        if not gesehen and not hinweise:
            hinweise.append("PubMed lieferte zu den Suchbegriffen keine Treffer.")
    elif internet:
        hinweise.append("Der Agent hat keine PubMed-Suchbegriffe formuliert.")

    # ── 4. Eigene neuronale Netze ──
    if netz_eingaben:
        fortschritt("netze")
        for w in netz_werkzeuge:
            if w.name not in netz_eingaben:
                continue
            _pruefen(abbruch)
            try:
                quellen.append(netze.auswerten(w, netz_eingaben[w.name]))
            except Exception as e:  # ein fehlerhaftes Netz darf den Agenten nicht aufhalten
                hinweise.append(f"Netz „{w.name}“: {e}")
    for w in netz_werkzeuge:
        if w.name not in netz_eingaben:
            hinweise.append(f"Netz „{w.name}“ nicht befragt – die nötigen Eingaben fehlen laut Agent in der Akte.")
    for nr, q in enumerate(quellen, 1):
        q["nr"] = nr

    # ── 5. Diagnosen ──
    _pruefen(abbruch)
    fortschritt("diagnose")
    if quellen:
        literatur = "Rechercheergebnisse:\n\n" + "\n\n".join(f"{_quellenkopf(q)}\n{q['text']}" for q in quellen)
        quellenhinweis = ("'quellen': die Nummern der Literaturstellen bzw. Netzergebnisse, die die Diagnose "
                          "stützen (leere Liste, wenn keine passt).")
    else:
        literatur = "Es liegen keine Rechercheergebnisse vor."
        quellenhinweis = "'quellen': leere Liste."
    n = einst["max_diagnosen"]
    eintrag = {"name": "...", "icd10": "...", "begruendung": "...", "quellen": [1, 2]}
    schema_diagnose = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "icd10": {"type": "string"}, "begruendung": {"type": "string"},
                       "quellen": {"type": "array", "items": {"type": "integer"}}},
        "required": ["name", "icd10", "begruendung", "quellen"],
    }
    schema = {"type": "object", "properties": {"diagnosen": {"type": "array", "items": schema_diagnose, "maxItems": n}},
              "required": ["diagnosen"]}
    beispiel = {"diagnosen": [eintrag]}
    rueckfragen_auftrag = ""
    if einst["rueckfragen"]:
        schema["properties"]["rueckfragen"] = _textliste(MAX_RUECKFRAGEN, 250)
        schema["required"].append("rueckfragen")
        beispiel["rueckfragen"] = ["..."]
        rueckfragen_auftrag = (
            f"\n\nUnter 'rueckfragen' stellst du bis zu {MAX_RUECKFRAGEN} kurze, konkrete Fragen an die behandelnde "
            "Ärztin oder den behandelnden Arzt – nur zu Angaben, die fehlen und die Differentialdiagnose deutlich "
            "eingrenzen würden. Frage nichts, was in den Patientendaten bereits beantwortet ist. Leere Liste, "
            "wenn nichts Wesentliches fehlt."
        )
    antwort = sprachmodelle.chat_json(einst, modell, [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": (
            f"Patientendaten:\n{patiententext}\n\n{literatur}\n\n"
            f"Nenne die bis zu {n} wahrscheinlichsten Differentialdiagnosen, absteigend nach Wahrscheinlichkeit. "
            "'name': die gängige deutsche Fachbezeichnung der Erkrankung, ohne Zusätze wie 'Verdacht auf'. "
            "'icd10': der ICD-10-Code (z. B. K35.8). 'begruendung': zwei bis drei Sätze, welche Angaben des "
            f"Patienten dafür sprechen. {quellenhinweis}{rueckfragen_auftrag}\n\n"
            f"Antworte nur mit JSON in genau dieser Form: {json.dumps(beispiel, ensure_ascii=False)}"
        )},
    ], schema, abbruch, denken)

    gueltige_nummern = {q["nr"] for q in quellen}
    diagnosen = []
    for d in antwort.get("diagnosen") or []:
        if not isinstance(d, dict) or not str(d.get("name") or "").strip():
            continue
        diagnosen.append({
            "name": str(d["name"]).strip(),
            "icd10": str(d.get("icd10") or "").strip(),
            "begruendung": str(d.get("begruendung") or "").strip(),
            "quellen": sorted({q for q in d.get("quellen") or [] if isinstance(q, int) and q in gueltige_nummern}),
        })
    return {
        "suchanfragen": [{"art": "buch", "text": a} for a in buch_anfragen]
                        + [{"art": "web", "text": a} for a in web_anfragen]
                        + [{"art": "netz", "text": f"{n}({', '.join(f'{k}={v}' for k, v in e.items())})"}
                           for n, e in netz_eingaben.items()],
        "quellen": quellen,
        "diagnosen": diagnosen[:n],
        "rueckfragen": _liste(antwort.get("rueckfragen"), MAX_RUECKFRAGEN) if einst["rueckfragen"] else [],
        "hinweise": hinweise,
    }
