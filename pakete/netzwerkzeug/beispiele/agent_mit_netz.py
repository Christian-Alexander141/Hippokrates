"""Ein LangChain-Agent mit lokalem Ollama-Modell und einem eigenen neuronalen Netz als Werkzeug.

Aufruf (aus dem Projektordner):
    .venv/bin/python pakete/netzwerkzeug/beispiele/agent_mit_netz.py [modell]

Voraussetzung: Hippokrates installiert (`pip install -e pakete/netzwerkzeug -e .`) und ein Ollama-Modell
mit Werkzeug-Unterstützung (z. B. qwen3.5:9b, mistral:7b, granite4.1:3b).
"""
import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.messages import ToolMessage
from langchain_ollama import ChatOllama

from netzwerkzeug import entdecken

# Alle Netze aus dem Ordner netze/ – hier das Beispielnetz anaemie_morphologie
netze = entdecken(Path(__file__).resolve().parents[3] / "netze")
werkzeuge = [f.objekt for f in netze.werkzeuge]

modell = ChatOllama(model=sys.argv[1] if len(sys.argv) > 1 else "qwen3.5:9b", temperature=0, reasoning=False)
agent = create_agent(
    modell,
    tools=werkzeuge,
    system_prompt=(
        "Du unterstützt ärztliches Fachpersonal. Nutze die Werkzeuge, wenn die Angaben dafür ausreichen, "
        "und nenne im Ergebnis, was das Netz geliefert hat. Antworte kurz auf Deutsch."
    ),
)

frage = ("Patientin, 34 Jahre, seit Wochen müde. Labor: Hb 10,4 g/dl, MCV 74 fl, Ferritin 6 µg/l. "
         "Wie ist die Anämie einzuordnen?")
ergebnis = agent.invoke({"messages": [{"role": "user", "content": frage}]})

for nachricht in ergebnis["messages"]:
    if isinstance(nachricht, ToolMessage):
        print(f"── Werkzeug {nachricht.name} ──\n{nachricht.content}\n")
print("── Antwort des Agenten ──\n" + ergebnis["messages"][-1].text)
