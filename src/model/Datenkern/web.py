"""Internetrecherche in PubMed-Abstracts über die frei zugängliche Europe-PMC-Schnittstelle.

Übertragen werden nur die Suchbegriffe, die ein Agent formuliert hat – keine Namen oder Patientendaten.
Die Funktion ist im Adminbereich standardmäßig ausgeschaltet.
"""
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request

API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


class WebFehler(RuntimeError):
    pass


def _text(s: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def suche(anfrage: str, anzahl: int = 2) -> list[dict]:
    parameter = urllib.parse.urlencode({
        "query": f"({anfrage}) AND SRC:MED AND HAS_ABSTRACT:y",
        "format": "json",
        "resultType": "core",
        "pageSize": anzahl,
    })
    req = urllib.request.Request(f"{API}?{parameter}",
                                 headers={"User-Agent": "Hippokrates/1.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as antwort:
            daten = json.load(antwort)
    except urllib.error.HTTPError as e:
        raise WebFehler(f"Europe PMC meldet Fehler {e.code}") from None
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise WebFehler(f"Europe PMC nicht erreichbar ({getattr(e, 'reason', e)})") from None

    treffer = []
    for eintrag in (daten.get("resultList") or {}).get("result") or []:
        pmid = eintrag.get("pmid") or eintrag.get("id")
        text = _text(eintrag.get("abstractText"))
        if not pmid or not text:
            continue
        journal = ((eintrag.get("journalInfo") or {}).get("journal") or {}).get("title") or eintrag.get("journalTitle")
        treffer.append({
            "id": f"PMID:{pmid}",
            "titel": _text(eintrag.get("title")).rstrip("."),
            "fundstelle": " ".join(x for x in (journal or "", str(eintrag.get("pubYear") or "")) if x),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "text": text[:1500],
        })
    return treffer
