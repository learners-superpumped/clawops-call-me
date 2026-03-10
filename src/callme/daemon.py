"""Daemon process entry point.

SDK Agent를 시작하고 HTTP Control API를 제공한다.
ngrok/webhook 없이 SDK의 reverse WebSocket으로 동작한다.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from logging.handlers import RotatingFileHandler

from .call_manager import CallManager
from .config import load_config, validate_config
from .daemon_api import DaemonApi
from .daemon_lifecycle import (
    CALLME_DIR,
    LOG_BACKUP_COUNT,
    LOG_FILE,
    LOG_MAX_BYTES,
    cleanup_pid_file,
    write_control_port,
    write_pid_file,
)


class _StreamToLogger:
    """File-like wrapper that forwards writes to the logging system."""

    def __init__(self, logger: logging.Logger, level: int) -> None:
        self._logger = logger
        self._level = level
        self._buffer = ""
        self.encoding = "utf-8"

    def write(self, message: str) -> int:
        if not message:
            return 0
        self._buffer += message
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.rstrip("\r")
            if line:
                self._logger.log(self._level, line)
        return len(message)

    def flush(self) -> None:
        if self._buffer:
            line = self._buffer.rstrip("\r")
            if line:
                self._logger.log(self._level, line)
            self._buffer = ""


CALLME_DIR.mkdir(parents=True, exist_ok=True)

if LOG_MAX_BYTES > 0:
    log_handler: logging.Handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=max(LOG_BACKUP_COUNT, 0),
        encoding="utf-8",
    )
else:
    log_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    handlers=[log_handler],
)
log = logging.getLogger("callme.daemon")

# Capture stray prints so everything goes through the rotating log handler.
sys.stdout = _StreamToLogger(logging.getLogger("callme.stdout"), logging.INFO)
sys.stderr = _StreamToLogger(logging.getLogger("callme.stderr"), logging.ERROR)

SHUTDOWN_GRACE_S = 30


async def main() -> None:
    config = load_config()
    errors = validate_config(config)
    if errors:
        log.error("Missing configuration:\n  - %s", "\n  - ".join(errors))
        sys.exit(1)

    write_pid_file()
    write_control_port(config.control_port)

    call_manager = CallManager(config)

    shutdown_timer: asyncio.TimerHandle | None = None
    shutdown_event = asyncio.Event()

    async def do_shutdown() -> None:
        log.info("Shutting down...")
        await daemon_api.shutdown()
        await call_manager.stop()
        cleanup_pid_file()
        shutdown_event.set()

    def on_ref_count_zero() -> None:
        nonlocal shutdown_timer
        log.info("No clients connected, shutting down in %ds...", SHUTDOWN_GRACE_S)
        loop = asyncio.get_event_loop()
        shutdown_timer = loop.call_later(
            SHUTDOWN_GRACE_S, lambda: asyncio.ensure_future(do_shutdown())
        )

    def on_ref_count_positive() -> None:
        nonlocal shutdown_timer
        if shutdown_timer:
            log.info("Client reconnected, cancelling shutdown")
            shutdown_timer.cancel()
            shutdown_timer = None

    daemon_api = DaemonApi(
        call_manager=call_manager,
        on_ref_count_zero=on_ref_count_zero,
        on_ref_count_positive=on_ref_count_positive,
    )

    try:
        await call_manager.start()
        await daemon_api.start(config.control_port)

        log.info("Daemon ready")
        log.info("Control API: http://127.0.0.1:%d", config.control_port)

        # Wait for shutdown signal
        loop = asyncio.get_event_loop()
        for sig in ("SIGINT", "SIGTERM"):
            try:
                loop.add_signal_handler(
                    getattr(__import__("signal"), sig),
                    lambda: asyncio.ensure_future(do_shutdown()),
                )
            except (NotImplementedError, AttributeError):
                pass

        await shutdown_event.wait()
    except Exception:
        log.exception("Fatal error")
        cleanup_pid_file()
        sys.exit(1)


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
