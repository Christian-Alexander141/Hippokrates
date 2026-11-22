#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
#  Hippokrates – zentrales Installationsskript für den Betrieb in Docker
#
#  Einmal ausführen, danach läuft Hippokrates unter http://127.0.0.1:8000:
#
#      ./installieren.sh
#
#  Erneut ausführen = aktualisieren (Image neu bauen, Container neu starten).
#  Die Sprachmodelle laufen weiterhin auf dem Host (Ollama, LM Studio …).
#  Hilfe:  ./installieren.sh --hilfe
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Empfohlene Modelle, falls auf dem Host noch keine passenden vorhanden sind
EMPFOHLEN_CHAT=("mistral:7b" "qwen3.5:9b")
EMPFOHLEN_EMBEDDING="granite-embedding:278m"
OLLAMA_HOST_URL="${OLLAMA_HOST_URL:-http://127.0.0.1:11434}"

ALLES_JA=0
OHNE_MODELLE=0
NUR_PRUEFEN=0
NETZ="auto"          # auto | host | bridge
PORT_WUNSCH=""
ZUSATZPAKETE="${HIPPOKRATES_ZUSATZPAKETE:-}"
OEFFNEN="frage"

hilfe() {
  cat <<'TEXT'
Hippokrates in Docker installieren und starten.

  ./installieren.sh [Optionen]

Optionen:
  -j, --ja               alle Rückfragen mit Ja beantworten (z. B. Modelle laden)
      --ohne-modelle     keine Sprachmodelle herunterladen
      --pruefen          nur prüfen und berichten, nichts verändern
      --port N           gewünschter Port (Standard 8000; belegt -> nächster freier)
      --netz host|bridge Netzvariante erzwingen (Standard: automatisch)
      --zusatzpakete "…" zusätzliche Python-Pakete für eigene Netze,
                         z. B. "onnxruntime scikit-learn"
      --nicht-oeffnen    Browser am Ende nicht öffnen
  -h, --hilfe            diese Hilfe

Danach im Projektordner:
  docker compose logs -f     Protokoll ansehen
  docker compose down        anhalten (Daten in ./daten bleiben erhalten)
  ./installieren.sh          aktualisieren
TEXT
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -j|--ja) ALLES_JA=1 ;;
    --ohne-modelle) OHNE_MODELLE=1 ;;
    --pruefen) NUR_PRUEFEN=1 ;;
    --port) PORT_WUNSCH="${2:?--port braucht eine Zahl}"; shift ;;
    --netz) NETZ="${2:?--netz braucht host oder bridge}"; shift ;;
    --zusatzpakete) ZUSATZPAKETE="${2-}"; shift ;;
    --nicht-oeffnen) OEFFNEN="nein" ;;
    -h|--hilfe|--help) hilfe; exit 0 ;;
    *) echo "Unbekannte Option: $1 (siehe --hilfe)" >&2; exit 2 ;;
  esac
  shift
done
[[ "$NETZ" =~ ^(auto|host|bridge)$ ]] || { echo "--netz: host oder bridge" >&2; exit 2; }

# ── Ausgabe ───────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  B=$'\e[1m'; G=$'\e[32m'; Y=$'\e[33m'; R=$'\e[31m'; C=$'\e[36m'; D=$'\e[2m'; N=$'\e[0m'
else
  B=""; G=""; Y=""; R=""; C=""; D=""; N=""
fi
SCHRITT=0
schritt() { SCHRITT=$((SCHRITT + 1)); printf '\n%s%s[%d] %s%s\n' "$B" "$C" "$SCHRITT" "$1" "$N"; }
ok()      { printf '  %s✓%s %s\n' "$G" "$N" "$1"; }
info()    { printf '  %s•%s %s\n' "$D" "$N" "$1"; }
warn()    { printf '  %s!%s %s\n' "$Y" "$N" "$1"; }
abbruch() { printf '\n  %s✗ %s%s\n' "$R" "$1" "$N" >&2; [[ $# -gt 1 ]] && printf '    %s\n' "${@:2}" >&2; exit 1; }

# Ja/Nein-Frage. Standard „ja“; ohne Terminal oder mit --ja ohne Rückfrage.
frage() {
  [[ $ALLES_JA -eq 1 ]] && return 0
  [[ -t 0 ]] || return 0
  local antwort
  read -r -p "  ? $1 [J/n] " antwort || return 1
  [[ -z "$antwort" || "$antwort" =~ ^[JjYy] ]]
}

port_belegt() {
  if command -v ss >/dev/null 2>&1; then
    ss -ltnH 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]$1\$"
  elif command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
  else
    (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
  fi
}

version_mindestens() {  # version_mindestens 2.29.1 2.24  -> wahr, wenn erste >= zweite
  local a b
  a="$(printf '%s' "$1" | sed 's/^v//')"
  b="$2"
  [[ "$(printf '%s\n%s\n' "$b" "$a" | sort -V | head -n1)" == "$b" ]]
}

printf '%sHippokrates – Installation in Docker%s\n' "$B" "$N"
printf '%sProjektordner: %s%s\n' "$D" "$PWD" "$N"
[[ $NUR_PRUEFEN -eq 1 ]] && printf '%sNur Prüfung – es wird nichts verändert.%s\n' "$Y" "$N"

# ── 1. Werkzeuge ──────────────────────────────────────────────────────────────
schritt "Voraussetzungen"
command -v curl >/dev/null 2>&1 || abbruch "curl fehlt." "Debian/Ubuntu: sudo apt install curl"
command -v docker >/dev/null 2>&1 || abbruch "Docker ist nicht installiert." \
  "Linux:  https://docs.docker.com/engine/install/  (Docker Engine)" \
  "macOS/Windows:  https://docs.docker.com/desktop/  (Docker Desktop)"
ok "Docker-Programm $(docker --version 2>/dev/null | sed -E 's/^Docker version ([^,]+).*/\1/')"
docker compose version >/dev/null 2>&1 || abbruch "Docker Compose (v2) fehlt." "Debian/Ubuntu: sudo apt install docker-compose-plugin"
COMPOSE_VERSION="$(docker compose version --short 2>/dev/null || echo 0)"
version_mindestens "$COMPOSE_VERSION" 2.24 || abbruch "Docker Compose $COMPOSE_VERSION ist zu alt (mindestens 2.24 nötig)."
ok "Docker Compose $COMPOSE_VERSION"

# ── 2. Docker-Dienst ─────────────────────────────────────────────────────────
schritt "Docker-Dienst"
docker_bereit() { docker info >/dev/null 2>&1; }
warten_auf_docker() {
  local i
  for i in $(seq 1 90); do docker_bereit && return 0; sleep 2; done
  return 1
}

# Docker starten: ohne --pruefen nach Rückfrage, mit --pruefen nur berichten
starten_angeboten() {  # starten_angeboten "Beschreibung" "Frage" befehl…
  local beschreibung="$1" frage_text="$2"; shift 2
  warn "$beschreibung"
  if [[ $NUR_PRUEFEN -eq 1 ]]; then info "(nur Prüfung) würde nach Rückfrage ausführen: $*"; return 1; fi
  frage "$frage_text" || abbruch "Docker läuft nicht." "Starten mit:  $*"
  "$@"
  info "warte auf Docker (bis zu 3 Minuten) …"
  warten_auf_docker || abbruch "Docker ist nicht rechtzeitig gestartet."
  ok "Docker gestartet"
}

DESKTOP=0
if docker_bereit; then
  ok "Docker läuft"
elif docker info 2>&1 | grep -qi "permission denied"; then
  abbruch "Keine Berechtigung für Docker." \
    "Benutzer zur Gruppe docker hinzufügen:  sudo usermod -aG docker \$USER" \
    "danach ab- und wieder anmelden und das Skript erneut starten."
elif DOCKER_CONTEXT=desktop-linux docker info >/dev/null 2>&1; then
  export DOCKER_CONTEXT=desktop-linux
  ok "Docker Desktop läuft (Kontext desktop-linux)"
elif [[ "$(uname -s)" == "Linux" ]] && systemctl --user cat docker-desktop.service >/dev/null 2>&1; then
  DESKTOP=1
  export DOCKER_CONTEXT=desktop-linux
  starten_angeboten "Docker Desktop ist installiert, läuft aber nicht." "Docker Desktop jetzt starten?" \
    systemctl --user start docker-desktop || true
elif [[ "$(uname -s)" == "Linux" ]] && systemctl cat docker.service >/dev/null 2>&1; then
  starten_angeboten "Der Docker-Dienst läuft nicht." "Docker-Dienst starten (sudo systemctl start docker)?" \
    sudo systemctl start docker || true
elif [[ "$(uname -s)" == "Darwin" ]]; then
  DESKTOP=1
  starten_angeboten "Docker Desktop läuft nicht." "Docker Desktop jetzt öffnen?" open -a Docker || true
else
  abbruch "Docker läuft nicht." "Docker starten und das Skript erneut ausführen."
fi

DOCKER_LAEUFT=0
if docker_bereit; then
  DOCKER_LAEUFT=1
  docker info --format '{{.OperatingSystem}}' 2>/dev/null | grep -qi "docker desktop" && DESKTOP=1
fi
[[ "${DOCKER_CONTEXT:-}" == "desktop-linux" ]] && DESKTOP=1
if [[ $DOCKER_LAEUFT -eq 1 && "${DOCKER_CONTEXT:-}" == "desktop-linux" && "$(docker context show 2>/dev/null || true)" != "desktop-linux" ]]; then
  if frage "Docker-Kontext dauerhaft auf Docker Desktop umstellen (damit „docker compose …“ später ohne Weiteres funktioniert)?"; then
    docker context use desktop-linux >/dev/null && ok "Docker-Kontext: desktop-linux"
  else
    info "Für spätere Befehle:  export DOCKER_CONTEXT=desktop-linux"
  fi
fi

# ── 3. Netzvariante ──────────────────────────────────────────────────────────
schritt "Netzvariante"
if [[ "$NETZ" == "auto" ]]; then
  if [[ "$(uname -s)" == "Linux" && $DESKTOP -eq 0 ]]; then NETZ="host"; else NETZ="bridge"; fi
fi
if [[ "$NETZ" == "host" ]]; then
  COMPOSE_DATEIEN="docker-compose.yml:docker-compose.hostnetz.yml"
  ok "Host-Netz: der Container erreicht Ollama direkt unter 127.0.0.1:11434"
else
  COMPOSE_DATEIEN="docker-compose.yml"
  ok "Bridge-Netz: der Container erreicht den Host unter host.docker.internal"
fi

# ── 4. Sprachmodelle auf dem Host ────────────────────────────────────────────
schritt "Sprachmodelle auf dem Host"
OLLAMA_OK=0
if curl -fsS --max-time 3 "$OLLAMA_HOST_URL/api/version" >/dev/null 2>&1; then
  OLLAMA_OK=1
  ok "Ollama erreichbar ($OLLAMA_HOST_URL)"
else
  warn "Ollama ist unter $OLLAMA_HOST_URL nicht erreichbar."
  if [[ "$(uname -s)" == "Linux" ]] && systemctl cat ollama.service >/dev/null 2>&1; then
    if [[ $NUR_PRUEFEN -eq 0 ]] && frage "Ollama-Dienst starten (sudo systemctl start ollama)?"; then
      sudo systemctl start ollama && sleep 2
      curl -fsS --max-time 3 "$OLLAMA_HOST_URL/api/version" >/dev/null 2>&1 && OLLAMA_OK=1 && ok "Ollama gestartet"
    fi
  elif ! command -v ollama >/dev/null 2>&1; then
    info "Ollama installieren: https://ollama.com/download – Hippokrates erkennt es danach von selbst."
    info "Alternativ LM Studio, llama.cpp, Jan oder GPT4All starten; auch diese werden gefunden."
  else
    info "Ollama starten (z. B. „ollama serve“) – Hippokrates erkennt es danach von selbst."
  fi
fi

if [[ $OLLAMA_OK -eq 1 ]]; then
  NAMEN="$(curl -fsS --max-time 5 "$OLLAMA_HOST_URL/api/tags" | grep -o '"name":"[^"]*"' | sed 's/"name":"//;s/"$//' || true)"
  CHAT="$(printf '%s\n' "$NAMEN" | grep -v -i -e embed -e cloud -e '^$' || true)"
  EMBED="$(printf '%s\n' "$NAMEN" | grep -i embed || true)"
  ANZ_CHAT=$(printf '%s' "$CHAT" | grep -c . || true)
  ANZ_EMBED=$(printf '%s' "$EMBED" | grep -c . || true)
  info "$ANZ_CHAT lokale(s) Chat-Modell(e), $ANZ_EMBED Embedding-Modell(e)"

  FEHLEN=()
  if [[ $ANZ_CHAT -lt 2 ]]; then
    for m in "${EMPFOHLEN_CHAT[@]}"; do
      printf '%s\n' "$NAMEN" | grep -qx "$m" || FEHLEN+=("$m")
    done
  fi
  [[ $ANZ_EMBED -eq 0 ]] && FEHLEN+=("$EMPFOHLEN_EMBEDDING")

  if [[ ${#FEHLEN[@]} -eq 0 ]]; then
    ok "genug Modelle für mehrere unabhängige Agenten vorhanden"
  elif [[ $OHNE_MODELLE -eq 1 ]]; then
    warn "Empfohlen wären noch: ${FEHLEN[*]} (übersprungen wegen --ohne-modelle)"
  else
    warn "Für mehrere unabhängige Agenten und die Fachbibliothek fehlen noch Modelle."
    if [[ $NUR_PRUEFEN -eq 0 ]] && frage "Jetzt herunterladen: ${FEHLEN[*]} (zusammen einige GB)?"; then
      for m in "${FEHLEN[@]}"; do
        info "lade $m …"
        if command -v ollama >/dev/null 2>&1; then
          ollama pull "$m" || warn "$m konnte nicht geladen werden"
        else
          curl -fsS "$OLLAMA_HOST_URL/api/pull" -d "{\"model\":\"$m\",\"stream\":false}" >/dev/null \
            && ok "$m geladen" || warn "$m konnte nicht geladen werden"
        fi
      done
    else
      info "Später möglich:  ollama pull ${FEHLEN[*]}"
    fi
  fi

  # Bridge-Netz unter Linux: Ollama muss außer auf 127.0.0.1 auch auf der Docker-Bridge lauschen
  if [[ "$NETZ" == "bridge" && "$(uname -s)" == "Linux" && $DESKTOP -eq 0 ]] && command -v ss >/dev/null 2>&1; then
    if ! ss -ltnH 2>/dev/null | awk '{print $4}' | grep -Eq '^(0\.0\.0\.0|\*|\[::\]|172\.[0-9.]+):11434$'; then
      warn "Ollama lauscht nur auf 127.0.0.1 – im Bridge-Netz ist es aus dem Container nicht erreichbar."
      info "Lösung: ohne --netz bridge starten (Host-Netz) oder OLLAMA_HOST=0.0.0.0 setzen (docs/docker.md)."
    fi
  fi
fi

# ── 5. Ordner und Konfiguration ──────────────────────────────────────────────
schritt "Ordner und Konfiguration"
if [[ $EUID -eq 0 && -n "${SUDO_UID:-}" ]]; then
  NUTZER_UID="$SUDO_UID"; NUTZER_GID="$SUDO_GID"
else
  NUTZER_UID="$(id -u)"; NUTZER_GID="$(id -g)"
fi

for ordner in daten netze; do
  if [[ ! -d "$ordner" ]]; then
    if [[ $NUR_PRUEFEN -eq 1 ]]; then
      info "(nur Prüfung) würde ./$ordner anlegen"
    else
      mkdir -p "$ordner"
      [[ $EUID -eq 0 ]] && chown "$NUTZER_UID:$NUTZER_GID" "$ordner"
      ok "./$ordner angelegt"
    fi
  else
    ok "./$ordner vorhanden"
  fi
done
if [[ -d daten && ! -w daten ]]; then
  abbruch "./daten ist für Benutzer $NUTZER_UID nicht beschreibbar." "Beheben mit:  sudo chown -R $NUTZER_UID:$NUTZER_GID daten"
fi
# Docker legt fehlende Bind-Mounts als root an – deshalb hier vorab und mit eigenem Besitzer.

LAEUFT_SCHON=0
if [[ $DOCKER_LAEUFT -eq 1 ]] && [[ -n "$(docker ps -q --filter name='^hippokrates$' 2>/dev/null || true)" ]]; then
  LAEUFT_SCHON=1
fi
ALTER_PORT=""
[[ -f .env ]] && ALTER_PORT="$(grep -E '^HIPPOKRATES_PORT=' .env | cut -d= -f2 || true)"
PORT="${PORT_WUNSCH:-${ALTER_PORT:-8000}}"
if [[ $LAEUFT_SCHON -eq 1 && "$PORT" == "${ALTER_PORT:-}" ]]; then
  ok "Port $PORT (Hippokrates läuft bereits und wird aktualisiert)"
else
  start="$PORT"
  while port_belegt "$PORT"; do
    PORT=$((PORT + 1))
    [[ $PORT -gt $((start + 20)) ]] && abbruch "Kein freier Port zwischen $start und $PORT gefunden." "Mit --port einen anderen wählen."
  done
  [[ "$PORT" != "$start" ]] && warn "Port $start ist belegt – verwende $PORT"
  ok "Port $PORT"
fi

ENV_INHALT="# Von installieren.sh erzeugt – wird bei jedem Lauf neu geschrieben.
# docker compose liest diese Datei; Befehle im Projektordner brauchen daher kein -f.
COMPOSE_PROJECT_NAME=hippokrates
COMPOSE_FILE=$COMPOSE_DATEIEN
HIPPOKRATES_PORT=$PORT
HIPPOKRATES_UID=$NUTZER_UID
HIPPOKRATES_GID=$NUTZER_GID
HIPPOKRATES_ZUSATZPAKETE=\"$ZUSATZPAKETE\""
if [[ $NUR_PRUEFEN -eq 1 ]]; then
  info "(nur Prüfung) würde .env schreiben:"
  printf '%s\n' "$ENV_INHALT" | sed 's/^/      /'
else
  if [[ -f .env ]] && ! grep -q "Von installieren.sh erzeugt" .env; then
    cp .env .env.vorher && warn "vorhandene .env gesichert als .env.vorher"
  fi
  printf '%s\n' "$ENV_INHALT" > .env
  ok ".env geschrieben (Netz: $NETZ, Port: $PORT, Benutzer: $NUTZER_UID:$NUTZER_GID)"
fi

# ── 6. Bauen und starten ─────────────────────────────────────────────────────
schritt "Image bauen und Container starten"
if [[ $NUR_PRUEFEN -eq 1 ]]; then
  info "(nur Prüfung) würde ausführen: docker compose up -d --build --remove-orphans"
  [[ $DOCKER_LAEUFT -eq 1 ]] && COMPOSE_FILE="$COMPOSE_DATEIEN" docker compose config --quiet && ok "Compose-Konfiguration gültig"
  printf '\n%sPrüfung abgeschlossen.%s Ohne --pruefen ausführen, um zu installieren.\n' "$B" "$N"
  exit 0
fi
info "beim ersten Mal dauert das einige Minuten …"
docker compose up -d --build --remove-orphans
ok "Container gestartet"

# ── 7. Prüfen ────────────────────────────────────────────────────────────────
schritt "Funktionsprüfung"
URL="http://127.0.0.1:$PORT"
bereit=0
for _ in $(seq 1 60); do
  if curl -fsS --max-time 2 "$URL/api/status" >/dev/null 2>&1; then bereit=1; break; fi
  sleep 2
done
if [[ $bereit -eq 0 ]]; then
  docker compose logs --tail 40 hippokrates >&2 || true
  abbruch "Hippokrates antwortet nicht unter $URL." "Protokoll: docker compose logs -f"
fi
ok "Hippokrates antwortet unter $URL"

MODELLE_JSON="$(curl -fsS --max-time 30 "$URL/api/modelle" || true)"
if printf '%s' "$MODELLE_JSON" | grep -q '"art":"ollama","url":"[^"]*","auto":false,"erreichbar":true'; then
  ANZ=$(printf '%s' "$MODELLE_JSON" | grep -o '"embedding":false' | wc -l | tr -d ' ')
  ok "Container erreicht Ollama auf dem Host – $ANZ Sprachmodelle zur Auswahl"
else
  warn "Der Container erreicht Ollama auf dem Host nicht."
  if [[ "$NETZ" == "bridge" && "$(uname -s)" == "Linux" ]]; then
    info "Ollama lauscht vermutlich nur auf 127.0.0.1. Lösung: OLLAMA_HOST=0.0.0.0 setzen (docs/docker.md)"
    [[ $DESKTOP -eq 0 ]] && info "oder ohne --netz bridge erneut ausführen (Host-Netz)."
  else
    info "Läuft Ollama auf dem Host? Hippokrates prüft laufend neu – kein Neustart nötig."
  fi
fi

# ── Fertig ───────────────────────────────────────────────────────────────────
printf '\n%s%s✓ Hippokrates läuft:%s %s%s%s\n\n' "$B" "$G" "$N" "$B" "$URL" "$N"
cat <<TEXT
  Erste Schritte
    1. Modelle & Technik:  Agenten wählen – oder „Alle lokalen Modelle“
    2. Adminbereich:       Fachbücher hochladen, eigene Netze freischalten
    3. Patienten anlegen   – der erste Abgleich startet automatisch

  Im Projektordner
    docker compose logs -f     Protokoll ansehen
    docker compose down        anhalten (Daten in ./daten bleiben erhalten)
    ./installieren.sh          aktualisieren
TEXT

if [[ "$OEFFNEN" != "nein" && -t 0 && -t 1 ]]; then
  oeffner=""
  command -v xdg-open >/dev/null 2>&1 && oeffner="xdg-open"
  command -v open >/dev/null 2>&1 && [[ "$(uname -s)" == "Darwin" ]] && oeffner="open"
  if [[ -n "$oeffner" ]] && frage "Hippokrates jetzt im Browser öffnen?"; then
    "$oeffner" "$URL" >/dev/null 2>&1 &
  fi
fi
