"""Deterministischer Abgleich der Agenten-Diagnosen – ohne Sprachmodell, gleiche Eingabe ergibt gleiche Ausgabe.

Zwei Nennungen gelten als dieselbe Diagnose, wenn
  1. ihre normalisierten Namen übereinstimmen (siehe `namensschluessel`) oder
  2. ihre ICD-10-Codes in derselben dreistelligen Kategorie liegen (abschaltbar).

Rangfolge: Anzahl der Agenten, die die Diagnose nennen (absteigend); bei Gleichstand der
mittlere Listenplatz bei diesen Agenten (aufsteigend); danach alphabetisch.
"""
import re
from collections import Counter

_FUELLWOERTER = {
    "der", "die", "das", "des", "dem", "den", "ein", "eine", "einer", "eines", "mit", "bei", "und",
    "von", "vom", "im", "in", "am", "an", "auf", "verdacht", "va",
}
_ROEMISCH = {"i": "1", "ii": "2", "iii": "3", "iv": "4"}


def namensschluessel(name: str) -> str:
    """Schreibvarianten angleichen: Groß/Klein, Umlaute, c/k/z (Appendicitis = Appendizitis),
    Klammerzusätze, 'V. a.', Füllwörter, Wortreihenfolge, römische Typziffern."""
    s = name.lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*(v\.\s*a\.|dd:?\s)", " ", s)
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), ("é", "e")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    woerter = set()
    for w in s.split():
        if w in _FUELLWOERTER:
            continue
        w = _ROEMISCH.get(w, w)
        w = w.replace("ck", "k").replace("ph", "f").replace("th", "t")
        w = re.sub(r"c(?=[eiy])", "z", w)       # Appendicitis -> appendizitis
        w = re.sub(r"(?<!s)c(?!h)", "k", w)     # Carcinom -> karzinom, 'sch'/'ch' bleiben
        woerter.add(w)
    return " ".join(sorted(woerter))


def icd_kategorie(code: str) -> str:
    """'k35.80' -> 'K35'; leer, wenn kein ICD-10-Code erkennbar ist."""
    m = re.search(r"\b([A-Z])\s?(\d{2})", code.upper())
    return m.group(1) + m.group(2) if m else ""


def _haeufigster(werte: list[str]) -> str:
    if not werte:
        return ""
    zaehler = Counter(werte)
    return min(zaehler, key=lambda w: (-zaehler[w], len(w), w))


def konsens(agenten: list[dict], icd_abgleich: bool = True) -> list[dict]:
    """agenten: [{'nr', 'modell', 'diagnosen': [{'name', 'icd10', 'begruendung', 'quellen'}]}] (nur erfolgreiche)."""
    nennungen = []
    for agent in sorted(agenten, key=lambda a: a["nr"]):
        for rang, d in enumerate(agent["diagnosen"], 1):
            schluessel = namensschluessel(d["name"])
            if schluessel:
                nennungen.append({"agent": agent["nr"], "modell": agent["modell"], "rang": rang,
                                  "schluessel": schluessel, **d})

    # Union-Find: Nennungen mit gleichem Namensschlüssel oder gleicher ICD-Kategorie zusammenführen
    eltern = list(range(len(nennungen)))

    def wurzel(i: int) -> int:
        while eltern[i] != i:
            eltern[i] = eltern[eltern[i]]
            i = eltern[i]
        return i

    erster: dict[tuple[str, str], int] = {}
    for i, n in enumerate(nennungen):
        merkmale = [("name", n["schluessel"])]
        if icd_abgleich and icd_kategorie(n["icd10"]):
            merkmale.append(("icd", icd_kategorie(n["icd10"])))
        for merkmal in merkmale:
            if merkmal in erster:
                a, b = wurzel(erster[merkmal]), wurzel(i)
                eltern[max(a, b)] = min(a, b)
            else:
                erster[merkmal] = i

    gruppen: dict[int, list[dict]] = {}
    for i, n in enumerate(nennungen):
        gruppen.setdefault(wurzel(i), []).append(n)

    ergebnis = []
    for mitglieder in gruppen.values():
        je_agent: dict[int, dict] = {}  # jeder Agent zählt je Diagnose nur einmal, mit seinem besten Platz
        for n in mitglieder:
            if n["agent"] not in je_agent or n["rang"] < je_agent[n["agent"]]["rang"]:
                je_agent[n["agent"]] = n
        stimmen = sorted(je_agent.values(), key=lambda n: n["agent"])
        ergebnis.append({
            "name": _haeufigster([n["name"] for n in stimmen]),
            "icd10": _haeufigster([n["icd10"].upper() for n in stimmen if icd_kategorie(n["icd10"])]),
            "stimmen": len(stimmen),
            "agenten_gesamt": len(agenten),
            "mittlerer_rang": round(sum(n["rang"] for n in stimmen) / len(stimmen), 2),
            "nennungen": [{k: n[k] for k in ("agent", "modell", "rang", "name", "icd10", "begruendung", "quellen")}
                          for n in stimmen],
        })
    ergebnis.sort(key=lambda g: (-g["stimmen"], g["mittlerer_rang"], g["name"].lower(), g["icd10"]))
    return ergebnis


def rueckfragen_buendeln(agenten: list[dict]) -> list[dict]:
    """Gleichlautende Rückfragen zusammenfassen; zuerst die, die mehrere Agenten stellen."""
    gruppen: dict[str, dict] = {}
    for agent in sorted(agenten, key=lambda a: a["nr"]):
        for frage in agent.get("rueckfragen") or []:
            schluessel = re.sub(r"[^a-z0-9äöüß]+", " ", frage.lower()).strip()
            if not schluessel:
                continue
            gruppe = gruppen.setdefault(schluessel, {"frage": frage.strip(), "agenten": []})
            if agent["nr"] not in gruppe["agenten"]:
                gruppe["agenten"].append(agent["nr"])
    # stabile Sortierung: bei gleicher Anzahl bleibt die Reihenfolge des ersten Auftretens
    return sorted(gruppen.values(), key=lambda g: -len(g["agenten"]))
