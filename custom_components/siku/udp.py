"""Async UDP helper for Siku integration.

Provides a small wrapper around asyncio DatagramProtocol/Transport
to send a payload and await a single response with timeout, plus
support for fire-and-forget send.
"""

from __future__ import annotations
import time
import asyncio
import logging

LOGGER = logging.getLogger(__name__)


class _UdpProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.transport: asyncio.DatagramTransport | None = None
        self._future: asyncio.Future[tuple[bytes, tuple[str, int]]] | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        # transport will be a DatagramTransport
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        if self._future and not self._future.done():
            self._future.set_result((data, addr))

    def error_received(self, exc: Exception) -> None:
        if self._future and not self._future.done():
            self._future.set_exception(exc)

    def connection_lost(self, exc: Exception | None) -> None:
        if self._future and not self._future.done():
            self._future.set_exception(exc or ConnectionError("UDP connection lost"))

    async def request(
        self, payload: bytes, timeout: float, addr: tuple[str, int]
    ) -> tuple[bytes, tuple[str, int]]:
        loop = asyncio.get_running_loop()
        self._future = loop.create_future()
        assert self.transport is not None
        self.transport.sendto(payload, addr)
        return await asyncio.wait_for(self._future, timeout=timeout)

    def send_only(self, payload: bytes, addr: tuple[str, int]) -> None:
        assert self.transport is not None
        self.transport.sendto(payload, addr)


class AsyncUdpClient:
    """Reusable UDP client using asyncio datagram transport."""

    def __init__(self, host: str, port: int) -> None:
        """Initialize the UDP client for a host and port."""
        self._host = host
        self._port = port
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: _UdpProtocol | None = None
        self._lock = asyncio.Lock()

    async def ensure_transport(self) -> None:
        """Ensure the asyncio datagram transport is created."""
        if self._transport and self._protocol:
            return
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            _UdpProtocol,
            remote_addr=(self._host, self._port),
        )
        self._transport = transport  # type: ignore[assignment]
        self._protocol = protocol  # type: ignore[assignment]

    async def close(self) -> None:
        """Close the transport and release resources."""
        if self._transport:
            self._transport.close()
        self._transport = None
        self._protocol = None

    async def request(self, payload: bytes, timeout: float = 5.0) -> bytes:
        """Send a payload and await the response with a timeout."""
        await self.ensure_transport()
        assert self._protocol is not None
        async with self._lock:
            start_time = time.time()
            try:
                LOGGER.debug(
                    "[UDP %s:%d] Sending %d bytes, waiting for response (timeout=%.1fs)",
                    self._host,
                    self._port,
                    len(payload),
                    timeout,
                )
                data, _ = await self._protocol.request(
                    payload, timeout, (self._host, self._port)
                )
                elapsed = time.time() - start_time
                LOGGER.debug(
                    "[UDP %s:%d] Received %d bytes in %.3f seconds",
                    self._host,
                    self._port,
                    len(data),
                    elapsed,
                )
                return data
            except asyncio.TimeoutError:
                elapsed = time.time() - start_time
                LOGGER.warning(
                    "[UDP %s:%d] No response received after %.3f seconds (timeout=%.1fs)",
                    self._host,
                    self._port,
                    elapsed,
                    timeout,
                )
                raise

    async def send_only(self, payload: bytes) -> None:
        """Send a payload without waiting for a response."""
        await self.ensure_transport()
        assert self._protocol is not None
        async with self._lock:
            self._protocol.send_only(payload, (self._host, self._port))
