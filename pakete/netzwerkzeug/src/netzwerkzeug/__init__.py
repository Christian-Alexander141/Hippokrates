"""netzwerkzeug – selbst geschriebene neuronale Netze in LangChain-Agenten (`create_agent`).

Drei Muster, ein Import:

    from netzwerkzeug import als_werkzeug, NetzMiddleware, NetzChatModell

1. `als_werkzeug(...)`   – Netz als Werkzeug; das Sprachmodell ruft es bei Bedarf auf.
2. `NetzMiddleware(...)` – Netz läuft vor jedem Agentenaufruf; Ergebnis steht im Systemprompt.
3. `NetzChatModell(...)` – eigenes generatives Netz als Chat-Modell des Agenten.

Dazu `entdecken(ordner)`, damit Anwendungen neue Netze ohne Codeänderung finden.
"""
from .adapter import TraegerNetz, ausfuehrer, zu_numpy
from .chatmodell import NetzChatModell, json_lesen
from .ergebnis import NetzErgebnis, Vorhersage
from .register import Entdeckung, Fund, entdecken, registrieren
from .werkzeug import als_werkzeug, ausfuehren, ist_netzwerkzeug, merkmalsvektor, netz_werkzeug

__version__ = "0.1.0"

__all__ = [
    "als_werkzeug", "netz_werkzeug", "ausfuehren", "ist_netzwerkzeug", "merkmalsvektor",
    "NetzMiddleware", "NetzZustand", "NetzChatModell", "json_lesen",
    "NetzErgebnis", "Vorhersage", "TraegerNetz", "ausfuehrer", "zu_numpy",
    "entdecken", "registrieren", "Entdeckung", "Fund",
]


def __getattr__(name: str):
    # Die Middleware braucht das Paket `langchain` (create_agent); der Rest kommt mit langchain-core aus.
    if name in ("NetzMiddleware", "NetzZustand"):
        from . import middleware
        return getattr(middleware, name)
    raise AttributeError(f"module 'netzwerkzeug' has no attribute {name!r}")
