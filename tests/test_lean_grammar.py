"""The Lean grammar is the official Lean 4 grammar, ported rule for rule.

``src/metabrowser/static/syntax/lean.js`` copies every regex of vscode-lean4's
``syntaxes/lean4.json`` into its ``UPSTREAM`` table. The copy it follows is pinned in
``tests/fixtures/vscode-lean4/`` (``lean4.json`` at vscode-lean4 commit
``9ac77ca57bf7b7ee5907269142a5bef979aa15bf``, with its Apache-2.0 ``LICENSE``).
Refreshing the fixture from a newer commit fails here until the port follows it.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from tests.required_tools import require_node

REPO_ROOT = Path(__file__).resolve().parents[1]
GRAMMAR = REPO_ROOT / "src/metabrowser/static/syntax/lean.js"
UPSTREAM = REPO_ROOT / "tests/fixtures/vscode-lean4/lean4.json"

# The port's two adaptations of an upstream regex, named in lean.js's header. A
# JavaScript character class reads POSIX `[:space:]` as the letters of the word.
ADAPTATIONS = {"[:space:]": r"\s"}


def _upstream_regexes(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key in ("match", "begin", "end"):
            if isinstance(node.get(key), str):
                yield node[key]
        for value in node.values():
            yield from _upstream_regexes(value)
    elif isinstance(node, list):
        for value in node:
            yield from _upstream_regexes(value)


def _adapted(regex: str) -> str:
    for old, new in ADAPTATIONS.items():
        regex = regex.replace(old, new)
    return regex


def _ported_regexes() -> set[str]:
    text = GRAMMAR.read_text(encoding="utf-8")
    return set(re.findall(r"^\s+\w+: String\.raw`([^`]*)`,$", text, flags=re.MULTILINE))


def test_the_port_carries_every_upstream_regex_and_no_other() -> None:
    upstream = {_adapted(regex) for regex in _upstream_regexes(json.loads(UPSTREAM.read_text()))}
    ported = _ported_regexes()
    assert upstream - ported == set(), "upstream rules the port does not carry"
    assert ported - upstream == set(), "ported rules upstream does not have"


SAMPLE = """import Mathlib
/-- A doc comment. -/
abbrev N := Nat
structure Point where
  x : Nat
deriving Repr
set_option autoImplicit false in
@[simp] theorem two : 1 + 1 = 2 := by
  sorry
#eval s!"x = {1 + 1}"
"""

HIGHLIGHT = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const [runtime, grammar, sample] = process.argv.slice(1);
const sandbox = {};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(runtime, "utf-8"), sandbox);
vm.runInContext(fs.readFileSync(grammar, "utf-8"), sandbox);
const result = sandbox.hljs.highlight(sample, { language: "lean4", ignoreIllegals: false });
const spans = [...result.value.matchAll(/<span class="([^"]+)">([^<]*)/g)].map((m) => [m[1], m[2]]);
console.log(JSON.stringify({ relevance: result.relevance, illegal: result.illegal, spans }));
"""


def test_lean_4_source_takes_the_ported_scopes_in_the_vendored_runtime() -> None:
    require_node()
    runtime = REPO_ROOT / "src/metabrowser/static/vendor/highlight.min.js"
    completed = subprocess.run(
        ["node", "-e", HIGHLIGHT, str(runtime), str(GRAMMAR), SAMPLE],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    result = json.loads(completed.stdout)
    spans = {(scope, text.strip()) for scope, text in result["spans"]}
    assert result["illegal"] is False
    for keyword in ("import", "abbrev", "structure", "where", "deriving", "set_option", "in"):
        assert ("hljs-keyword", keyword) in spans, keyword
    assert ("hljs-keyword", "#eval") in spans
    assert ("hljs-comment", "/-- A doc comment. -/") in spans
    assert ("hljs-meta", "@[simp]") in spans
    assert ("hljs-title function_", "two") in spans
    assert ("hljs-sorry", "sorry") in spans
    assert ("hljs-type", "Nat") not in spans
    assert ("hljs-number", "1") in spans
