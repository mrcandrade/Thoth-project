# Guia de Desenvolvimento — Thoth (software)

Guia de setup do **sistema de IA agêntico**. A visão acadêmica do projeto está
no `README.md` da raiz; a especificação completa, em `docs/plano/`.

> O **Thoth** transforma a mão protética **HACKberry** (3 servos de dedos) em um
> assistente robótico multiagente (Agno + visão + voz). Leia antes:
> [`docs/hardware.md`](hardware.md) (o que o hardware faz/não faz) e
> [`docs/protocol.md`](protocol.md) (protocolo serial).

## Requisitos

- **Python 3.11+**
- **arduino-cli** (para gravar o firmware) + core `arduino:avr`
- **Webcam Logitech** (USB), **microfone padrão do Windows**, **alto-falante padrão do notebook**
- Placa **HACKberry Hand Board Mk2** (Arduino Nano) com a mão montada, ligada por **micro-USB**
- Chaves de API: **Anthropic** (Claude), **Groq**, **Cerebras**

## Dispositivos (seu setup)

- **Câmera (Logitech):** rode `python scripts/check_devices.py` para descobrir o
  índice e ajuste `CAMERA_INDEX` no `.env` (geralmente `0` ou `1`).
- **Microfone:** deixe `MIC_DEVICE=` vazio → usa o **microfone padrão do Windows**.
- **Saída de áudio:** deixe `AUDIO_OUTPUT_DEVICE=` vazio → fala no **alto-falante
  padrão do notebook** (TTS via SAPI5 do Windows, sem custo de API).
- **Braço:** plugue o Arduino no USB e defina `SERIAL_PORT=COMx` (o `check_devices`
  também lista as portas seriais).

## Ativação por voz ("Mendes")

O sistema chama-se **Mendes**. Diga **"Mendes"** e na sequência o comando — ex.:
*"Mendes, aperte minha mão"*, *"Mendes, aponte"*, *"Mendes, quem está na sala?"*.
No modo padrão (`WAKE_MODE=phrase`) a palavra é detectada na transcrição (Groq
Whisper), sem precisar treinar um modelo de wake word.

## Interface web (dashboard)

Com `python -m thoth` rodando, abra **http://127.0.0.1:8000**. O painel mostra:
o **vídeo da visão computacional** (com caixas/nomes), o **status da mão** (modo e
ângulos), a **transcrição da voz**, um **log de eventos** e **botões de controle
manual** (abrir/punho/apontar/pinça/apertar) + **PARADA DE EMERGÊNCIA**.

## Setup

```powershell
# 1) ambiente + dependências
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"          # ou: just setup

# 2) configuração
Copy-Item .env.example .env      # edite e preencha as chaves/SERIAL_PORT

# 3) modelos de visão (MediaPipe .task)
python scripts/download_models.py

# 4) diagnóstico de dispositivos (descubra câmera/porta/mic)
python scripts/check_devices.py
```

## Fluxo por fase (ver `docs/plano/` Seção 3)

| Fase | Comando | O que valida |
|------|---------|--------------|
| 1–2  | `python scripts/flash_firmware.py --port COM5` → `python scripts/serial_repl.py --port COM5` | Firmware + protocolo serial (digite `open`, `shake`, `point`…). |
| 1–2  | `uvicorn thoth.api.server:app --reload` → POST `/command {"gesto":"shake"}` | Atuação via API, sem agentes. |
| 3–4  | `python scripts/enroll_face.py --name "Prof. Fulano"` | Enrollment + reconhecimento facial. |
| 5    | (configure `GROQ_API_KEY`) | Wake word → VAD → STT. |
| 6–7  | `python -m thoth`  (ou `just run`) → abra **http://127.0.0.1:8000** | Orquestrador Agno + percepção + atuação + **dashboard web** + voz do **Mendes**. |

## Testes e qualidade

```powershell
pytest -m "not hardware"     # testes sem hardware
pytest -m hardware           # exige a mão conectada
ruff check src tests
mypy src
```

## Princípios de arquitetura (resumo)

- **Injeção de config:** só `core/config.py` lê o ambiente; o resto recebe `Settings`.
- **Fábrica de modelos:** só `llm/factory.py` instancia Claude/Groq/Cerebras.
- **Limites em um lugar:** `safety/limits.py` é a fonte única (espelha o firmware).
- **Camadas desacopladas:** percepção e atuação só conversam pelo `core/event_bus.py`.
- **Controle de baixo nível no firmware:** slew-rate, clamp, watchdog e e-stop
  vivem no Arduino — o LLM é *soft-real-time* e nunca está no laço crítico.
