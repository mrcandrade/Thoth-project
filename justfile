# Uso: `just <alvo>`   (instale o `just`: https://github.com/casey/just)
# Sem `just`, rode os comandos à mão.

# cria venv, instala deps + extras dev, copia .env
setup:
    uv venv && uv pip install -e ".[dev]"
    cp -n .env.example .env || true

# baixa o modelo de mão do MediaPipe (hand_landmarker.task)
models:
    python scripts/download_models.py

# sobe o painel web (dashboard de controle + espelhar a mão)
web:
    python scripts/web.py

# baixa a voz PT-BR do Piper (TTS do agente)
piper:
    python scripts/download_piper.py

# conversa por voz com o Marco (Fase 1 do agente)
voz:
    python scripts/voice_chat.py

# compila e grava o firmware (arduino-cli)
flash port="COM17":
    python scripts/flash_firmware.py --port {{port}}

# REPL manual do protocolo serial (debug dos comandos)
serial port="COM17":
    python scripts/serial_repl.py --port {{port}}

# lista câmeras e portas seriais
devices:
    python scripts/check_devices.py

# testes (exclui os que exigem hardware)
test:
    pytest -m "not hardware"

lint:
    ruff check src tests
