"""Rastreamento da mão (MediaPipe Tasks - HandLandmarker) -> flexão por dedo (0..1).

Usa a API nova do MediaPipe (Tasks), que exige o modelo `hand_landmarker.task`
em models/mediapipe/ (baixe com scripts/download_models.py). Recebe um frame BGR,
detecta a mão, desenha os landmarks e calcula a flexão de cada grupo de dedos:
  thumb (polegar), index (indicador), other (média de médio/anelar/mínimo)
onde 0.0 = ABERTO/estendido e 1.0 = FECHADO/flexionado.

Heurística robusta a rotação no plano: distância da ponta de cada dedo ao pulso,
normalizada pelo tamanho da mão (pulso -> base do médio). Ajuste fino: _EXT_CURL.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

# Silencia avisos benignos do MediaPipe/TFLite (camada C++) — deve vir ANTES de
# qualquer import de mediapipe (que é adiado para dentro do HandTracker).
os.environ.setdefault("GLOG_minloglevel", "2")

import cv2
import numpy as np

log = logging.getLogger("thoth.hand_track")

# Conexões do esqueleto da mão (21 pontos) para desenhar.
_CONN = [
    (0, 1), (1, 2), (2, 3), (3, 4),            # polegar
    (0, 5), (5, 6), (6, 7), (7, 8),            # indicador
    (5, 9), (9, 10), (10, 11), (11, 12),       # médio
    (9, 13), (13, 14), (14, 15), (15, 16),     # anelar
    (13, 17), (17, 18), (18, 19), (19, 20),    # mínimo
    (0, 17),                                   # palma
]
_TIPS = {"index": 8, "middle": 12, "ring": 16, "pinky": 20}
_EXT_CURL = {
    # (estendido=flex0, fechado=flex1). Indicador com 'estendido' menor p/ abrir 100%.
    "index": (1.78, 1.05),
    "middle": (2.1, 1.05),
    "ring": (2.0, 1.0),
    "pinky": (1.8, 0.95),
}
# Polegar: distância ponta(4) -> base do mínimo(17), normalizada (aberto, fechado).
# 'aberto' menor => polegar relaxado já conta como aberto (não contrai sozinho).
_THUMB_EXT, _THUMB_CURL = 1.25, 0.55


def _norm(v: float, ext: float, curl: float) -> float:
    return float(np.clip((ext - v) / (ext - curl + 1e-6), 0.0, 1.0))


class HandTracker:
    def __init__(self, model_path: str | Path, min_det: float = 0.6, flip: bool = True):
        self._flip = flip  # espelha a imagem na horizontal (visão de espelho)
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp
        model_path = str(model_path)
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"modelo MediaPipe não encontrado: {model_path} "
                "(rode: python scripts/download_models.py)"
            )
        options = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=min_det,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._lm = vision.HandLandmarker.create_from_options(options)
        self._ts_ms = 0

    def close(self) -> None:
        try:
            self._lm.close()
        except Exception:  # noqa: BLE001
            pass

    def process(self, frame_bgr: np.ndarray) -> tuple[np.ndarray, tuple[float, float, float] | None]:
        if self._flip:
            frame_bgr = cv2.flip(frame_bgr, 1)  # espelha horizontalmente
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_img = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        self._ts_ms += 33  # timestamp monotônico crescente (exigência do modo VIDEO)
        res = self._lm.detect_for_video(mp_img, self._ts_ms)

        flex: tuple[float, float, float] | None = None
        if res.hand_landmarks:
            lms = res.hand_landmarks[0]
            h, w = frame_bgr.shape[:2]
            px = [(int(lm.x * w), int(lm.y * h)) for lm in lms]
            for a, b in _CONN:
                cv2.line(frame_bgr, px[a], px[b], (0, 200, 0), 2)
            for (x, y) in px:
                cv2.circle(frame_bgr, (x, y), 3, (0, 120, 255), -1)

            pts = np.array([[lm.x, lm.y] for lm in lms], dtype=np.float32)
            flex = self._flex(pts)
            t, i, o = flex
            cv2.putText(frame_bgr, f"polegar {t*100:.0f}%  indicador {i*100:.0f}%  3dedos {o*100:.0f}%",
                        (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 230, 0), 2)
        else:
            cv2.putText(frame_bgr, "mostre a mao para a camera", (10, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 230), 2)
        return frame_bgr, flex

    def _flex(self, pts: np.ndarray) -> tuple[float, float, float]:
        wrist = pts[0]
        scale = float(np.linalg.norm(pts[9] - wrist)) + 1e-6  # pulso -> base do médio

        def ratio(idx: int) -> float:
            return float(np.linalg.norm(pts[idx] - wrist)) / scale

        index = _norm(ratio(_TIPS["index"]), *_EXT_CURL["index"])
        middle = _norm(ratio(_TIPS["middle"]), *_EXT_CURL["middle"])
        ring = _norm(ratio(_TIPS["ring"]), *_EXT_CURL["ring"])
        pinky = _norm(ratio(_TIPS["pinky"]), *_EXT_CURL["pinky"])
        other = (middle + ring + pinky) / 3.0

        thumb_ratio = float(np.linalg.norm(pts[4] - pts[17])) / scale
        thumb = _norm(thumb_ratio, _THUMB_EXT, _THUMB_CURL)
        return thumb, index, other
