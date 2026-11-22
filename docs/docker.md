# Hippokrates mit Docker

Hippokrates läuft im Container; **die Sprachmodelle stellt weiterhin der Host bereit** (Ollama, LM Studio, llama.cpp …). Der Container enthält nur die Anwendung: Python-Server, React-Oberfläche, die Bibliothek `netzwerkzeug` und die eigenen Netze aus `netze/`.

```
┌──────────────────────── Host ─────────────────────────┐
│  Ollama :11434   LM Studio :1234   llama.cpp :8080 …  │
│        ▲                 ▲                ▲           │
│        └──────── host.docker.internal ────┘           │
│                          │                            │
│   ┌──────── Container „hippokrates“ ────────┐         │
│   │  FastAPI + React-Oberfläche  :8000      │◀── 127.0.0.1:8000 (Browser)
│   │  /daten  ◀── ./daten   (Patienten, Bibliothek, Index)
│   │  /app/netze ◀── ./netze (eigene neuronale Netze, nur lesend)
│   └─────────────────────────────────────────┘         │
└───────────────────────────────────────────────────────┘
```

## Schnellstart: ein Befehl

```bash
./installieren.sh
```

Das Skript führt durch alle Schritte und fragt nach, bevor es etwas am System ändert:

| Schritt | Was passiert |
|---|---|
| Voraussetzungen | prüft `curl`, Docker und Docker Compose ≥ 2.24 |
| Docker-Dienst | erkennt Docker Engine und Docker Desktop; startet sie nach Rückfrage (`systemctl --user start docker-desktop`, `sudo systemctl start docker`, macOS: `open -a Docker`) |
| Netzvariante | Docker Engine unter Linux → Host-Netz (Ollama ohne Umkonfiguration erreichbar); Docker Desktop → Bridge-Netz über `host.docker.internal` |
| Sprachmodelle | prüft Ollama auf dem Host; fehlen Chat- oder Embedding-Modelle, bietet es `mistral:7b`, `qwen3.5:9b` und `granite-embedding:278m` zum Download an |
| Ordner und Konfiguration | legt `daten/` und `netze/` mit dem eigenen Benutzer als Besitzer an (sonst legt Docker sie als root an), wählt einen freien Port und schreibt `.env` |
| Bauen und starten | `docker compose up -d --build` |
| Funktionsprüfung | wartet auf `/api/status` und prüft über `/api/modelle`, ob der Container die Modelle des Hosts erreicht – mit Hinweis zur Lösung, falls nicht |

Danach: <http://127.0.0.1:8000> (oder der angezeigte Port). Erneut ausführen = aktualisieren.

| Option | Wirkung |
|---|---|
| `--pruefen` | nur prüfen und berichten, nichts verändern |
| `-j`, `--ja` | alle Rückfragen bejahen (unbeaufsichtigte Installation) |
| `--ohne-modelle` | keine Sprachmodelle herunterladen |
| `--port N` | gewünschter Port; ist er belegt, wird der nächste freie genommen |
| `--netz host\|bridge` | Netzvariante erzwingen |
| `--zusatzpakete "…"` | Python-Pakete für eigene Netze mit ins Image, z. B. `"onnxruntime scikit-learn"` |
| `--nicht-oeffnen` | Browser am Ende nicht öffnen |

Die erzeugte `.env` enthält unter anderem `COMPOSE_FILE`. Deshalb funktionieren im Projektordner alle Compose-Befehle ohne `-f`:

```bash
docker compose logs -f          # Protokoll
docker compose ps               # Status inkl. Healthcheck (/api/status)
docker compose down             # anhalten – Daten in ./daten bleiben erhalten
```

## Manuell einrichten

| System | Befehl |
|---|---|
| **Linux** (Docker Engine, ohne Änderung an Ollama) | `docker compose -f docker-compose.yml -f docker-compose.hostnetz.yml up -d --build` |
| **Docker Desktop** (Linux, macOS, Windows) | `docker compose up -d --build` |
| Linux mit Bridge-Netz | `docker compose up -d --build` – Ollama vorher erreichbar machen (siehe unten) |

## Wie der Container die Modelle des Hosts findet

| Variable | Standard im Container | Bedeutung |
|---|---|---|
| `HIPPOKRATES_OLLAMA_URL` | `http://host.docker.internal:11434` | Ollama-Adresse; fest vorgegeben, in der Oberfläche nicht änderbar |
| `HIPPOKRATES_MODELL_HOST` | `host.docker.internal` | Rechner, auf dem LM Studio, llama.cpp, Jan, GPT4All … gesucht werden |
| `HIPPOKRATES_HOST` / `HIPPOKRATES_PORT` | `0.0.0.0` / `8000` | Adresse, auf der der Server im Container lauscht |
| `HIPPOKRATES_DATEN` | `/daten` | Patientendaten, Fachbibliothek, Suchindex |
| `HIPPOKRATES_NETZE` | `/app/netze` | Ordner der eigenen neuronalen Netze |

Die Modellliste wird bei jedem Öffnen der Oberfläche und alle 30 Sekunden neu abgefragt. Ein auf dem Host neu installiertes Modell (`ollama pull …`) erscheint also ohne Neustart des Containers.

### Linux: Ollama über die Docker-Bridge erreichbar machen

Ollama lauscht standardmäßig nur auf `127.0.0.1`. Ein Container im Bridge-Netz erreicht den Host aber über die Bridge-Adresse (meist `172.17.0.1`). Zwei Wege:

1. **Host-Netz verwenden** (`docker-compose.hostnetz.yml`): Der Container nutzt das Netz des Hosts, `127.0.0.1:11434` ist direkt erreichbar. Hippokrates lauscht dann selbst auf `127.0.0.1:8000` des Hosts. Das ist der einfachste und sicherste Weg.
2. **Ollama auf allen Schnittstellen lauschen lassen:**
   ```bash
   sudo systemctl edit ollama
   # [Service]
   # Environment="OLLAMA_HOST=0.0.0.0:11434"
   sudo systemctl restart ollama
   ```
   Achtung: Ollama ist dann auch aus dem lokalen Netz erreichbar. Port 11434 per Firewall auf die Docker-Netze beschränken, z. B. `sudo ufw allow from 172.16.0.0/12 to any port 11434` und `sudo ufw deny 11434`.

Prüfen: `docker compose exec hippokrates python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/api/version').read())"`

## Daten

`./daten` wird nach `/daten` eingebunden. Das ist derselbe Ordner, den Hippokrates ohne Docker verwendet; eine bestehende Installation lässt sich also direkt übernehmen und umgekehrt. Damit die Dateien dem eigenen Benutzer gehören, läuft der Container mit `HIPPOKRATES_UID`/`HIPPOKRATES_GID` (Standard 1000). Bei anderer Benutzer-ID:

```bash
HIPPOKRATES_UID=$(id -u) HIPPOKRATES_GID=$(id -g) docker compose up -d
```

Die per Umgebung vorgegebene Ollama-Adresse wird nicht in die Datenbank geschrieben – außerhalb von Docker gilt weiter die eigene Einstellung.

## Eigene neuronale Netze im Container

`./netze` ist nur lesend eingebunden. Neue oder geänderte `.py`-Dateien erkennt Hippokrates ohne Neustart (Adminbereich → „Eigene neuronale Netze“). Brauchen die Netze zusätzliche Pakete, werden diese beim Bauen installiert:

```bash
# z. B. ONNX Runtime und scikit-learn
HIPPOKRATES_ZUSATZPAKETE="onnxruntime scikit-learn" docker compose up -d --build

# PyTorch nur für CPU (deutlich kleineres Image)
HIPPOKRATES_ZUSATZPAKETE="--extra-index-url https://download.pytorch.org/whl/cpu torch" docker compose up -d --build
```

Netze auf der GPU benötigen das NVIDIA Container Toolkit und in `docker-compose.yml` unter `hippokrates` einen Eintrag `gpus: all`. Die Sprachmodelle selbst nutzen weiterhin die GPU des Hosts über Ollama.

## Sicherheit

- Der Port wird nur auf `127.0.0.1` veröffentlicht. Hippokrates hat keine Benutzeranmeldung – nicht ins Netzwerk freigeben.
- Der Container läuft ohne Root-Rechte.
- Netze im Ordner `netze/` sind ausführbarer Python-Code: nur eigene, vertrauenswürdige Dateien ablegen.
