"""Reconhecimento facial em tempo real: identidade + confiança.

Usa a biblioteca ``face_recognition`` (dlib, encodings de 128-D) — simples de
integrar para o MVP. Para máxima robustez a pose/iluminação, a alternativa
recomendada é InsightFace (buffalo_l, ArcFace 512-D) — ver bloco comentado.

A galeria é gerada por ``scripts/enroll_face.py`` a partir das fotos em
``data/known_faces/<Nome>/*.jpg``.
"""
from __future__ import annotations

import pickle
from pathlib import Path

import cv2
import face_recognition
import numpy as np


class FaceRecognizer:
    def __init__(self, gallery_path: str | Path = "data/encodings.pkl", tolerance: float = 0.45):
        # tolerance: distância euclidiana máx. para considerar "match".
        # ~0.6 é o default da lib; 0.4–0.5 reduz falsos positivos. CALIBRE.
        self.gallery_path = Path(gallery_path)
        with self.gallery_path.open("rb") as f:
            self.gallery: dict[str, np.ndarray] = pickle.load(f)
        self.names = list(self.gallery.keys())
        self.matrix = (
            np.stack(list(self.gallery.values())) if self.gallery else np.empty((0, 128))
        )
        self.tolerance = tolerance

    def identify(self, frame_bgr: np.ndarray) -> list[tuple[str, float, tuple]]:
        """Retorna lista de (nome, confiança 0–1, bbox) para cada rosto no frame."""
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        boxes = face_recognition.face_locations(rgb, model="hog")
        encs = face_recognition.face_encodings(rgb, boxes)
        results: list[tuple[str, float, tuple]] = []

        for enc, box in zip(encs, boxes):
            if self.matrix.shape[0] == 0:
                results.append(("Desconhecido", 0.0, box))
                continue
            dists = np.linalg.norm(self.matrix - enc, axis=1)
            best = int(np.argmin(dists))
            dist = float(dists[best])
            if dist <= self.tolerance:
                # confiança aproximada: 1 quando dist=0, 0 quando dist=tolerance
                conf = max(0.0, 1.0 - dist / self.tolerance)
                results.append((self.names[best], conf, box))
            else:
                results.append(("Desconhecido", 0.0, box))
        return results


# ---------------------------------------------------------------------------
# ALTERNATIVA DE MAIOR PRECISÃO — InsightFace (ArcFace, 512-D), via ONNX:
#
#   from insightface.app import FaceAnalysis
#   import numpy as np
#   app = FaceAnalysis(name="buffalo_l")
#   app.prepare(ctx_id=-1)          # ctx_id=-1 => CPU; 0 => GPU (onnxruntime-gpu)
#   faces = app.get(frame_bgr)      # cada face: .embedding (512-D) e .bbox
#   # match por similaridade de cosseno contra a galeria (threshold ~0.35–0.5; CALIBRE)
#   def cosine(a, b): return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
#
# InsightFace roda bem em CPU via ONNX e é mais robusto a pose/iluminação.
# ---------------------------------------------------------------------------
