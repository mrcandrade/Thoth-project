"""Baixa o modelo de rastreamento da mão do MediaPipe para models/mediapipe/.

Fonte: https://ai.google.dev/edge/mediapipe (Google). Não é versionado no Git.
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

DEST = Path(__file__).resolve().parents[1] / "models" / "mediapipe"

MODELS = {
    "hand_landmarker": "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
}


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    for name, url in MODELS.items():
        out = DEST / Path(url).name
        if out.exists():
            print(f"[ok] {out.name} já existe")
            continue
        print(f"baixando {name}: {url}")
        try:
            urllib.request.urlretrieve(url, out)
            print(f"  -> {out}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ! falha ({exc}). Verifique a URL atual em ai.google.dev.")


if __name__ == "__main__":
    main()
