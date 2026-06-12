"""Compila e grava o firmware custom via arduino-cli.

Requer o arduino-cli instalado e o core AVR:
    arduino-cli core install arduino:avr

Uso:  python scripts/flash_firmware.py --port COM5
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from glob import glob
from pathlib import Path

SKETCH = Path(__file__).resolve().parents[1] / "firmware" / "hackberry_serial"

# Caminho do arduino-cli, resolvido em runtime (preenchido por find_cli()).
CLI = "arduino-cli"


def find_cli() -> str | None:
    """Localiza o arduino-cli, mesmo que ainda não esteja no PATH da sessão.

    (winget adiciona ao PATH da máquina; um terminal já aberto não enxerga isso.)
    """
    found = shutil.which("arduino-cli")
    if found:
        return found
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        r"C:\Program Files\Arduino CLI\arduino-cli.exe",
        r"C:\Program Files (x86)\Arduino CLI\arduino-cli.exe",
        os.path.join(local, "Microsoft", "WinGet", "Links", "arduino-cli.exe"),
        r"C:\ProgramData\chocolatey\bin\arduino-cli.exe",
    ]
    candidates += glob(
        os.path.join(local, "Microsoft", "WinGet", "Packages",
                     "ArduinoSA.CLI*", "**", "arduino-cli.exe"),
        recursive=True,
    )
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None

_INSTALL_HELP = """\
arduino-cli não foi encontrado no PATH.

Instale (escolha uma opção) e reabra o terminal:
  winget install -e --id ArduinoSA.CLI
  choco  install arduino-cli            (PowerShell como Administrador)
  ou baixe de: https://arduino.github.io/arduino-cli/latest/installation/

Depois, instale o core AVR (uma vez só):
  arduino-cli core update-index
  arduino-cli core install arduino:avr
"""


def run(cmd: list[str]) -> int:
    print("$", " ".join(cmd))
    return subprocess.call(cmd)


def ensure_core() -> None:
    """Garante o core arduino:avr e a biblioteca Servo (instala se faltarem)."""
    out = subprocess.run([CLI, "core", "list"], capture_output=True, text=True)
    if "arduino:avr" not in (out.stdout or ""):
        print("Core arduino:avr ausente — instalando…")
        run([CLI, "core", "update-index"])
        run([CLI, "core", "install", "arduino:avr"])

    libs = subprocess.run([CLI, "lib", "list"], capture_output=True, text=True)
    if "Servo" not in (libs.stdout or ""):
        print("Biblioteca Servo ausente — instalando…")
        run([CLI, "lib", "install", "Servo"])


def main() -> None:
    ap = argparse.ArgumentParser(description="Flash do firmware HACKberry (arduino-cli).")
    ap.add_argument("--port", required=True, help="porta serial (ex.: COM5, /dev/ttyUSB0)")
    ap.add_argument("--fqbn", default="arduino:avr:nano", help="placa (Mk2 = Arduino Nano)")
    ap.add_argument("--old-bootloader", action="store_true",
                    help="use se a gravação falhar (clones de Nano usam o bootloader antigo)")
    ap.add_argument("--sketch", default=str(SKETCH),
                    help="pasta do sketch a gravar (padrão: firmware/hackberry_serial)")
    args = ap.parse_args()
    sketch_dir = Path(args.sketch)

    global CLI
    cli = find_cli()
    if cli is None:
        print(_INSTALL_HELP)
        sys.exit(1)
    CLI = cli
    print(f"# usando: {CLI}")
    if not sketch_dir.exists():
        raise SystemExit(f"sketch não encontrado: {sketch_dir}")

    ensure_core()

    def compile_and_upload(fqbn: str) -> int:
        rc = run([CLI, "compile", "--fqbn", fqbn, str(sketch_dir)])
        if rc != 0:
            return rc
        return run([CLI, "upload", "--fqbn", fqbn, "-p", args.port, str(sketch_dir)])

    base = args.fqbn
    fqbn = base + (":cpu=atmega328old" if args.old_bootloader else "")
    rc = compile_and_upload(fqbn)

    # Auto-fallback: clones de Nano (CH340) usam o bootloader antigo (57600).
    if rc != 0 and not args.old_bootloader:
        print("\nUpload falhou. Tentando com o BOOTLOADER ANTIGO (comum em clones CH340)…\n")
        rc = compile_and_upload(base + ":cpu=atmega328old")

    print("\nOK: firmware gravado." if rc == 0 else "\nFALHA na gravação.")
    sys.exit(rc)


if __name__ == "__main__":
    main()
