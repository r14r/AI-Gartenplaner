import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://ollama:11434').rstrip('/')
MODELS = [item.strip() for item in os.getenv('OLLAMA_MODELS', '').split(',') if item.strip()]
PARALLEL = max(1, int(os.getenv('OLLAMA_INIT_PARALLEL', '2')))
POLL_SECONDS = max(1, int(os.getenv('OLLAMA_INIT_POLL_SECONDS', '2')))


def now():
    return datetime.now(timezone.utc).isoformat()


def log(message: str):
    print(f"[ollama-init {now()}] {message}", flush=True)


def http_json(method: str, path: str, payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    with urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode('utf-8'))


def wait_for_ollama():
    log(f"Waiting for Ollama at {BASE_URL}")
    while True:
        try:
            payload = http_json('GET', '/api/tags')
            log(f"Ollama ready, currently installed: {len(payload.get('models', []))}")
            return
        except Exception as exc:
            log(f"Still waiting: {exc}")
            time.sleep(POLL_SECONDS)


def pull_model(model: str):
    payload = json.dumps({'model': model, 'stream': True}).encode('utf-8')
    req = Request(f"{BASE_URL}/api/pull", data=payload, headers={'Content-Type': 'application/json'}, method='POST')
    log(f"Start pulling {model}")
    with urlopen(req, timeout=3600) as response:
        for raw_line in response:
            line = raw_line.decode('utf-8', errors='ignore').strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                log(f"{model}: {line}")
                continue
            status = event.get('status', '')
            completed = event.get('completed')
            total = event.get('total')
            if completed is not None and total:
                percent = int((completed / total) * 100)
                log(f"{model}: {status} {percent}%")
            else:
                log(f"{model}: {status}")
    log(f"Finished pulling {model}")
    return model


def main():
    if not MODELS:
        log('No models configured. Nothing to do.')
        return 0
    wait_for_ollama()
    log(f"Installing {len(MODELS)} model(s) with parallelism={PARALLEL}")
    failures = []
    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        futures = {pool.submit(pull_model, model): model for model in MODELS}
        for future in as_completed(futures):
            model = futures[future]
            try:
                future.result()
            except Exception as exc:
                failures.append((model, str(exc)))
                log(f"FAILED {model}: {exc}")
    if failures:
        log(f"Completed with failures: {failures}")
        return 1
    log('All configured models are installed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
