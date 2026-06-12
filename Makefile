# Equivalente ao justfile para ambientes sem `just`.
# Em Windows, rode via `make` (Git Bash / MSYS) ou copie os comandos manualmente.

PORT ?= COM5

.PHONY: setup models run api flash serial devices test test-hw lint

setup:
	python -m venv .venv
	. .venv/bin/activate && pip install -e ".[dev]"
	cp -n .env.example .env || true

models:
	python scripts/download_models.py

run:
	python -m thoth

api:
	uvicorn thoth.api.server:app --reload --host 127.0.0.1 --port 8000

flash:
	python scripts/flash_firmware.py --port $(PORT)

serial:
	python scripts/serial_repl.py --port $(PORT)

devices:
	python scripts/check_devices.py

test:
	pytest -m "not hardware"

test-hw:
	pytest -m hardware

lint:
	ruff check src tests && mypy src
