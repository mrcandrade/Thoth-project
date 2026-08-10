# Jokenpô Robótico 🤖✊✋✌️

Jogue **pedra, papel e tesoura** contra a mão protética **HACKberry** do projeto
Thoth, pelo navegador. A visão computacional lê o seu gesto pela webcam, o robô
sorteia a jogada e a **executa fisicamente na mão**, o resultado é julgado, o
**placar** é atualizado e tudo é **narrado por voz**.

Construído sobre o **framework Agno** (workflow determinístico), com **agentes
usando a API da Anthropic (Claude)**, e integrado ao hardware/visão/voz do Thoth.

---

## Como funciona (uma rodada = uma execução do workflow Agno)

```
detectar_gesto → sortear_jogada → mover_braco → julgar_rodada → narrar_resultado
```

| Step | O que faz | Tecnologia |
|------|-----------|------------|
| `detectar_gesto`  | Lê seu gesto (pedra/papel/tesoura) | MediaPipe (local) + **Claude Vision** como fallback |
| `sortear_jogada`  | Sorteia a jogada do robô (justo) | RNG puro |
| `mover_braco`     | Move a mão HACKberry: pedra=✊FIST, papel=✋OPEN, tesoura=✌️POINT | Serial (HandLink do Thoth) |
| `julgar_rodada`   | Vitória / derrota / empate + placar | lógica pura |
| `narrar_resultado`| Narra o resultado e o placar + fala | **Agente Claude (Agno)** + TTS |

Se a câmera não vir o gesto, a rodada é encerrada com um pedido gentil (sem contar
ponto). Se a mão não estiver conectada, o jogo continua sem o movimento físico.

## Arquitetura

```
jokenpo/
  orquestrador.py                # servidor web (FastAPI): placar, /video, API do jogo
  workflow_jokenpo_robotico.py   # o fluxo Agno com os 5 steps (async)
  providers_jokenpo_robotico.py  # modelos + fallback (anthropic → openai → cerebras)
  config_jokenpo_robotico.py     # env/modelos/paths
  game/
    logic.py        # regras puras (sortear, julgar, mapeamento de gestos)
    state.py        # placar + última rodada + frame do vídeo (thread-safe)
    vision.py       # GestureClassifier (MediaPipe) + classificar_com_vlm (Claude)
    arm.py          # ArmAdapter sobre o ArmController do Thoth
    narrator.py     # locutor (agente Claude/Agno) + síntese de voz (TTS do Thoth)
    services.py     # câmera em thread + amostragem de gesto + wiring
  web/static/index.html          # placar visual (SPA)
  tests/test_logic.py            # testes da lógica (sem hardware)
```

## Rodar

Pré-requisitos: a mão HACKberry no serial (opcional), uma webcam e o modelo do
MediaPipe do Thoth (`../models/mediapipe/hand_landmarker.task` — baixe com
`python ../scripts/download_models.py`).

```bash
cd jokenpo
python -m venv .venv && .venv\Scripts\Activate.ps1   # Windows (PowerShell)
pip install -r requirements.txt                       # instala Thoth (-e ..) + Agno + Anthropic
copy .env.example .env                                 # e preencha ANTHROPIC_API_KEY
python orquestrador.py
```

Abra **http://127.0.0.1:7777**, clique em **Começar** e depois em **JOGAR RODADA**.
Sem câmera, use os botões ✊ ✋ ✌️ (jogada manual).

## API

| Método | Rota | Descrição |
|--------|------|-----------|
| GET  | `/`            | Placar (SPA) |
| GET  | `/video`       | Stream MJPEG da câmera (com landmarks) |
| GET  | `/api/estado`  | Placar + status (braço/câmera) |
| POST | `/api/jogar`   | Roda uma rodada. Body opcional `{"gesto":"pedra"}` (manual) |
| POST | `/api/saudar`  | Saudação inicial (texto + áudio) |
| POST | `/api/reset`   | Zera o placar |
| POST | `/api/estop`   | Parada de emergência (abre a mão) |

## Notas

- **Provider principal:** Anthropic/Claude (`claude-haiku-4-5`). Sem chave, o jogo
  ainda roda com narração em frases prontas e detecção só por MediaPipe.
- **Justiça:** o robô sorteia de forma independente do seu gesto (RNG puro).
- **Tesoura:** os "três dedos" da HACKberry movem juntos, então a tesoura física é
  aproximada por `POINT` (indicador apontando).
- Configurações de hardware/voz vêm do `.env` (compartilham as chaves do Thoth).
