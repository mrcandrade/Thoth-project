"""Visão computacional do jogo: classifica o gesto (pedra/papel/tesoura).

Dois níveis, do mais rápido ao mais robusto:

1. **MediaPipe HandLandmarker** (local, ~tempo real): detecta os 21 pontos da
   mão e decide quais dedos estão estendidos -> pedra/papel/tesoura. Também
   desenha o esqueleto no frame (feedback visual do stream de vídeo).
2. **VLM da Anthropic (Claude)** (fallback): quando o MediaPipe fica em dúvida
   (gesto ambíguo), envia o frame para o Claude e pede uma palavra. Usa a API
   da Anthropic — o mesmo provedor dos agentes.

Reaproveita o modelo ``models/mediapipe/hand_landmarker.task`` do Thoth.
"""
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

os.environ.setdefault("GLOG_minloglevel", "2")  # silencia avisos do TFLite

import cv2
import numpy as np

log = logging.getLogger("jokenpo.vision")

# Esqueleto da mão (21 landmarks) para desenhar.
_CONN = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
]
# (tip, pip) de cada dedo — dedo estendido se a ponta está mais longe do pulso
# que a junta PIP (robusto a rotação no plano).
_FINGERS = {"index": (8, 6), "middle": (12, 10), "ring": (16, 14), "pinky": (20, 18)}


def _dist(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


class GestureClassifier:
    """Encapsula o HandLandmarker do MediaPipe + a heurística de jokenpô."""

    def __init__(self, model_path: str | Path, flip: bool = True):
        self._flip = flip
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp
        model_path = str(model_path)
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"modelo MediaPipe não encontrado: {model_path} "
                "(rode: python scripts/download_models.py no projeto Thoth)"
            )
        options = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.6,
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

    def process(self, frame_bgr: np.ndarray) -> tuple[np.ndarray, str | None]:
        """Recebe um frame BGR, devolve (frame anotado, jogada|None)."""
        if self._flip:
            frame_bgr = cv2.flip(frame_bgr, 1)  # visão de espelho
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_img = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        self._ts_ms += 33
        res = self._lm.detect_for_video(mp_img, self._ts_ms)

        jogada: str | None = None
        if res.hand_landmarks:
            lms = res.hand_landmarks[0]
            h, w = frame_bgr.shape[:2]
            px = [(int(lm.x * w), int(lm.y * h)) for lm in lms]
            for a, b in _CONN:
                cv2.line(frame_bgr, px[a], px[b], (0, 200, 0), 2)
            for (x, y) in px:
                cv2.circle(frame_bgr, (x, y), 3, (0, 120, 255), -1)

            pts = np.array([[lm.x, lm.y] for lm in lms], dtype=np.float32)
            jogada = self._classificar(pts)
            rotulo = jogada.upper() if jogada else "?"
            cv2.putText(frame_bgr, rotulo, (10, 40), cv2.FONT_HERSHEY_SIMPLEX,
                        1.1, (0, 230, 0), 3)
        else:
            cv2.putText(frame_bgr, "mostre a mao", (10, 34),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 230), 2)
        return frame_bgr, jogada

    def _classificar(self, pts: np.ndarray) -> str | None:
        wrist = pts[0]
        estendido = {}
        for nome, (tip, pip) in _FINGERS.items():
            estendido[nome] = _dist(pts[tip], wrist) > _dist(pts[pip], wrist)
        n = sum(estendido.values())

        if n == 0:
            return "pedra"                       # punho fechado
        if n >= 4:
            return "papel"                       # mão aberta
        if estendido["index"] and estendido["middle"] \
                and not estendido["ring"] and not estendido["pinky"]:
            return "tesoura"                     # indicador + médio
        return None                              # ambíguo -> deixa o VLM decidir


def classificar_com_vlm(frame_bgr: np.ndarray, model: str, timeout: float = 8.0) -> str | None:
    """Fallback: pergunta ao Claude (VLM da Anthropic) qual é o gesto.

    Devolve a jogada normalizada ou None (sem chave, erro ou resposta inválida).
    """
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic

        from .logic import normalizar_jogada

        ok, buf = cv2.imencode(".jpg", frame_bgr)
        if not ok:
            return None
        b64 = base64.b64encode(buf.tobytes()).decode("ascii")
        client = anthropic.Anthropic(api_key=key, timeout=timeout)
        msg = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text", "text": (
                        "Nesta imagem, a pessoa faz um gesto de jokenpô: pedra (punho "
                        "fechado), papel (mão aberta) ou tesoura (dois dedos em V). "
                        "Responda com UMA palavra: pedra, papel ou tesoura.")},
                ],
            }],
        )
        txt = "".join(getattr(b, "text", "") for b in msg.content)
        return normalizar_jogada(txt)
    except Exception as exc:  # noqa: BLE001
        log.warning("VLM Anthropic falhou (%s): %s", type(exc).__name__, str(exc)[:200])
        return None
