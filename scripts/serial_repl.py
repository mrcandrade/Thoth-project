"""REPL manual do protocolo serial — debug do firmware SEM os agentes.

Conecta via HandLink e envia linhas cruas (ou atalhos) digitadas no terminal.
Atalhos: open/fist/point/pinch/shake -> P:<NOME> ; stop -> S ; status -> ?.

Uso:  python scripts/serial_repl.py --port COM5
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Permite rodar sem `pip install -e .` (adiciona src/ ao path).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from thoth.actuation.serial_client import HandLink  # noqa: E402

SHORTCUTS = {
    "open": "P:OPEN", "fist": "P:FIST", "point": "P:POINT",
    "pinch": "P:PINCH", "shake": "P:SHAKE", "stop": "S", "status": "?",
}


async def main() -> None:
    ap = argparse.ArgumentParser(description="REPL serial da mão HACKberry.")
    ap.add_argument("--port", default="COM5")
    ap.add_argument("--baud", type=int, default=115200)
    args = ap.parse_args()

    hand = HandLink(port=args.port, baud=args.baud)
    print(f"conectando em {args.port}…")
    await hand.connect()
    print("conectado. Comandos:", ", ".join(SHORTCUTS), "| ou linha crua (ex.: G:80,80,80) | 'q' sai")

    try:
        while True:
            line = await asyncio.to_thread(input, "> ")
            line = line.strip()
            if line in {"q", "quit", "exit"}:
                break
            raw = SHORTCUTS.get(line.lower(), line)
            try:
                resp = await hand._send_raw(raw)
                print("  <-", resp)
            except Exception as exc:  # noqa: BLE001
                print("  ! erro:", exc)
    finally:
        await hand.stop()
        await hand.close()


if __name__ == "__main__":
    asyncio.run(main())
