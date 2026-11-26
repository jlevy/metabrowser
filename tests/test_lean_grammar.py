"""The Lean grammar is the official Lean 4 grammar, ported rule for rule.

``src/metabrowser/static/syntax/lean.js`` copies every regex of vscode-lean4's
``syntaxes/lean4.json`` into a constant of its own. The copy it follows is pinned in
``tests/fixtures/vscode-lean4/`` (``lean4.json`` at vscode-lean4 commit
``9ac77ca57bf7b7ee5907269142a5bef979aa15bf``, with its Apache-2.0 ``LICENSE``).
Refreshing the fixture from a newer commit fails here until the port follows it.

The constants are held to the fixture verbatim. What the port changes for JavaScript and
Highlight.js is in ``lean.js``'s ``ADAPTATIONS``, and each entry has behaviour cases in
``ADAPTATIONS`` here. ``RULES`` runs source through the vendored runtime for every
upstream constant, so a rule that is wired to the wrong mode, scope, or order fails
even though its regex is still in the file.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from metabrowser.settings import SYNTAX_HIGHLIGHT_MAX_BYTES
from tests.required_tools import require_node

REPO_ROOT = Path(__file__).resolve().parents[1]
GRAMMAR = REPO_ROOT / "src/metabrowser/static/syntax/lean.js"
RUNTIME = REPO_ROOT / "src/metabrowser/static/vendor/highlight.min.js"
UPSTREAM = REPO_ROOT / "tests/fixtures/vscode-lean4/lean4.json"

# One node process runs every snippet; a larger budget than any of them needs, and the
# budget the work-bound test holds the grammar to.
NODE_TIMEOUT_SECONDS = 20

Token = tuple[str, str]
Case = tuple[str, list[Token]]

COMMENT = "hljs-comment"
ESCAPE = "hljs-char escape_"
KEYWORD = "hljs-keyword"
LITERAL = "hljs-literal"
META = "hljs-meta"
NUMBER = "hljs-number"
SORRY = "hljs-sorry"
STRING = "hljs-string"
TITLE = "hljs-title function_"
TYPE = "hljs-type"


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


@cache
def _grammar_text() -> str:
    return GRAMMAR.read_text(encoding="utf-8")


def _ported_regexes() -> dict[str, str]:
    """The upstream constants of lean.js, by name.

    A name starts with a lowercase letter: Biome's unsafe fix for an unused variable
    renames it with a leading underscore, which must not count as carrying the rule.
    """
    return dict(
        re.findall(
            r"^  const ([a-z]\w*) = String\.raw`([^`]*)`;$", _grammar_text(), flags=re.MULTILINE
        )
    )


def _scan_limit() -> int:
    match = re.search(r"^  const SCAN_LIMIT = (\d+);$", _grammar_text(), flags=re.MULTILINE)
    assert match, "lean.js no longer declares SCAN_LIMIT"
    return int(match.group(1))


def test_the_port_carries_every_upstream_regex_and_no_other() -> None:
    upstream = set(_upstream_regexes(json.loads(UPSTREAM.read_text(encoding="utf-8"))))
    ported = set(_ported_regexes().values())
    assert upstream - ported == set(), "upstream rules the port does not carry"
    assert ported - upstream == set(), "ported rules upstream does not have"


# Every (scope, text) the runtime marks in the snippet, in order, by innermost scope.
# Text outside any scope is left out, so `[]` says the snippet stays plain.
RULES: dict[str, list[Case]] = {
    "dashCommentBegin": [("x -- note\ny", [(COMMENT, "-- note")])],
    "dashCommentEnd": [("-- a\n-- b", [(COMMENT, "-- a"), (COMMENT, "-- b")])],
    "docCommentBegin": [
        (
            "/-- doc /- n -/ more -/ x",
            [(COMMENT, "/-- doc "), (COMMENT, "/- n -/"), (COMMENT, " more -/")],
        ),
    ],
    "modDocCommentBegin": [
        (
            "/-! mod /- n -/ more -/ x",
            [(COMMENT, "/-! mod "), (COMMENT, "/- n -/"), (COMMENT, " more -/")],
        ),
    ],
    "blockCommentBegin": [
        (
            "/- a /- nested -/ still -/ x",
            [(COMMENT, "/- a "), (COMMENT, "/- nested -/"), (COMMENT, " still -/")],
        ),
    ],
    "commentEnd": [
        ("/- a -/ 1 /- b -/", [(COMMENT, "/- a -/"), (NUMBER, "1"), (COMMENT, "/- b -/")]),
    ],
    "sortKeywords": [
        ("Prop Type Sort Nat Types", [(TYPE, "Prop"), (TYPE, "Type"), (TYPE, "Sort")])
    ],
    "attributeCommand": [
        ("attribute [simp] foo", [(META, "attribute [simp]")]),
        ("attribute [local simp] foo", [(META, "attribute [local")]),
    ],
    "attributeAt": [
        ("@[simp] x", [(META, "@[simp]")]),
        ("@[simp, inline] x", [(META, "@[simp,")]),
    ],
    "modifiers": [
        ("private x", [(KEYWORD, "private")]),
        ("x.private private.x", []),
    ],
    # Upstream puts `#exit` between two `\b`, so it needs a word character before it.
    "unfinished": [
        ("sorry admit", [(SORRY, "sorry"), (SORRY, "admit")]),
        ("#exit", []),
        ("foo#exit", [(SORRY, "#exit")]),
    ],
    "hashCommands": [
        ("#check x", [(KEYWORD, "#check")]),
        ("#eval! 1", [(KEYWORD, "#eval"), (NUMBER, "1")]),
    ],
    "derivingInstance": [
        ("deriving instance Repr for Foo", [(KEYWORD, "deriving instance"), (KEYWORD, "for")]),
    ],
    # Only capture 1, the command, is a keyword; the `{…}` binder stays plain.
    "definitionBegin": [
        ("def f := 1", [(KEYWORD, "def"), (TITLE, "f"), (NUMBER, "1")]),
        ("instance {n : Nat} : OfNat Foo n", [(KEYWORD, "instance")]),
        ("theorem {u} foo : True", [(KEYWORD, "theorem"), (TITLE, "foo")]),
        ("x.def y", []),
    ],
    # The end is tried before the name, as TextMate does, at each of its tokens.
    "definitionEnd": [
        ("structure Point where", [(KEYWORD, "structure"), (TITLE, "Point"), (KEYWORD, "where")]),
        ("structure A extends B", [(KEYWORD, "structure"), (TITLE, "A"), (KEYWORD, "extends")]),
        ("instance : Foo", [(KEYWORD, "instance")]),
        ("def f (x : Nat)", [(KEYWORD, "def"), (TITLE, "f")]),
        ("def f [Foo]", [(KEYWORD, "def"), (TITLE, "f")]),
        ("def f {a}", [(KEYWORD, "def"), (TITLE, "f")]),
        ("def f ⦃a⦄", [(KEYWORD, "def"), (TITLE, "f")]),
        ("inductive T | a", [(KEYWORD, "inductive"), (TITLE, "T")]),
        (
            "theorem foo -- c\n  : True",
            [(KEYWORD, "theorem"), (TITLE, "foo"), (COMMENT, "-- c")],
        ),
    ],
    "definitionName": [
        ("def foo.bar : Nat", [(KEYWORD, "def"), (TITLE, "foo.bar")]),
        ("def foo.{u} x", [(KEYWORD, "def"), (TITLE, "foo.")]),
        ("abbrev N := Nat", [(KEYWORD, "abbrev"), (TITLE, "N")]),
    ],
    "definitionComma": [
        ("theorem foo , bar : True", [(KEYWORD, "theorem"), (TITLE, "foo"), (TITLE, "bar")]),
    ],
    # `trace[…]` is followed by `\b` upstream, so it is a keyword only before a word.
    "keywords": [
        ("fun x => by simp", [(KEYWORD, "fun"), (KEYWORD, "by")]),
        ("x.end end", [(KEYWORD, "end")]),
        ("import all X", [(KEYWORD, "import all")]),
        ("termination_by? x", [(KEYWORD, "termination_by")]),
        ("trace[Meta.debug]x", [(KEYWORD, "trace[Meta.debug]")]),
        ("trace_goal[a]x trace[a b]x", [(KEYWORD, "trace_goal[a]")]),
    ],
    "guillemetBegin": [
        ("«def» x", []),
        ("theorem «my thm» : True", [(KEYWORD, "theorem"), (TITLE, "«my thm»")]),
    ],
    "guillemetEnd": [("«a» def «b» : T", [(KEYWORD, "def"), (TITLE, "«b»")])],
    # Capture 1, the prefix, is a keyword inside the string. `throwError` is taken by
    # the keyword rule first, as upstream orders them, so its string does not interpolate.
    "interpolatedBegin": [
        ('s!"x"', [(KEYWORD, "s!"), (STRING, '"x"')]),
        ('m! "x"', [(KEYWORD, "m!"), (STRING, ' "x"')]),
        (
            'panic! "x {y}"',
            [
                (KEYWORD, "panic!"),
                (STRING, ' "x '),
                (KEYWORD, "{"),
                (STRING, "y"),
                (KEYWORD, "}"),
                (STRING, '"'),
            ],
        ),
        (
            'trace[a] "{1}"',
            [
                (KEYWORD, "trace[a]"),
                (STRING, ' "'),
                (KEYWORD, "{"),
                (NUMBER, "1"),
                (KEYWORD, "}"),
                (STRING, '"'),
            ],
        ),
        ('throwError "bad {x}"', [(KEYWORD, "throwError"), (STRING, '"bad {x}"')]),
    ],
    "interpolationBegin": [
        (
            's!"a {1 + 1} b"',
            [
                (KEYWORD, "s!"),
                (STRING, '"a '),
                (KEYWORD, "{"),
                (NUMBER, "1"),
                (STRING, " + "),
                (NUMBER, "1"),
                (KEYWORD, "}"),
                (STRING, ' b"'),
            ],
        ),
    ],
    "interpolationEnd": [
        (
            's!"{s!"in {y}"}"',
            [
                (KEYWORD, "s!"),
                (STRING, '"'),
                (KEYWORD, "{"),
                (KEYWORD, "s!"),
                (STRING, '"in '),
                (KEYWORD, "{"),
                (STRING, "y"),
                (KEYWORD, "}"),
                (STRING, '"'),
                (KEYWORD, "}"),
                (STRING, '"'),
            ],
        ),
    ],
    "stringQuote": [
        ('"a" b "c"', [(STRING, '"a"'), (STRING, '"c"')]),
        ('"a {1} b"', [(STRING, '"a {1} b"')]),
    ],
    "escapeSimple": [
        (
            r'"a\n\"q\\"',
            [
                (STRING, '"a'),
                (ESCAPE, r"\n"),
                (ESCAPE, r"\""),
                (STRING, "q"),
                (ESCAPE, "\\\\"),
                (STRING, '"'),
            ],
        ),
        (r's!"\t"', [(KEYWORD, "s!"), (STRING, '"'), (ESCAPE, r"\t"), (STRING, '"')]),
    ],
    "escapeHex": [(r'"\x41\xZ"', [(STRING, '"'), (ESCAPE, r"\x41"), (STRING, r'\xZ"')])],
    "escapeUnicode": [
        (r'"\u03B1\u03"', [(STRING, '"'), (ESCAPE, r"\u03B1"), (STRING, r'\u03"')]),
    ],
    "booleans": [("true false truer x", [(LITERAL, "true"), (LITERAL, "false")])],
    "character": [
        ("'a' f' x' 'b'", [(STRING, "'a'"), (STRING, "'b'")]),
        ("a]'b'", []),
    ],
    "characterEscape": [
        (
            r"'\n' '\x41' '\u03B1'",
            [(STRING, r"'\n'"), (STRING, r"'\x41'"), (STRING, r"'\u03B1'")],
        ),
    ],
    "numbers": [
        ("0x1F 42 x1 1_000", [(NUMBER, "0x1F"), (NUMBER, "42")]),
    ],
}


def _adaptation_cases() -> dict[str, list[Case]]:
    """Behaviour that holds only with the named entry of lean.js's ADAPTATIONS."""
    limit = _scan_limit()
    fits, over = "a" * limit, "a" * (limit + 1)
    return {
        # POSIX `[:space:]` is whitespace: a name holds the letters of the word and
        # stops at a tab.
        "posixSpace": [
            ("def space_d : T", [(KEYWORD, "def"), (TITLE, "space_d")]),
            ("def foo\tbar : T", [(KEYWORD, "def"), (TITLE, "foo"), (TITLE, "bar")]),
        ],
        # A binder closes on its own line; a `{` left open is the definition's end.
        "lineScopedBinder": [
            ("def {u} foo : T", [(KEYWORD, "def"), (TITLE, "foo")]),
            ("def {\n  x } foo : T", [(KEYWORD, "def")]),
        ],
        # A bracket closed within the limit is read as upstream reads it; one closed
        # past it is as if it were not closed.
        "boundedScan": [
            (f"def {{{fits}}} f : T", [(KEYWORD, "def"), (TITLE, "f")]),
            (f"def {{{over}}} f : T", [(KEYWORD, "def")]),
            (f"trace[{fits}]x", [(KEYWORD, f"trace[{fits}]")]),
            (f"trace[{over}]x", []),
            (f"@[{fits}] x", [(META, f"@[{fits}]")]),
            (f"@[{over}] x", [(META, f"@[{fits}")]),
        ],
        # Greek letters are word characters: a name starts and ends at their edges, a
        # keyword inside one is not a keyword, and a quote after one is not a character.
        "unicodeWord": [
            ("def αβ : Nat := 1", [(KEYWORD, "def"), (TITLE, "αβ"), (NUMBER, "1")]),
            (
                "theorem ε_pos (h : 0 < ε) : True",
                [(KEYWORD, "theorem"), (TITLE, "ε_pos"), (NUMBER, "0")],
            ),
            ("fun x => αin β", [(KEYWORD, "fun")]),
            ("α'b' 'c'", [(STRING, "'c'")]),
        ],
    }


# Prints, for each snippet in the JSON array on stdin, the (scope, text) pairs the
# vendored runtime marks, by innermost scope.
TOKENIZE = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const [runtime, grammar] = process.argv.slice(1);
const sandbox = {};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(runtime, "utf-8"), sandbox);
vm.runInContext(fs.readFileSync(grammar, "utf-8"), sandbox);
const entities = { "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#x27;": "'" };
function tokens(source) {
  const result = sandbox.hljs.highlight(source, { language: "lean4", ignoreIllegals: false });
  const scopes = [];
  const marked = [];
  for (const part of result.value.matchAll(/<span class="([^"]+)">|<\/span>|([^<]+)/g)) {
    if (part[1]) {
      scopes.push(part[1]);
    } else if (part[2] === undefined) {
      scopes.pop();
    } else if (scopes.length > 0) {
      marked.push([scopes.at(-1), part[2].replace(/&[a-z#0-9]+;/g, (entity) => entities[entity])]);
    }
  }
  return marked;
}
const sources = JSON.parse(fs.readFileSync(0, "utf-8"));
console.log(JSON.stringify(sources.map(tokens)));
"""


def _node(script: str, stdin: str) -> Any:
    require_node()
    completed = subprocess.run(
        ["node", "-e", script, str(RUNTIME), str(GRAMMAR)],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=NODE_TIMEOUT_SECONDS,
        check=True,
    )
    return json.loads(completed.stdout)


def _all_cases() -> list[tuple[str, Case]]:
    tables = {**RULES, **_adaptation_cases()}
    return [(name, case) for name, cases in tables.items() for case in cases]


@cache
def _marked() -> dict[str, list[Token]]:
    sources = sorted({source for _name, (source, _expected) in _all_cases()})
    results = _node(TOKENIZE, json.dumps(sources))
    return {
        source: [(scope, text) for scope, text in tokens]
        for source, tokens in zip(sources, results, strict=True)
    }


def test_every_upstream_rule_has_a_behaviour_case() -> None:
    assert set(RULES) == set(_ported_regexes())


def test_every_adaptation_has_a_behaviour_case() -> None:
    declared = re.findall(r"^    (\w+): \(source\) =>", _grammar_text(), flags=re.MULTILINE)
    assert declared, "lean.js no longer declares ADAPTATIONS"
    assert set(_adaptation_cases()) == set(declared)


@pytest.mark.parametrize(
    ("source", "expected"),
    [pytest.param(*case, id=f"{name}:{case[0]!r}") for name, case in _all_cases()],
)
def test_lean_source_takes_the_upstream_scopes(source: str, expected: list[Token]) -> None:
    assert _marked()[source] == expected


# An opener upstream scans from to a closer that never comes, repeated to the size of
# the largest file the browser highlights. Unbounded, each occurrence rescans the rest
# of the file, and the four inputs took two minutes between them.
UNCLOSED_OPENERS = ("def { ", "def { x\n", "trace[", "trace_goal[")

COUNT_KEYWORDS = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const [runtime, grammar] = process.argv.slice(1);
const sandbox = {};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(runtime, "utf-8"), sandbox);
vm.runInContext(fs.readFileSync(grammar, "utf-8"), sandbox);
const { units, bytes } = JSON.parse(fs.readFileSync(0, "utf-8"));
const counts = units.map((unit) => {
  const source = unit.repeat(Math.ceil(bytes / unit.length));
  const html = sandbox.hljs.highlight(source, { language: "lean4" }).value;
  return html.split('<span class="hljs-keyword">').length - 1;
});
console.log(JSON.stringify(counts));
"""


def test_an_unclosed_opener_at_the_highlight_limit_is_bounded_work() -> None:
    """The scan for a closing bracket is bounded, so the largest file cannot freeze a tab.

    The node process has one budget for all four inputs, many times what the
    bounded grammar needs and a fraction of what the unbounded one took, so this fails by
    the work done and not by a slow machine. Each `def` is still a keyword, and an
    unclosed `trace[` is still plain.
    """
    counts = _node(
        COUNT_KEYWORDS,
        json.dumps({"units": UNCLOSED_OPENERS, "bytes": SYNTAX_HIGHLIGHT_MAX_BYTES}),
    )
    expected = [
        -(-SYNTAX_HIGHLIGHT_MAX_BYTES // len(unit)) if unit.startswith("def") else 0
        for unit in UNCLOSED_OPENERS
    ]
    assert counts == expected
