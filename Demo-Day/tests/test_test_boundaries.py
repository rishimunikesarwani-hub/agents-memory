import socket

import pytest


def test_deterministic_test_cannot_connect_to_external_service():
    with socket.socket() as connection, pytest.raises(RuntimeError, match="External network is disabled"):
        connection.connect(("192.0.2.1", 443))
