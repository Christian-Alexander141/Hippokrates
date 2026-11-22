# Eigene neuronale Netze in LangChain-Agenten

Dieses Dokument beschreibt, wie sich **selbst geschriebene neuronale Netze** – ein PyTorch-Klassifikator, ein exportiertes ONNX-Modell, ein scikit-learn-Modell, ein eigenes kleines Sprachmodell – in **LangChain-Agenten** (`create_agent`) verwenden lassen. Die Umsetzung ist die Bibliothek **`netzwerkzeug`** in [`pakete/netzwerkzeug`](../pakete/netzwerkzeug). Sie ist unabhängig von Hippokrates nutzbar: installieren, importieren, fertig.

```python
from netzwerkzeug import als_werkzeug, NetzMiddleware, NetzChatModell, entdecken
```

---

## 1. Das Problem

Ein LangChain-Agent besteht aus einem **Sprachmodell**, das entscheidet, und **Werkzeugen**, die es aufrufen kann. Ein eigenes neuronales Netz passt zunächst in keine der beiden Rollen:

- Es versteht keinen Text, sondern erwartet Tensoren in fester Form, normiert und in fester Reihenfolge.
- Es liefert Logits oder Zahlenvektoren, mit denen ein Sprachmodell nichts anfangen kann.
- Es hat Gewichte, die geladen werden müssen (oft groß, oft auf der GPU), und ist nicht immer threadsicher.
- Jedes Framework (PyTorch, ONNX Runtime, scikit-learn, Keras) wird anders aufgerufen.

`netzwerkzeug` übernimmt diese Übersetzung einmal, allgemein und getestet.

## 2. Drei Muster

| Muster | Wer entscheidet, ob das Netz befragt wird? | Woher kommen die Eingaben? | Geeignet für |
|---|---|---|---|
| **1. Werkzeug** `als_werkzeug()` | das Sprachmodell | das Sprachmodell liest sie aus dem Gespräch | Netze, die nur manchmal passen; Modelle mit gutem Tool Calling |
| **2. Middleware** `NetzMiddleware` | immer, vor dem ersten Modellaufruf | strukturierte Daten aus `runtime.context` oder dem Zustand | Netze, die immer gehört werden sollen; kleine Modelle ohne zuverlässiges Tool Calling; Bilder und Messreihen |
| **3. Chat-Modell** `NetzChatModell` | – das Netz **ist** das Sprachmodell | – | eigene generative Netze (selbst trainierte Sprachmodelle) |

```
                       ┌──────────────────────── create_agent(...) ────────────────────────┐
                       │                                                                    │
  Nutzer ──▶ [Middleware: NetzMiddleware] ──▶ Sprachmodell ──tool_call──▶ [Werkzeug: Netz]  │
             Netz läuft immer, Ergebnis       (Ollama, LM Studio …       Eingabe validieren │
             landet im Systemprompt            oder NetzChatModell)      → Vorverarbeitung  │
                                                     ▲                   → Netz             │
                                                     └──── ToolMessage ◀─ → Nachverarbeitung│
                                                     Text fürs Modell + Artefakt (Daten)    │
                       └────────────────────────────────────────────────────────────────────┘
```

Die Muster lassen sich kombinieren: Ein Agent kann mehrere Netze als Werkzeuge haben, zusätzlich eine Middleware und als Modell ein `NetzChatModell`.

## 3. Installation

```bash
pip install -e pakete/netzwerkzeug            # Kern: langchain-core, pydantic, numpy
pip install -e "pakete/netzwerkzeug[agent]"   # zusätzlich langchain (create_agent, Middleware)
pip install langchain-ollama                  # lokale Sprachmodelle über Ollama
pip install torch                             # nur wenn das Netz PyTorch ist (ebenso onnxruntime …)
```

Für Hippokrates ist das bereits in der `pyproject.toml` des Projekts enthalten (`pip install -e pakete/netzwerkzeug -e .`).

## 4. Schnellstart

```python
from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field
from netzwerkzeug import als_werkzeug


class Blutbild(BaseModel):                    # 1. Eingaben beschreiben
    hb: float = Field(description="Hämoglobin in g/dl")
    mcv: float = Field(description="MCV in fl")
    weiblich: bool = Field(description="true bei weiblichem Geschlecht")


anaemie = als_werkzeug(                       # 2. Netz verpacken
    mein_netz,                                # PyTorch, ONNX, sklearn, Keras oder Funktion
    name="anaemie_morphologie",
    beschreibung="Ordnet eine Anämie morphologisch ein. Nur aufrufen, wenn Hb und MCV vorliegen.",
    eingabe=Blutbild,
    klassen=["keine Anämie", "mikrozytär", "normozytär", "makrozytär"],
)

agent = create_agent(ChatOllama(model="qwen3.5:9b"), tools=[anaemie])   # 3. benutzen
agent.invoke({"messages": [{"role": "user", "content": "Hb 10,4 g/dl, MCV 74 fl, Patientin"}]})
```

Ein lauffähiges Beispiel mit lokalem Ollama-Modell liegt in [`pakete/netzwerkzeug/beispiele/agent_mit_netz.py`](../pakete/netzwerkzeug/beispiele/agent_mit_netz.py). Mit `qwen3.5:9b` ruft der Agent dort das Beispielnetz selbstständig auf und begründet seine Antwort mit dessen Ergebnis.

---

## 5. Muster 1 – das Netz als Werkzeug

### 5.1 Das Eingabemodell ist der Vertrag

Das Pydantic-Modell unter `eingabe=` erfüllt drei Aufgaben auf einmal:

1. **Tool-Signatur:** LangChain erzeugt daraus das JSON-Schema, das das Sprachmodell sieht. Die `description` jedes Feldes ist die Anleitung für das Modell – Einheiten gehören hinein.
2. **Validierung:** Grenzen wie `Field(ge=2, le=25)` fangen Einheitenfehler ab (Hb 98 statt 9,8). Ungültige Aufrufe werden nicht ausgeführt; das Modell bekommt eine verständliche Fehlermeldung und kann korrigiert neu aufrufen.
3. **Merkmalsreihenfolge:** Die Standard-Vorverarbeitung legt die Felder **in Deklarationsreihenfolge** in einen Vektor der Form `(1, n)`. Zahlen bleiben Zahlen, `bool` wird 1/0, Zahlenlisten werden angehängt.

### 5.2 Vor- und Nachverarbeitung

Fast jedes trainierte Netz braucht dieselbe Normierung wie beim Training. Dafür gibt es `vorverarbeitung`:

```python
import numpy as np

MITTEL = np.array([12.8, 89.0, 0.5], dtype=np.float32)   # aus dem Trainingsdatensatz
STREUUNG = np.array([2.1, 9.5, 0.5], dtype=np.float32)

werkzeug = als_werkzeug(
    netz, name="…", beschreibung="…", eingabe=Blutbild, klassen=KLASSEN,
    vorverarbeitung=lambda d: ((np.array([[d.hb, d.mcv, d.weiblich]], dtype=np.float32) - MITTEL) / STREUUNG),
)
```

Die Ausgabe wird standardmäßig so gedeutet:

| Angabe | Netzausgabe | Ergebnis |
|---|---|---|
| `klassen=[…]` (n Klassen) | n Logits **oder** n Wahrscheinlichkeiten | Wahrscheinlichkeiten; Softmax nur, wenn die Werte nicht schon eine Verteilung sind (`softmax=True/False` erzwingt es) |
| `klassen=[a, b]` | 1 Wert | Sigmoid-Ausgabe für Klasse `b` (Logit wird erkannt) |
| `ausgaben=[…]`, `einheiten=[…]` | m Werte | benannte Regressionswerte mit Einheit |
| keine Angabe | m Werte | „Ausgabe 1 … m“ |

Wer mehr braucht, gibt `nachverarbeitung=(ausgabe, eingabe) -> …` an und liefert ein `NetzErgebnis`, ein `dict` (`{"Klasse": Wahrscheinlichkeit}`) oder einfach Text.

### 5.3 Was der Agent zurückbekommt

Das Werkzeug arbeitet mit `response_format="content_and_artifact"`:

- **Für das Sprachmodell** (`ToolMessage.content`) ein kurzer, eindeutiger Text:
  ```
  Ergebnis des neuronalen Netzes „anaemie_morphologie“ (Version 0.1-demo) – Wahrscheinlichkeiten der Klassen:
  - mikrozytäre Anämie: 100,0 %
  - normozytäre Anämie: 0,0 %
  Hinweis: Demonstrationsnetz auf synthetischen Daten – nicht klinisch validiert.
  ```
- **Für Programme** (`ToolMessage.artifact`) dieselben Daten strukturiert: `netz`, `art`, `vorhersagen` (Bezeichnung, Wert, Einheit), `version`, `hinweis` und die validierte `eingabe`. So lassen sich Ergebnisse protokollieren, anzeigen oder prüfen, ohne Text zu parsen.

### 5.4 Frameworks

Der passende Adapter wird am Objekt erkannt; PyTorch, ONNX Runtime und TensorFlow werden nur importiert, wenn ein solches Netz übergeben wird.

| Netz | Aufruf durch `netzwerkzeug` |
|---|---|
| `torch.nn.Module` (auch TorchScript) | `eval()`, `torch.inference_mode()`, Eingabe auf Gerät und Datentyp des Netzes; Tupel-Ausgaben → erstes Element, `.logits` wird erkannt |
| `onnxruntime.InferenceSession` | erster Eingang, Datentyp aus dem Modell |
| scikit-learn u. ä. | `predict_proba` bei Klassifikation, sonst `predict` |
| Keras / TensorFlow | `predict(x, verbose=0)` |
| beliebige Funktion | `f(x)` – darf auch direkt ein `NetzErgebnis`, `dict` oder Text liefern |

**PyTorch, Gewichte erst bei Bedarf laden:**

```python
import torch
from torch import nn


class Risikonetz(nn.Module):
    def __init__(self):
        super().__init__()
        self.schichten = nn.Sequential(nn.Linear(5, 32), nn.ReLU(), nn.Linear(32, 3))

    def forward(self, x):
        return self.schichten(x)


def laden() -> nn.Module:
    netz = Risikonetz()
    netz.load_state_dict(torch.load("gewichte/risiko.pt", map_location="cpu"))
    return netz


risiko = als_werkzeug(
    laden=laden,                    # erst beim ersten Aufruf – Import und Modellsuche bleiben schnell
    geraet="cuda",                  # optional
    name="verschlechterungsrisiko",
    beschreibung="Risiko einer klinischen Verschlechterung in 24 h aus fünf Vitalwerten.",
    eingabe=Vitalwerte,
    klassen=["niedrig", "mittel", "hoch"],
    version="2.1",
    hinweis="Validiert an 4 812 Aufenthalten der Station X (AUC 0,83).",
)
```

**ONNX** (z. B. aus PyTorch oder TensorFlow exportiert, ohne die Frameworks zur Laufzeit):

```python
import onnxruntime as ort
werkzeug = als_werkzeug(laden=lambda: ort.InferenceSession("risiko.onnx"), name="…", beschreibung="…",
                        eingabe=Vitalwerte, klassen=["niedrig", "mittel", "hoch"])
```

**Regression:**

```python
egfr = als_werkzeug(netz, name="egfr_schaetzer", beschreibung="…", eingabe=Labor,
                    ausgaben=["eGFR"], einheiten=["ml/min/1,73 m²"])
```

### 5.5 Dekorator-Variante

Wenn die Auswertung ohnehin eigener Code ist:

```python
from netzwerkzeug import netz_werkzeug

@netz_werkzeug(klassen=["negativ", "positiv"], version="1.0")
def sepsis_screening(daten: Vitalwerte) -> torch.Tensor:
    """Sepsis-Screening aus Vitalwerten. Nur bei Fieber oder Hypothermie aufrufen."""
    return netz(torch.tensor([[daten.herzfrequenz, daten.atemfrequenz, …]]))
```

Name, Beschreibung und Eingabemodell kommen aus Funktionsname, Docstring und Typangabe.

### 5.6 Netze ohne Werkzeugaufruf direkt nutzen

```python
from netzwerkzeug import ausfuehren
text, artefakt = ausfuehren(anaemie, {"hb": 10.4, "mcv": 74, "weiblich": True})
```

So nutzt auch Hippokrates die Netze in seinem festen Agentenablauf (siehe Abschnitt 9).

---

## 6. Muster 2 – Middleware: das Netz läuft immer

Werkzeuge setzen voraus, dass das Sprachmodell sie zuverlässig aufruft und die Eingaben richtig überträgt. Bei kleinen lokalen Modellen ist beides nicht garantiert. Liegen die Eingaben ohnehin strukturiert vor (Laborwerte aus dem LIS, ein Bild, eine Messreihe), ist es sicherer, das Netz **deterministisch vor dem Agenten** auszuwerten:

```python
from dataclasses import dataclass
from langchain.agents import create_agent
from netzwerkzeug import NetzMiddleware


@dataclass
class Kontext:
    labor: Blutbild


middleware = NetzMiddleware(
    [anaemie],
    eingaben=lambda state, runtime: {"anaemie_morphologie": runtime.context.labor},
)
agent = create_agent(modell, middleware=[middleware], context_schema=Kontext,
                     system_prompt="Du unterstützt ärztliches Fachpersonal …")

ergebnis = agent.invoke({"messages": [{"role": "user", "content": "Bitte einordnen."}]},
                        context=Kontext(labor=Blutbild(hb=8.9, mcv=110, weiblich=False)))
ergebnis["netz_befunde"]     # strukturierte Ergebnisse dieses Aufrufs
```

Ablauf: `before_agent` wertet die Netze einmal je Aufruf aus und legt sie im Agentenzustand (`netz_befunde`) ab; `wrap_model_call` hängt die Texte an den Systemprompt jeder Modellanfrage an. Das Sprachmodell sieht die Ergebnisse also wie einen Befund, ohne selbst etwas aufrufen zu müssen. `eingaben` gibt für jedes Netz die Eingabe als Pydantic-Objekt oder `dict` zurück; nicht genannte Netze werden übersprungen.

---

## 7. Muster 3 – ein eigenes generatives Netz als Chat-Modell

Ist das eigene Netz selbst ein Sprachmodell (z. B. ein kleiner, selbst trainierter Transformer), wird es mit `NetzChatModell` zum Modell des Agenten:

```python
from netzwerkzeug import NetzChatModell

def erzeuge(prompt: str, **optionen) -> str:
    ids = tokenizer.encode(prompt)
    return tokenizer.decode(mein_lm.generate(ids, max_new_tokens=400, **optionen))

modell = NetzChatModell(erzeuge=erzeuge, modellname="mein-lm", erzeuge_optionen={"temperature": 0.2})
agent = create_agent(modell, tools=[anaemie])
```

`erzeuge` bekommt den fertigen Prompt als Text (oder mit `nachrichtenformat="chat"` die Nachrichten als Liste). **Werkzeugaufrufe funktionieren auch ohne eingebaute Unterstützung:** Sind Werkzeuge gebunden, beschreibt der Prompt sie samt JSON-Schema und verlangt eine Antwort der Form `{"werkzeug": "…", "argumente": {…}}` oder `{"antwort": "…"}`. `NetzChatModell` übersetzt das in echte `tool_calls`, sodass `create_agent` normal weiterarbeitet. Ob das eigene Netz dieses Format zuverlässig einhält, hängt von seinem Training ab – Feinabstimmung auf das Format hilft.

---

## 8. Automatische Erkennung

Anwendungen sollen neue Netze finden, ohne dass ihr Code geändert werden muss. `entdecken()` sucht bei **jedem Aufruf** neu:

```python
from netzwerkzeug import entdecken

e = entdecken("netze/")       # Ordner + installierte Pakete + registrieren()
e.werkzeuge                   # [Fund(name, objekt, quelle), …]
e.chatmodelle                 # NetzChatModell-Instanzen
e.fehler                      # fehlerhafte Dateien brechen die Suche nicht ab
agent = create_agent(modell, tools=[f.objekt for f in e.werkzeuge])
```

| Weg | So wird ein Netz bekannt |
|---|---|
| **Ordner** | `.py`-Datei, die auf Modulebene ein Werkzeug (`als_werkzeug`) oder `NetzChatModell` definiert. Geänderte Dateien werden neu geladen, Dateien mit `_` am Anfang ignoriert. |
| **Paket** | Entry Point in der Gruppe `netzwerkzeug.netze`: <br>`[project.entry-points."netzwerkzeug.netze"]`<br>`anaemie = "mein_paket.netze:anaemie_werkzeug"` |
| **Code** | `registrieren(werkzeug)` |

> Dateien im Netze-Ordner werden als Python-Code ausgeführt. Nur eigene, vertrauenswürdige Dateien hineinlegen.

---

## 9. Einbindung in Hippokrates

```
netze/anaemie_morphologie.py ──entdecken()──▶ Adminbereich: „Eigene neuronale Netze“ (freischalten)
                                                        │
             Agent (Planung) ◀── JSON-Schema des Eingabemodells + „anwendbar: true/false“
                  │  überträgt Hb, MCV, Geschlecht aus der Akte
                  ▼
             netzwerkzeug.ausfuehren()  ──▶  Quelle [n] „Neuronales Netz …“ mit Wahrscheinlichkeiten
                  ▼
             Agent (Diagnose) zitiert [n] ──▶ Diagnoseansicht: Balken je Klasse, Eingaben, Hinweis
```

- **Ablegen:** Eine `.py`-Datei in den Ordner `netze/` legen (in Docker als Volume eingebunden). Das mitgelieferte [`netze/anaemie_morphologie.py`](../netze/anaemie_morphologie.py) ist eine vollständige Vorlage: ein selbst geschriebenes NumPy-MLP, das beim ersten Aufruf in unter einer Sekunde trainiert wird.
- **Freischalten:** Im **Adminbereich** unter „Eigene neuronale Netze“. Die Liste wird bei jedem Öffnen neu gesucht; Ladefehler werden angezeigt.
- **Ablauf im Agenten:** Hippokrates' Diagnose-Agenten laufen in festen Schritten (Planen → Fachbibliothek → PubMed → **Netze** → Diagnose), damit auch kleine Modelle ohne zuverlässiges Tool Calling funktionieren. Die Netze werden dabei wie Werkzeuge genutzt: In der Planungsphase füllt jeder Agent das Eingabeschema jedes freigeschalteten Netzes aus der Akte aus – oder erklärt es für nicht anwendbar. Das Netz rechnet lokal; sein Ergebnis wird zur nummerierten Quelle, die der Agent in der Diagnose zitieren kann.
- **Eigene Netze als Agenten-Modell:** Ein `NetzChatModell` im Ordner erscheint unter „Modelle & Technik“ als Quelle „Eigene Netze“ und kann wie jedes Sprachmodell als Agent arbeiten.
- **Konsens:** Alle Agenten befragen dasselbe Netz. Ein Netzergebnis ist daher ein gemeinsamer **Beleg**, keine zusätzliche unabhängige Stimme – es kann die Agenten in dieselbe Richtung lenken. Die Diagnoseansicht zeigt deshalb bei jeder Quelle, welche Agenten sie zitiert haben.

---

## 10. Gute Praxis für medizinische Netze

- **Version und Hinweis angeben.** `version=` und `hinweis=` erscheinen in jedem Ergebnis – das Sprachmodell und die Ärztin sehen, mit welchem Stand und unter welchen Einschränkungen gerechnet wurde.
- **Grenzen im Eingabemodell.** Physiologisch plausible Bereiche (`ge`, `le`) verhindern, dass Einheitenfehler stillschweigend durchrechnen.
- **Beschreibung als Gebrauchsanweisung.** Wann aufrufen, wann nicht („Nur aufrufen, wenn Hb und MCV als Zahlen vorliegen“). Das verhindert erfundene Eingaben.
- **Kalibrierte Wahrscheinlichkeiten.** Sprachmodelle nehmen „100 %“ wörtlich. Netze vor dem Einsatz kalibrieren (Temperature Scaling, Platt Scaling) oder Ergebnisse mit `top_k` und `hinweis` einordnen.
- **Determinismus.** Inferenz ohne Dropout (`eval()` übernimmt der PyTorch-Adapter), feste Seeds beim Training, keine zufällige Vorverarbeitung.
- **Lokal rechnen.** Netze laufen im Prozess der Anwendung; Patientendaten verlassen den Rechner dabei nicht.
- **Threadsicherheit.** Mehrere Agenten rufen ein Netz gleichzeitig auf. Standardmäßig serialisiert `netzwerkzeug` die Auswertung; `threadsicher=True` erlaubt parallele Aufrufe, wenn das Netz das verträgt (z. B. ONNX Runtime).
- **Zulassung.** Ein Netz, das Diagnosen stützt, kann ein Medizinprodukt sein. Das mitgelieferte Beispielnetz ist ausdrücklich nicht klinisch validiert.

---

## 11. Referenz

| Name | Zweck |
|---|---|
| `als_werkzeug(netz=None, *, name, beschreibung, eingabe, klassen=None, ausgaben=None, einheiten=None, laden=None, vorverarbeitung=None, nachverarbeitung=None, top_k=3, softmax=None, hinweis="", version="", geraet=None, threadsicher=False, metadaten=None) -> BaseTool` | Netz als LangChain-Werkzeug |
| `@netz_werkzeug(name=None, beschreibung=None, **optionen)` | Auswertungsfunktion als Werkzeug |
| `ausfuehren(werkzeug, argumente) -> (text, artefakt)` | Werkzeug ohne Agent aufrufen |
| `NetzMiddleware(werkzeuge, eingaben, *, ueberschrift=…)` | Netze vor dem Agenten auswerten (`create_agent(middleware=[…])`) |
| `NetzChatModell(erzeuge, modellname="…", nachrichtenformat="text", erzeuge_optionen={})` | eigenes generatives Netz als Chat-Modell, mit Werkzeugaufrufen per JSON |
| `entdecken(ordner=None, *, pakete=True) -> Entdeckung` | Netze aus Ordner, Entry Points und Register |
| `registrieren(*objekte)` | Werkzeug oder Chat-Modell zur Laufzeit bekannt machen |
| `NetzErgebnis`, `Vorhersage` | einheitliches Ergebnis (`als_text()`, `als_dict()`) |
| `ausfuehrer(netz)`, `zu_numpy(ausgabe)`, `merkmalsvektor(daten)` | Bausteine der Adapter für eigene Erweiterungen |

**Tests:** `.venv/bin/python -m unittest discover pakete/netzwerkzeug/tests` – darunter vollständige Durchläufe mit `create_agent` für alle drei Muster (mit einem Skript-Modell anstelle eines echten Sprachmodells).
