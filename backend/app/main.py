import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://ollama:11434').rstrip('/')
DEFAULT_OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5:7b-instruct')
REQUEST_TIMEOUT_SECONDS = 3600.0
DEFAULT_MODELS = [item.strip() for item in os.getenv('OLLAMA_MODELS', DEFAULT_OLLAMA_MODEL).split(',') if item.strip()]
CORS_ORIGINS = [item.strip() for item in os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',') if item.strip()]
CONFIG_DIR = Path(os.getenv('CONFIG_DIR', '/app/data'))
CONFIG_PATH = CONFIG_DIR / 'app_config.json'
MODEL_CACHE_PATH = CONFIG_DIR / 'model_cache.json'
PULL_HISTORY_PATH = CONFIG_DIR / 'pull_history.json'
MAX_PARALLEL_PULLS = max(1, int(os.getenv('OLLAMA_PULL_PARALLEL', '2')))

app = FastAPI(title='Garden AI Backend', version='1.4.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=['*'],
    allow_headers=['*'],
)

pull_tasks: Dict[str, dict] = {}
pull_tasks_lock = threading.Lock()
pull_semaphore = threading.Semaphore(MAX_PARALLEL_PULLS)
ai_tasks: Dict[str, dict] = {}
ai_tasks_lock = threading.Lock()
admin_query_tasks: Dict[str, dict] = {}
admin_query_tasks_lock = threading.Lock()

CURATED_MODELS = [
    'qwen2.5:7b-instruct',
    'llama3.1:8b',
    'phi4-mini',
    'gemma3:12b',
    'mistral:7b',
    'llama3.2:3b',
]


class Plant(BaseModel):
    id: str
    name: str
    sort: Optional[str] = ''
    category: Optional[str] = ''
    subcategory: Optional[str] = ''
    standort: Optional[str] = ''
    wasserbedarf: Optional[str] = ''
    zehrer: Optional[str] = ''
    wuchsform: Optional[str] = ''
    pflanzenfamilie: Optional[str] = ''
    guteNachbarn: List[str] = Field(default_factory=list)
    schlechteNachbarn: List[str] = Field(default_factory=list)
    hinweise: Optional[str] = ''


class BedRequest(BaseModel):
    bed_name: str
    location: Optional[str] = ''
    soil: Optional[str] = ''
    size: Optional[str] = ''
    plants: List[Plant]


class BedModel(BaseModel):
    id: str
    name: str
    location: Optional[str] = 'sonnig'
    soil: Optional[str] = 'locker'
    size: Optional[str] = '2 x 1 m'
    seedIds: List[str] = Field(default_factory=list)


class AutoPlanRequest(BaseModel):
    beds: List[BedModel]
    available_seed_ids: List[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    active_model: str = DEFAULT_OLLAMA_MODEL
    analysis_model: Optional[str] = None
    planning_model: Optional[str] = None
    fallback_model: Optional[str] = None
    preferred_models: List[str] = Field(default_factory=lambda: list(DEFAULT_MODELS))
    temperature: float = 0.2
    notes: str = ''


class PullRequest(BaseModel):
    model: str


class CopyRequest(BaseModel):
    source: str
    destination: str


class DeleteRequest(BaseModel):
    model: str


class GenerateAdminRequest(BaseModel):
    model: str
    prompt: str
    system: Optional[str] = None
    temperature: float = 0.2
    keep_alive: Optional[str] = '5m'
    stream: bool = True


class GenerateTaskRequest(GenerateAdminRequest):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json_file(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def write_json_file(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')



def parse_size(value):
    try:
        return int(value)
    except Exception:
        return 0


def parse_modified_at(value):
    return value or ''


def short_digest(value: Optional[str]) -> str:
    if not value:
        return ''
    return value[:18]


def create_admin_query_task(req: GenerateTaskRequest):
    task_id = str(uuid.uuid4())
    task = {
        'id': task_id,
        'type': 'ollama-generate',
        'status': 'queued',
        'progress': 0,
        'created_at': now_iso(),
        'model': req.model,
        'prompt': req.prompt,
        'steps': [],
        'chunks': [],
        'response': '',
        'metrics': None,
        'error': None,
    }
    with admin_query_tasks_lock:
        admin_query_tasks[task_id] = task
    thread = threading.Thread(target=run_admin_query_task, args=(task_id, req.model_dump()), daemon=True)
    thread.start()
    return task


def append_admin_step(task_id: str, phase: str, message: str, progress: int):
    event = {
        'timestamp': now_iso(),
        'phase': phase,
        'message': message,
        'progress': progress,
    }
    with admin_query_tasks_lock:
        task = admin_query_tasks.get(task_id)
        if not task:
            return
        task['progress'] = max(task.get('progress', 0), progress)
        task['current_phase'] = phase
        task['current_message'] = message
        task.setdefault('steps', []).append(event)
        task['steps'] = task['steps'][-200:]
        task['updated_at'] = event['timestamp']


def append_admin_chunk(task_id: str, chunk: str):
    with admin_query_tasks_lock:
        task = admin_query_tasks.get(task_id)
        if not task:
            return
        task['response'] = (task.get('response') or '') + chunk
        task.setdefault('chunks', []).append({'timestamp': now_iso(), 'text': chunk})
        task['chunks'] = task['chunks'][-400:]


def finish_admin_query_task(task_id: str, status: str, metrics: Optional[dict] = None, error: Optional[str] = None):
    with admin_query_tasks_lock:
        task = admin_query_tasks.get(task_id)
        if not task:
            return
        task['status'] = status
        task['progress'] = 100 if status == 'completed' else task.get('progress', 0)
        task['finished_at'] = now_iso()
        if metrics is not None:
            task['metrics'] = metrics
        if error:
            task['error'] = error


def run_admin_query_task(task_id: str, payload: dict):
    try:
        model = payload['model']
        prompt = payload['prompt']
        system = payload.get('system')
        temperature = float(payload.get('temperature') or 0.2)
        keep_alive = payload.get('keep_alive') or '5m'
        append_admin_step(task_id, 'validate', 'Eingaben validiert', 5)
        append_admin_step(task_id, 'connect', f'Verbinde zu Ollama mit {model}', 15)
        request_json = {
            'model': model,
            'prompt': prompt,
            'stream': True,
            'keep_alive': keep_alive,
            'options': {'temperature': temperature},
        }
        if system:
            request_json['system'] = system
        append_admin_step(task_id, 'request', 'Streaming-Anfrage gestartet', 25)
        metrics = {}
        with httpx.stream('POST', f'{OLLAMA_BASE_URL}/api/generate', json=request_json, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                if isinstance(line, bytes):
                    line = line.decode('utf-8', errors='ignore')
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    append_admin_chunk(task_id, line)
                    continue
                chunk = data.get('response') or ''
                if chunk:
                    append_admin_chunk(task_id, chunk)
                    append_admin_step(task_id, 'stream', f'{len((data.get("response") or "").split())} neue Token empfangen', min(90, 30 + len((data.get('response') or '')) // 2))
                if data.get('done'):
                    metrics = {
                        'done_reason': data.get('done_reason'),
                        'total_duration': data.get('total_duration'),
                        'load_duration': data.get('load_duration'),
                        'prompt_eval_count': data.get('prompt_eval_count'),
                        'eval_count': data.get('eval_count'),
                        'eval_duration': data.get('eval_duration'),
                    }
        append_admin_step(task_id, 'finalize', 'Antwort vollständig empfangen', 98)
        finish_admin_query_task(task_id, 'completed', metrics=metrics)
    except Exception as exc:
        append_admin_step(task_id, 'error', f'Fehler: {exc}', 100)
        finish_admin_query_task(task_id, 'failed', error=str(exc))


async def fetch_model_details(model_name: str):
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.post(f'{OLLAMA_BASE_URL}/api/show', json={'model': model_name})
        response.raise_for_status()
        return response.json()


async def delete_model_remote(model_name: str):
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.delete(f'{OLLAMA_BASE_URL}/api/delete', json={'model': model_name})
        response.raise_for_status()
        return response.json() if response.content else {'status': 'ok'}


async def copy_model_remote(source: str, destination: str):
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.post(f'{OLLAMA_BASE_URL}/api/copy', json={'source': source, 'destination': destination})
        response.raise_for_status()
        return response.json() if response.content else {'status': 'ok'}


@app.on_event('startup')
async def startup_event():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        save_config(AppConfig())
    if not MODEL_CACHE_PATH.exists():
        write_json_file(MODEL_CACHE_PATH, {'versions': {}, 'snapshots': []})
    if not PULL_HISTORY_PATH.exists():
        write_json_file(PULL_HISTORY_PATH, [])


async def fetch_installed_models() -> List[dict]:
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.get(f'{OLLAMA_BASE_URL}/api/tags')
        response.raise_for_status()
        payload = response.json()
    return payload.get('models', [])


def load_config() -> AppConfig:
    return AppConfig(**read_json_file(CONFIG_PATH, AppConfig().model_dump()))


def save_config(config: AppConfig) -> AppConfig:
    write_json_file(CONFIG_PATH, config.model_dump())
    return config


def get_active_model() -> str:
    cfg = load_config()
    return cfg.analysis_model or cfg.active_model or DEFAULT_OLLAMA_MODEL


def append_pull_history(entry: dict):
    history = read_json_file(PULL_HISTORY_PATH, [])
    history.append(entry)
    write_json_file(PULL_HISTORY_PATH, history[-200:])


def update_model_cache(models: List[dict]):
    cache = read_json_file(MODEL_CACHE_PATH, {'versions': {}, 'snapshots': []})
    versions = cache.get('versions', {})
    for item in models:
        name = item.get('name')
        if not name:
            continue
        version_entry = {
            'name': name,
            'digest': item.get('digest'),
            'size': item.get('size'),
            'modified_at': item.get('modified_at'),
            'seen_at': now_iso(),
        }
        versions.setdefault(name, [])
        if not versions[name] or versions[name][-1].get('digest') != version_entry.get('digest'):
            versions[name].append(version_entry)
        else:
            versions[name][-1].update(version_entry)
    snapshots = cache.get('snapshots', [])
    snapshots.append({
        'captured_at': now_iso(),
        'models': [
            {
                'name': item.get('name'),
                'digest': item.get('digest'),
                'size': item.get('size'),
                'modified_at': item.get('modified_at'),
            }
            for item in models
        ]
    })
    cache['versions'] = versions
    cache['snapshots'] = snapshots[-30:]
    write_json_file(MODEL_CACHE_PATH, cache)
    return cache


async def refresh_model_cache():
    models = await fetch_installed_models()
    cache = update_model_cache(models)
    return models, cache


def append_ai_step(task_id: str, phase: str, message: str, progress: int):
    event = {
        'timestamp': now_iso(),
        'phase': phase,
        'message': message,
        'progress': progress,
    }
    with ai_tasks_lock:
        task = ai_tasks.get(task_id)
        if not task:
            return
        task['progress'] = max(task.get('progress', 0), progress)
        task['current_phase'] = phase
        task['current_message'] = message
        task.setdefault('steps', []).append(event)
        task['steps'] = task['steps'][-120:]
        task['updated_at'] = event['timestamp']


def finish_ai_task(task_id: str, *, status: str, result: Optional[dict] = None, error: Optional[str] = None, progress: int = 100):
    with ai_tasks_lock:
        task = ai_tasks.get(task_id)
        if not task:
            return
        task['status'] = status
        task['progress'] = progress
        task['finished_at'] = now_iso()
        if result is not None:
            task['result'] = result
        if error:
            task['error'] = error


def build_analysis_prompt(data: BedRequest):
    plant_lines = []
    for idx, plant in enumerate(data.plants, start=1):
        label = f"{plant.name} {plant.sort}".strip()
        plant_lines.append(
            f"""{idx}. {label}
- Kategorie: {plant.category or '-'}
- Unterkategorie: {plant.subcategory or '-'}
- Standort: {plant.standort or '-'}
- Wasserbedarf: {plant.wasserbedarf or '-'}
- Zehrer: {plant.zehrer or '-'}
- Wuchsform: {plant.wuchsform or '-'}
- Pflanzenfamilie: {plant.pflanzenfamilie or '-'}
- Gute Nachbarn: {', '.join(plant.guteNachbarn) if plant.guteNachbarn else '-'}
- Schlechte Nachbarn: {', '.join(plant.schlechteNachbarn) if plant.schlechteNachbarn else '-'}
- Hinweise: {plant.hinweise or '-'}"""
        )

    system_prompt = (
        'Du bist ein erfahrener Garten- und Mischkultur-Assistent. ' 
        'Analysiere Beete anhand von Mischkultur, Pflanzenfamilien, Zehrern, Wasserbedarf, Standort, Wuchshöhe und Praxis im Beet. ' 
        'Antworte ausschließlich als valides JSON mit den Feldern score, summary, good_pairs, conflicts, recommendations, layout_suggestion.'
    )

    user_prompt = f"""Analysiere dieses Beet:

Beet:
- Name: {data.bed_name}
- Standort: {data.location or '-'}
- Boden: {data.soil or '-'}
- Größe: {data.size or '-'}

Pflanzen:
{chr(10).join(plant_lines)}

Bewerte die Kombination und mache einen konkreten Beetvorschlag."""

    return system_prompt, user_prompt


def call_ollama_json_sync(system_prompt: str, user_prompt: str, model: str, temperature: float):
    schema = {
        'type': 'object',
        'properties': {
            'score': {'type': 'number'},
            'summary': {'type': 'string'},
            'good_pairs': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'plants': {'type': 'array', 'items': {'type': 'string'}},
                        'reason': {'type': 'string'}
                    },
                    'required': ['plants', 'reason']
                }
            },
            'conflicts': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'plants': {'type': 'array', 'items': {'type': 'string'}},
                        'reason': {'type': 'string'}
                    },
                    'required': ['plants', 'reason']
                }
            },
            'recommendations': {'type': 'array', 'items': {'type': 'string'}},
            'layout_suggestion': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'plant': {'type': 'string'},
                        'position': {'type': 'string'},
                        'reason': {'type': 'string'}
                    },
                    'required': ['plant', 'position', 'reason']
                }
            }
        },
        'required': ['score', 'summary', 'good_pairs', 'conflicts', 'recommendations', 'layout_suggestion']
    }
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = client.post(
            f'{OLLAMA_BASE_URL}/api/generate',
            json={
                'model': model,
                'system': system_prompt,
                'prompt': user_prompt,
                'stream': False,
                'format': schema,
                'options': {'temperature': temperature},
            }
        )
        response.raise_for_status()
        data = response.json()
    return json.loads(data.get('response', '{}'))


def merge_analysis(deterministic: dict, llm: Optional[dict], model: Optional[str], source: str):
    if not llm:
        merged = dict(deterministic)
        merged['source'] = source
        merged['model'] = model
        return merged

    merged = dict(deterministic)
    merged['score'] = llm.get('score', deterministic.get('score'))
    merged['summary'] = llm.get('summary') or deterministic.get('summary')

    def dedupe_items(items, key_builder):
        seen = set()
        out = []
        for item in items:
            key = key_builder(item)
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    merged['good_pairs'] = dedupe_items((deterministic.get('good_pairs') or []) + (llm.get('good_pairs') or []), lambda x: tuple(x.get('plants', [])) + (x.get('reason', ''),))
    merged['conflicts'] = dedupe_items((deterministic.get('conflicts') or []) + (llm.get('conflicts') or []), lambda x: tuple(x.get('plants', [])) + (x.get('reason', ''),))
    merged['recommendations'] = list(dict.fromkeys((deterministic.get('recommendations') or []) + (llm.get('recommendations') or [])))
    merged['layout_suggestion'] = llm.get('layout_suggestion') or deterministic.get('layout_suggestion') or []
    merged['source'] = source
    merged['model'] = model
    return merged


def run_analysis_task(task_id: str, payload: dict):
    deterministic = None
    try:
        append_ai_step(task_id, 'validate', 'Eingabedaten werden validiert', 5)
        data = BedRequest(**payload)

        with ai_tasks_lock:
            task = ai_tasks[task_id]
            task['status'] = 'running'
            task['started_at'] = now_iso()
            task['bed_name'] = data.bed_name

        append_ai_step(task_id, 'rules', 'Regelengine prüft Mischkultur und Konflikte', 15)
        deterministic = deterministic_analysis(data)

        cfg = load_config()
        model = cfg.analysis_model or cfg.active_model or DEFAULT_OLLAMA_MODEL
        system_prompt, user_prompt = build_analysis_prompt(data)
        append_ai_step(task_id, 'prompt', f'Prompt wird für Modell {model} vorbereitet', 30)

        append_ai_step(task_id, 'connect', 'Ollama-Erreichbarkeit wird geprüft', 45)
        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                health = client.get(f'{OLLAMA_BASE_URL}/api/tags')
                health.raise_for_status()
        except Exception:
            append_ai_step(task_id, 'fallback', 'Ollama nicht erreichbar, Fallback auf Regelengine', 100)
            finish_ai_task(task_id, status='completed', result=merge_analysis(deterministic, None, None, 'deterministic-fallback'))
            return

        append_ai_step(task_id, 'ollama', f'Ollama-Anfrage läuft mit {model}', 60)
        llm = call_ollama_json_sync(system_prompt, user_prompt, model, cfg.temperature)
        append_ai_step(task_id, 'merge', 'KI-Antwort wird mit Regelengine zusammengeführt', 85)

        result = merge_analysis(deterministic, llm, model, 'ollama+deterministic')
        append_ai_step(task_id, 'done', 'Analyse abgeschlossen', 100)
        finish_ai_task(task_id, status='completed', result=result)
    except Exception as exc:
        append_ai_step(task_id, 'error', f'Analyse fehlgeschlagen: {exc}', 100)
        fallback = merge_analysis(deterministic or {'score': 0, 'summary': 'Analyse fehlgeschlagen', 'good_pairs': [], 'conflicts': [], 'recommendations': [], 'layout_suggestion': [], 'source': 'failed'}, None, None, 'error') if deterministic else None
        finish_ai_task(task_id, status='failed', result=fallback, error=str(exc), progress=100)


def normalize_progress(status: str, completed: Optional[int], total: Optional[int]) -> int:
    if total and completed is not None and total > 0:
        return int(max(0, min(100, (completed / total) * 100)))
    lowered = (status or '').lower()
    if 'success' in lowered or 'complete' in lowered:
        return 100
    if 'pulling manifest' in lowered:
        return 5
    if 'verifying' in lowered:
        return 92
    return 0


async def call_ollama_json(system_prompt: str, user_prompt: str):
    cfg = load_config()
    model = cfg.analysis_model or cfg.active_model or DEFAULT_OLLAMA_MODEL
    return call_ollama_json_sync(system_prompt, user_prompt, model, cfg.temperature)


def deterministic_analysis(data: BedRequest):
    warnings = []
    positives = []

    plants = data.plants
    for i, plant_a in enumerate(plants):
        for plant_b in plants[i + 1:]:
            label_a = f"{plant_a.name} {plant_a.sort}".strip()
            label_b = f"{plant_b.name} {plant_b.sort}".strip()

            bad_match = any(plant_b.name in item or item in plant_b.name for item in plant_a.schlechteNachbarn) or \
                any(plant_a.name in item or item in plant_a.name for item in plant_b.schlechteNachbarn)
            if bad_match:
                warnings.append({'plants': [label_a, label_b], 'reason': 'schlechte Nachbarschaft laut Regelbasis'})

            if plant_a.pflanzenfamilie and plant_a.pflanzenfamilie == plant_b.pflanzenfamilie and plant_a.pflanzenfamilie in {'Kreuzblütler', 'Nachtschattengewächse'}:
                warnings.append({'plants': [label_a, label_b], 'reason': f'gleiche Pflanzenfamilie ({plant_a.pflanzenfamilie})'})

            good_match = any(plant_b.name in item or item in plant_b.name for item in plant_a.guteNachbarn) or \
                any(plant_a.name in item or item in plant_a.name for item in plant_b.guteNachbarn)
            if good_match:
                positives.append({'plants': [label_a, label_b], 'reason': 'gute Mischkultur laut Regelbasis'})

    score = 80
    score -= min(len(warnings) * 10, 50)
    score += min(len(positives) * 5, 15)
    score = max(10, min(score, 100))

    recommendations = []
    if warnings:
        recommendations.append('Problematische Kombinationen besser auf zwei Beete verteilen.')
    if positives:
        recommendations.append('Bewährte Partner möglichst nahe zusammen platzieren.')
    if not recommendations:
        recommendations.append('Kombination wirkt neutral. Wasserbedarf und Platzbedarf im Blick behalten.')

    layout = []
    for plant in plants:
        position = 'Mitte'
        if 'hoch' in (plant.wuchsform or '') or 'rank' in (plant.wuchsform or ''):
            position = 'Hinten'
        elif 'niedrig' in (plant.wuchsform or '') or 'unterirdisch' in (plant.wuchsform or ''):
            position = 'Vorne'
        layout.append({'plant': f"{plant.name} {plant.sort}".strip(), 'position': position, 'reason': f"Wuchsform: {plant.wuchsform or 'unbekannt'}"})

    summary = 'Die Kombination ist insgesamt brauchbar.'
    if score >= 85:
        summary = 'Die Kombination ist gut geeignet.'
    elif score < 60:
        summary = 'Die Kombination ist kritisch und sollte überarbeitet werden.'

    return {
        'score': score,
        'summary': summary,
        'good_pairs': positives,
        'conflicts': warnings,
        'recommendations': recommendations,
        'layout_suggestion': layout,
        'source': 'deterministic'
    }


def run_pull_task(task_id: str, model: str):
    with pull_semaphore:
        with pull_tasks_lock:
            task = pull_tasks[task_id]
            task.update({'status': 'running', 'started_at': now_iso(), 'log': [f'Starte Pull für {model}'], 'progress': 1})
        try:
            with httpx.stream('POST', f'{OLLAMA_BASE_URL}/api/pull', json={'model': model, 'stream': True}, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    if isinstance(line, bytes):
                        line = line.decode('utf-8', errors='ignore')
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        payload = {'status': line}
                    status = payload.get('status', '')
                    completed = payload.get('completed')
                    total = payload.get('total')
                    entry = {
                        'timestamp': now_iso(),
                        'status': status,
                        'completed': completed,
                        'total': total,
                        'digest': payload.get('digest'),
                    }
                    progress = normalize_progress(status, completed, total)
                    with pull_tasks_lock:
                        task = pull_tasks[task_id]
                        task['progress'] = max(task.get('progress', 0), progress)
                        task['last_update'] = entry['timestamp']
                        task['current_status'] = status
                        task.setdefault('events', []).append(entry)
                        task['events'] = task['events'][-300:]
                        if status:
                            task.setdefault('log', []).append(status)
                            task['log'] = task['log'][-80:]
            with pull_tasks_lock:
                task = pull_tasks[task_id]
                task.update({'status': 'completed', 'progress': 100, 'finished_at': now_iso(), 'current_status': 'completed'})
                task.setdefault('log', []).append('Modell erfolgreich installiert')
            append_pull_history({'task_id': task_id, 'model': model, 'status': 'completed', 'finished_at': now_iso()})
            try:
                models = httpx.get(f'{OLLAMA_BASE_URL}/api/tags', timeout=REQUEST_TIMEOUT_SECONDS).json().get('models', [])
                update_model_cache(models)
            except Exception:
                pass
        except Exception as exc:
            with pull_tasks_lock:
                task = pull_tasks[task_id]
                task.update({'status': 'failed', 'finished_at': now_iso(), 'error': str(exc), 'current_status': 'failed'})
                task.setdefault('log', []).append(f'Fehler: {exc}')
            append_pull_history({'task_id': task_id, 'model': model, 'status': 'failed', 'finished_at': now_iso(), 'error': str(exc)})


@app.post('/api/ai/analyze-bed-task')
def create_analyze_bed_task(body: BedRequest):
    task_id = str(uuid.uuid4())
    task = {
        'id': task_id,
        'type': 'analyze-bed',
        'status': 'queued',
        'progress': 0,
        'created_at': now_iso(),
        'bed_name': body.bed_name,
        'steps': [],
        'result': None,
    }
    with ai_tasks_lock:
        ai_tasks[task_id] = task
    thread = threading.Thread(target=run_analysis_task, args=(task_id, body.model_dump()), daemon=True)
    thread.start()
    return {'task_id': task_id, 'status': 'queued'}


@app.get('/api/ai/analyze-bed-task/{task_id}')
def get_analyze_bed_task(task_id: str):
    with ai_tasks_lock:
        task = ai_tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail='Task nicht gefunden')
        return task


@app.get('/api/ai/analyze-bed-tasks')
def list_analyze_bed_tasks():
    with ai_tasks_lock:
        tasks = list(ai_tasks.values())
    tasks.sort(key=lambda item: item.get('created_at', ''), reverse=True)
    return {'tasks': tasks[:30]}


@app.get('/api/health')
async def health():
    ollama_reachable = False
    installed_models = []
    try:
        models, _ = await refresh_model_cache()
        ollama_reachable = True
        installed_models = [item.get('name') for item in models if item.get('name')]
    except Exception:
        ollama_reachable = False

    cfg = load_config()
    return {
        'status': 'ok',
        'ollama_reachable': ollama_reachable,
        'active_model': get_active_model(),
        'configured_models': cfg.preferred_models,
        'installed_models': installed_models,
    }


@app.get('/api/config')
def get_config():
    config = load_config()
    return {
        'config': config.model_dump(),
        'defaults': {'models': DEFAULT_MODELS, 'active_model': DEFAULT_OLLAMA_MODEL},
    }


@app.put('/api/config')
def update_config(config: AppConfig):
    if not config.active_model:
        raise HTTPException(status_code=400, detail='active_model darf nicht leer sein')
    if not config.preferred_models:
        config.preferred_models = list(DEFAULT_MODELS)
    return {'config': save_config(config).model_dump()}


@app.get('/api/ollama/models')
async def ollama_models():
    models, cache = await refresh_model_cache()
    return {
        'models': [
            {
                'name': item.get('name'),
                'size': item.get('size'),
                'modified_at': item.get('modified_at'),
                'digest': item.get('digest'),
            }
            for item in models
        ],
        'cache': cache,
    }


@app.get('/api/ollama/cache')
def ollama_cache():
    return read_json_file(MODEL_CACHE_PATH, {'versions': {}, 'snapshots': []})


@app.get('/api/ollama/pull-tasks')
def list_pull_tasks():
    with pull_tasks_lock:
        tasks = list(pull_tasks.values())
    tasks.sort(key=lambda item: item.get('created_at', ''), reverse=True)
    return {'tasks': tasks}


@app.get('/api/ollama/pull-tasks/{task_id}')
def get_pull_task(task_id: str):
    with pull_tasks_lock:
        task = pull_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task nicht gefunden')
    return task


@app.post('/api/ollama/pull')
def ollama_pull(body: PullRequest):
    model = body.model.strip()
    if not model:
        raise HTTPException(status_code=400, detail='model fehlt')
    task_id = str(uuid.uuid4())
    task = {
        'id': task_id,
        'model': model,
        'status': 'queued',
        'progress': 0,
        'created_at': now_iso(),
        'log': [f'Queue: {model}'],
        'events': [],
        'current_status': 'queued',
    }
    with pull_tasks_lock:
        pull_tasks[task_id] = task
    append_pull_history({'task_id': task_id, 'model': model, 'status': 'queued', 'created_at': task['created_at']})
    thread = threading.Thread(target=run_pull_task, args=(task_id, model), daemon=True)
    thread.start()
    return task




@app.get('/api/admin/ollama/health')
async def admin_ollama_health():
    try:
        models = await fetch_installed_models()
        return {
            'status': 'ok',
            'reachable': True,
            'installed_count': len(models),
            'default_model': get_active_model(),
            'curated_models': CURATED_MODELS,
        }
    except Exception as exc:
        return {
            'status': 'error',
            'reachable': False,
            'installed_count': 0,
            'default_model': get_active_model(),
            'curated_models': CURATED_MODELS,
            'detail': str(exc),
        }


@app.get('/api/admin/ollama/models')
async def admin_list_models():
    models, cache = await refresh_model_cache()
    config = load_config()
    rows = []
    for item in models:
        rows.append({
            'name': item.get('name'),
            'size': item.get('size'),
            'modified_at': item.get('modified_at'),
            'digest': item.get('digest'),
            'details': item.get('details') or {},
            'is_default': item.get('name') == (config.analysis_model or config.active_model),
            'cached_versions': len((cache.get('versions') or {}).get(item.get('name'), [])),
        })
    rows.sort(key=lambda x: x.get('name') or '')
    return {'models': rows, 'curated_models': CURATED_MODELS, 'default_model': get_active_model(), 'cache': cache}


@app.get('/api/admin/ollama/models/{model_name:path}')
async def admin_show_model(model_name: str):
    details = await fetch_model_details(model_name)
    return {'model': model_name, 'details': details}


@app.delete('/api/admin/ollama/models/{model_name:path}')
async def admin_delete_model(model_name: str):
    result = await delete_model_remote(model_name)
    try:
        await refresh_model_cache()
    except Exception:
        pass
    return {'ok': True, 'result': result}


@app.post('/api/admin/ollama/copy')
async def admin_copy_model(body: CopyRequest):
    if not body.source.strip() or not body.destination.strip():
        raise HTTPException(status_code=400, detail='source und destination sind erforderlich')
    result = await copy_model_remote(body.source.strip(), body.destination.strip())
    try:
        await refresh_model_cache()
    except Exception:
        pass
    return {'ok': True, 'result': result}


@app.post('/api/admin/ollama/generate')
async def admin_generate(body: GenerateAdminRequest):
    payload = {
        'model': body.model,
        'prompt': body.prompt,
        'stream': False,
        'keep_alive': body.keep_alive,
        'options': {'temperature': body.temperature},
    }
    if body.system:
        payload['system'] = body.system
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.post(f'{OLLAMA_BASE_URL}/api/generate', json=payload)
        response.raise_for_status()
        data = response.json()
    return data


@app.post('/api/admin/ollama/generate-task')
def admin_generate_task(body: GenerateTaskRequest):
    if not body.model.strip() or not body.prompt.strip():
        raise HTTPException(status_code=400, detail='model und prompt sind erforderlich')
    task = create_admin_query_task(body)
    return {'task_id': task['id'], 'status': task['status']}


@app.get('/api/admin/ollama/generate-task/{task_id}')
def admin_get_generate_task(task_id: str):
    with admin_query_tasks_lock:
        task = admin_query_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task nicht gefunden')
    return task


@app.get('/api/admin/ollama/generate-tasks')
def admin_list_generate_tasks():
    with admin_query_tasks_lock:
        tasks = list(admin_query_tasks.values())
    tasks.sort(key=lambda item: item.get('created_at', ''), reverse=True)
    return {'tasks': tasks[:30]}


@app.post('/api/ai/analyze-bed')
async def analyze_bed(data: BedRequest):
    fallback = deterministic_analysis(data)
    system_prompt = (
        'Du bist ein Garten- und Mischkultur-Assistent. Analysiere Beetkombinationen anhand von Mischkultur, '
        'Pflanzenfamilien, Zehrerklassen, Wasserbedarf, Standort, Wuchsform und Platzbedarf. Antworte nur als valides JSON.'
    )
    plant_lines = []
    for index, plant in enumerate(data.plants, start=1):
        plant_lines.append(
            f"{index}. {plant.name} {plant.sort}\n"
            f"- Kategorie: {plant.category}\n"
            f"- Standort: {plant.standort}\n"
            f"- Wasserbedarf: {plant.wasserbedarf}\n"
            f"- Zehrer: {plant.zehrer}\n"
            f"- Wuchsform: {plant.wuchsform}\n"
            f"- Pflanzenfamilie: {plant.pflanzenfamilie}\n"
            f"- Gute Nachbarn: {', '.join(plant.guteNachbarn) if plant.guteNachbarn else '-'}\n"
            f"- Schlechte Nachbarn: {', '.join(plant.schlechteNachbarn) if plant.schlechteNachbarn else '-'}\n"
            f"- Hinweise: {plant.hinweise or '-'}"
        )
    user_prompt = (
        f"Beetname: {data.bed_name}\n"
        f"Standort: {data.location}\n"
        f"Boden: {data.soil}\n"
        f"Größe: {data.size}\n\n"
        'Pflanzen:\n' + '\n\n'.join(plant_lines) + '\n\n'
        'Gib Score, Zusammenfassung, gute Kombinationen, Konflikte, Empfehlungen und Layoutvorschlag zurück.'
    )
    try:
        result = await call_ollama_json(system_prompt, user_prompt)
        result['source'] = 'ollama'
        result['model'] = get_active_model()
        return result
    except Exception:
        fallback['model'] = get_active_model()
        return fallback


@app.post('/api/ai/auto-plan')
async def auto_plan(data: AutoPlanRequest):
    planned_beds = []
    for bed in data.beds:
        ids = list(dict.fromkeys(bed.seedIds))
        planned_beds.append({
            'id': bed.id,
            'name': bed.name,
            'location': bed.location,
            'soil': bed.soil,
            'size': bed.size,
            'seedIds': ids[:6]
        })
    return {
        'beds': planned_beds,
        'summary': 'Auto-Plan ausgeführt. Doppelte Einträge wurden entfernt und Beetlisten konsolidiert.',
        'model': get_active_model(),
    }
