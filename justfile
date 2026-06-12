# Uso: `just <alvo>`   (instale o `just`: https://github.com/casey/just)
# Em Windows sem `just`, use os comandos equivalentes do Makefile ou rode-os à mão.

# cria venv, instala deps + extras dev, copia .env
setup:
    uv venv && uv pip install -e ".[dev]"
    cp -n .env.example .env || true

# baixa os .task do MediaPipe
models:
    python scripts/download_models.py

# enrolla um rosto: just enroll "Prof. Fulano"
enroll name:
    python scripts/enroll_face.py --name "{{name}}" --src data/known_faces

# sobe orquestrador + agentes
run:
    python -m thoth

# apenas a API/telemetria
api:
    uvicorn thoth.api.server:app --reload --host 127.0.0.1 --port 8000

# compila e grava o firmware custom (arduino-cli)
flash port="COM5":
    python scripts/flash_firmware.py --port {{port}}

# REPL manual do protocolo serial (debug sem agentes)
serial port="COM5":
    python scripts/serial_repl.py --port {{port}}

# lista câmeras, microfones e portas seriais
devices:
    python scripts/check_devices.py

# testes (exclui os que exigem hardware)
test:
    pytest -m "not hardware"

# testes com a mão física conectada
test-hw:
    pytest -m hardware

lint:
    ruff check src tests && mypy src
