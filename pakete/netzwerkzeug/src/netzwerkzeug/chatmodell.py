"""Muster 3: ein selbst geschriebenes generatives Netz als Chat-Modell des Agenten.

    modell = NetzChatModell(erzeuge=mein_netz.generiere, modellname="mein-lm")
    agent = create_agent(modell, tools=[...])

`erzeuge` bekommt den fertigen Prompt (Text) – oder mit `nachrichtenformat="chat"` die Nachrichten
als Liste von {"role", "content"} – und liefert Text zurück. Werkzeugaufrufe funktionieren auch ohne
eingebaute Tool-Unterstützung des Netzes: Sind Werkzeuge gebunden, beschreibt der Prompt sie und
verlangt eine JSON-Antwort, die hier in `tool_calls` übersetzt wird.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Callable, Literal, Sequence

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field

def json_lesen(text: str) -> Any:
    """Erstes JSON-Objekt im Text (Text davor/danach und Markdown-Zäune werden ignoriert)."""
    start = text.find("{")
    while start >= 0:
        try:
            return json.JSONDecoder().raw_decode(text[start:])[0]
        except ValueError:
            start = text.find("{", start + 1)
    return None


class NetzChatModell(BaseChatModel):
    """Beliebige Textgenerierung als LangChain-Chat-Modell – inklusive Werkzeugaufrufen per JSON-Protokoll."""

    erzeuge: Callable[..., str]
    """Text -> Text (oder Nachrichtenliste -> Text bei `nachrichtenformat="chat"`)."""
    modellname: str = "netzwerkzeug"
    nachrichtenformat: Literal["text", "chat"] = "text"
    erzeuge_optionen: dict[str, Any] = Field(default_factory=dict)
    """Werden bei jedem Aufruf an `erzeuge` übergeben (z. B. max_tokens, temperature)."""
    werkzeuge: list[dict[str, Any]] = Field(default_factory=list)
    werkzeugwahl: Any = None

    @property
    def _llm_type(self) -> str:
        return "netzwerkzeug"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"modellname": self.modellname}

    def bind_tools(self, tools: Sequence[Any], *, tool_choice: Any = None, **kwargs: Any) -> "NetzChatModell":
        return self.model_copy(update={"werkzeuge": [convert_to_openai_tool(t) for t in tools],
                                       "werkzeugwahl": tool_choice})

    # ── Prompt ──────────────────────────────────────────────────────────────
    def _werkzeug_anleitung(self) -> str:
        beschreibungen = []
        for w in self.werkzeuge:
            f = w["function"]
            beschreibungen.append(f"- {f['name']}: {f.get('description', '')}\n  Argumente (JSON-Schema): "
                                  f"{json.dumps(f.get('parameters', {}), ensure_ascii=False)}")
        wahl = self.werkzeugwahl
        pflicht = wahl in ("any", "required") or isinstance(wahl, (dict, str)) and wahl not in (None, "auto", "none")
        regel = ("Du MUSST jetzt ein Werkzeug aufrufen." if pflicht
                 else "Rufe ein Werkzeug auf, wenn es hilft; sonst antworte direkt.")
        return ("Verfügbare Werkzeuge:\n" + "\n".join(beschreibungen) + f"\n\n{regel}\nAntworte ausschließlich mit "
                'JSON: {"werkzeug": "<name>", "argumente": {…}} für einen Werkzeugaufruf oder '
                '{"antwort": "<Text>"} für die endgültige Antwort.')

    def _nachrichten(self, messages: list[BaseMessage]) -> list[dict[str, str]]:
        liste = []
        for m in messages:
            inhalt = m.text if hasattr(m, "text") else str(m.content)
            if isinstance(m, AIMessage) and m.tool_calls:
                inhalt += "\n" + "\n".join(json.dumps({"werkzeug": c["name"], "argumente": c["args"]}, ensure_ascii=False)
                                           for c in m.tool_calls)
            if isinstance(m, ToolMessage):
                inhalt = f"Ergebnis von {m.name or 'Werkzeug'}: {inhalt}"
            rolle = {"system": "system", "human": "user", "ai": "assistant", "tool": "tool"}.get(m.type, "user")
            liste.append({"role": rolle, "content": inhalt.strip()})
        if self.werkzeuge and self.werkzeugwahl != "none":
            anleitung = self._werkzeug_anleitung()
            if liste and liste[0]["role"] == "system":
                liste[0]["content"] += "\n\n" + anleitung
            else:
                liste.insert(0, {"role": "system", "content": anleitung})
        return liste

    @staticmethod
    def als_text(nachrichten: list[dict[str, str]]) -> str:
        namen = {"system": "System", "user": "Nutzer", "assistant": "Assistent", "tool": "Werkzeug"}
        return "\n\n".join(f"{namen[n['role']]}: {n['content']}" for n in nachrichten) + "\n\nAssistent:"

    # ── Generierung ─────────────────────────────────────────────────────────
    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None,
                  run_manager: CallbackManagerForLLMRun | None = None, **kwargs: Any) -> ChatResult:
        nachrichten = self._nachrichten(messages)
        eingabe = nachrichten if self.nachrichtenformat == "chat" else self.als_text(nachrichten)
        optionen = {**self.erzeuge_optionen, **({"stop": stop} if stop else {})}
        text = str(self.erzeuge(eingabe, **optionen))
        return ChatResult(generations=[ChatGeneration(message=self._antwort(text))])

    def _antwort(self, text: str) -> AIMessage:
        if not self.werkzeuge or self.werkzeugwahl == "none":
            return AIMessage(content=text)
        daten = json_lesen(text)
        namen = {w["function"]["name"] for w in self.werkzeuge}
        if isinstance(daten, dict) and daten.get("werkzeug") in namen:
            argumente = daten.get("argumente")
            return AIMessage(content="", tool_calls=[{
                "name": daten["werkzeug"], "args": argumente if isinstance(argumente, dict) else {},
                "id": f"call_{uuid.uuid4().hex[:12]}", "type": "tool_call"}])
        if isinstance(daten, dict) and isinstance(daten.get("antwort"), str):
            return AIMessage(content=daten["antwort"])
        return AIMessage(content=text)

