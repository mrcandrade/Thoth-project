"""Testes da lógica pura do jogo (sem hardware, sem LLM, sem câmera)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import logic  # noqa: E402


def test_julgar_vitorias_do_jogador():
    assert logic.julgar("pedra", "tesoura") == "vitoria"
    assert logic.julgar("papel", "pedra") == "vitoria"
    assert logic.julgar("tesoura", "papel") == "vitoria"


def test_julgar_derrotas_do_jogador():
    assert logic.julgar("tesoura", "pedra") == "derrota"
    assert logic.julgar("pedra", "papel") == "derrota"
    assert logic.julgar("papel", "tesoura") == "derrota"


def test_julgar_empates():
    for j in logic.JOGADAS:
        assert logic.julgar(j, j) == "empate"


def test_sortear_sempre_valido():
    for _ in range(200):
        assert logic.sortear_jogada() in logic.JOGADAS


def test_gesto_robo_mapeia_para_gestos_do_firmware():
    assert logic.GESTO_ROBO == {"pedra": "fist", "papel": "open", "tesoura": "point"}


def test_normalizar_jogada():
    assert logic.normalizar_jogada("PEDRA") == "pedra"
    assert logic.normalizar_jogada("mão aberta") == "papel"
    assert logic.normalizar_jogada("dois dedos em V") == "tesoura"
    assert logic.normalizar_jogada("sei lá") is None


if __name__ == "__main__":
    import traceback

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    falhas = 0
    for fn in fns:
        try:
            fn()
            print("OK  ", fn.__name__)
        except Exception:  # noqa: BLE001
            falhas += 1
            print("FALHA", fn.__name__)
            traceback.print_exc()
    print(f"\n{len(fns) - falhas}/{len(fns)} testes passaram.")
    sys.exit(1 if falhas else 0)
