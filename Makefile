# Makefile for Linux System Health Dashboard
# Phase 1.0: Standard entry points for development and CI

.PHONY: check test lint typecheck type-check arch format coverage help

# Default target
help:
	@echo "Available targets (run from repository root):"
	@echo "  check      - Run all fast-tier checks (lint, typecheck, arch, test)"
	@echo "  test       - Run backend tests (default tier, excluding perf/soak/quarantine)"
	@echo "  lint       - Run Ruff checks"
	@echo "  format     - Check Ruff formatting"
	@echo "  typecheck  - Run strict mypy"
	@echo "  type-check - Alias for typecheck"
	@echo "  arch       - Run architecture checks with import-linter"
	@echo "  coverage   - Run tests with coverage report"

# check: Fast tier - everything the CI runs
check: lint typecheck arch test

# test: Backend tests (default tier, excluding perf, soak, privileged, quarantine)
test:
	cd backend && uv run pytest -m "not perf and not soak and not privileged and not quarantine"

# lint: Run Ruff checks
lint:
	cd backend && uv run ruff check .

# format: Check Ruff formatting
format:
	cd backend && uv run ruff format --check .

# typecheck: Run strict mypy
typecheck:
	cd backend && uv run mypy --strict src

# type-check: Alias for typecheck
type-check: typecheck

# arch: Run architecture checks with import-linter
arch:
	cd backend && uv run lint-imports

# coverage: Run tests with coverage report
coverage:
	cd backend && uv run pytest --cov=src/monitor --cov-report=term-missing
