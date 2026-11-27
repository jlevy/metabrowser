"""Whether a file's mode can refuse this process, for the tests that stage a refusal.

A test that makes a directory read-only, to see what the product does when a write is
refused, needs the refusal to happen. Root's writes are never refused by a mode, so for
root the write succeeds and the test fails on a refusal that never came, which says
nothing about the product; the tests that ask here failed so in a cloud container whose
shell is root (2026-11-26), and passed there as an ordinary user of a user namespace.
CI runs as an ordinary user and runs them, so strict mode fails the skip there
(``docs/e2e-testing.md``, "Skips").

A test calls :func:`require_mode_denials` before it stages the refusal, as
``tests/ipv6_loopback.py``'s tests ask for an IPv6 loopback.
"""

from __future__ import annotations

import os
from typing import Final

import pytest

MODE_DENIAL_SKIP: Final = "root is never denied by modes, so a denial cannot be staged"


def modes_deny() -> bool:
    """Whether a file's mode can refuse this process: always, except for root."""

    geteuid = getattr(os, "geteuid", None)
    return geteuid is None or geteuid() != 0


def require_mode_denials() -> None:
    """Skip the calling test where a file's mode cannot refuse this process."""

    if not modes_deny():
        pytest.skip(MODE_DENIAL_SKIP)
