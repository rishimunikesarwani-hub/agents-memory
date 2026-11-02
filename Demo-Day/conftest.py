import socket

import pytest

from user_memory.config import Settings
from user_memory.evidence import build_fingerprint


def pytest_addoption(parser):
    parser.addoption("--backend", choices=("memory", "postgres"), default="memory")


def pytest_configure(config):
    Settings.from_env()


@pytest.hookimpl(optionalhook=True)
def pytest_json_modifyreport(json_report):
    settings = Settings.from_env()
    json_report["verification"] = {
        "build_fingerprint": build_fingerprint(),
        "chat_model": settings.chat_model,
        "memory_model": settings.memory_model,
        "embedding_model": settings.embedding_model,
        "embedding_dims": settings.embedding_dims,
        "real_api_key_recorded": False,
    }


@pytest.fixture(autouse=True)
def prevent_unmarked_external_network(request, monkeypatch):
    if request.node.get_closest_marker("live") is not None:
        return
    original_connect = socket.socket.connect

    def guarded_connect(sock, address):
        host = address[0] if isinstance(address, tuple) else ""
        if host not in {"127.0.0.1", "::1", "localhost"}:
            raise RuntimeError("External network is disabled in deterministic tests.")
        return original_connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
