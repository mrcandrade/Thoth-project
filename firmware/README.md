# Firmware — HACKberry (host-controlled)

Sketch custom que substitui a lógica autônoma nativa (sensor→servo) por um
**loop controlado por host** com protocolo serial seguro. É o marco crítico da
Fase 2 do plano (ver `docs/plano/PLANO_IMPLEMENTACAO.md`, Seções 5.1 e 6).

> **Licença:** GPLv3 — deriva do firmware HACKberry de exiii Inc. / Mission ARM Japan.

## Hardware

- Placa: **HACKberry Hand Board Mk2** (Arduino **Nano**, ATmega328P). Mk1 = Arduino Micro.
- Servos: **polegar → D9** (SEM PPTC), **indicador → D5** (PPTC 500 mA), **três dedos → D6** (PPTC 500 mA).
- Alimentação: bateria Li-ion **7,2 V**. **Não** alimente os servos pela USB.

> ⚠️ **Pinagem:** os pinos acima seguem o manual da Mk2. O sketch oficial do
> repositório `mission-arm/HACKberry` pode usar outro mapeamento. **Confira o
> silk da sua placa** e ajuste `PIN_THUMB/PIN_INDEX/PIN_OTHER` se necessário.

## Protocolo serial (115200 8N1, terminador `\n`)

| Host → MCU | Significado |
|------------|-------------|
| `G:<thumb>,<index>,<other>` | ângulos absolutos (graus), com clamp |
| `P:<nome>` | gesto: `OPEN`, `FIST`, `POINT`, `PINCH`, `SHAKE` |
| `S` | STOP seguro = abre a mão |
| `H` | heartbeat (mantém o watchdog vivo) |
| `?` | status |

| MCU → Host | Significado |
|------------|-------------|
| `R` | pronto (boot) |
| `A:<eco>` | ACK |
| `E:<cod>:<msg>` | erro (1=range, 2=parse, 3=wdt, 4=cmd) |
| `S:<th>,<idx>,<ot>,<mode>` | status (modo: `HOST`/`SAFE`) |

Mantenha este protocolo em sincronia com `src/thoth/actuation/serial_client.py`.

## Como gravar (arduino-cli)

```bash
arduino-cli core install arduino:avr
arduino-cli compile --fqbn arduino:avr:nano firmware/hackberry_serial
arduino-cli upload  --fqbn arduino:avr:nano -p COM5 firmware/hackberry_serial
```

Ou use o atalho: `just flash COM5` (chama `scripts/flash_firmware.py`).

## Pasta `reference/`

Coloque aqui (somente leitura) os sketches **nativos** originais para comparação:
`Hackberryv3.0.ino` (sensor de pressão) e `HACKBERRY_V3.1_Mk2_EMG.ino` (EMG),
baixados de https://github.com/mission-arm/HACKberry — **não** os versionamos
aqui por serem GPLv3 de terceiros (baixe-os diretamente).
