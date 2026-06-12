"""Lista câmeras, microfones e portas seriais disponíveis (diagnóstico)."""
from __future__ import annotations


def list_serial() -> None:
    print("\n=== Portas seriais ===")
    try:
        from serial.tools import list_ports

        ports = list(list_ports.comports())
        if not ports:
            print("  (nenhuma)")
        for p in ports:
            print(f"  {p.device:12} {p.description}")
    except ImportError:
        print("  pyserial não instalado")


def list_cameras(max_index: int = 5) -> None:
    print("\n=== Câmeras ===")
    try:
        import cv2

        found = 0
        for i in range(max_index):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                print(f"  index {i}: {w}x{h}")
                found += 1
            cap.release()
        if not found:
            print("  (nenhuma)")
    except ImportError:
        print("  opencv-python não instalado")


def list_mics() -> None:
    print("\n=== Dispositivos de áudio ===")
    try:
        import sounddevice as sd

        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                print(f"  index {i}: {d['name']} ({d['max_input_channels']} canais in)")
    except ImportError:
        print("  sounddevice não instalado")
    except Exception as exc:  # noqa: BLE001
        print(f"  erro ao consultar áudio: {exc}")


if __name__ == "__main__":
    list_serial()
    list_cameras()
    list_mics()
