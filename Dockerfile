# syntax=docker/dockerfile:1
# Hippokrates im Container. Die Sprachmodelle stellt weiterhin der Host bereit (Ollama, LM Studio …).
# Anleitung: docs/docker.md

# ── 1. React-Oberfläche bauen ────────────────────────────────────────────────
FROM node:22-slim AS oberflaeche
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ── 2. Laufzeit ──────────────────────────────────────────────────────────────
FROM python:3.12-slim

# Zusätzliche Python-Pakete für eigene Netze, z. B. „onnxruntime scikit-learn“ (PyTorch nur für CPU:
# „--extra-index-url https://download.pytorch.org/whl/cpu torch“)
ARG ZUSATZPAKETE=""

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HIPPOKRATES_DOCKER=1 \
    HIPPOKRATES_HOST=0.0.0.0 \
    HIPPOKRATES_PORT=8000 \
    HIPPOKRATES_DATEN=/daten \
    HIPPOKRATES_NETZE=/app/netze \
    HIPPOKRATES_OBERFLAECHE=/app/frontend/dist \
    HIPPOKRATES_OLLAMA_URL=http://host.docker.internal:11434 \
    HIPPOKRATES_MODELL_HOST=host.docker.internal

WORKDIR /app
COPY pyproject.toml ./
COPY pakete/ pakete/
RUN pip install ./pakete/netzwerkzeug . ${ZUSATZPAKETE}

COPY src/ src/
COPY netze/ netze/
COPY --from=oberflaeche /app/frontend/dist frontend/dist

RUN useradd --uid 1000 --create-home hippokrates && mkdir -p /daten && chown hippokrates:hippokrates /daten
USER hippokrates

EXPOSE 8000
VOLUME ["/daten"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ['HIPPOKRATES_PORT']}/api/status\", timeout=4)"

CMD ["python", "src/main.py"]
