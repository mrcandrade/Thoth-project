## 4. Tecnologias

Esta seção justifica cada dependência do Projeto Thoth no contexto real do hardware (a **mão protética HACKberry** — três servos de dedo, sem atuador de pulso/braço) e do pipeline cognitivo (visão + voz + agentes). Para cada tecnologia: **papel exato no sistema**, **versão/instalação**, **por que esta escolha** e **1–2 alternativas com trade-offs**. As versões e IDs de modelo refletem a pesquisa de junho/2026; onde a pesquisa marcou incerteza, o texto sinaliza defensivamente — confirme o ID na doc oficial antes de fixar em produção.

> **Premissa de versão:** o ecossistema `agno` migrou para a linha **v2.x** (API diferente da 1.x). Todo o código deste plano assume `agno>=2.6`. A versão verificada mais recente é **2.6.13** (2026-06-10).

### 4.1 Matriz-resumo de tecnologias

| Biblioteca | Camada | Papel | Por que | Alternativa | Roda em CPU? | Licença |
|---|---|---|---|---|---|---|
| `agno` | Orquestração | Framework multiagente (`Agent`, `Team`, tools, `session_state`) | Multi-provedor sem lock-in, tools = funções Python, estado compartilhado entre agentes | LangGraph / CrewAI (mais pesados, mais opinativos) | Sim (LLM é remoto) | MPL-2.0 |
| `anthropic` | Cognição | SDK Claude (planejamento, coordenação, diálogo) | Raciocínio e tool-use confiáveis para o agente orquestrador | SDK OpenAI/Gemini (troca de provedor) | Sim (API remota) | MIT |
| `groq` | Cognição/Percepção | SDK Groq: STT (Whisper) + visão (Llama 4) + LLM rápido | STT em PT-BR e visão multimodal a baixa latência, baixo custo | `openai` apontado p/ base_url Groq | Sim (API remota) | Apache-2.0 (cliente) |
| `cerebras-cloud-sdk` | Cognição | Inferência de altíssima velocidade (sub-agentes/fan-out) | ~3000 tok/s; reduz latência do loop reativo | Groq (também rápido); Claude Haiku | Sim (API remota) | Apache-2.0 (cliente) |
| `opencv-python` | Percepção | Captura de webcam, pré-processamento de frames | Padrão de fato; controle fino de FPS/buffer | `imageio`/`picamera2` (menos completo) | Sim | Apache-2.0 |
| `mediapipe` | Percepção | Detecção de face/pose/mãos e **gestos** (LIVE_STREAM) | Tasks otimizadas, 7 gestos built-in, callback assíncrono | YOLO-pose (mais pesado, sem gestos prontos) | Sim | Apache-2.0 |
| `insightface` + `onnxruntime` | Percepção | Reconhecimento facial (embeddings ArcFace 512-D) | SOTA, rápido em CPU via ONNX | `face_recognition` (dlib, build difícil no Windows) | Sim | MIT (código)¹ |
| `openwakeword` | Voz | Palavra de ativação ("acordar" o robô) | Apache-2.0, grátis, sem chave/registro | Porcupine/Picovoice (comercial, AccessKey) | Sim | Apache-2.0 |
| `silero-vad` | Voz | Detecção de atividade de voz (segmentar fala) | Rede neural; corta silêncio antes do STT | `webrtcvad` (leve, mas confunde ruído) | Sim | MIT |
| `faster-whisper` | Voz | STT **offline** (fallback sem internet) | Privacidade, latência local previsível | Vosk (menor acurácia); Groq cloud | Sim (lento p/ modelos grandes) | MIT |
| **TTS** (Piper) | Voz | Síntese de fala (resposta falada) | Local, PT-BR, ONNX, sem custo/rede | gTTS / ElevenLabs (nuvem, dependência de rede) | Sim | MIT |
| `pyserial` + `pyserial-asyncio` | Hardware | Ponte serial com o firmware HACKberry | Async casa com event loop do Agno | Comunicação síncrona + thread/fila (mais frágil) | Sim | BSD-3-Clause |
| `fastapi` | Interface | API HTTP (telemetria, controle, dashboard) | Async-nativo, validação Pydantic, docs OpenAPI | Flask (síncrono); Litestar | Sim | MIT |
| `websockets` (via FastAPI) | Interface | Stream bidirecional em tempo real (eventos/UI) | Empurra estado da mão/percepção para o cliente | SSE (unidirecional); MQTT (broker extra) | Sim | BSD-3-Clause |
| `pydantic` | Núcleo | Schemas de mensagens, config, structured outputs | Validação em runtime; integra Agno/FastAPI | `dataclasses` + validação manual | Sim | MIT |
| `python-dotenv` | Núcleo | Carregar chaves de API de `.env` | Tira segredos do código | `os.environ` puro / `pydantic-settings` | Sim | BSD-3-Clause |
| `numpy` | Núcleo | Álgebra de frames, embeddings, áudio | Base de toda a stack de visão/áudio | — (incontornável) | Sim | BSD-3-Clause |
| `asyncio` (stdlib) | Núcleo | Loop de eventos, concorrência I/O | Casa com Agno/FastAPI/pyserial-asyncio | `threading` (mais difícil de raciocinar) | Sim | PSF |
| `uv` | Tooling | Gerenciador de ambiente/dependências | Resolução e instalação muito rápidas | Poetry (mais maduro, mais lento) | Sim | Apache-2.0/MIT |
| `pytest` | Tooling | Testes (protocolo serial, parsers, gestos) | Padrão; fixtures, `pytest-asyncio` | `unittest` (stdlib, menos ergonômico) | Sim | MIT |
| `loguru` | Tooling | Logging estruturado de todo o pipeline | Configuração trivial, sinks rotativos | `logging` (stdlib, verboso) | Sim | MIT |

> ¹ **Atenção de licença do InsightFace:** o *código* é MIT, porém vários **modelos pré-treinados** (incl. `buffalo_l`) são distribuídos para **uso não-comercial / acadêmico**. Para um projeto acadêmico da UFRGS isto é adequado, mas qualquer uso comercial exige revisão da licença do pacote de modelos. Ver também a Seção 4.5.

---

### 4.2 Camada de orquestração e cognição

#### Agno AI (`agno`)

- **Papel:** espinha dorsal multiagente. Cada capacidade do robô vira um agente (`PerceptionAgent`, `VoiceAgent`, `HandActuatorAgent`, `PlannerAgent`), e um `Team` orquestra a colaboração. As *tools* são funções Python comuns — incluindo a função que envia gestos ao firmware. O **estado compartilhado** (última pessoa vista, modo de operação, posição atual dos servos) vive em `session_state`, acessível por todos os agentes.
- **Instalação:** `uv pip install agno` (ou `pip install agno`). Versão verificada: **2.6.13**. Python 3.11+ recomendado.
- **Por que:** Agno trata qualquer função Python como tool (baixo atrito para expor `mover_servo`, `fechar_mao`, `descrever_cena`); é **multi-provedor** (Claude + Groq + Cerebras no mesmo programa, sem lock-in); e o overhead de instanciação por agente é mínimo (claim do vendor: ~3µs / ~5KiB — não verificado independentemente, mas favorável a um loop de robô). Importante: Agno é **soft-real-time** — a latência real é dominada pelo provedor LLM. **O controle de baixo nível (limites de servo, parada de emergência) NÃO deve depender do agente**; fica no firmware e no cliente serial.
- **API v2 essencial (verificada):**

```python
from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.tools import tool
from agno.run.context import RunContext  # caminho provável; CONFIRME na doc v2

@tool
def fechar_mao(run_context: RunContext) -> str:
    """Fecha a preensão da mão HACKberry (gesto CLOSE)."""
    run_context.session_state.setdefault("hand", {})["grip"] = "closed"
    # ...envia comando serial ao firmware (ver Seção 5)...
    return "preensão fechada"

planner = Agent(
    model=Claude(id="claude-opus-4-8", cache_system_prompt=True),
    instructions=["Você coordena uma mão protética. Acione tools com gatilhos explícitos."],
    tools=[fechar_mao],
    add_history_to_context=True,
)
```

- **Coordenação multiagente — nota de nomenclatura:** o enunciado original fala em modo *"collaborate"*, mas a **v2 atual expõe `route` / `coordinate` / `broadcast`** (`from agno.team import Team, TeamMode`). O equivalente colaborativo em v2 é **`TeamMode.coordinate`** (líder delega em sequência e sintetiza, mantendo contexto compartilhado). Para o loop reativo crítico, `broadcast` (paralelo) reduz latência; `coordinate` é sequencial (mais lento, mais coerente). *Não confirmado* se `collaborate` ainda é alias válido em 2.6 — use `coordinate`.
- **Memória/estado:** em v2 **não existe mais** parâmetro `memory=`/`storage=` separado (era da 1.x). Usa-se `db=<BaseDb>` + `memory_manager`/`enable_agentic_memory`. O `session_state` (dict) é persistido via `db` entre runs e é o canal de **estado compartilhado do time** (`run_context.session_state`, verificado).
- **Alternativas:**
  - **LangGraph** — grafos de estado explícitos, ótimo para fluxos determinísticos complexos; trade-off: mais verboso e opinativo, curva mais íngreme, menos "função-Python-é-tool".
  - **CrewAI** — abstração de "crew/role" agradável; trade-off: mais pesado, historicamente mais acoplado a um estilo de orquestração e menos flexível para o estado compartilhado de baixa latência que um robô exige.

#### Claude API (`anthropic`)

- **Papel:** cérebro de **planejamento, raciocínio, coordenação de agentes e diálogo** — o agente orquestrador (`PlannerAgent`) e o tradutor de comando-em-linguagem-natural para gestos (ex.: "aperte minha mão" → tool `fechar_mao`).
- **Instalação:** `pip install anthropic`. Autenticação por `ANTHROPIC_API_KEY` (env). No Agno: `Claude(id="claude-opus-4-8")`.
- **IDs de modelo atuais (verificados via skill oficial Claude API, cache 2026-06):** use as strings **exatas**, **sem sufixo de data**.

| Modelo | ID | Contexto | Saída máx | Preço in / out (US$/1M) |
|---|---|---|---|---|
| Claude Opus 4.8 | `claude-opus-4-8` | 1M | 128K | 5,00 / 25,00 |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | 1M | 64K | 3,00 / 15,00 |
| Claude Haiku 4.5 | `claude-haiku-4-5` | 200K | 64K | 1,00 / 5,00 |

- **Thinking e effort (verificados):** Opus 4.8/4.7 usam **adaptive thinking** — `thinking={"type": "adaptive"}`. **Atenção:** em Opus 4.7/4.8, `budget_tokens`, `temperature`/`top_p`/`top_k` e *prefill* de assistant **retornam 400** (foram removidos). Controle a profundidade via `output_config={"effort": "..."}` — níveis `low` | `medium` | `high` | `xhigh` | `max` (`high` é o default; `xhigh`/`high` recomendados para coordenação agêntica). Eleve `max_tokens` para **≥16000** em tarefas de raciocínio (o default do Agno é 8192).

```python
import anthropic
client = anthropic.Anthropic()  # lê ANTHROPIC_API_KEY
resp = client.messages.create(
    model="claude-opus-4-8",
    max_tokens=16000,
    thinking={"type": "adaptive"},
    output_config={"effort": "high"},
    tools=[{
        "name": "fechar_mao",
        "description": "Use quando o usuário pedir para apertar/fechar a mão, segurar um objeto ou cumprimentar com aperto.",
        "input_schema": {"type": "object", "properties": {}},
    }],
    messages=[{"role": "user", "content": "Pode apertar minha mão?"}],
)
```

- **Boa prática de tool-use (verificada):** descreva *quando* chamar cada tool (não só o que faz) — Opus 4.8 aciona tools de forma conservadora; gatilhos explícitos na `description` aumentam o acerto. Sempre `json.loads()` no `input` (nunca regex). No loop manual: itere até `stop_reason == "end_turn"`, anexe `response.content` completo a cada turno e cada `tool_result` deve casar o `tool_use_id`.
- **Nota Agno:** a doc do Agno ainda mostra um ID legado (`claude-3-5-sonnet-...`) — **substitua por `claude-opus-4-8`**.
- **Alternativas:** SDK **OpenAI** (GPT) ou **Google Gemini** — viáveis pela camada multi-provedor do Agno; trade-off: troca o perfil de tool-use/raciocínio e a economia. Mantém-se Claude por confiabilidade de coordenação agêntica e tool-use, que aqui valem mais que custo bruto.

#### Groq API (`groq`)

- **Papel triplo:** **(1) STT** via Whisper (transcrição de PT-BR); **(2) visão multimodal** via Llama 4 (descrever cena, detectar objetos perigosos); **(3) LLM rápido** para respostas curtas de baixa latência no loop reativo.
- **Instalação:** `pip install groq`. `GROQ_API_KEY` no ambiente. PowerShell: `$env:GROQ_API_KEY="gsk_..."`.
- **IDs de modelo (verificados):**
  - **STT:** `whisper-large-v3` (multilíngue, **inclui PT-BR**, melhor acurácia, suporta tradução) ou `whisper-large-v3-turbo` (mais rápido/barato, só transcrição). Use **v3 com `language="pt"`** para acurácia. Endpoint: `audio.transcriptions.create`. Limite 25 MB (free) / 100 MB (dev).
  - **Visão:** `meta-llama/llama-4-scout-17b-16e-instruct` (17B ativos/109B) ou `meta-llama/llama-4-maverick-17b-128e-instruct` (17B/400B). Até 5 imagens/request; base64 ≤ 4 MB (HTTP 413 se exceder).
  - **Texto rápido:** `llama-3.1-8b-instant` (mais rápido/barato) ou `llama-3.3-70b-versatile` (128K, tool use, JSON mode).

```python
from groq import Groq
client = Groq()  # lê GROQ_API_KEY
with open("fala.wav", "rb") as f:
    t = client.audio.transcriptions.create(
        file=f, model="whisper-large-v3", language="pt",
        response_format="verbose_json",
    )
print(t.text)
```

- **Por que:** Groq roda Whisper em velocidade muito acima de tempo-real (~200x+ para o turbo), cobre **PT-BR** e ainda oferece visão multimodal — três necessidades do robô num só provedor. **Gargalo prático:** rate limit por **TPM (free ~6.000)** — mantenha system prompts curtos e use *prompt caching* (não conta para rate limit) no prompt fixo do robô. 30 RPM ≈ 1 req/2s no free; uso concorrente exige tier pago.
- **Alternativas:** SDK **`openai`** apontado para `base_url="https://api.groq.com/openai/v1"` (API compatível) — útil se já houver código OpenAI; trade-off: menos idiomático que o cliente nativo. Para STT/visão sem nuvem, ver `faster-whisper` (offline) e Claude (visão nativa) — porém **Cerebras NÃO faz STT nem (na doc atual) visão**.

#### Cerebras API (`cerebras-cloud-sdk`)

- **Papel:** **inferência de altíssima velocidade** complementar — sub-agentes, fan-out e respostas reativas onde tokens/segundo importam mais que profundidade de raciocínio.
- **Instalação:** `pip install cerebras-cloud-sdk`. `CEREBRAS_API_KEY` no ambiente. Base URL OpenAI-compatível: `https://api.cerebras.ai/v1`. No Agno: `from agno.models.cerebras import Cerebras` (há também `CerebrasOpenAI`, endpoint OpenAI-compatível).
- **IDs de modelo (verificados na doc oficial):** produção `gpt-oss-120b` (~3000 tok/s); preview `zai-glm-4.7`. A família `llama-4-scout-17b-16e-instruct` / `llama-3.3-70b` / `qwen-3-*` aparece no catálogo. **Atenção:** `qwen-3-32b` e `llama-3.3-70b` têm **deprecação anunciada para 2026-02-16** (não reconfirmada na overview atual). **CONFIRME o ID em `inference-docs.cerebras.ai/models/overview`** antes de fixar em produção; o default do Agno é `Cerebras(id="llama-4-scout-17b-16e-instruct")`.

```python
from agno.agent import Agent
from agno.models.cerebras import Cerebras
reflexo = Agent(model=Cerebras(id="gpt-oss-120b"), markdown=False)
```

- **Por que:** quando o robô precisa de uma decisão imediata (ex.: classificar rapidamente um gesto reconhecido em "apertar/apontar/parar"), a velocidade de geração do Cerebras corta latência percebida. **Limitação:** Cerebras **não oferece STT** e a doc atual **não confirma visão** — para áudio→texto use Groq/Whisper, para visão use Groq (Llama 4) ou Claude.
- **Alternativas:** **Groq** (também baixa latência, e ainda cobre STT/visão) ou **Claude Haiku 4.5** (mais rápido/barato dentro do ecossistema Anthropic) — trade-off: Haiku não atinge os tok/s do Cerebras, mas simplifica o stack para um só provedor.

---

### 4.3 Camada de percepção (visão)

#### OpenCV (`opencv-python`)

- **Papel:** captura de webcam e pré-processamento dos frames que alimentam MediaPipe, reconhecimento facial e a visão multimodal.
- **Instalação:** `pip install opencv-python` (ou `opencv-contrib-python` para módulos extras).
- **Por que:** controle fino e portável da câmera. No Windows, `cv2.VideoCapture(0, cv2.CAP_DSHOW)` reduz latência de abertura; `cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)` evita frames atrasados. **Padrão obrigatório:** `cap.read()` é bloqueante — use uma **thread dedicada de captura** que mantém apenas o último frame ("latest-frame"), e o loop de inferência consome esse frame. **Não** rode 5 modelos MediaPipe em série no mesmo frame a 30 FPS na CPU; processe em cadência menor (a cada N frames) e a 640×480.
- **Alternativas:** **`imageio`**/**`picamera2`** (este último específico de Raspberry Pi) — trade-off: menos completos para o controle de FPS/buffer e o pipeline de visão em tempo real.

#### MediaPipe (`mediapipe`)

- **Papel:** detecção em tempo real de **face, pose e mãos** e, crucialmente, **reconhecimento de gestos** — a ponte natural entre "o que a pessoa faz" e "o que a mão responde".
- **Instalação:** `pip install mediapipe`. Modelos `.task` baixados de ai.google.dev.
- **API atual (verificada):** namespace `mediapipe.tasks.python.vision`. Três `RunningMode`: `IMAGE`, `VIDEO`, `LIVE_STREAM` (este usa **callback assíncrono** — ideal para webcam). O `GestureRecognizer` já classifica **7 gestos built-in**: `Closed_Fist`, `Open_Palm`, `Pointing_Up`, `Thumb_Down`, `Thumb_Up`, `Victory`, `ILoveYou`.

```python
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import mediapipe as mp

def on_result(result, output_image, timestamp_ms):
    if result.gestures:
        print(result.gestures[0][0].category_name)

opts = vision.GestureRecognizerOptions(
    base_options=python.BaseOptions(model_asset_path="gesture_recognizer.task"),
    running_mode=vision.RunningMode.LIVE_STREAM,
    result_callback=on_result)
rec = vision.GestureRecognizer.create_from_options(opts)
# loop: rec.recognize_async(mp_img, timestamp_ms)  # timestamp DEVE ser monotônico crescente
```

- **Por que:** tarefas prontas e leves (CPU), gestos built-in que mapeiam direto para a semântica da mão (ex.: `Closed_Fist` ↔ confirmar fechamento; `Pointing_Up` ↔ gesto de apontar). **Ressalva de hardware:** MediaPipe reconhece o gesto da **pessoa**; a HACKberry *responde* com seus 3 servos, mas **não se reorienta no espaço** (não há atuador de pulso/braço).
- **Alternativas:** **YOLO-pose**/Ultralytics — boa para detecção de pose robusta; trade-off: mais pesado, exige treino/curadoria e **não traz reconhecimento de gestos pronto**.

#### Reconhecimento facial — `face_recognition` **vs** InsightFace (recomendação: **InsightFace**)

- **Papel:** identificar indivíduos conhecidos (ex.: cumprimentar automaticamente um professor cadastrado).
- **Recomendação: InsightFace (`buffalo_l`, ArcFace, embeddings 512-D) sobre `onnxruntime`.**
  - **Instalação:** `pip install insightface onnxruntime` (use `onnxruntime-gpu` se houver CUDA).
  - **Por que:** acurácia SOTA, robusto a rostos não-frontais, e **roda bem em CPU** via ONNX. Fluxo: extrair embedding 512-D de 1–3 fotos por pessoa (*enrollment*) → guardar `{nome: embedding}` → reconhecer por **similaridade de cosseno** contra a galeria.

```python
from insightface.app import FaceAnalysis
import numpy as np
app = FaceAnalysis(name="buffalo_l"); app.prepare(ctx_id=-1)  # ctx_id=-1 => CPU
faces = app.get(bgr_frame)                # cada face tem .embedding e .bbox
sim = np.dot(emb, known) / (np.linalg.norm(emb) * np.linalg.norm(known))
```

- **Threshold:** ~0,35–0,5 de similaridade de cosseno — **calibre empiricamente** com sua câmera e iluminação (incerto por depender do hardware/ambiente).
- **Alternativa — `face_recognition` (dlib):** mais simples de usar; trade-off: **build do dlib no Windows é o ponto de dor**, acurácia cai em rostos não-frontais, e GPU exige dlib compilado com CUDA. **DeepFace** é um wrapper de conveniência (envolve ArcFace/FaceNet/dlib) — útil para comparar backbones, porém menos eficiente que usar a engine ONNX diretamente.
- **Licença:** ver nota ¹ na matriz e a Seção 4.5 (modelos `buffalo_l` para uso não-comercial/acadêmico).

---

### 4.4 Camada de voz

A arquitetura de voz é uma cascata: **openWakeWord** (ativa) → **Silero VAD** (segmenta a fala) → **Groq Whisper** (transcreve; `faster-whisper` como fallback offline) → agentes → **Piper TTS** (responde falando).

#### Palavra de ativação — openWakeWord **vs** Porcupine (recomendação: **openWakeWord**)

- **Papel:** "acordar" o robô sem processar áudio continuamente nos modelos caros.
- **Recomendação: `openwakeword`** — `pip install openwakeword`. **Apache-2.0, grátis, sem chave/registro**, com modelos pré-treinados e treino de palavra customizada. Escolha default para um projeto acadêmico/open-source.
- **Alternativa — Porcupine/Picovoice (`pvporcupine`):** qualidade alta e estável, footprint mínimo para embarcado; trade-off: **comercial**, exige **AccessKey**, free tier limitado e licença paga para produção/escala. Use só se precisar de footprint embarcado mínimo com suporte comercial.

#### VAD — Silero VAD **vs** webrtcvad (recomendação: **Silero VAD**)

- **Papel:** segmentar a fala (acumular frames enquanto há voz; fechar o segmento após ~300–700 ms de silêncio) antes de enviar ao STT — corta custo e latência ao não mandar silêncio à Groq.
- **Recomendação: `silero-vad`** — `pip install silero-vad`. Rede neural, multilíngue, muito mais preciso; trivial num PC.

```python
from silero_vad import load_silero_vad, get_speech_timestamps
model = load_silero_vad()
ts = get_speech_timestamps(audio_16k, model, sampling_rate=16000)
```

- **Alternativa — `webrtcvad`:** leve, baseado em energia/GMM (chunks de 10/20/30 ms a 8/16 kHz); trade-off: rápido porém **confunde ruído/música com fala** — pior em ambiente de laboratório barulhento.

#### STT offline — `faster-whisper` (fallback)

- **Papel:** transcrição **sem internet** / com latência local previsível, como fallback do Groq cloud.
- **Instalação:** `pip install faster-whisper` (backend CTranslate2).
- **Por que:** privacidade, sem custo por chamada, latência previsível. Em GPU `large-v3` é rápido; em CPU pura, prefira `base`/`small` (modelos grandes ficam lentos). **Arquitetura recomendada:** Groq turbo como caminho primário (velocidade/qualidade) e `faster-whisper` como rede de segurança offline.
- **Alternativa:** **Vosk** (mais leve) — trade-off: acurácia menor, sobretudo em PT-BR.

#### TTS — Piper (recomendação local)

- **Papel:** **síntese de fala** — converter a resposta textual dos agentes em voz (a tecnologia que faltava no enunciado para fechar o loop conversacional).
- **Recomendação: Piper** (`pip install piper-tts`) — TTS **local**, baseado em ONNX, com vozes em **PT-BR**, MIT, sem custo nem dependência de rede; consistente com a filosofia open-source/acadêmica do projeto e com a privacidade do fallback offline.
- **Alternativas:** **gTTS** (Google, simples) ou **ElevenLabs** (qualidade premium) — trade-off: ambas são **na nuvem**, adicionam dependência de rede e, no caso do ElevenLabs, custo por caractere; minam o caminho offline.

---

### 4.5 Camada de hardware (ponte serial)

#### PySerial + pyserial-asyncio

- **Papel:** transportar comandos (gestos nomeados + ângulos por servo) e telemetria entre o cliente Python e o **firmware Arduino customizado** da HACKberry (Arduino Nano / ATmega328P, Mk2). Lembrete: o firmware **nativo é autônomo (sensor→servo) e não expõe API de comandos** — por isso o plano exige firmware custom (ver Seções 5 e 6).
- **Instalação:** `pip install pyserial pyserial-asyncio`.
- **Por que `pyserial-asyncio`:** casa com o **event loop** do Agno/FastAPI — a leitura serial vira coroutine não-bloqueante, sem thread de polling. O `pyserial` síncrono exigiria thread dedicada + filas (`run_in_executor`), viável porém mais frágil. Padrão: handshake no boot (esperar banner `R`), fila serializada (1 comando em voo para preservar a ordem de ACK), `heartbeat` periódico (200–500 ms) para o **watchdog** do firmware, e backoff de reconexão.
- **Alternativa:** **pyserial síncrono em thread dedicada** — funciona, mas adiciona complexidade de sincronização entre threads e o loop assíncrono.

---

### 4.6 Camada de interface (API e tempo real)

#### FastAPI

- **Papel:** API HTTP para telemetria (estado dos servos, bateria, modo), controle (disparar gestos, alternar HOST/EMG), e backend de um dashboard/diagnóstico.
- **Instalação:** `pip install "fastapi[standard]"` (traz Uvicorn). Versão estável atual da linha 0.1xx.
- **Por que:** **async-nativo** (mesmo loop do Agno e do pyserial-asyncio), validação automática via **Pydantic** e docs OpenAPI grátis — ideal para um projeto de pesquisa que precisa de instrumentação e reprodutibilidade.
- **Alternativa:** **Flask** (síncrono, ecossistema enorme) — trade-off: integra pior com o pipeline assíncrono; **Litestar** é alternativa async moderna, porém com comunidade menor.

#### WebSockets (via Starlette/FastAPI; `websockets`)

- **Papel:** **stream bidirecional em tempo real** — empurrar para o cliente os eventos de percepção (pessoa reconhecida, gesto detectado) e o estado da mão à medida que mudam, e receber comandos interativos.
- **Instalação:** já disponível via FastAPI; cliente standalone com `pip install websockets`.
- **Por que:** o robô produz um fluxo contínuo de eventos; polling HTTP teria latência e desperdício. WebSocket dá baixa latência e canal de volta.
- **Alternativas:** **SSE** (Server-Sent Events) — mais simples, porém **unidirecional** (só servidor→cliente); **MQTT** — ótimo para frota de dispositivos IoT, mas adiciona um **broker** externo, excessivo para um robô único.

---

### 4.7 Núcleo, tooling e qualidade

| Tecnologia | Papel | Instalação | Por que | Alternativa (trade-off) |
|---|---|---|---|---|
| **Pydantic** | Schemas de mensagens serial/eventos, config tipada, structured outputs dos agentes | `pip install pydantic` | Validação em runtime; é a base de validação do FastAPI e integra `output_schema` do Agno | `dataclasses` + checagem manual (sem validação automática) |
| **python-dotenv** | Carregar `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `CEREBRAS_API_KEY` de `.env` | `pip install python-dotenv` | Mantém segredos fora do código/VCS | `os.environ` puro (sem `.env`); `pydantic-settings` (config tipada — boa evolução) |
| **NumPy** | Embeddings faciais, buffers de áudio (16 kHz), manipulação de frames | `pip install numpy` | Dependência incontornável de OpenCV/InsightFace/Silero | — (não há substituto realista) |
| **asyncio** (stdlib) | Loop de eventos único que une Agno, FastAPI, pyserial-asyncio e WebSockets | Python 3.11+ | Concorrência I/O-bound sem threads; é o "tecido conjuntivo" do sistema | `threading`/`multiprocessing` (mais difícil de coordenar com I/O assíncrono) |
| **uv** | Ambiente virtual e resolução/instalação de dependências | Instalador oficial (`pipx install uv` ou script) | Muito mais rápido que pip/Poetry; lockfile reprodutível | **Poetry** (mais maduro/estável, porém mais lento) |
| **pytest** | Testes do parser de protocolo serial, clamps de ângulo, mapeamento de gestos, mocks de LLM | `pip install pytest pytest-asyncio` | Padrão de fato; fixtures e suporte async | `unittest` (stdlib, menos ergonômico) |
| **loguru** | Logging estruturado de percepção→decisão→atuação, com sinks rotativos | `pip install loguru` | Configuração trivial, ótimo para depurar o pipeline e auditar ações da mão | `logging` (stdlib, mais verboso de configurar) |

> **Sugestão (opcional):** `pydantic-settings` para centralizar config (pinos, baudrate, thresholds, IDs de modelo) num único objeto tipado, alimentado por `.env` — reduz "números mágicos" espalhados pelo código.

---

### 4.8 Atribuição de modelos de IA por papel

Princípio de projeto (verificado na pesquisa): **a latência real é dominada pelo provedor LLM**, e Agno é soft-real-time. Logo, separe **raciocínio profundo** (Claude) de **reatividade de baixa latência** (Cerebras/Groq), e mantenha o controle crítico fora do agente.

| Agente / papel | Provedor | ID de modelo (verificado) | Justificativa (latência · custo · capacidade) |
|---|---|---|---|
| **PlannerAgent / Orquestrador** (líder do `Team`) | Claude | `claude-opus-4-8` (adaptive thinking, `effort: "high"`/`"xhigh"`) | Capacidade: melhor raciocínio e tool-use confiável p/ coordenar agentes. Latência: maior, aceitável fora do loop crítico. Custo: 5/25 por 1M — mais caro, reservado a decisões importantes. |
| **DialogueAgent** (conversa natural) | Claude | `claude-sonnet-4-6` | Equilíbrio velocidade/inteligência (3/15 por 1M); diálogo fluido sem o custo do Opus. Subir p/ Opus só em conversas que exijam raciocínio profundo. |
| **VoiceAgent — STT** | Groq | `whisper-large-v3` (`language="pt"`) | Capacidade: PT-BR com boa acurácia. Latência: ~200x+ tempo-real. Custo: ~US$0,04/h de áudio. *Turbo* (`whisper-large-v3-turbo`) se priorizar custo/velocidade. |
| **PerceptionAgent — visão multimodal** | Groq | `meta-llama/llama-4-scout-17b-16e-instruct` | Capacidade: fusão texto+imagem nativa p/ descrever cena/objetos. Latência baixa. Custo baixo. *Maverick* se precisar de mais capacidade. Alternativa: visão nativa do Claude. |
| **ReflexAgent / sub-agentes reativos** (classificar gesto, decisão imediata) | Cerebras | `gpt-oss-120b` (~3000 tok/s) — **confirme o ID na overview** | Latência: a mais baixa (tokens/s extremos). Capacidade: suficiente p/ classificação curta. Custo: competitivo. Não faz STT/visão. |
| **Respostas curtas de baixa latência** (confirmações, fala curta) | Groq | `llama-3.1-8b-instant` | Latência/custo mínimos p/ respostas triviais; evita gastar Opus/Sonnet em "ok, fechando a mão". |
| **Fallback de raciocínio econômico** | Claude | `claude-haiku-4-5` | Mantém o ecossistema Anthropic quando se quer baixo custo (1/5 por 1M) sem trocar de SDK; mais rápido que Opus/Sonnet. |
| **STT offline (sem rede)** | Local | `faster-whisper` (`base`/`small` em CPU, `large-v3` em GPU) | Capacidade: privacidade, latência local previsível. Sem custo por chamada. Fallback do Groq. |

> **Sinalizações de incerteza (não inventar):** (a) o **ID Cerebras** de produção deve ser confirmado em `inference-docs.cerebras.ai/models/overview` — há deprecações anunciadas para alguns modelos Llama/Qwen; (b) o caminho de import `from agno.run.context import RunContext` é **provável**, não 100% confirmado — verifique na doc v2; (c) `distil-whisper` da Groq é **só inglês** — não serve PT-BR.

---

### 4.9 Considerações de licença (leitura obrigatória)

O Projeto Thoth herda licenças de três fontes que **co-existem** mas têm restrições distintas. Tratar isto corretamente é parte da qualidade de pesquisa.

| Componente | Licença | Implicação prática |
|---|---|---|
| **Hardware HACKberry** (peças impressas em 3D, design mecânico) | **CC BY-NC-SA 4.0** | **NÃO-comercial** + atribuição + **ShareAlike**. Você pode imprimir, modificar e usar academicamente, mas **não pode vender** nem incorporar em produto comercial sem permissão; derivados do *design* devem manter a mesma licença. |
| **Firmware HACKberry** (sketch Arduino, incl. o **firmware custom** deste plano) | **GPLv3** | **Copyleft forte.** Como o plano deriva do `Hackberryv3.0.ino` (reaproveita limites nativos `outThumbMax`/`outIndexMax`/`outOtherMax` e a lógica de clamp), o **firmware custom também deve ser GPLv3** e ter seu código-fonte disponibilizado. |
| **Software do host** (cliente Python, agentes, visão, voz) | Permissivas (MIT/Apache-2.0/BSD/MPL) — `agno` MPL-2.0; demais MIT/Apache/BSD | Compatíveis entre si para uso acadêmico. **Atenção ao MPL-2.0 do Agno:** copyleft *por arquivo* — modificações **nos arquivos do próprio Agno** devem ser publicadas; seu código que apenas *usa* a biblioteca não é contaminado. |

**Pontos de atenção específicos:**

- **Fronteira GPLv3 ↔ host Python:** o firmware GPLv3 roda **no microcontrolador** e se comunica com o host **por protocolo serial** (separação de processos / "mere aggregation"). Logo, o cliente Python (MIT/Apache) **não** é obrigado a virar GPLv3 — mas o **firmware custom é**, e seu fonte deve acompanhar qualquer distribuição do robô.
- **Uso NÃO-comercial do hardware (CC BY-NC-SA):** este é o alerta mais importante. O projeto é **acadêmico (UFRGS/Enfitec Jr./CTA-IF)** — adequado à cláusula NC. **Qualquer tentativa de comercializar** a prótese (venda, spin-off, produto) exige negociar licenciamento com a exiii Inc. / Mission ARM Japan.
- **Modelos InsightFace `buffalo_l`:** *código* MIT, **modelos** tipicamente **não-comerciais/acadêmicos** — alinhado ao contexto da UFRGS, mas reavaliar antes de qualquer uso comercial.
- **Modelos open-weights via API (Llama 4, gpt-oss, Whisper):** aqui você consome **serviços** (Groq/Cerebras) sob seus respectivos termos de uso; as licenças dos pesos (ex.: Llama Community License) recaem sobre *redistribuição de pesos*, não sobre chamadas de API — mas registre os termos de cada provedor.
- **Atribuição (BY) e ShareAlike (SA):** mantenha um arquivo `THIRD_PARTY_LICENSES`/`NOTICE` no repositório creditando a HACKberry (exiii Inc. / Mission ARM Japan) e listando todas as dependências e suas licenças. É exigência da CC BY-NC-SA e boa prática de pesquisa reprodutível.
