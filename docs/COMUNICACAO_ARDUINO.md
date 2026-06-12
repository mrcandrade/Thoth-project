# Como o Arduino conversa com o software do Mendes

Este documento explica, ponta a ponta, **como o computador (onde roda o Mendes)
controla os servos da mão HACKberry através do Arduino**. É a "cola" entre a IA e
o hardware.

## 1. Visão geral da cadeia

```
  VOZ / VISÃO            CÉREBRO (IA)              ATUAÇÃO (Python)         HARDWARE
 ┌────────────┐   evento  ┌──────────────┐  gesto  ┌───────────────┐  USB   ┌──────────┐
 │ microfone  │──────────▶│ Orquestrador │────────▶│  HandLink     │═══════▶│ Arduino  │──▶ 3 servos
 │ + webcam   │  no bus   │ (Agno/Claude)│  válido │ (serial async)│ serial │  Nano    │   (dedos)
 └────────────┘           └──────────────┘         └───────────────┘ 115200 └──────────┘
        ▲                        │ Safety (veto)            ▲   ACK/status        │
        └────────────────────────┴──────── TTS (voz) ◀──────┴─────────────────────┘
```

1. Você diz **"Mendes, aperte minha mão"** → o microfone capta → Silero VAD recorta
   a fala → Groq Whisper transcreve → o pipeline detecta a palavra **"Mendes"** e
   publica o comando no **event bus**.
2. O **Orquestrador** (Agno + Claude) interpreta, pede ao **Safety** para validar,
   e ao **Motion** para executar o gesto `shake`.
3. A primitiva de movimento chama o **`HandLink`**, que envia uma linha de texto
   pela **porta serial USB** para o Arduino.
4. O **firmware** no Arduino interpreta o comando, move os servos com suavização
   (slew-rate) e responde com um **ACK**.
5. O Mendes confirma por voz (**TTS**) e o dashboard web mostra tudo em tempo real.

> O ponto-chave de segurança: o **controle fino dos servos vive no firmware**
> (suavização, limites, watchdog), nunca depende da nuvem. Se a internet ou o PC
> caírem, o firmware **abre a mão** sozinho.

## 2. A camada física: USB ↔ Serial

- Você liga o Arduino Nano (placa HACKberry Mk2) ao notebook por um **cabo
  micro-USB**. O chip USB-serial da placa cria uma **porta COM** no Windows
  (ex.: `COM5`). Descubra qual com:

  ```powershell
  python scripts/check_devices.py     # lista portas seriais, câmeras e microfones
  ```

- Coloque a porta no `.env`: `SERIAL_PORT=COM5`.
- Parâmetros da linha serial: **115200 bps, 8 bits, sem paridade, 1 stop (8N1)**.
- Ao abrir a porta, o Nano **reinicia automaticamente** (sinal DTR). Por isso o
  `HandLink` espera o banner `R` (de *ready*) antes de enviar comandos.

## 3. O protocolo (linguagem entre PC e Arduino)

Em vez de bytes binários, usamos **texto simples, uma linha por comando**
(terminada por `\n`). É legível, fácil de depurar e robusto. Especificação
canônica em [`docs/protocol.md`](protocol.md). Resumo:

| O PC envia | Significado |
|------------|-------------|
| `P:SHAKE\n` | execute o gesto "apertar a mão" |
| `G:108,115,115\n` | vá para estes ângulos (polegar, indicador, três dedos) |
| `S\n` | PARE com segurança (abre a mão) |
| `H\n` | "estou vivo" (heartbeat, a cada ~300 ms) |
| `?\n` | me diga seu status |

| O Arduino responde | Significado |
|--------------------|-------------|
| `R` | liguei e estou pronto |
| `A:P:SHAKE` | recebi e aceitei o comando (ACK) |
| `E:1:range` | erro (1=fora do limite, 2=parse, 3=watchdog, 4=comando inválido) |
| `S:108,115,115,HOST` | status: ângulos atuais + modo (HOST/SAFE) |

Você pode **falar manualmente** com o Arduino, sem a IA, para testar:

```powershell
python scripts/serial_repl.py --port COM5
> open      # envia P:OPEN
> shake     # envia P:SHAKE
> G:90,90,90
> stop      # envia S
```

## 4. O lado Python: `HandLink` (cliente serial assíncrono)

Arquivo: [`src/thoth/actuation/serial_client.py`](../src/thoth/actuation/serial_client.py).

Responsabilidades:

- **Abrir/reconectar** a porta (`pyserial-asyncio`, integrado ao `asyncio`).
- **Enviar comandos e aguardar o ACK** (com timeout). Um *lock* garante "um
  comando em voo por vez", preservando a ordem das respostas.
- **Heartbeat**: envia `H` periodicamente para manter o watchdog do firmware vivo.
- **Ler o status** assíncrono e expor `last_status` (usado pelo dashboard).
- **Política de segurança na reconexão**: ao reconectar, NUNCA repete um gesto
  perigoso — manda `S` (abre a mão).

As **primitivas de movimento** ([`actuation/motion_primitives.py`](../src/thoth/actuation/motion_primitives.py))
traduzem intenções em comandos, sempre respeitando os limites de
[`safety/limits.py`](../src/thoth/safety/limits.py) (a mesma fonte de verdade que
o firmware).

## 5. O lado Arduino: firmware `hackberry_serial.ino`

Arquivo: [`firmware/hackberry_serial/hackberry_serial.ino`](../firmware/hackberry_serial/hackberry_serial.ino).

O `loop()` faz três coisas **sem nunca bloquear**:

1. **Lê a serial** caractere a caractere até o `\n`, monta a linha e interpreta o
   comando (`handleLine`).
2. **Watchdog de heartbeat**: se não receber `H` por ~1 s, conclui que o PC sumiu
   e **abre a mão** (`goSafeOpen`) — fail-safe.
3. **Tick de controle a 50 Hz**: move cada servo **no máximo alguns graus por
   ciclo** (slew-rate) em direção ao alvo, aplicando `constrain` aos limites. Ao
   ficar parado, faz `detach()` para cortar o PWM (reduz jitter e protege o servo
   do **polegar (D9), que não tem fusível PPTC**).

Pinos (placa Mk2): **polegar → D9, indicador → D5, três dedos → D6**.
⚠️ Confira o silk da sua placa antes de gravar (o sketch oficial usa outro mapa).

Gravar o firmware:

```powershell
python scripts/flash_firmware.py --port COM5     # usa arduino-cli (placa Arduino Nano)
```

## 6. Fluxo completo de um comando ("Mendes, aperte minha mão")

1. **Mic → STT**: `perception/audio/pipeline.py` transcreve e detecta "Mendes".
2. **Bus**: publica `comando_voz {texto: "aperte minha mão"}`.
3. **Orquestrador** (`agents/team.py`): Safety valida (é gesto de mão → OK),
   Motion chama `motion.apertar_a_mao(hand)`.
4. **HandLink**: envia `G:108,115,115\n` (≈70% do curso, fecho suave).
5. **Firmware**: clampa, suaviza até os ângulos, responde `A:G`.
6. **Mendes** fala a resposta (TTS) e o **dashboard** mostra o status atualizado.

Tudo isso aparece em tempo real em **http://127.0.0.1:8000** enquanto roda
`python -m thoth`.
