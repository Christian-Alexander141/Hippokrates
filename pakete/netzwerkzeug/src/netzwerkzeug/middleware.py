"""Muster 2: Netze laufen deterministisch vor dem Agenten – ihr Ergebnis steht im Systemprompt.

Anders als bei einem Werkzeug entscheidet hier nicht das Sprachmodell, ob das Netz befragt wird:
Die Middleware wertet es bei jedem Agentenaufruf aus, sobald die Eingaben vorliegen. Das passt,
wenn ein Netz immer gehört werden soll (Risiko-Score, Bildklassifikation eines Anhangs) oder wenn
das Sprachmodell zu klein für zuverlässige Werkzeugaufrufe ist.

    middleware = NetzMiddleware([werkzeug], eingaben=lambda state, runtime: {"anaemie": runtime.context.labor})
    agent = create_agent(modell, middleware=[middleware], context_schema=Kontext)
"""
from __future__ import annotations

from typing import Any, Callable, NotRequired, Sequence

from langchain.agents.middleware import AgentMiddleware, AgentState, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from .werkzeug import ausfuehren

Eingaben = Callable[[dict[str, Any], Any], "dict[str, dict[str, Any] | BaseModel] | None"]


class NetzZustand(AgentState):
    netz_befunde: NotRequired[list[dict[str, Any]]]
    """Ergebnisse der Netze dieses Aufrufs: {"netz", "text", "artefakt"}."""


class NetzMiddleware(AgentMiddleware[NetzZustand, Any]):
    state_schema = NetzZustand

    def __init__(self, werkzeuge: Sequence[BaseTool], eingaben: Eingaben, *,
                 ueberschrift: str = "Ergebnisse eigener neuronaler Netze (vor dem Gespräch ausgewertet)"):
        """
        Args:
            werkzeuge: mit `als_werkzeug` erstellte Netze.
            eingaben: (state, runtime) -> {werkzeugname: Eingabe}; nicht genannte Netze werden übersprungen.
                Typischerweise aus `runtime.context` (strukturierte Daten) – ohne Umweg über das Sprachmodell.
            ueberschrift: Einleitung des Abschnitts im Systemprompt.
        """
        super().__init__()
        self.werkzeuge = {w.name: w for w in werkzeuge}
        self.eingaben = eingaben
        self.ueberschrift = ueberschrift

    def before_agent(self, state: NetzZustand, runtime: Any) -> dict[str, Any] | None:
        auftraege = self.eingaben(state, runtime) or {}
        befunde = []
        for name, argumente in auftraege.items():
            werkzeug = self.werkzeuge.get(name)
            if werkzeug is None:
                raise KeyError(f"Unbekanntes Netz „{name}“ – bekannt sind: {', '.join(self.werkzeuge)}")
            if isinstance(argumente, BaseModel):
                argumente = argumente.model_dump()
            text, artefakt = ausfuehren(werkzeug, argumente, aufruf_id=f"middleware-{name}")
            befunde.append({"netz": name, "text": text, "artefakt": artefakt})
        return {"netz_befunde": befunde}

    def _mit_befunden(self, request: ModelRequest) -> ModelRequest:
        befunde = request.state.get("netz_befunde") or []
        if not befunde:
            return request
        abschnitt = self.ueberschrift + ":\n\n" + "\n\n".join(b["text"] for b in befunde)
        alt = request.system_message.text if request.system_message else ""
        return request.override(system_message=SystemMessage(content=f"{alt}\n\n{abschnitt}".strip()))

    def wrap_model_call(self, request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> Any:
        return handler(self._mit_befunden(request))

    async def awrap_model_call(self, request: ModelRequest, handler: Callable[[ModelRequest], Any]) -> Any:
        return await handler(self._mit_befunden(request))
