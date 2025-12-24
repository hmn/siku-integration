"""Async UDP helper for Siku integration."""

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
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        if self._future and not self._future.done():
            self._future.set_result((data, addr))

    def error_received(self, exc: Exception) -> None:
        LOGGER.error("UDP error received: %s", exc)
        if self._future and not self._future.done():
            self._future.set_exception(exc)

    def connection_lost(self, exc: Exception | None) -> None:
        if exc:
            LOGGER.debug("UDP connection lost: %s", exc)
        if self._future and not self._future.done():
            self._future.set_exception(exc or ConnectionError("UDP connection lost"))

    async def request(
        self, payload: bytes, timeout: float
    ) -> tuple[bytes, tuple[str, int]]:
        """Send payload to the pre-connected destination and wait for response."""
        loop = asyncio.get_running_loop()
        self._future = loop.create_future()

        if not self.transport:
            raise ConnectionError("Transport not initialized")

        # Since we use remote_addr in create_datagram_endpoint,
        # we don't pass the address to sendto().
        self.transport.sendto(payload)
        return await asyncio.wait_for(self._future, timeout=timeout)

    def send_only(self, payload: bytes) -> None:
        """Send payload to the pre-connected destination."""
        if not self.transport:
            raise ConnectionError("Transport not initialized")
        self.transport.sendto(payload)


class AsyncUdpClient:
    """Reusable UDP client supporting IPv4, IPv6, and DNS."""

    def __init__(self, host: str, port: int) -> None:
        """Initialize the UDP client with the target host and port."""
        self._host = host
        self._port = port
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: _UdpProtocol | None = None
        self._lock = asyncio.Lock()
        self._req_counter = 0

    def _next_request_id(self) -> str:
        """Generate a unique request ID based on timestamp and counter."""
        self._req_counter = (self._req_counter + 1) % 1_000_000
        return f"{int(time.time() * 1000)}-{self._req_counter:06d}"

    async def ensure_transport(self) -> None:
        """Ensure the transport is created, supporting both IPv4 and IPv6."""
        if self._transport and not self._transport.is_closing():
            return

        loop = asyncio.get_running_loop()

        # create_datagram_endpoint handles DNS resolution and
        # picks AF_INET or AF_INET6 automatically.
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

    async def request(
        self, payload: bytes, timeout: float = 5.0, request_id: str | None = None
    ) -> bytes:
        """Send a payload and await the response with a timeout, logging by request id."""
        async with self._lock:
            await self.ensure_transport()
            assert self._protocol is not None

            rid = request_id or self._next_request_id()
            preview = payload[:8].hex().upper()
            start_time = time.time()

            try:
                LOGGER.debug(
                    "[UDP %s:%d req=%s] Sending %d bytes (hex head=%s)",
                    self._host,
                    self._port,
                    rid,
                    len(payload),
                    preview,
                )
                # No longer passing (host, port) here because the transport is 'connected'
                data, _ = await self._protocol.request(payload, timeout)

                elapsed = time.time() - start_time
                LOGGER.debug(
                    "[UDP %s:%d req=%s] Received %d bytes in %.3f seconds",
                    self._host,
                    self._port,
                    rid,
                    len(data),
                    elapsed,
                )
                return data

            except (asyncio.TimeoutError, ConnectionError, OSError) as err:
                # On any network failure or timeout, clear the transport so it
                # can be re-established on the next retry.
                LOGGER.warning(
                    "[UDP %s:%d req=%s] Communication failed: %s",
                    self._host,
                    self._port,
                    rid,
                    repr(err),
                )
                await self.close()
                raise

    async def send_only(self, payload: bytes, request_id: str | None = None) -> None:
        """Send a payload without waiting for a response, logging by request id."""
        async with self._lock:
            await self.ensure_transport()
            assert self._protocol is not None
            rid = request_id or self._next_request_id()
            preview = payload[:8].hex().upper()
            try:
                LOGGER.debug(
                    "[UDP %s:%d req=%s] Sending %d bytes (hex head=%s)",
                    self._host,
                    self._port,
                    rid,
                    len(payload),
                    preview,
                )
                self._protocol.send_only(payload)
            except Exception as err:
                LOGGER.warning(
                    "[UDP %s:%d req=%s] Send failed: %s",
                    self._host,
                    self._port,
                    rid,
                    repr(err),
                )
                await self.close()
                raise
