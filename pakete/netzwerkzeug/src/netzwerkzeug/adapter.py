"""Adapter: bringen beliebige Netze auf die gemeinsame Form  Eingabe -> Ausgabe (meist NumPy-Array).

Unterstützt werden ohne weitere Angaben:

* PyTorch (`torch.nn.Module`, auch TorchScript) – Auswertung im `eval`-Modus unter `inference_mode`
* ONNX Runtime (`onnxruntime.InferenceSession`)
* scikit-learn und ähnliche (`predict_proba` bzw. `predict`)
* Keras / TensorFlow (`predict`)
* jede aufrufbare Funktion

PyTorch, ONNX Runtime und TensorFlow werden nur importiert, wenn ein solches Netz übergeben wird.
"""
from __future__ import annotations

import threading
from typing import Any, Callable

import numpy as np

Ausfuehrer = Callable[[Any], Any]


def zu_numpy(ausgabe: Any) -> np.ndarray:
    """Netzausgabe in ein NumPy-Array umwandeln.

    Tupel aus Tensoren (z. B. `(logits, hidden)`) -> erstes Element; Objekte mit `.logits`
    (Hugging-Face-Stil) -> `logits`; Tensoren -> `detach().cpu().numpy()`.
    """
    if hasattr(ausgabe, "logits"):
        ausgabe = ausgabe.logits
    if isinstance(ausgabe, tuple) and ausgabe and hasattr(ausgabe[0], "shape"):
        ausgabe = ausgabe[0]
    if hasattr(ausgabe, "detach"):  # torch.Tensor
        ausgabe = ausgabe.detach().cpu().numpy()
    elif hasattr(ausgabe, "numpy") and not isinstance(ausgabe, np.ndarray):  # tf.Tensor
        ausgabe = ausgabe.numpy()
    return np.asarray(ausgabe, dtype=np.float64)


def _ist_torch_modul(netz: Any) -> bool:
    typ = type(netz)
    if not any(k.__module__.startswith("torch") for k in typ.__mro__):
        return False
    import torch
    return isinstance(netz, torch.nn.Module)


def _torch(netz: Any, geraet: str | None) -> Ausfuehrer:
    import torch

    netz.eval()
    if geraet:
        netz.to(geraet)
    parameter = list(netz.parameters())
    ziel = torch.device(geraet) if geraet else (parameter[0].device if parameter else torch.device("cpu"))
    dtyp = next((p.dtype for p in parameter if p.is_floating_point()), torch.float32)

    def ausfuehren(x: Any) -> np.ndarray:
        with torch.inference_mode():
            if isinstance(x, np.ndarray):
                y = netz(torch.as_tensor(x, dtype=dtyp, device=ziel))
            elif isinstance(x, torch.Tensor):
                y = netz(x.to(ziel))
            elif isinstance(x, dict):  # z. B. Tokenizer-Ausgabe
                y = netz(**{k: v.to(ziel) if hasattr(v, "to") else v for k, v in x.items()})
            else:
                y = netz(x)
        return zu_numpy(y)

    return ausfuehren


_ONNX_TYPEN = {"tensor(float)": np.float32, "tensor(double)": np.float64, "tensor(int64)": np.int64,
               "tensor(int32)": np.int32, "tensor(float16)": np.float16, "tensor(bool)": np.bool_}


def _onnx(sitzung: Any) -> Ausfuehrer:
    eingang = sitzung.get_inputs()[0]
    dtyp = _ONNX_TYPEN.get(eingang.type, np.float32)

    def ausfuehren(x: Any) -> np.ndarray:
        feed = x if isinstance(x, dict) else {eingang.name: np.asarray(x, dtype=dtyp)}
        return zu_numpy(sitzung.run(None, feed)[0])

    return ausfuehren


def ausfuehrer(netz: Any, *, geraet: str | None = None, wahrscheinlichkeiten: bool = True) -> Ausfuehrer:
    """Passenden Adapter für `netz` wählen.

    `wahrscheinlichkeiten`: bei scikit-learn-Modellen `predict_proba` statt `predict` verwenden.
    """
    if _ist_torch_modul(netz):
        return _torch(netz, geraet)
    if hasattr(netz, "get_inputs") and hasattr(netz, "run"):  # onnxruntime.InferenceSession
        return _onnx(netz)
    if wahrscheinlichkeiten and hasattr(netz, "predict_proba"):
        return lambda x: zu_numpy(netz.predict_proba(x))
    if hasattr(netz, "predict") and hasattr(netz, "layers"):  # Keras
        return lambda x: zu_numpy(netz.predict(x, verbose=0))
    if hasattr(netz, "predict"):
        return lambda x: zu_numpy(netz.predict(x))
    if callable(netz):
        return netz  # Ausgabe unverändert: Funktionen dürfen auch fertige Ergebnisse (dict, str, NetzErgebnis) liefern
    raise TypeError(
        f"Für Objekte vom Typ {type(netz).__name__} gibt es keinen Adapter. Übergib eine aufrufbare Funktion "
        "oder ein PyTorch-, ONNX-, scikit-learn- oder Keras-Modell."
    )


class TraegerNetz:
    """Lädt ein Netz erst beim ersten Aufruf (`laden`) und serialisiert die Auswertung.

    Das Laden großer Gewichte beim Import würde jede Modellsuche der Anwendung verlangsamen;
    die Sperre schützt Netze, die nicht threadsicher sind (mehrere Agenten rufen parallel auf).
    """

    def __init__(self, netz: Any = None, laden: Callable[[], Any] | None = None, *,
                 geraet: str | None = None, wahrscheinlichkeiten: bool = True, threadsicher: bool = False):
        if netz is None and laden is None:
            raise ValueError("Entweder `netz` oder `laden` angeben.")
        self._netz, self._laden = netz, laden
        self._geraet, self._wahrscheinlichkeiten = geraet, wahrscheinlichkeiten
        self._ausfuehrer: Ausfuehrer | None = None
        self._sperre = threading.Lock()
        self._threadsicher = threadsicher

    @property
    def geladen(self) -> bool:
        return self._ausfuehrer is not None

    def _bereit(self) -> Ausfuehrer:
        if self._ausfuehrer is None:
            netz = self._netz if self._netz is not None else self._laden()
            self._ausfuehrer = ausfuehrer(netz, geraet=self._geraet, wahrscheinlichkeiten=self._wahrscheinlichkeiten)
        return self._ausfuehrer

    def __call__(self, x: Any) -> np.ndarray:
        if self._threadsicher:
            with self._sperre:  # nur das Laden schützen
                f = self._bereit()
            return f(x)
        with self._sperre:
            return self._bereit()(x)
