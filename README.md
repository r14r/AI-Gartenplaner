# Garden AI App

Dieses Projekt enthält:

- Vue 3 + Vite + PrimeVue Frontend
- FullCalendar Kalenderansicht für Aussaat, Auspflanzen und Ernte
- Beetplanung mit Drag & Drop
- Regelengine für Mischkultur-Hinweise
- KI-Beetberatung über FastAPI + Ollama
- Docker-Compose-Umgebung mit Frontend, Backend, Ollama und Ollama-Init-Service
- Konfigurationsseite zum Auswählen des verwendeten Ollama-Modells
- Pull-Task-System mit Fortschrittsanzeige im Frontend
- Model Cache / Versioning System für installierte Ollama-Modelle

## Wichtige Fixes in diesem Stand

- Alle Service-Ports werden zentral über `.env` gesteuert.
- Public- und Private-Ports sind getrennt konfigurierbar.
- Das Frontend verwendet keinen fehlerhaften `.bin/vite`-Aufruf mehr.
- Der Init-Service verwendet kein `curl` und kein fragiles Shell-Parsing mehr.
- Das Modell-Pulling im Init-Service läuft parallel mit Fortschrittslogs.
- Das Backend bietet Pull-Tasks mit Polling-API für die UI.

## Port-Konfiguration

Alle relevanten Ports werden in `.env` gesetzt:

```env
FRONTEND_PORT_PUBLIC=5173
FRONTEND_PORT_PRIVATE=5173
BACKEND_PORT_PUBLIC=8000
BACKEND_PORT_PRIVATE=8000
OLLAMA_PORT_PUBLIC=11434
OLLAMA_PORT_PRIVATE=11434
```

## Ollama-Init-Service

Beim Start der Compose-Umgebung wartet der Service `ollama-init` auf Ollama und installiert automatisch die in `OLLAMA_MODELS` definierten Modelle.

Weitere Parameter:

```env
OLLAMA_MODELS=qwen2.5:7b-instruct,llama3.1:8b,phi4-mini
OLLAMA_INIT_PARALLEL=2
OLLAMA_INIT_POLL_SECONDS=2
OLLAMA_PULL_PARALLEL=2
```

## Konfigurationsseite

Im Tab **Konfiguration** kannst du:

- installierte Ollama-Modelle anzeigen
- das aktive Modell für Analysen festlegen
- optional ein separates Analysemodell setzen
- Temperatur speichern
- weitere Modelle direkt aus der App nachinstallieren
- laufende Pull-Tasks mit Fortschritt sehen
- Cache-/Versionsinformationen der Modelle sehen

Die Konfiguration wird im Backend unter `/app/data/app_config.json` gespeichert.

## Model Cache / Versioning

Das Backend schreibt zusätzlich:

- `/app/data/model_cache.json`
- `/app/data/pull_history.json`

Gespeichert werden dabei:

- bekannte Modellnamen
- zuletzt gesehene Digests
- Größen und Modified-Timestamps
- Snapshots der installierten Modelle
- Historie gestarteter und abgeschlossener Pull-Tasks

## Start mit Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

Danach:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000/docs`
- Ollama: `http://localhost:11434`

## Start ohne Docker

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

### Ollama lokal

```bash
ollama serve
ollama pull qwen2.5:7b-instruct
```

## Technische Hinweise

- Das Frontend ist in JavaScript umgesetzt, damit keine TypeScript-Konfigurationsprobleme auftreten.
- Falls Ollama nicht erreichbar ist, liefert die API weiterhin eine deterministische Fallback-Antwort aus der Regelengine.
- Der Init-Service ist idempotent: bereits vorhandene Modelle werden von Ollama nicht erneut vollständig geladen.
- Pull-Tasks im Backend laufen begrenzt parallel und liefern Fortschrittswerte für die UI.


## Justfile

Wichtige Kommandos:

```bash
just up
just rebuild
just init-models
just logs
just logs backend
just logs frontend
just logs ollama
just urls
```

## Hinweise zu persistenten Modellen

- Das Ollama-Volume ist fest benannt und bleibt zwischen normalen Rebuilds erhalten.
- `just rebuild` löscht keine Volumes.
- Fehlende Modelle kannst du mit `just init-models` nachziehen.


## Ollama Admin

Die Oberfläche enthält zusätzlich einen **Ollama Admin**-Tab mit:

- Liste installierter Modelle
- Live-Installation weiterer Modelle
- Detailansicht über `show`
- Modellkopie über `copy`
- Modelllöschung über `delete`
- Query-Konsole mit synchroner oder Streaming-Ausführung
- Schritt-für-Schritt-Status und Query-Historie
