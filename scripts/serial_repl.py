"""REPL manual do protocolo serial — debug e CALIBRAÇÃO do firmware (sem agentes).

Conecta via HandLink e permite controlar a mão por GESTOS ou por DEDO individual.

Uso:  python scripts/serial_repl.py --port COM17

Comandos:
  open / fist / point / pinch / shake / stop / status   -> gestos nomeados
  t <ang>   i <ang>   o <ang>     -> define o ângulo de UM dedo (polegar/indicador/tres)
  t+ t- i+ i- o+ o-               -> ajusta ±10° aquele dedo (calibração fina)
  G:<t>,<i>,<o>                   -> envia os 3 ângulos de uma vez (linha crua)
  ?                               -> status ;  q -> sair
  (ângulos: ~15 = ABERTO, ~165 = FECHADO; o firmware faz o clamp aos limites)
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Permite rodar sem `pip install -e .` (adiciona src/ ao path).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from thoth.actuation.serial_client import HandLink  # noqa: E402

GESTURES = {"open", "fist", "point", "pinch", "shake"}
NUDGE = 10
IDX = {"t": 0, "i": 1, "o": 2}        # polegar, indicador, tres dedos
NOMES = {"t": "polegar", "i": "indicador", "o": "tres dedos"}

HELP = (
    "comandos: open/fist/point/pinch/shake/stop/status | "
    "t <ang> i <ang> o <ang> | t+ t- i+ i- o+ o- | G:t,i,o | q (sair)"
)


async def main() -> None:
    ap = argparse.ArgumentParser(description="REPL/calibração da mão HACKberry.")
    ap.add_argument("--port", default="COM17")
    ap.add_argument("--baud", type=int, default=115200)
    args = ap.parse_args()

    hand = HandLink(port=args.port, baud=args.baud)
    print(f"conectando em {args.port}…")
    await hand.connect()
    print("conectado!\n" + HELP)

    # estado local dos 3 dedos (lógico). Sincroniza com o firmware ao iniciar.
    estado = [15, 15, 15]
    st = await hand.query()
    if st:
        estado = [st.thumb, st.index, st.other]
        print(f"posição atual: polegar={st.thumb} indicador={st.index} tres={st.other} ({st.mode})")

    async def aplicar() -> None:
        resp = await hand.set_angles(estado[0], estado[1], estado[2])
        print(f"  -> G:{estado[0]},{estado[1]},{estado[2]}  ({resp})")

    try:
        while True:
            line = (await asyncio.to_thread(input, "> ")).strip()
            if not line:
                continue
            low = line.lower()

            if low in {"q", "quit", "exit"}:
                break

            if low in GESTURES:
                resp = await hand.gesture(low)
                print(f"  -> {resp}")
                st = await hand.query()              # ressincroniza o estado local
                if st:
                    estado = [st.thumb, st.index, st.other]
                continue

            if low == "stop":
                print("  ->", await hand.stop())
                st = await hand.query()
                if st:
                    estado = [st.thumb, st.index, st.other]
                continue

            if low in {"status", "?"}:
                st = await hand.query()
                print("  ->", f"polegar={st.thumb} indicador={st.index} tres={st.other} ({st.mode})"
                      if st else "(sem status)")
                continue

            # nudge: t+ / t- / i+ / o- ...
            if len(low) == 2 and low[0] in IDX and low[1] in "+-":
                k = IDX[low[0]]
                estado[k] = max(0, min(180, estado[k] + (NUDGE if low[1] == "+" else -NUDGE)))
                print(f"  {NOMES[low[0]]} = {estado[k]}")
                await aplicar()
                continue

            # set por dedo: "t 90"
            partes = low.split()
            if len(partes) == 2 and partes[0] in IDX and partes[1].lstrip("-").isdigit():
                k = IDX[partes[0]]
                estado[k] = max(0, min(180, int(partes[1])))
                print(f"  {NOMES[partes[0]]} = {estado[k]}")
                await aplicar()
                continue

            # linha crua (ex.: G:165,15,15) — enviada direto ao firmware
            try:
                print("  ->", await hand._send_raw(line))
            except Exception as exc:  # noqa: BLE001
                print("  ! erro:", exc)
    finally:
        await hand.stop()
        await hand.close()


if __name__ == "__main__":
    asyncio.run(main())
