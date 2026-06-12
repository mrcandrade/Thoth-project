# Protocolo Serial — Thoth ↔ HACKberry (fonte canônica)

Esta é a especificação única do protocolo. Deve casar **exatamente** entre o
firmware (`firmware/hackberry_serial/hackberry_serial.ino`) e o cliente Python
(`src/thoth/actuation/serial_client.py`).

- **Porta:** USB serial, **115200 8N1**, terminador de linha `\n`.
- Após abrir a porta, o Nano reinicia (auto-reset por DTR) e emite o banner `R`.

## Host → MCU

| Comando | Exemplo | Efeito |
|---------|---------|--------|
| `G:<thumb>,<index>,<other>` | `G:80,80,80` | Define ângulos absolutos (graus). Aplica **clamp** aos limites. |
| `P:<nome>` | `P:SHAKE` | Gesto nomeado: `OPEN`, `FIST`, `POINT`, `PINCH`, `SHAKE`. |
| `S` | `S` | **STOP seguro**: abre a mão (libera objeto) e entra em modo `SAFE`. |
| `H` | `H` | Heartbeat: zera o watchdog. O host envia a cada ~300 ms. |
| `?` | `?` | Solicita status. |

## MCU → Host

| Resposta | Exemplo | Significado |
|----------|---------|-------------|
| `R` | `R` | Pronto (boot). |
| `A:<eco>` | `A:G`, `A:P:FIST`, `A:H`, `A:S` | ACK do comando aceito. |
| `E:<cod>:<msg>` | `E:1:range` | Erro. Códigos: `1`=range, `2`=parse, `3`=wdt, `4`=cmd. |
| `S:<th>,<idx>,<ot>,<mode>` | `S:80,80,80,HOST` | Status. `mode` ∈ {`HOST`, `SAFE`}. |

## Semântica de segurança

- **Watchdog de heartbeat:** se o firmware não receber `H` por `WDT_MS` (~1000 ms),
  executa `goSafeOpen()` (abre a mão) e emite `E:3:wdt`. Perder o host **libera**
  o objeto — nunca aperta mais forte.
- **Watchdog de hardware:** `wdt_enable(WDTO_2S)` reinicia a placa se o loop travar.
- **Clamp:** todo ângulo é restringido a `[MIN, MAX]` por servo (espelha
  `src/thoth/safety/limits.py`). `G:` fora do range ainda é aplicado **clampado**,
  porém retorna `E:1:range` para sinalizar.
- **detach por ociosidade:** após `IDLE_MS` parado no alvo, os servos são
  desconectados (corta PWM) — reduz jitter e protege o servo do polegar (sem PPTC).

## Convenção de ângulos

`menor = ABERTO/ESTENDIDO`, `maior = FLEXIONADO/FECHADO`. Limites do MVP:
`thumb 10..150`, `index 10..160`, `other 10..160` (calibre com sua mão montada).
