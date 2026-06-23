"""Baixa uma voz PT-BR do Piper (TTS) para models/piper/.

Fonte: rhasspy/piper-voices no Hugging Face. Não versionado no Git.
Uso:  python scripts/download_piper.py [--voice pt_BR-faber-medium]
"""
from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

DEST = Path(__file__).resolve().parents[1] / "models" / "piper"
BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

# voz -> caminho relativo (idioma/voz/qualidade) no repo de vozes
VOICES = {
    "pt_BR-faber-medium": "pt/pt_BR/faber/medium/pt_BR-faber-medium",
    "pt_BR-edresson-low": "pt/pt_BR/edresson/low/pt_BR-edresson-low",
}


def _download(url: str, out: Path) -> None:
    if out.exists() and out.stat().st_size > 1000:
        print(f"[ok] {out.name} já existe")
        return
    print(f"baixando {url}")
    urllib.request.urlretrieve(url, out)
    print(f"  -> {out} ({out.stat().st_size} bytes)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Baixa uma voz PT-BR do Piper.")
    ap.add_argument("--voice", default="pt_BR-faber-medium", choices=list(VOICES))
    args = ap.parse_args()

    DEST.mkdir(parents=True, exist_ok=True)
    rel = VOICES[args.voice]
    try:
        _download(f"{BASE}/{rel}.onnx", DEST / f"{args.voice}.onnx")
        _download(f"{BASE}/{rel}.onnx.json", DEST / f"{args.voice}.onnx.json")
        print(f"\nVoz pronta: {args.voice}  (configure PIPER_VOICE no .env)")
    except Exception as exc:  # noqa: BLE001
        print(f"! falha ({exc}). Verifique a URL em huggingface.co/rhasspy/piper-voices.")


if __name__ == "__main__":
    main()
