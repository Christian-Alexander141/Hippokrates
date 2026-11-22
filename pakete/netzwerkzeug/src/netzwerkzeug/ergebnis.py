"""Einheitliches Ergebnis eines Netzes – als Text für das Sprachmodell und als Daten für Programme."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Sequence

import numpy as np

Art = Literal["klassifikation", "regression", "frei"]


@dataclass
class Vorhersage:
    bezeichnung: str
    wert: float
    einheit: str = ""


@dataclass
class NetzErgebnis:
    netz: str
    art: Art
    vorhersagen: list[Vorhersage] = field(default_factory=list)
    text: str = ""  # nur bei art="frei"
    hinweis: str = ""
    version: str = ""

    def als_text(self) -> str:
        """Kompakte, eindeutige Darstellung für das Sprachmodell."""
        kopf = f"Ergebnis des neuronalen Netzes „{self.netz}“" + (f" (Version {self.version})" if self.version else "")
        if self.art == "klassifikation":
            zeilen = [f"- {v.bezeichnung}: {_prozent(v.wert)}" for v in self.vorhersagen]
            kopf += " – Wahrscheinlichkeiten der Klassen:"
        elif self.art == "regression":
            zeilen = [f"- {v.bezeichnung}: {_zahl(v.wert)}{' ' + v.einheit if v.einheit else ''}" for v in self.vorhersagen]
            kopf += ":"
        else:
            zeilen = [self.text]
            kopf += ":"
        if self.hinweis:
            zeilen.append(f"Hinweis: {self.hinweis}")
        return "\n".join([kopf, *zeilen])

    def als_dict(self) -> dict[str, Any]:
        return asdict(self)


def _prozent(x: float) -> str:
    return f"{x * 100:.1f} %".replace(".", ",")


def _zahl(x: float) -> str:
    return f"{x:.4g}"


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - np.max(x))
    return e / e.sum()


def wahrscheinlichkeiten(werte: np.ndarray, anzahl_klassen: int, softmax: bool | None = None) -> np.ndarray:
    """Logits oder Wahrscheinlichkeiten -> Wahrscheinlichkeitsvektor der Länge `anzahl_klassen`.

    `softmax=None` erkennt selbst: Werte in [0, 1] mit Summe 1 bleiben, ein einzelner Wert in [0, 1]
    bei zwei Klassen gilt als Sigmoid-Ausgabe der zweiten Klasse, alles andere wird per Softmax normiert.
    """
    w = np.asarray(werte, dtype=np.float64).reshape(-1)
    if anzahl_klassen == 2 and w.size == 1:
        logit = softmax if softmax is not None else not 0.0 <= w[0] <= 1.0
        p = float(1 / (1 + np.exp(-w[0]))) if logit else float(w[0])
        return np.array([1 - p, p])
    if w.size != anzahl_klassen:
        raise ValueError(f"Das Netz liefert {w.size} Werte, angegeben sind aber {anzahl_klassen} Klassen.")
    if softmax is None:
        softmax = not (np.all(w >= 0) and np.all(w <= 1) and abs(w.sum() - 1) < 1e-3)
    return _softmax(w) if softmax else w


def standard_nachverarbeitung(ausgabe: np.ndarray, *, netz: str, klassen: Sequence[str] | None,
                              ausgaben: Sequence[str] | None, einheiten: Sequence[str] | None,
                              top_k: int, softmax: bool | None, hinweis: str, version: str) -> NetzErgebnis:
    y = np.asarray(ausgabe, dtype=np.float64)
    if y.ndim > 1 and y.shape[0] == 1:  # Batch-Dimension einer Einzelanfrage entfernen
        y = y[0]
    if klassen:
        p = wahrscheinlichkeiten(y, len(klassen), softmax)
        reihenfolge = sorted(range(len(klassen)), key=lambda i: (-p[i], i))[:max(1, top_k)]
        return NetzErgebnis(netz, "klassifikation", [Vorhersage(klassen[i], round(float(p[i]), 6)) for i in reihenfolge],
                            hinweis=hinweis, version=version)
    y = y.reshape(-1)
    namen = list(ausgaben or [f"Ausgabe {i + 1}" for i in range(y.size)])
    if len(namen) != y.size:
        raise ValueError(f"Das Netz liefert {y.size} Werte, angegeben sind aber {len(namen)} Ausgaben.")
    einh = list(einheiten or [""] * y.size)
    return NetzErgebnis(netz, "regression", [Vorhersage(n, float(v), e) for n, v, e in zip(namen, y, einh)],
                        hinweis=hinweis, version=version)
