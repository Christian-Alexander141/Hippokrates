"""Automatische Erkennung: Anwendungen finden Netze, ohne dass ihr Code geändert werden muss.

Drei Wege, ein Netz bekannt zu machen:

1. **Ordner** – eine `.py`-Datei in einem Netze-Ordner, die auf Modulebene Werkzeuge (`als_werkzeug`)
   oder Chat-Modelle (`NetzChatModell`) definiert. Geänderte Dateien werden beim nächsten
   `entdecken()` neu geladen.
2. **Paket** – ein installiertes Paket mit Entry Point in der Gruppe `netzwerkzeug.netze`:
       [project.entry-points."netzwerkzeug.netze"]
       anaemie = "mein_paket.netze:anaemie_werkzeug"
   Der Entry Point darf auf ein Werkzeug, ein Chat-Modell, eine Liste davon oder eine Funktion zeigen,
   die eines davon zurückgibt.
3. **Code** – `registrieren(werkzeug)` zur Laufzeit.
"""
from __future__ import annotations

import importlib.util
import sys
import threading
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

ENTRY_POINT_GRUPPE = "netzwerkzeug.netze"

_registriert: dict[str, BaseTool | BaseChatModel] = {}
_module: dict[Path, tuple[float, list[Any]]] = {}  # Datei -> (mtime, gefundene Objekte)
_sperre = threading.Lock()


@dataclass
class Fund:
    name: str
    objekt: BaseTool | BaseChatModel
    quelle: str  # Datei, Entry Point oder "registriert"

    @property
    def ist_chatmodell(self) -> bool:
        return isinstance(self.objekt, BaseChatModel)


@dataclass
class Entdeckung:
    werkzeuge: list[Fund] = field(default_factory=list)
    chatmodelle: list[Fund] = field(default_factory=list)
    fehler: list[str] = field(default_factory=list)

    def werkzeug(self, name: str) -> BaseTool | None:
        return next((f.objekt for f in self.werkzeuge if f.name == name), None)

    def chatmodell(self, name: str) -> BaseChatModel | None:
        return next((f.objekt for f in self.chatmodelle if f.name == name), None)


def _name(objekt: Any) -> str:
    if isinstance(objekt, BaseTool):
        return objekt.name
    return getattr(objekt, "modellname", None) or getattr(objekt, "model_name", None) or type(objekt).__name__


def registrieren(*objekte: BaseTool | BaseChatModel) -> None:
    for o in objekte:
        if not isinstance(o, (BaseTool, BaseChatModel)):
            raise TypeError(f"Nur Werkzeuge und Chat-Modelle lassen sich registrieren, nicht {type(o).__name__}.")
        _registriert[_name(o)] = o


def _sammeln(wert: Any) -> list[Any]:
    if isinstance(wert, (BaseTool, BaseChatModel)):
        return [wert]
    if isinstance(wert, (list, tuple)):
        return [o for w in wert for o in _sammeln(w)]
    if callable(wert) and not isinstance(wert, type):
        return _sammeln(wert())
    return []


def _datei_laden(pfad: Path) -> list[Any]:
    mtime = pfad.stat().st_mtime
    bekannt = _module.get(pfad)
    if bekannt and bekannt[0] == mtime:
        return bekannt[1]
    modulname = f"_netzwerkzeug_ordner.{pfad.parent.name}.{pfad.stem}"
    spec = importlib.util.spec_from_file_location(modulname, pfad)
    if spec is None or spec.loader is None:
        raise ImportError("kein Python-Modul")
    modul = importlib.util.module_from_spec(spec)
    sys.modules[modulname] = modul
    try:
        spec.loader.exec_module(modul)
    except BaseException:
        sys.modules.pop(modulname, None)
        raise
    objekte = [w for k, w in vars(modul).items()
               if not k.startswith("_") and isinstance(w, (BaseTool, BaseChatModel))]
    _module[pfad] = (mtime, objekte)
    return objekte


def entdecken(ordner: str | Path | None = None, *, pakete: bool = True) -> Entdeckung:
    """Alle Netze aus Ordner, installierten Paketen und `registrieren()` – bei jedem Aufruf neu ermittelt.

    Fehlerhafte Dateien oder Entry Points brechen die Suche nicht ab, sondern landen in `fehler`.
    """
    ergebnis = Entdeckung()
    funde: list[Fund] = []
    with _sperre:
        if ordner is not None and Path(ordner).is_dir():
            for pfad in sorted(Path(ordner).glob("*.py")):
                if pfad.name.startswith("_"):
                    continue
                try:
                    funde += [Fund(_name(o), o, pfad.name) for o in _datei_laden(pfad.resolve())]
                except Exception as e:  # noqa: BLE001 – fremder Code darf die Suche nicht abbrechen
                    _module.pop(pfad.resolve(), None)
                    ergebnis.fehler.append(f"{pfad.name}: {type(e).__name__}: {e}")
        if pakete:
            for ep in entry_points(group=ENTRY_POINT_GRUPPE):
                try:
                    funde += [Fund(_name(o), o, f"Paket {ep.value}") for o in _sammeln(ep.load())]
                except Exception as e:  # noqa: BLE001
                    ergebnis.fehler.append(f"Entry Point {ep.name}: {type(e).__name__}: {e}")
        funde += [Fund(n, o, "registriert") for n, o in _registriert.items()]

    gesehen: set[tuple[bool, str]] = set()
    for f in funde:
        schluessel = (f.ist_chatmodell, f.name)
        if schluessel in gesehen:
            ergebnis.fehler.append(f"„{f.name}“ ist mehrfach vorhanden – verwendet wird das erste ({f.quelle} ignoriert).")
            continue
        gesehen.add(schluessel)
        (ergebnis.chatmodelle if f.ist_chatmodell else ergebnis.werkzeuge).append(f)
    return ergebnis
