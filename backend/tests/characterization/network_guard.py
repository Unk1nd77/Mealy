"""Opt-in pytest plugin: deny sockets except the disposable Redis endpoint."""

import os
import sys
from urllib.parse import urlparse


def pytest_configure(config):
    redis = urlparse(os.environ.get("REDIS_URL", "redis://127.0.0.1:1/15"))
    allowed = set()
    if os.environ.get("MEALY_DISPOSABLE_REDIS") == "1":
        allowed.add(("127.0.0.1", redis.port))
    if os.environ.get("MEALY_DISPOSABLE_DB") == "1":
        database = urlparse(os.environ["TEST_DATABASE_URL"])
        allowed.add(("127.0.0.1", database.port))

    def guard(event, args):
        if event == "socket.connect":
            address = args[1]
            if not isinstance(address, tuple) or address[:2] not in allowed:
                raise RuntimeError("CHARACTERIZATION_NETWORK_BLOCK: unexpected socket connection")

    sys.addaudithook(guard)
