.DEFAULT_GOAL := help

# Tokens for `make run` / `make compose-up` come from .env (see .env.example)
-include .env
export

.PHONY: help install lint fmt test ci run docker-build docker-run compose-up compose-down dev-up dev-down dev-logs helm-lint helm-template clean

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*?##/ {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies into .venv
	uv sync

lint: ## Ruff: lint + formatting check
	uv run ruff check
	uv run ruff format --check

fmt: ## Ruff: autofix lint findings and reformat
	uv run ruff check --fix
	uv run ruff format

test: ## Run the test suite
	uv run pytest

ci: lint test ## Everything CI runs

run: ## Run the app locally with reload (reads .env)
	uv run uvicorn am_tg.main:create_app --factory --reload

docker-build: ## Build the Docker image (am-tg:local)
	docker build -t am-tg:local .

docker-run: docker-build ## Run the image locally (reads .env, mounts sources.yaml)
	docker run --rm -p 127.0.0.1:9119:9119 \
		-v $(PWD)/sources.yaml:/etc/am-tg/sources.yaml:ro \
		-e AM_TG_SOURCES_FILE=/etc/am-tg/sources.yaml \
		--env-file .env \
		am-tg:local

compose-up: ## Start via docker compose (builds if needed)
	docker compose up -d --build

compose-down: ## Stop docker compose services
	docker compose down

DEV_COMPOSE = docker compose -f docker-compose.yml -f dev/docker-compose.yml

dev-up: ## Start the dev stack: am-tg + prometheus + alertmanager + grafana (:3000)
	$(DEV_COMPOSE) up -d --build

dev-down: ## Stop the dev stack
	$(DEV_COMPOSE) down

dev-logs: ## Tail am-tg logs from the dev stack
	$(DEV_COMPOSE) logs -f am-tg

helm-lint: ## Lint the Helm chart
	helm lint deploy/helm/am-tg

helm-template: ## Render the Helm chart with example values
	helm template am-tg deploy/helm/am-tg \
		--set 'sources.defaults.bot_token=$${TG_BOT_TOKEN}' \
		--set 'sources.sources[0].name=example' \
		--set 'sources.sources[0].token=$${AM_TG_TOKEN_EXAMPLE}' \
		--set 'sources.sources[0].chat_id=-100123456789'

clean: ## Remove venv and tool caches
	rm -rf .venv .pytest_cache .ruff_cache
