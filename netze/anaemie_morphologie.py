"""Beispielnetz für Hippokrates: morphologische Einordnung einer Anämie aus Hb, MCV und Geschlecht.

Ein kleines, selbst geschriebenes mehrschichtiges Perzeptron (NumPy, ohne PyTorch). Es wird beim
ersten Aufruf in unter einer Sekunde auf synthetischen Daten trainiert, die aus Lehrbuchgrenzen
erzeugt sind (WHO: Anämie bei Hb < 12 g/dl bei Frauen bzw. < 13 g/dl bei Männern; MCV < 80 fl
mikrozytär, 80–100 fl normozytär, > 100 fl makrozytär).

Es dient als Vorlage für eigene Netze – NICHT zur klinischen Anwendung. Jede `.py`-Datei in diesem
Ordner, die auf Modulebene ein Werkzeug definiert, erscheint automatisch in Hippokrates unter
„Modelle & Technik → Eigene neuronale Netze“.
"""
import numpy as np
from pydantic import BaseModel, Field
from netzwerkzeug import als_werkzeug

KLASSEN = ["keine Anämie", "mikrozytäre Anämie", "normozytäre Anämie", "makrozytäre Anämie"]


class Blutbild(BaseModel):
    hb: float = Field(ge=2, le=25, description="Hämoglobin in g/dl (bei Angabe in g/l durch 10 teilen)")
    mcv: float = Field(ge=40, le=160, description="Mittleres Erythrozyteneinzelvolumen (MCV) in fl")
    weiblich: bool = Field(description="true bei weiblichem, false bei männlichem Geschlecht")


class MLP:
    """Zwei Schichten: 3 Eingaben -> 16 tanh -> 4 Klassen (Logits)."""

    def __init__(self, rng: np.random.Generator):
        self.w1 = rng.normal(0, 0.5, (3, 16))
        self.b1 = np.zeros(16)
        self.w2 = rng.normal(0, 0.5, (16, 4))
        self.b2 = np.zeros(4)

    @staticmethod
    def normieren(x: np.ndarray) -> np.ndarray:
        return (x - np.array([12.5, 90.0, 0.5])) / np.array([2.5, 12.0, 0.5])

    def vorwaerts(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        h = np.tanh(self.normieren(x) @ self.w1 + self.b1)
        return h, h @ self.w2 + self.b2

    def __call__(self, x: np.ndarray) -> np.ndarray:
        return self.vorwaerts(np.asarray(x, dtype=np.float64))[1]


def _beschriften(x: np.ndarray) -> np.ndarray:
    hb, mcv, weiblich = x[:, 0], x[:, 1], x[:, 2]
    anaemie = hb < np.where(weiblich > 0.5, 12.0, 13.0)
    form = np.select([mcv < 80, mcv > 100], [1, 3], 2)
    return np.where(anaemie, form, 0)


def trainieren(schritte: int = 600, seed: int = 7) -> MLP:
    rng = np.random.default_rng(seed)
    x = np.column_stack([rng.uniform(5, 18, 2500), rng.uniform(55, 125, 2500), rng.integers(0, 2, 2500)])
    y = np.eye(4)[_beschriften(x)]
    netz, lr = MLP(rng), 0.08
    momente = {k: (np.zeros_like(v), np.zeros_like(v)) for k, v in vars(netz).items()}
    for t in range(1, schritte + 1):  # Adam, volle Charge
        h, logits = netz.vorwaerts(x)
        p = np.exp(logits - logits.max(1, keepdims=True))
        p /= p.sum(1, keepdims=True)
        d2 = (p - y) / len(x)
        dh = (d2 @ netz.w2.T) * (1 - h ** 2)
        xn = MLP.normieren(x)
        gradienten = {"w2": h.T @ d2, "b2": d2.sum(0), "w1": xn.T @ dh, "b1": dh.sum(0)}
        for k, g in gradienten.items():
            m, v = momente[k]
            m[:] = 0.9 * m + 0.1 * g
            v[:] = 0.999 * v + 0.001 * g ** 2
            setattr(netz, k, getattr(netz, k) - lr * (m / (1 - 0.9 ** t)) / (np.sqrt(v / (1 - 0.999 ** t)) + 1e-8))
    return netz


anaemie_morphologie = als_werkzeug(
    laden=trainieren,
    name="anaemie_morphologie",
    beschreibung=(
        "Ordnet ein Blutbild morphologisch ein: keine, mikrozytäre, normozytäre oder makrozytäre Anämie. "
        "Nur aufrufen, wenn Hämoglobin (Hb) und MCV als Zahlenwerte in den Patientendaten stehen."
    ),
    eingabe=Blutbild,
    klassen=KLASSEN,
    top_k=2,
    version="0.1-demo",
    hinweis="Demonstrationsnetz auf synthetischen Daten – nicht klinisch validiert.",
)
