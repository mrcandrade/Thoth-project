"""Cliente de visão: captura um frame da câmera e pergunta a um VLM.

Usa o modelo multimodal configurado em VISION_MODEL (ex.: llama-4-scout na Groq).
Reaproveita o endpoint OpenAI-compatible (mesma chave do LLM). É usado pelas
skills de visão (ver_cena, ler_texto, reconhecer_objetos) e pelo jokenpô.
"""
from __future__ import annotations

import base64
import logging
import threading

from thoth.core.config import get_settings

log = logging.getLogger("thoth.skills.vision_client")

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        from thoth.agent.llm import resolve_endpoint

        base, key = resolve_endpoint(get_settings())
        _client = OpenAI(base_url=base, api_key=key)
    return _client


def _capturar_sync(warmup: int) -> str | None:
    """Captura síncrona (pode bloquear): roda dentro de uma thread com timeout."""
    import cv2

    s = get_settings()
    cap = cv2.VideoCapture(s.camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()  # libera o handle parcial antes do fallback (evita vazamento)
        cap = cv2.VideoCapture(s.camera_index)
    if not cap.isOpened():
        cap.release()
        log.warning("não consegui abrir a câmera índice %s", s.camera_index)
        return None
    try:
        frame = None
        for _ in range(max(1, warmup)):  # descarta quadros iniciais (auto-exposição)
            ok, f = cap.read()
            if ok:
                frame = f
        if frame is None:
            return None
        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            return None
        return base64.b64encode(buf.tobytes()).decode("ascii")
    finally:
        cap.release()


def capturar_frame_b64(warmup: int = 5, timeout: float = 6.0) -> str | None:
    """Captura um quadro JPEG em base64 (ou None). Com timeout para não travar o loop.

    A captura roda numa thread separada: se a câmera congelar (driver USB bugado),
    devolvemos None em vez de bloquear o agente indefinidamente.
    """
    try:
        import cv2  # noqa: F401  (só valida a instalação aqui)
    except ImportError:
        log.warning("opencv (cv2) não instalado — visão indisponível.")
        return None

    box: dict[str, str | None] = {"b64": None}

    def _work() -> None:
        try:
            box["b64"] = _capturar_sync(warmup)
        except Exception as exc:  # noqa: BLE001
            log.warning("captura da câmera falhou: %s", exc)

    th = threading.Thread(target=_work, daemon=True, name="cam-capture")
    th.start()
    th.join(timeout)
    if th.is_alive():
        log.warning("captura da câmera excedeu %.1fs — câmera pode estar travada", timeout)
        return None
    return box["b64"]


def perguntar_visao(pergunta: str, max_tokens: int = 300) -> str:
    """Captura um frame e faz uma pergunta sobre ele ao VLM; devolve a resposta."""
    b64 = capturar_frame_b64()
    if b64 is None:
        return "Não consegui acessar a câmera agora."
    s = get_settings()
    try:
        resp = _get_client().chat.completions.create(
            model=s.vision_model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": pergunta},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }],
            temperature=0.3,
            max_tokens=max_tokens,
        )
        out = (resp.choices[0].message.content or "").strip()
        return out or "Não consegui interpretar a imagem."
    except Exception as exc:  # noqa: BLE001
        log.warning("visão falhou (%s): %s", type(exc).__name__, str(exc)[:200])
        return f"Falha ao analisar a imagem ({type(exc).__name__})."
