# Hardware — HACKberry (reconciliação com o manual)

> Resumo operacional. A especificação completa está em
> `docs/plano/PLANO_IMPLEMENTACAO.md` (Seção 0.1 e Seção 6).

## O que é

A **HACKberry** é uma **mão protética** open-source (exiii Inc. / Mission ARM
Japan), impressa em 3D. **Não é um braço posicionador.** Os "3 DOF" são três
servomotores de **dedos** (controle de preensão).

> ⚠️ **Pinos: o manual diverge da placa real.** O mapeamento abaixo é o **medido
> nesta unidade** (via `firmware/servo_scan`), que vale sobre o manual.

| DOF | Servo | Pino REAL (medido) | Pino no manual | Proteção |
|-----|-------|--------------------|----------------|----------|
| Polegar (abdução/rotação) | pequeno | **D5** | D9 | **SEM PPTC** ⚠️ |
| Indicador (flexão) | grande | **D6** | D5 | PPTC 500 mA |
| Três dedos (médio/anelar/mínimo) | pequeno | **D3** | D6 | PPTC 500 mA |

(D9 não é usado nesta placa. O firmware `hackberry_serial.ino` usa os pinos REAIS.)

- Sensor (pressão fotorrefletor **ou** EMG MyoWare) → **A1 (SENS)**.
- Placa: **HACKberry Hand Board Mk2** (Arduino **Nano**, ATmega328P). Mk1 = Micro.
- Energia: bateria Li-ion **7,2 V / 2200 mAh**; entrada 7–12 V (máx 20 V).
- **Pulso:** ajustável **só manualmente**, em incrementos de 90°. Sem motor no
  pulso/antebraço/braço.

## O que é viável vs. gap de hardware

| Comando | Viável? | Como |
|---------|---------|------|
| Aperte minha mão | ✅ | gesto `SHAKE` (fecho suave ~70%) |
| Aponte | ⚠️ parcial | gesto `POINT`; a mão **não se reorienta** para mirar |
| Feche/abra a mão | ✅ | `FIST` / `OPEN` |
| Levante o braço | ❌ | exige atuador de ombro/cotovelo (Seção 7.1) |
| Quem está na sala? | ✅ | só visão computacional |

## Licenciamento

- **Firmware** (Arduino sketch): **GPLv3** — derivados herdam GPLv3.
- **Hardware / modelos 3D / placas:** **CC BY-NC-SA 4.0** (uso **não-comercial**).
