# netzwerkzeug

Selbst geschriebene neuronale Netze in **LangChain-Agenten** (`create_agent`) – als Werkzeug, als Middleware oder als Chat-Modell. Ein Import, keine Anpassung am Agenten.

```python
from langchain.agents import create_agent
from pydantic import BaseModel, Field
from netzwerkzeug import als_werkzeug


class Blutbild(BaseModel):
    hb: float = Field(description="Hämoglobin in g/dl")
    mcv: float = Field(description="MCV in fl")
    weiblich: bool = Field(description="true bei weiblichem Geschlecht")


werkzeug = als_werkzeug(mein_torch_netz, name="anaemie_morphologie", eingabe=Blutbild,
                        beschreibung="Ordnet eine Anämie ein. Nur aufrufen, wenn Hb und MCV vorliegen.",
                        klassen=["keine Anämie", "mikrozytär", "normozytär", "makrozytär"])

agent = create_agent("ollama:qwen3.5:9b", tools=[werkzeug])
```

| | |
|---|---|
| **Muster** | `als_werkzeug` / `@netz_werkzeug` (Netz als Tool) · `NetzMiddleware` (Netz läuft immer vor dem Agenten) · `NetzChatModell` (eigenes generatives Netz als Modell, Tool Calling per JSON-Protokoll) |
| **Frameworks** | PyTorch, ONNX Runtime, scikit-learn, Keras/TensorFlow, beliebige Funktionen – automatisch erkannt |
| **Ergebnis** | Text für das Sprachmodell + strukturiertes Artefakt (`ToolMessage.artifact`) |
| **Erkennung** | `entdecken(ordner)`: `.py`-Dateien in einem Ordner, Entry Points `netzwerkzeug.netze`, `registrieren()` |
| **Abhängigkeiten** | `langchain-core`, `pydantic`, `numpy`; `langchain` für `create_agent`/Middleware |

```bash
pip install -e pakete/netzwerkzeug            # Kern
pip install -e "pakete/netzwerkzeug[agent]"   # mit langchain (create_agent, NetzMiddleware)
python -m unittest discover pakete/netzwerkzeug/tests
```

Ausführliche Dokumentation mit Konzept, allen drei Mustern, Framework-Beispielen und Hinweisen für medizinische Netze: [`docs/eigene-netze.md`](../../docs/eigene-netze.md). Ein lauffähiges Beispiel mit lokalem Ollama-Modell: [`beispiele/agent_mit_netz.py`](beispiele/agent_mit_netz.py).

Lizenz: GPL-3.0-or-later
