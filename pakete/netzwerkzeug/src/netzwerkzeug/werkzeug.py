"""Muster 1: ein Netz als LangChain-Werkzeug – das Sprachmodell entscheidet, wann es das Netz aufruft.

    werkzeug = als_werkzeug(netz, name="…", beschreibung="…", eingabe=Eingabemodell, klassen=[…])
    agent = create_agent("ollama:qwen3.5:9b", tools=[werkzeug])

Das Eingabemodell (Pydantic) ist zugleich die Tool-Signatur für das Sprachmodell und die Validierung
der Argumente. Das Werkzeug liefert Text für das Sprachmodell und das strukturierte Ergebnis als
Artefakt (`ToolMessage.artifact`) für Programme.
"""
from __future__ import annotations

import inspect
import re
from typing import Any, Callable, Sequence, get_type_hints

import numpy as np
from langchain_core.tools import BaseTool, StructuredTool, ToolException
from pydantic import BaseModel, ValidationError

from .adapter import TraegerNetz, zu_numpy
from .ergebnis import NetzErgebnis, Vorhersage, standard_nachverarbeitung

Vorverarbeitung = Callable[[BaseModel], Any]
Nachverarbeitung = Callable[[np.ndarray, BaseModel], "NetzErgebnis | dict | str | Sequence[float]"]

_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def merkmalsvektor(daten: BaseModel) -> np.ndarray:
    """Standard-Vorverarbeitung: Felder des Eingabemodells in Deklarationsreihenfolge -> Zeilenvektor (1, n).

    Zahlen werden übernommen, Wahrheitswerte zu 1/0, Zahlenlisten aneinandergehängt. Für Texte,
    Kategorien oder Bilder eine eigene `vorverarbeitung` angeben.
    """
    werte: list[float] = []
    for feld in type(daten).model_fields:
        wert = getattr(daten, feld)
        if isinstance(wert, bool):
            werte.append(1.0 if wert else 0.0)
        elif isinstance(wert, (int, float)):
            werte.append(float(wert))
        elif isinstance(wert, (list, tuple)) and all(isinstance(w, (int, float)) for w in wert):
            werte.extend(float(w) for w in wert)
        else:
            raise TypeError(
                f"Feld „{feld}“ ({type(wert).__name__}) lässt sich nicht automatisch in eine Zahl umwandeln – "
                "bitte eine eigene `vorverarbeitung` angeben."
            )
    return np.asarray([werte], dtype=np.float32)


def _ergebnis(roh: Any, daten: BaseModel, name: str, klassen, ausgaben, einheiten, top_k, softmax, hinweis,
              version, nachverarbeitung: Nachverarbeitung | None) -> NetzErgebnis:
    if not isinstance(roh, (NetzErgebnis, str, dict)):
        roh = zu_numpy(roh)  # Tensoren, Listen, Hugging-Face-Ausgaben
    if nachverarbeitung is not None:
        roh = nachverarbeitung(roh, daten)
    if isinstance(roh, NetzErgebnis):
        roh.netz = roh.netz or name
        roh.hinweis = roh.hinweis or hinweis
        roh.version = roh.version or version
        return roh
    if isinstance(roh, str):
        return NetzErgebnis(name, "frei", text=roh, hinweis=hinweis, version=version)
    if isinstance(roh, dict):  # {"Klasse": Wahrscheinlichkeit} bzw. {"Größe": Wert}
        art = "klassifikation" if klassen else "regression"
        paare = sorted(roh.items(), key=lambda kv: -float(kv[1])) if art == "klassifikation" else list(roh.items())
        if art == "klassifikation":
            paare = paare[:max(1, top_k)]
        return NetzErgebnis(name, art, [Vorhersage(str(k), float(v)) for k, v in paare], hinweis=hinweis, version=version)
    return standard_nachverarbeitung(np.asarray(roh, dtype=np.float64), netz=name, klassen=klassen, ausgaben=ausgaben,
                                     einheiten=einheiten, top_k=top_k, softmax=softmax, hinweis=hinweis, version=version)


def _validierungsfehler(fehler: ValidationError) -> str:
    teile = [f"{'.'.join(map(str, e['loc'])) or 'Eingabe'}: {e['msg']}" for e in fehler.errors()]
    return "Ungültige Eingabe für das Netz – " + "; ".join(teile) + ". Bitte korrigiert erneut aufrufen."


def als_werkzeug(
    netz: Any = None,
    *,
    name: str,
    beschreibung: str,
    eingabe: type[BaseModel],
    klassen: Sequence[str] | None = None,
    ausgaben: Sequence[str] | None = None,
    einheiten: Sequence[str] | None = None,
    laden: Callable[[], Any] | None = None,
    vorverarbeitung: Vorverarbeitung | None = None,
    nachverarbeitung: Nachverarbeitung | None = None,
    top_k: int = 3,
    softmax: bool | None = None,
    hinweis: str = "",
    version: str = "",
    geraet: str | None = None,
    threadsicher: bool = False,
    metadaten: dict[str, Any] | None = None,
) -> BaseTool:
    """Ein Netz als LangChain-Werkzeug (`StructuredTool`) verpacken.

    Args:
        netz: PyTorch-, ONNX-, scikit-learn- oder Keras-Modell oder eine Funktion. Alternativ `laden`.
        name: Werkzeugname für das Sprachmodell (a–z, 0–9, _ und -).
        beschreibung: Wann und wofür das Sprachmodell das Netz aufrufen soll. Sie entscheidet maßgeblich,
            ob das Modell das Werkzeug richtig einsetzt.
        eingabe: Pydantic-Modell der Eingaben; `Field(description=…)` erklärt dem Sprachmodell jedes Feld.
        klassen: Klassennamen bei Klassifikation – die Ausgabe wird dann zu Wahrscheinlichkeiten.
        ausgaben, einheiten: Namen und Einheiten der Ausgabewerte bei Regression.
        laden: Funktion, die das Netz erst beim ersten Aufruf lädt (große Gewichte, GPU).
        vorverarbeitung: Eingabemodell -> Netzeingabe. Standard: `merkmalsvektor`.
        nachverarbeitung: (Netzausgabe als NumPy-Array, Eingabe) -> `NetzErgebnis`, dict, str oder Werte.
            Standard: Klassen -> Wahrscheinlichkeiten, sonst benannte Ausgabewerte.
        top_k: Anzahl der genannten Klassen.
        softmax: Ausgabe als Logits behandeln (True), als Wahrscheinlichkeiten (False) oder selbst erkennen (None).
        hinweis: Wird jedem Ergebnis angehängt, z. B. „nicht klinisch validiert“.
        version: Version des Netzes – erscheint im Ergebnis, damit Ergebnisse nachvollziehbar bleiben.
        geraet: z. B. "cuda" oder "cpu" (nur PyTorch).
        threadsicher: True, wenn das Netz gleichzeitig von mehreren Threads ausgewertet werden darf.
        metadaten: zusätzliche Angaben, die Anwendungen anzeigen können.
    """
    if not _NAME.match(name):
        raise ValueError(f"Ungültiger Werkzeugname „{name}“ – erlaubt sind a–z, A–Z, 0–9, _ und - (max. 64 Zeichen).")
    if not (isinstance(eingabe, type) and issubclass(eingabe, BaseModel)):
        raise TypeError("`eingabe` muss eine Pydantic-Klasse (BaseModel) sein.")
    traeger = TraegerNetz(netz, laden, geraet=geraet, wahrscheinlichkeiten=bool(klassen), threadsicher=threadsicher)
    vor = vorverarbeitung or merkmalsvektor

    def auswerten(**argumente: Any) -> tuple[str, dict[str, Any]]:
        try:
            daten = eingabe(**argumente)
        except ValidationError as e:
            raise ToolException(_validierungsfehler(e)) from None
        ergebnis = _ergebnis(traeger(vor(daten)), daten, name, klassen, ausgaben, einheiten, top_k, softmax,
                             hinweis, version, nachverarbeitung)
        artefakt = ergebnis.als_dict() | {"eingabe": daten.model_dump(mode="json")}
        return ergebnis.als_text(), artefakt

    return StructuredTool.from_function(
        func=auswerten,
        name=name,
        description=beschreibung.strip(),
        args_schema=eingabe,
        response_format="content_and_artifact",
        handle_tool_error=lambda e: f"Fehler im Netz „{name}“: {e}",
        handle_validation_error=lambda e: _validierungsfehler(e) if isinstance(e, ValidationError) else str(e),
        metadata={
            "netzwerkzeug": True,
            "art": "klassifikation" if klassen else ("regression" if ausgaben else "frei"),
            "klassen": list(klassen or []),
            "ausgaben": list(ausgaben or []),
            "einheiten": list(einheiten or []),
            "hinweis": hinweis,
            "version": version,
            **(metadaten or {}),
        },
    )


def netz_werkzeug(
    funktion: Callable | None = None,
    *,
    name: str | None = None,
    beschreibung: str | None = None,
    **optionen: Any,
) -> Any:
    """Dekorator-Variante: eine Auswertungsfunktion `f(daten: Eingabemodell) -> Ausgabe` wird zum Werkzeug.

        @netz_werkzeug(klassen=["…", "…"])
        def anaemie(daten: Blutbild) -> torch.Tensor:
            \"\"\"Beschreibung für das Sprachmodell.\"\"\"
            return netz(torch.tensor([[daten.hb, daten.mcv]]))

    Name und Beschreibung stammen, wenn nicht angegeben, aus Funktionsname und Docstring; das
    Eingabemodell aus der Typangabe des ersten Parameters.
    """

    def dekorieren(f: Callable) -> BaseTool:
        parameter = list(inspect.signature(f).parameters)
        if not parameter:
            raise TypeError(f"{f.__name__} braucht einen Parameter mit Pydantic-Typangabe.")
        eingabe = get_type_hints(f).get(parameter[0])
        if not (isinstance(eingabe, type) and issubclass(eingabe, BaseModel)):
            raise TypeError(f"Der erste Parameter von {f.__name__} braucht eine Pydantic-Typangabe.")
        doc = inspect.getdoc(f) or ""
        if not (beschreibung or doc):
            raise ValueError(f"{f.__name__}: bitte `beschreibung` angeben oder einen Docstring schreiben.")
        return als_werkzeug(f, name=name or f.__name__, beschreibung=beschreibung or doc, eingabe=eingabe,
                            vorverarbeitung=optionen.pop("vorverarbeitung", lambda d: d), **optionen)

    return dekorieren(funktion) if funktion is not None else dekorieren


def ist_netzwerkzeug(objekt: Any) -> bool:
    return isinstance(objekt, BaseTool) and bool((objekt.metadata or {}).get("netzwerkzeug"))


def ausfuehren(werkzeug: BaseTool, argumente: dict[str, Any], aufruf_id: str = "netzwerkzeug") -> tuple[str, dict | None]:
    """Werkzeug direkt (ohne Agent) aufrufen -> (Text, Artefakt). Für eigene Abläufe und Middleware."""
    nachricht = werkzeug.invoke({"type": "tool_call", "name": werkzeug.name, "args": argumente, "id": aufruf_id})
    return str(nachricht.content), getattr(nachricht, "artifact", None)
