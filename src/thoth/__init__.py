"""Thoth — controle web da mão protética HACKberry.

Entrega: painel web (FastAPI) que comanda a mão por serial (gestos, ângulos por
dedo, e-stop) e espelha a mão do usuário via visão computacional (MediaPipe).
Camadas: perception/vision (câmera + rastreamento) · actuation (serial + gestos)
· safety (limites) · api + web (painel). Suba com: python scripts/web.py
"""

__version__ = "0.1.0"
