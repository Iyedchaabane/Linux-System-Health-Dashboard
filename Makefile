.PHONY: help check test lint typecheck type-check arch clean up down restart logs status build test-all

help:
	@echo "Available targets:"
	@echo "  help       - show this help"
	@echo "  up         - start via docker compose"
	@echo "  down       - stop via docker compose"
	@echo "  restart    - restart stack"
	@echo "  logs       - tail logs"
	@echo "  status     - compose status"
	@echo "  build      - docker compose build"
	@echo "  test       - pytest backend only"
	@echo "  test-all   - backend + frontend"
	@echo "  lint       - ruff + mypy + tsc/eslint"
	@echo "  typecheck  - mypy and tsc"
	@echo "  arch       - import-linter"
	@echo "  clean      - remove containers/images (volumes untouched; requires 'yes')"

REPO_ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
check: lint typecheck arch test

up:
	docker compose up -d --build

down:
	docker compose down

restart: down up

logs:
	docker compose logs -f --tail=100

status:
	docker compose ps

build:
	docker compose build

test:
	cd backend && uv run pytest -m "not perf and not soak and not privileged and not quarantine"

test-all: test
	cd frontend && npm run test

lint:
	cd backend && uv run ruff check . && uv run mypy --strict src && cd ../frontend && npm run lint && npm run typecheck

typecheck:
	cd backend && uv run mypy --strict src && cd ../frontend && npm run typecheck

arch:
	cd backend && uv run lint-imports

clean:
	@echo "WARNING: removes compose containers/images (volumes retained)."
	@read -p "Type 'yes' to continue: " ans; [ "$$ans" = "yes" ] && (cd $(REPO_ROOT) && docker compose down --rmi local) || echo "cancelled"
