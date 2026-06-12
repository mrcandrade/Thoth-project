"""Baixa os modelos .task do MediaPipe Tasks para models/mediapipe/.

Fonte: https://ai.google.dev/edge/mediapipe (Google). Os arquivos NÃO são
versionados no Git (ver .gitignore).
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

DEST = Path(__file__).resolve().parents[1] / "models" / "mediapipe"

MODELS = {
    "face_detector": "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.task",
    "face_landmarker": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
    "hand_landmarker": "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
    "gesture_recognizer": "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task",
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
