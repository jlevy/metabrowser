"""Make a test run a module's import again, and leave the process as it found it.

A test that has to see a module import (a pin's routes are imported as it is served, so a
first request does not import them on the event loop) forgets the module so the next
import runs its code. Deleting it from ``sys.modules`` is not enough, and what is left
behind is a trap for every test that runs after it in the same process:

* Importing a submodule also sets it as an attribute of its package, which undoing the
  deletion does not put back. Afterwards ``sys.modules`` holds the old module and the
  package holds the new one.
* ``import pkg.mod`` and ``from pkg.mod import name``, which the server does where it
  serves a route, read ``sys.modules``: the old module. ``from pkg import mod``, which a
  test does to patch it, reads the package's attribute: the new one.
* A patch of the module the test imported then changes a module the server does not run.
  ``tests/test_cli_git_pin_golden.py::test_golden_pin_age_groups`` fixes the clock that
  way, and where it ran after such a test in one pytest-xdist worker every file was
  "older" by the real clock (mb-6byq, three CI failures).

``forget_module`` removes both and puts both back.
"""

from __future__ import annotations

import sys

import pytest


def forget_module(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """Forget the module *name* until *monkeypatch* undoes, so its next import runs it afresh.

    Undoing puts back the module in ``sys.modules`` and the attribute its package holds,
    so afterwards every way of reaching it finds one object.
    """

    parent_name, _, child = name.rpartition(".")
    monkeypatch.delitem(sys.modules, name, raising=False)
    parent = sys.modules.get(parent_name)
    if parent is not None:
        monkeypatch.delattr(parent, child, raising=False)
