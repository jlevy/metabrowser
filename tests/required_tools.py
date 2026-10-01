"""Gate for tests that need Node or Git on ``PATH``.

Both are prerequisites of this repository (``docs/development.md``). The first test
that needs one and finds it missing stops the session with one message. It used to
skip, and a run without Node then passed having checked none of the browser contracts
under ``tests/dom``.

Stopping, rather than failing each test, says it once instead of once per test, and a
run that selects no test needing the tool is not affected at all.

A developer who really has no Node, or no Git, names the tool in
``METABROWSER_ALLOW_MISSING_TOOLS`` (comma-separated). The tests that need it then
skip, and ``pytest -rs`` lists them. CI and ``make test`` never set it.

``tests/admitted_git.py`` is the same gate with the default the other way round: an
admitted Git release is not a prerequisite, so its absence skips unless CI names one.
"""

from __future__ import annotations

import os
import shutil

import pytest

ALLOW_MISSING_TOOLS_ENV = "METABROWSER_ALLOW_MISSING_TOOLS"
TOOLS = ("git", "node")


def _require(tool: str) -> str:
    found = shutil.which(tool)
    if found is not None:
        return found
    value = os.environ.get(ALLOW_MISSING_TOOLS_ENV, "")
    named = {name.strip() for name in value.split(",")} - {""}
    if tool in named:
        pytest.skip(f"{tool} is not on PATH, and {ALLOW_MISSING_TOOLS_ENV} allows that")
    message = (
        f"{tool} is not on PATH, and a selected test needs it. Install it "
        f"(docs/development.md), or set {ALLOW_MISSING_TOOLS_ENV}={tool} to skip the "
        "tests that need it."
    )
    if unknown := sorted(named - set(TOOLS)):
        message += (
            f" {ALLOW_MISSING_TOOLS_ENV}={value!r} names {', '.join(unknown)}, which this "
            f"gate does not know; the names it takes are {' and '.join(TOOLS)}."
        )
    pytest.exit(message, returncode=1)


def require_node() -> str:
    """Return the path of ``node``; without one, stop the run, or skip where allowed."""

    return _require("node")


def require_git() -> str:
    """Return the path of ``git``; without one, stop the run, or skip where allowed."""

    return _require("git")


# For a whole module or a parametrized case, where no test body is at hand to call the
# functions above. The fixtures they name are in tests/conftest.py.
needs_node = pytest.mark.usefixtures("node_on_path")
needs_git = pytest.mark.usefixtures("git_on_path")
