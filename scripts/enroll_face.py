"""Enrollment facial: gera/atualiza a galeria de encodings.

Lê fotos em ``<src>/<Nome>/*.jpg``, calcula um encoding médio (128-D) por
pessoa com a biblioteca ``face_recognition`` e salva em ``<out>`` (pickle).

Uso:
    python scripts/enroll_face.py                       # processa todas as pessoas
    python scripts/enroll_face.py --name "Prof. Fulano" # apenas uma (merge na galeria)
"""
from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import face_recognition  # depende de dlib
import numpy as np


def encode_person(person_dir: Path) -> np.ndarray | None:
    encs: list[np.ndarray] = []
    for img_path in sorted(person_dir.glob("*.jp*g")):
        image = face_recognition.load_image_file(img_path)  # RGB
        boxes = face_recognition.face_locations(image, model="hog")  # "cnn" se tiver GPU
        found = face_recognition.face_encodings(image, boxes)
        if not found:
            print(f"[aviso] nenhum rosto em {img_path}")
            continue
        encs.append(found[0])
    if not encs:
        return None
    print(f"  {person_dir.name}: {len(encs)} foto(s)")
    return np.mean(np.stack(encs), axis=0)  # 1 vetor 128-D representativo


def main() -> None:
    ap = argparse.ArgumentParser(description="Enrollment facial (face_recognition).")
    ap.add_argument("--src", default="data/known_faces", help="diretório com <Nome>/*.jpg")
    ap.add_argument("--out", default="data/encodings.pkl", help="arquivo da galeria")
    ap.add_argument("--name", default=None, help="processa apenas esta pessoa (merge)")
    args = ap.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    if not src.exists():
        raise SystemExit(f"diretório de fotos não existe: {src}")

    # carrega galeria existente (para merge incremental)
    gallery: dict[str, np.ndarray] = {}
    if out.exists():
        with out.open("rb") as f:
            gallery = pickle.load(f)

    people = (
        [src / args.name] if args.name else [p for p in sorted(src.iterdir()) if p.is_dir()]
    )
    print(f"Processando {len(people)} pessoa(s)…")
    for person_dir in people:
        if not person_dir.is_dir():
            print(f"[aviso] pulando {person_dir} (não é diretório)")
            continue
        vec = encode_person(person_dir)
        if vec is not None:
            gallery[person_dir.name] = vec

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        pickle.dump(gallery, f)
    print(f"galeria salva: {len(gallery)} pessoa(s) -> {out}")


if __name__ == "__main__":
    main()
