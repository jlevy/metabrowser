"""Spike: one policy, the platform's confinement prefix.

``probes.py`` asks for confinement by policy and gets the prefix of whichever backend
this platform has: ``confine_linux.py`` behind the host's interpreter on Linux, and
``sandbox-exec`` with a profile from ``confine_macos.py`` on macOS. That is the shape the
plan gives ``metabrowser.isolation``: a backend is a command prefix, chosen by a probe.
"""

from __future__ import annotations

import os
import sys
import sysconfig
from typing import Any

import confine_macos
import confine_probe


def name() -> str | None:
    """This platform's backend, or None where the spike has none."""
    if sys.platform.startswith("linux"):
        return "landlock+seccomp"
    if sys.platform == "darwin":
        return "sandbox-exec"
    return None


def interpreter_roots() -> list[str]:
    """What the host's interpreter itself reads, beyond the system's libraries."""
    if sys.platform.startswith("linux"):
        return confine_probe.interpreter_roots()
    found = {sys.prefix, sys.base_prefix, sys.exec_prefix, sysconfig.get_path("stdlib")}
    return sorted(found | {os.path.realpath(path) for path in found})


def prefix(policy: dict[str, Any], program: str | None = None) -> list[str]:
    """The command prefix that confines what follows it to *policy*.

    *program* is what will follow it. ``sandbox-exec`` execs it under the profile, so
    with ``processes`` set to ``none`` the profile must name it.
    """
    if sys.platform == "darwin":
        exec_list = [*policy.get("exec", []), *([program] if program else [])]
        return confine_macos.prefix({**policy, "exec": exec_list})
    return confine_probe.prefix(policy)
