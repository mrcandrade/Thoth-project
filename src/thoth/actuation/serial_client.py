"""Cliente serial assíncrono para o firmware hackberry_serial.ino (`HandLink`).

Usa pyserial-asyncio (casa com o event loop do Agno: leitura não-bloqueante,
sem thread de polling). Conexão/handshake, reconexão com backoff, envio de
comando com ACK e timeout, heartbeat assíncrono e parsing de status.

O import de ``serial_asyncio`` é adiado para ``connect()`` para que importar
este módulo não exija a dependência (útil em testes com uma mão falsa).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

log = logging.getLogger("thoth.hand")


@dataclass
class HandStatus:
    thumb: int
    index: int
    other: int
    mode: str  # "HOST" | "SAFE"


class HandLink:
    """Mantém a sessão serial com a mão. Uma instância, compartilhada por todo o app."""

    def __init__(
        self,
        port: str,
        baud: int = 115200,
        ack_timeout: float = 0.4,
        heartbeat_period: float = 0.3,
    ):
        self.port = port
        self.baud = baud
        self.ack_timeout = ack_timeout
        self.heartbeat_period = heartbeat_period

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._ack_waiter: asyncio.Future[str] | None = None
        self._send_lock = asyncio.Lock()  # 1 comando "em voo" -> preserva ordem dos ACKs
        self._tasks: list[asyncio.Task] = []
        self._connected = asyncio.Event()
        self.last_status: HandStatus | None = None

    # ---- ciclo de vida -----------------------------------------------------
    async def connect(self) -> None:
        """Conecta, espera o banner 'R' e dispara reader + heartbeat."""
        import serial_asyncio  # pip install pyserial-asyncio  (import adiado)

        backoff = 0.5
        while True:
            try:
                self._reader, self._writer = await serial_asyncio.open_serial_connection(
                    url=self.port, baudrate=self.baud
                )
                # após abrir a porta, o Nano reinicia (auto-reset DTR): aguarda o banner 'R'
                await self._await_ready(timeout=5.0)
                self._connected.set()
                self._tasks = [
                    asyncio.create_task(self._reader_loop(), name="hand-reader"),
                    asyncio.create_task(self._heartbeat_loop(), name="hand-heartbeat"),
                ]
                log.info("HandLink conectado em %s", self.port)
                return
            except Exception as exc:  # noqa: BLE001
                log.warning("Falha ao conectar (%s); retry em %.1fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 5.0)

    async def _await_ready(self, timeout: float) -> None:
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            line = await asyncio.wait_for(self._reader.readline(), timeout=timeout)
            if line.strip() == b"R":
                return
        raise TimeoutError("banner 'R' não recebido")

    async def close(self) -> None:
        for t in self._tasks:
            t.cancel()
        self._tasks = []
        if self._writer:
            self._writer.close()
        self._connected.clear()

    # ---- envio com ACK -----------------------------------------------------
    async def _send_raw(self, line: str) -> str:
        """Envia uma linha e aguarda a próxima resposta (ACK/ERR). Serializado."""
        async with self._send_lock:
            self._ack_waiter = asyncio.get_event_loop().create_future()
            self._writer.write((line + "\n").encode())
            await self._writer.drain()
            try:
                return await asyncio.wait_for(self._ack_waiter, self.ack_timeout)
            except asyncio.TimeoutError:
                log.error("timeout aguardando ACK de %r", line)
                raise
            finally:
                self._ack_waiter = None

    async def set_angles(self, thumb: int, index: int, other: int) -> str:
        return await self._send_raw(f"G:{thumb},{index},{other}")

    async def gesture(self, name: str) -> str:
        return await self._send_raw(f"P:{name.upper()}")

    async def stop(self) -> str:
        """E-stop lógico: abre a mão imediatamente."""
        return await self._send_raw("S")

    async def query(self) -> HandStatus | None:
        await self._send_raw("?")
        return self.last_status

    # ---- loops internos ----------------------------------------------------
    async def _reader_loop(self) -> None:
        try:
            while True:
                raw = await self._reader.readline()
                if not raw:
                    raise ConnectionError("EOF na serial")
                line = raw.decode(errors="replace").strip()
                if not line:
                    continue
                self._route(line)
        except Exception as exc:  # noqa: BLE001
            log.error("reader_loop caiu: %s — reconectando", exc)
            self._connected.clear()
            asyncio.create_task(self._reconnect())

    def _route(self, line: str) -> None:
        if line.startswith("S:"):  # status assíncrono
            try:
                t, i, o, mode = line[2:].split(",")
                self.last_status = HandStatus(int(t), int(i), int(o), mode)
            except ValueError:
                log.warning("status malformado: %r", line)
        # ACK/ERR resolvem o future do comando em voo
        if self._ack_waiter and not self._ack_waiter.done():
            if line.startswith("E:"):
                self._ack_waiter.set_exception(RuntimeError(line))
            else:
                self._ack_waiter.set_result(line)

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_period)
            if self._connected.is_set():
                try:
                    await self._send_raw("H")
                except Exception:  # noqa: BLE001
                    pass  # falha de heartbeat é tratada pela reconexão do reader

    async def _reconnect(self) -> None:
        await self.close()
        await asyncio.sleep(0.5)
        await self.connect()
        # política de segurança: NÃO reenviar gesto perigoso automaticamente.
        await self.stop()  # deixa a mão aberta após reconectar
