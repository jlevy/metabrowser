"""How a command-line tool that ``metab`` runs was installed, and the step that upgrades it.

``metab`` runs ``git`` and ``gh``, so it owns their minimums (``ACQUISITION_MINIMUM`` in
:mod:`metabrowser.git.process`, ``GH_MINIMUM`` in the GitHub plugin's ``gh_status.py``),
and the step that brings one up to its minimum is written beside each. This module only
reads, from the executable's canonical path, which package manager put it there, so each
tool's step names that manager's own upgrade rather than a second install beside it.
``metab --doctor`` reports the step as a check's ``remedy`` (:mod:`metabrowser.cli.doctor`).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Literal

type InstallMethod = Literal["homebrew", "macports", "apple", "other"]
"""Who installed a tool: Homebrew, MacPorts, Apple's developer tools, or anything else."""


def install_method(executable: str) -> InstallMethod:
    """Which package manager installed *executable*, read from its canonical path.

    Homebrew links ``bin/<tool>`` to a version under ``Cellar/``, MacPorts installs under
    ``/opt/local/``, and on macOS ``/usr/bin/git`` is Apple's shim for the Command Line
    Tools or Xcode, as is anything under them. Reads only the path, never the tool.
    """

    real = os.path.realpath(executable)
    if "/Cellar/" in real:
        return "homebrew"
    if real.startswith("/opt/local/"):
        return "macports"
    if sys.platform == "darwin" and (
        real.startswith(("/usr/bin/", "/Library/Developer/CommandLineTools/"))
        or ".app/Contents/Developer/" in real
    ):
        return "apple"
    return "other"


@dataclass(frozen=True, slots=True)
class Remedy:
    """What fixes a check: a sentence, and the one command to run or page to open.

    ``command`` is a shell command to copy as it is, ``url`` a page to open; either may
    be ``None``, and both are when nothing the user runs fixes it.
    """

    text: str
    command: str | None = None
    url: str | None = None

    def to_json(self) -> dict[str, str | None]:
        return {"text": self.text, "command": self.command, "url": self.url}


__all__ = ["InstallMethod", "Remedy", "install_method"]
