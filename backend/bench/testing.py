"""Isolation helpers: keep every benchmark run offline and away from developer state."""
from __future__ import annotations

import os
import socket
import tempfile

import pytest


def isolate_environment() -> None:
    """Point the app at a throwaway SQLite file and force mock providers.

    Must run before ``app.main`` / ``app.db.session`` are imported (they read settings at
    import time). ``tests/conftest.py`` does the same for pytest; this is for the CLI.
    """
    if "DATABASE_URL" not in os.environ:
        os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp(prefix='ctbench-')}/bench.db"
    os.environ.setdefault("MOCK_PROVIDERS", "true")


@pytest.fixture
def no_network(monkeypatch):
    """Fail loudly if any test tries to open an outbound socket connection."""
    def _blocked(self, *args, **kwargs):  # noqa: ARG001
        raise RuntimeError("network access is blocked in CommonThreadBench tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    yield


def block_network_for_process() -> None:
    """Permanently block outbound sockets in this process (used by the offline CLI)."""
    def _blocked(self, *args, **kwargs):  # noqa: ARG001
        raise RuntimeError("network access is blocked in CommonThreadBench offline runs")

    socket.socket.connect = _blocked
    socket.socket.connect_ex = _blocked
