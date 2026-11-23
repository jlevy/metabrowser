"""Whether this machine can listen on ``::1``, for the tests that serve on IPv6.

A machine with IPv6 turned off (some containers) has no IPv6 loopback, and a test that
binds one skips there. CI's runners have one, so strict mode fails the skip
(``docs/e2e-testing.md``, "Skips").
"""

from __future__ import annotations

import socket
from functools import cache

import pytest

IPV6_LOOPBACK_SKIP = "this machine has no IPv6 loopback"


@cache
def _has_ipv6_loopback() -> bool:
    if not socket.has_ipv6:
        return False
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as probe:
            probe.bind(("::1", 0))
    except OSError:
        return False
    return True


def require_ipv6_loopback() -> None:
    """Skip the calling test where ``::1`` cannot be bound."""

    if not _has_ipv6_loopback():
        pytest.skip(IPV6_LOOPBACK_SKIP)
