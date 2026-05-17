# Hippokrates
Standalone-KI-System für medizinische Diagnoseunterstützung mit Multi-LLM-Konsensus und patientenindividueller RAG-Architektur.


## Überblick

MediConsult AI ist ein vollständig eigenständiges, serverbasiertes System, das medizinisches Fachpersonal bei der Diagnosestellung unterstützt. Es verbindet patientenindividuelle Retrieval-Augmented Generation (RAG) mit einem parallelen Multi-LLM-Ansatz: Mehrere Sprachmodelle analysieren dieselben Patientendaten unabhängig voneinander. Ein Konsensus-Algorithmus bewertet und gewichtet die Antworten – häufig übereinstimmende Diagnosen werden höher eingestuft, Ausreißer werden gefiltert oder verworfen.

Das System ist nicht mit externen Diensten oder Krankenhausinformationssystemen verbunden. Alle Patientendaten werden direkt im System erfasst und verbleiben dort.


## Kernfunktionen

### Patientenverwaltung (Admin-Bereich)
- Anlegen und Verwalten von Patientenprofilen
- Strukturierte Erfassung von Anamnese und Vorerkrankungen
- Manuelle Eingabe und Hochladen von Laborbefunden (PDF, CSV)
- Erfassung von Blutwerten, Vitaminen und Spurenelementen mit Referenzwerten
- Upload von Befundberichten und Bilddokumenten

### KI-Diagnoseunterstützung
- Pro Patient eine isolierte RAG-Instanz auf Basis der patientenspezifischen Daten
- Parallele Verarbeitung durch mehrere Sprachmodelle (LLM A … LLM N)
- Konsensus-Engine: semantischer Abgleich und Ranking der Modellantworten
- Automatisches Verwerfen von Ausreißern unterhalb eines Ähnlichkeitsschwellwerts
- Strukturierte Ausgabe mit Diagnosevorschlag und Konfidenz-Score

### Dashboard
- Patientensuche nach Name, ID oder Geburtsdatum
- Visualisierung von Spurenelementen (Zn, Fe, Mg, Cu, Se u. a.) mit Referenzbereich
- Ampelsystem für Vitaminversorgung (B12, D, K2, Folsäure u. a.)
- Hervorhebung kritischer Blutwerte (Hb, Kreatinin, CRP u. a.)
- Zeitlicher Verlauf aller Messwerte

### Agentische Funktion *(in Entwicklung)*
- LLM-Peer-Review: Modelle prüfen und kommentieren die Antworten der anderen
- Nutzer-definierter Iterationszeitraum
- Audit-Log aller Überprüfungsschritte

---

## Systemarchitektur

```
┌─────────────────────────────────────────────────────┐
│                   Admin-Bereich                     │
│  Patient anlegen · Anamnese · Labor · Dokumente     │
└────────────────────────┬────────────────────────────┘
                         │ speichern
┌────────────────────────▼────────────────────────────┐
│              Datenspeicher & KI-Kern                │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ Relationale  │  │ Vektorspeicher│  │  Datei-   │ │
│  │     DB       │  │ (RAG/Patient) │  │ speicher  │ │
│  └──────────────┘  └──────────────┘  └───────────┘ │
│                                                     │
│         LLM-Orchestrator · Konsensus-Engine         │
└────────────────────────┬────────────────────────────┘
                         │ lesen
┌────────────────────────▼────────────────────────────┐
│                Dashboard (Read-Only)                │
│  Suche · Spurenelemente · Vitamine · Blutwerte      │
│  KI-Diagnoseanfrage · Verlauf & Historie            │
└─────────────────────────────────────────────────────┘
```

---

## Tech-Stack (Referenzimplementierung)

| Schicht | Technologie |
|---|---|
| Backend | Python · FastAPI |
| Datenbank | PostgreSQL + pgvector |
| RAG-Framework | LangChain / LlamaIndex |
| LLM (lokal) | Ollama · Llama 3 · Mistron · Meditron |
| LLM (API) | OpenAI · Anthropic Claude |
| Frontend | React · TypeScript · Tailwind CSS |
| Dokumentenverarbeitung | PDFPlumber · Tesseract OCR |
| Deployment | Docker · Docker Compose |

---

## Datenschutz & Sicherheit

- **Vollständig standalone** – keine Verbindung zu externen APIs oder Diensten erforderlich
- Alle Patientendaten verbleiben auf dem lokalen Server
- Rollenbasierte Zugriffskontrolle (Admin / Arzt / Lesezugriff)
- Verschlüsselte Datenbankverbindungen
- Audit-Log für alle Datenzugriffe und KI-Anfragen
- Konform mit den Anforderungen der DSGVO und §203 StGB (ärztliche Schweigepflicht)

> **Hinweis:** Dieses System dient ausschließlich der Entscheidungsunterstützung. Es ersetzt nicht die ärztliche Diagnose und Behandlungsentscheidung.

---

## Installation

```bash
# Repository klonen
git clone https://github.com/dein-name/mediconsult-ai.git
cd mediconsult-ai

# Umgebungsvariablen konfigurieren
cp .env.example .env

# System starten
docker compose up -d
```

Die Anwendung ist anschließend erreichbar unter `http://localhost:3000`.

Eine detaillierte Installationsanleitung findet sich in [`docs/setup.md`](docs/setup.md).

---

## Projektstruktur

```
mediconsult-ai/
├── backend/
│   ├── api/            # FastAPI-Routen
│   ├── rag/            # RAG-Logik pro Patient
│   ├── llm/            # LLM-Orchestrator & Konsensus
│   └── models/         # Datenbankmodelle
├── frontend/
│   ├── admin/          # Dateneingabe & Patientenverwaltung
│   └── dashboard/      # Visualisierung & Diagnoseansicht
├── docs/               # Dokumentation
└── docker-compose.yml
```

---

## Status

| Komponente | Status |
|---|---|
| Admin-Bereich / Dateneingabe | 🔧 In Entwicklung |
| Patientendatenbank | 🔧 In Entwicklung |
| RAG-Engine (pro Patient) | 🔧 In Entwicklung |
| Multi-LLM-Orchestrator | 🔧 In Entwicklung |
| Konsensus-Algorithmus | 🔧 In Entwicklung |
| Dashboard | 🔧 In Entwicklung |
| Agentische Peer-Review | 📋 Geplant |

---

## Lizenz

Dieses Projekt steht unter der [MIT License](LICENSE).

---

## Mitwirken

Issues und Pull Requests sind willkommen. Bitte lies zunächst [`CONTRIBUTING.md`](CONTRIBUTING.md).
