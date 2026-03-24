set dotenv-load := true

compose := "docker compose"

default:
    @just --list

up:
    {{compose}} up

up-d:
    {{compose}} up -d

build:
    {{compose}} build

rebuild:
    {{compose}} build --no-cache
    {{compose}} up -d

down:
    {{compose}} down

ps:
    {{compose}} ps

logs:
    {{compose}} logs -f

logs-service service:
    {{compose}} logs -f {{service}}

logs-frontend:
    {{compose}} logs -f frontend

logs-backend:
    {{compose}} logs -f backend

logs-ollama:
    {{compose}} logs -f ollama

logs-init:
    {{compose}} logs -f ollama-init

init-models:
    {{compose}} --profile init up --no-deps ollama-init

ollama-list:
    {{compose}} exec ollama ollama list

ollama-pull model:
    {{compose}} exec ollama ollama pull {{model}}

urls:
    @echo "Frontend: http://localhost:{{env_var('FRONTEND_PORT_PUBLIC')}}"
    @echo "Backend:  http://localhost:{{env_var('BACKEND_PORT_PUBLIC')}}/docs"
    @echo "Ollama:   http://localhost:{{env_var('OLLAMA_PORT_PUBLIC')}}"

health:
    @echo "Backend health:"
    @curl -fsS "http://localhost:{{env_var('BACKEND_PORT_PUBLIC')}}/api/health" || true
    @echo ""
    @echo "Ollama tags:"
    @curl -fsS "http://localhost:{{env_var('OLLAMA_PORT_PUBLIC')}}/api/tags" || true
    @echo ""

bootstrap:
    {{compose}} up -d ollama backend frontend
    just init-models
    just urls

clean:
    {{compose}} down

reset:
    {{compose}} down -v
    docker volume rm -f {{env_var('OLLAMA_VOLUME_NAME')}} || true
    docker volume rm -f {{env_var('BACKEND_DATA_VOLUME_NAME')}} || true
