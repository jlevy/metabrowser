"""Reader messages say what happened and one remedy, never Metabrowser's internals.

docs/design-system-messages.md is the guide; this module holds the parts of it a
machine can. The browser half reads every string and template in the shipped scripts
through tests/dom/reader-message-literals.mjs, which parses them with the TypeScript
compiler's parser, and fails on a rule's pattern in a literal some reader could see. The
server half parses the package's Python and fails when an answer's reader field carries
a caught exception's own text. Each rule has a test that plants a violation and watches
it fail, so a rule whose pattern stops matching the code fails too.

The owner's words that set it, 2026-11-24, after a guided-review notice listed commit
IDs, merge-base mechanics, and an internal plan's path: "we should not be showing
internal plan specs or so much excessive confusing detail on any error messages, ever."
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

import pytest

from tests.required_tools import require_node

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = REPO_ROOT / "src" / "metabrowser"
STATIC = PACKAGE / "static"
BUILTIN_PLUGINS = PACKAGE / "builtin_plugins"
EXTRACTOR = REPO_ROOT / "tests" / "dom" / "reader-message-literals.mjs"
# The command line's errors are a developer's terminal output, outside the guide
# ("Where the Detail Goes").
CLI_PACKAGE = PACKAGE / "cli"

# The most sentences one string may hold: the statement, then the remedy
# (docs/design-system-messages.md, "Length and Punctuation").
MAX_SENTENCES = 2

# The fields of a JSON answer that a page shows a reader. `detail` and `code` are the
# agent's, and may hold anything.
READER_FIELDS = frozenset({"error", "message", "summary"})


class Record(TypedDict):
    file: str
    line: int
    kind: str
    text: str
    expressions: list[str]
    context: str
    functions: list[str]
    callee: str
    caught: bool


@dataclass(frozen=True)
class Finding:
    rule: str
    where: str
    text: str

    def __str__(self) -> str:
        return f"{self.where}: [{self.rule}] {self.text[:160]!r}"


# -- Rules for browser literals ---------------------------------------------------------

_TAG = re.compile(r"<[^>]*>")
_PROSE = re.compile(r"[A-Za-z]{2,}\s+[A-Za-z]{2,}")
_PLACEHOLDER = "${…}"

MECHANICS = re.compile(
    r"\bmerge[- ]?bases?\b|\brebas(?:e|ed|es|ing)\b|\bforce[- ]push|\bstack ?traces?\b"
    r"|\bTraceback\b|\bdecompress|\bworkers?\b|\bchild process|\bsubprocess"
    r"|\breader process|\bschema version|/api/|\bstderr\b|\bbudgets?\b",
    re.IGNORECASE,
)
INTERNAL_PATH = re.compile(
    r"(?<![\w@/.-])[\w.-]*\w\.(?:md|py)\b|\b(?:docs|specs|src|plans?)/[\w./-]+"
)
HTTP_STATUS = re.compile(r"\bHTTP\s+[1-5]\d\d\b|\bHTTP\s*\$\{…\}|\(HTTP\b")
COMMIT_EXPRESSION = re.compile(
    r"shortCommit\(|(?:^|\.)(?:sha|oid|head_sha|base_sha|merge_base)\b|\bcommit\.id\b"
)
NOTICE_BUILDER = re.compile(r"notice", re.IGNORECASE)
LIST_TAG = frozenset({"ul", "ol", "li"})
NOTICE_MARKUP_LIST = re.compile(
    r"""class=\\?["'][^"']*\bnotice\b[^"']*["'][\s\S]*<(?:ul|ol|li)\b"""
)
ERROR_NAME = re.compile(r"^(?:String\()?(?:err|error|e|exc|exception|caught|thrown)(?:\.|\))")
DETAIL_EXPRESSION = re.compile(
    r"(?:^|[.\s(?])(?:error|message|detail|reason|said|why|cause|failure)\b"
)
SENTENCE_END = re.compile(r"[.!?](?=\s+[A-Z“\"$])")
EXCLAMATION = re.compile(r"[A-Za-z]!(?=\s|$)")
TONE = re.compile(r"\b(?:please|unfortunately|oops)\b|^\s*(?:Failed to\b|Error:)", re.IGNORECASE)


def _visible(text: str) -> str:
    return _TAG.sub(" ", text)


def _is_prose(text: str) -> bool:
    return bool(_PROSE.search(_visible(text)))


def _readable(record: Record) -> bool:
    """Whether a reader could see the literal: not a console argument, a built-in error's
    argument, a module specifier, a property key, or a comparison operand."""
    return record["context"] == "text"


def _where(record: Record) -> str:
    return f"{Path(record['file']).relative_to(PACKAGE)}:{record['line']}"


def _in_notice_builder(record: Record) -> bool:
    return any(NOTICE_BUILDER.search(name) for name in record["functions"])


def rule_mechanics(record: Record) -> bool:
    """Internal mechanics named in a sentence."""
    return (
        record["kind"] in ("string", "template")
        and _is_prose(record["text"])
        and bool(MECHANICS.search(_visible(record["text"])))
    )


def rule_internal_path(record: Record) -> bool:
    """A source file, spec, or plan named in a sentence."""
    return (
        record["kind"] in ("string", "template")
        and _is_prose(record["text"])
        and bool(INTERNAL_PATH.search(_visible(record["text"])))
    )


def rule_http_status(record: Record) -> bool:
    """An HTTP status in the text."""
    return record["kind"] in ("string", "template") and bool(
        HTTP_STATUS.search(_visible(record["text"]))
    )


def rule_commit_id(record: Record) -> bool:
    """A commit ID interpolated into a sentence, or named in a notice's builder."""
    if record["kind"] == "call":
        return _in_notice_builder(record)
    return (
        record["kind"] == "template"
        and _is_prose(record["text"].replace(_PLACEHOLDER, " "))
        and any(COMMIT_EXPRESSION.search(expression) for expression in record["expressions"])
    )


def rule_list_in_notice(record: Record) -> bool:
    """A notice built as a list: a list element made in its builder, or written in its
    markup."""
    if record["kind"] == "string" and record["text"] in LIST_TAG and record["callee"]:
        return _in_notice_builder(record)
    return record["kind"] in ("string", "template") and bool(
        NOTICE_MARKUP_LIST.search(record["text"])
    )


def rule_exception_text(record: Record) -> bool:
    """A caught exception's own message, stack, or `String()` read outside a console
    call."""
    return record["kind"] in ("access", "stringified") and (
        record["caught"] or bool(ERROR_NAME.match(record["text"]))
    )


def rule_appended_detail(record: Record) -> bool:
    """A failure's detail appended to a sentence, as `: ${error}` or `(${reason})`."""
    if record["kind"] != "template" or not record["expressions"]:
        return False
    parts = record["text"].split(_PLACEHOLDER)
    if not _is_prose(" ".join(parts)):
        return False
    for index, expression in enumerate(record["expressions"]):
        before, after = parts[index], parts[index + 1]
        introduced = before.rstrip().endswith(":") or before.endswith("(")
        if introduced and DETAIL_EXPRESSION.search(expression):
            return not before.rstrip().endswith(":") or not after.strip(" .")
    return False


def rule_tone(record: Record) -> bool:
    """An exclamation mark, a "please", "unfortunately", or "oops", or a failure that opens
    with "Failed to" or "Error:"."""
    if record["kind"] not in ("string", "template"):
        return False
    visible = _visible(record["text"])
    return bool(EXCLAMATION.search(visible)) or (_is_prose(visible) and bool(TONE.search(visible)))


def rule_too_many_sentences(record: Record) -> bool:
    """More sentences in one string than MAX_SENTENCES."""
    if record["kind"] not in ("string", "template") or not _is_prose(record["text"]):
        return False
    visible = _visible(record["text"]).strip()
    return len(SENTENCE_END.findall(visible)) + 1 > MAX_SENTENCES


BROWSER_RULES: dict[str, Callable[[Record], bool]] = {
    "mechanics": rule_mechanics,
    "internal-path": rule_internal_path,
    "http-status": rule_http_status,
    "commit-id": rule_commit_id,
    "list-in-notice": rule_list_in_notice,
    "exception-text": rule_exception_text,
    "appended-detail": rule_appended_detail,
    "tone": rule_tone,
    "too-many-sentences": rule_too_many_sentences,
}

# A file a rule does not apply to, and why. An entry whose file no longer breaks the rule
# fails test_every_allowlist_entry_is_still_needed, so the list only shrinks.
BROWSER_ALLOWLIST: dict[tuple[str, str], str] = {
    ("builtin_plugins/github/guided-review.js", "mechanics"): (
        "rewritten in claude/concise-guide-notice (mb-b9qd)"
    ),
    ("builtin_plugins/github/guided-review.js", "commit-id"): (
        "rewritten in claude/concise-guide-notice (mb-b9qd)"
    ),
    ("builtin_plugins/github/guided-review.js", "list-in-notice"): (
        "rewritten in claude/concise-guide-notice (mb-b9qd)"
    ),
    ("builtin_plugins/diff/diff-model.js", "exception-text"): (
        "the validators return a FormatError's location as data for their tests; the views "
        "that call them log it and show a fixed sentence (diff/index.js INVALID_DOCUMENT)"
    ),
    ("builtin_plugins/markdown/markdown-worker-client.js", "mechanics"): (
        "asError's fallback names a worker failure for the console; no view shows a "
        "worker error's text (markdown/rendered.js renderKpressError shows fixed copy)"
    ),
    ("builtin_plugins/markdown/markdown-worker.js", "exception-text"): (
        "the worker posts its failure to markdown-worker-client.js, which rejects with it; "
        "the views that await it show their own copy and log the error"
    ),
    ("static/request-error.js", "exception-text"): (
        "classifyRequestError reads the message of a RequestError only, which the code "
        "that made it wrote as reader copy"
    ),
}


def shipped_scripts() -> list[Path]:
    scripts = sorted(STATIC.glob("*.js"))
    scripts += sorted(
        path
        for pattern in ("*.js", "*.mjs")
        for path in BUILTIN_PLUGINS.rglob(pattern)
        if "vendor" not in path.parts
    )
    return scripts


def extract(paths: Iterable[Path]) -> list[Record]:
    require_node()
    result = subprocess.run(
        ["node", str(EXTRACTOR), *map(str, paths)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, f"extractor failed:\n{result.stderr}"
    return json.loads(result.stdout)


def browser_findings(records: Iterable[Record]) -> list[Finding]:
    return [
        Finding(rule, _where(record), record["text"])
        for record in records
        if _readable(record)
        for rule, applies in BROWSER_RULES.items()
        if applies(record)
    ]


def _allowed(finding: Finding, allowlist: dict[tuple[str, str], str]) -> bool:
    return (finding.where.rsplit(":", 1)[0], finding.rule) in allowlist


@pytest.fixture(scope="module")
def shipped_findings() -> list[Finding]:
    return browser_findings(extract(shipped_scripts()))


def test_reader_messages_in_the_browser_follow_the_guide(shipped_findings: list[Finding]) -> None:
    offenders = [str(f) for f in shipped_findings if not _allowed(f, BROWSER_ALLOWLIST)]
    assert not offenders, (
        "reader messages break docs/design-system-messages.md; say what happened and one "
        "remedy, and keep the detail in the route's JSON or the console:\n  "
        + "\n  ".join(offenders)
    )


def test_every_browser_allowlist_entry_is_still_needed(shipped_findings: list[Finding]) -> None:
    found = {(f.where.rsplit(":", 1)[0], f.rule) for f in shipped_findings}
    stale = sorted(
        f"{file} [{rule}]" for file, rule in BROWSER_ALLOWLIST if (file, rule) not in found
    )
    assert not stale, "remove these allowlist entries, which no longer match:\n  " + "\n  ".join(
        stale
    )


def test_the_scan_reads_the_shipped_scripts(shipped_findings: list[Finding]) -> None:
    """A scan that read nothing would pass: it must see the shell and a plugin's copy."""
    records = extract([STATIC / "app.js", BUILTIN_PLUGINS / "diff" / "diff-view.js"])
    texts = {record["text"] for record in records if _readable(record)}
    assert "Could not preview this file." in texts
    assert any(record["context"] == "console" for record in records)
    assert any(record["context"] == "thrown" for record in records)


# -- Each browser rule fails on a planted violation --------------------------------------

PLANTED: dict[str, str] = {
    "mechanics": 'note.textContent = "Its merge base moved after a rebase.";',
    "internal-path": 'note.textContent = "See docs/project/specs/plan.md for why.";',
    "http-status": "note.textContent = `Could not list branches (HTTP ${status}).`;",
    "commit-id": "note.textContent = `The branch is now at ${shortCommit(head)}.`;",
    "list-in-notice": 'function staleNotice() { return element("ul", "", "notice-items"); }',
    "exception-text": "try { run(); } catch (failure) { note.textContent = failure.message; }",
    "appended-detail": "note.textContent = `Could not read the log: ${error}`;",
    "tone": 'button.dataset.tipText = "Copied!";',
    "too-many-sentences": (
        'note.textContent = "This failed. It was the network. Try again later.";'
    ),
}
PLANTED_ELSEWHERE: dict[str, str] = {
    "commit-id": "function freshnessNotice() { return shortCommit(head); }",
    "list-in-notice": "box.innerHTML = '<div class=\"notice\"><ul><li>one</li></ul></div>';",
    "exception-text": "function show(error) { note.textContent = String(error); }",
    "appended-detail": "note.textContent = `The switch was refused (${said}).`;",
    "tone": 'note.textContent = "Failed to load the file. Please reload.";',
}


def _plant(tmp_path: Path, name: str, source: str) -> list[Finding]:
    path = tmp_path / f"{name}.js"
    path.write_text(source, encoding="utf-8")
    records = extract([path])
    for record in records:
        record["file"] = str(PACKAGE / "static" / path.name)
    return browser_findings(records)


@pytest.mark.parametrize("rule", sorted(BROWSER_RULES))
def test_each_browser_rule_fails_on_a_planted_violation(tmp_path: Path, rule: str) -> None:
    assert rule in PLANTED, f"plant a violation of {rule}"
    plantings = [PLANTED[rule], *([PLANTED_ELSEWHERE[rule]] if rule in PLANTED_ELSEWHERE else [])]
    for index, source in enumerate(plantings):
        found = {finding.rule for finding in _plant(tmp_path, f"{rule}-{index}", source)}
        assert rule in found, f"{rule} did not fire on {source!r}; it found {sorted(found)}"


def test_what_no_reader_sees_is_not_a_message(tmp_path: Path) -> None:
    """Console arguments, built-in errors' arguments, keys, and comparisons are code."""
    source = "\n".join(
        [
            'console.warn("merge base moved after a rebase", error.message);',
            'throw new Error("Markdown worker failed: see src/worker.py (HTTP 500)");',
            'const kinds = { "merge base moved": 1 };',
            'if (state === "the worker stopped") { done(); }',
            'import { x } from "./docs/plan.md";',
            'note.textContent = "No files were modified in the past week.";',
            "note.textContent = `Showing ${shown} of ${total} files.`;",
        ]
    )
    assert _plant(tmp_path, "clean", source) == []


# -- Server answers ---------------------------------------------------------------------

# A server finding a page never shows, and why, keyed by module and enclosing function.
# An entry that no longer matches fails test_every_server_allowlist_entry_is_still_needed.
SERVER_ALLOWLIST: dict[tuple[str, str], str] = {
    ("cache/atomic.py", "parse_record"): (
        "a cache record's validation reasons reach the log, the command line, and the "
        "/api/cache/ routes, which no page calls; a page's acquisition answers a fixed "
        "sentence for a RecordError (checkout_store.py)"
    ),
    ("cache/layout.py", "read_config"): (
        "config.yml's validation names the setting to fix, for `metab doctor`, command-line "
        "acquisition, and /api/cache/layout, which no page calls; a page's acquisition "
        "answers a fixed sentence for a LayoutError (checkout_store.py)"
    ),
    ("event_log_route.py", "read_log"): (
        "the Details panel (static/event-reports.js showDetails) reads only a 2xx answer "
        "and drops a refusal's body, which is for `metab --api`"
    ),
    ("event_log_route.py", "api_event_log"): (
        "the Details panel (static/event-reports.js showDetails) reads only a 2xx answer "
        "and drops a refusal's body, which is for `metab --api`"
    ),
    ("event_log_route.py", "api_event_log_failures"): (
        "the Details panel (static/event-reports.js showDetails) reads only a 2xx answer "
        "and drops a refusal's body, which is for `metab --api`"
    ),
    ("file_type_registry.py", "load_file_type_registry_from_text"): (
        "parses the packaged file-type registry, at import (file_type_filters.py) and when "
        "an inventory contract is built; a broken document stops startup"
    ),
    ("gz_io.py", "_read_decoded"): (
        "a ContentReadError's text is its detail (content_errors.py): routes answer its "
        "reader_message as `error` and this text as `detail` or the structured plugin's "
        "`parse_error`, which no page shows"
    ),
    ("gz_io.py", "_pump"): (
        "a ContentReadError's text is its detail (content_errors.py): routes answer its "
        "reader_message as `error` and this text as `detail` or the structured plugin's "
        "`parse_error`, which no page shows"
    ),
    ("kpress_adapter.py", "export_kpress_document"): (
        "/api/kpress/export (server.py api_kpress_export) answers this text only as "
        "`detail` and `diagnostics` under a fixed `error`, and no page calls that route"
    ),
    ("plugin_loader/artifact_contracts.py", "_validated_schema"): (
        "validates the packaged cache schemas when cache_contract_registry() first builds "
        "them; an unenforceable schema is a packaging defect doctor_plugins "
        "(cli/plugins.py) reports, and no route catches ContractRegistryError"
    ),
    ("recent_targets.py", "read"): (
        "only the command line reads and writes the recent targets list (cli/recent_cli.py, "
        "record_quietly in cli/serve.py); no route imports the module"
    ),
    ("recent_targets.py", "_directory"): (
        "only the command line reads and writes the recent targets list (cli/recent_cli.py, "
        "record_quietly in cli/serve.py); no route imports the module"
    ),
    ("recent_targets.py", "_change"): (
        "only the command line reads and writes the recent targets list (cli/recent_cli.py, "
        "record_quietly in cli/serve.py); no route imports the module"
    ),
    ("smoke_probes.py", "safe"): (
        "cmd_health, a developer's `python -m metabrowser.smoke_probes` probe, prints this "
        "JSON to a terminal; no route serves it"
    ),
}


def _defined_classes(modules: Iterable[Path]) -> tuple[set[str], set[str]]:
    """Every class the package defines, and those that are the command line's errors."""
    defined: set[str] = set()
    bases: dict[str, set[str]] = {}
    for module in modules:
        for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef):
                defined.add(node.name)
                bases[node.name] = {
                    base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
                    for base in node.bases
                }
    cli = {"CLIError"}
    grew = True
    while grew:
        grew = False
        for name, parents in bases.items():
            if name not in cli and parents & cli:
                cli.add(name)
                grew = True
    return defined, cli


def _caught_types(handler: ast.ExceptHandler) -> list[str]:
    caught = handler.type
    nodes = caught.elts if isinstance(caught, ast.Tuple) else [caught] if caught else []
    return [
        node.id
        if isinstance(node, ast.Name)
        else node.attr
        if isinstance(node, ast.Attribute)
        else ""
        for node in nodes
    ]


def _carries(value: ast.AST, name: str) -> bool:
    """Whether *value* writes the text of the exception bound to *name*: through `str()`,
    `repr()`, an f-string, `format`, `%`, its `strerror` or `args`, or `type(x)`."""

    def is_name(node: ast.AST) -> bool:
        return isinstance(node, ast.Name) and node.id == name

    def text_of(node: ast.AST) -> bool:
        if is_name(node):
            return True
        if isinstance(node, ast.Attribute) and is_name(node.value):
            return node.attr in {"strerror", "args", "filename", "msg", "message", "stderr"}
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in {"str", "repr", "type"}:
                return any(text_of(argument) for argument in node.args)
        if isinstance(node, ast.Attribute) and node.attr == "__name__":
            return text_of(node.value)
        return False

    for node in ast.walk(value):
        if isinstance(node, ast.FormattedValue) and any(
            text_of(inner) for inner in ast.walk(node.value)
        ):
            return True
        if isinstance(node, ast.Call):
            func = node.func
            stringified = isinstance(func, ast.Name) and func.id in {"str", "repr"}
            if stringified and node.args and text_of(node.args[0]):
                return True
            formatted = isinstance(func, ast.Attribute) and func.attr == "format"
            if formatted and any(text_of(argument) for argument in node.args):
                return True
        if (
            isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Mod)
            and any(text_of(inner) for inner in ast.walk(node.right))
        ):
            return True
    return False


def _function_names(tree: ast.Module) -> dict[ast.AST, str]:
    """The function each node sits in, by name."""
    owner: dict[ast.AST, str] = {}

    def walk(node: ast.AST, name: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = (
                child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else name
            )
            owner[child] = inner
            walk(child, inner)

    walk(tree, "<module>")
    return owner


def _annotated_types(annotation: ast.expr | None) -> list[str]:
    """The class names an annotation such as `OSError | ValueError` names."""
    if isinstance(annotation, ast.Name):
        return [annotation.id]
    if isinstance(annotation, ast.Attribute):
        return [annotation.attr]
    if isinstance(annotation, ast.BinOp):
        return _annotated_types(annotation.left) + _annotated_types(annotation.right)
    return []


def _bindings(tree: ast.Module, defined: set[str]) -> Iterator[tuple[str, list[ast.stmt]]]:
    """Each name bound to an exception Metabrowser did not define, with the statements it
    is read in: an `except` clause's, or a function's whose parameter is annotated with
    such an exception, as a helper that classifies one is."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.name is not None:
            types = _caught_types(node)
            if not types or not all(kind in defined for kind in types):
                yield node.name, node.body
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                types = _annotated_types(argument.annotation)
                if (
                    types
                    and all(
                        kind.endswith(("Error", "Exception")) for kind in types if kind != "None"
                    )
                    and not all(kind in defined for kind in types)
                ):
                    yield argument.arg, node.body


def server_findings(
    modules: Iterable[Path], defined: set[str], cli_errors: set[str]
) -> Iterator[Finding]:
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        owner = _function_names(tree)
        relative = module.relative_to(PACKAGE) if module.is_relative_to(PACKAGE) else module
        seen: set[int] = set()
        for name, body in _bindings(tree, defined):
            for node in (inner for statement in body for inner in ast.walk(statement)):
                if not isinstance(node, (ast.Dict, ast.Call)):
                    continue
                carried: list[ast.AST] = []
                if isinstance(node, ast.Dict):
                    carried = [
                        value
                        for key, value in zip(node.keys, node.values, strict=True)
                        if isinstance(key, ast.Constant) and key.value in READER_FIELDS
                    ]
                else:
                    carried = [
                        keyword.value for keyword in node.keywords if keyword.arg in READER_FIELDS
                    ]
                    func = node.func
                    called = (
                        func.id
                        if isinstance(func, ast.Name)
                        else func.attr
                        if isinstance(func, ast.Attribute)
                        else ""
                    )
                    if (
                        called in defined
                        and called not in cli_errors
                        and called.endswith(("Error", "Exception"))
                    ):
                        carried += node.args
                if id(node) not in seen and any(_carries(value, name) for value in carried):
                    seen.add(id(node))
                    yield Finding(
                        "server-exception-text",
                        f"{relative}:{node.lineno}",
                        f"{owner.get(node, '<module>')}: {ast.unparse(node)}",
                    )


def server_modules() -> list[Path]:
    return sorted(path for path in PACKAGE.rglob("*.py") if not path.is_relative_to(CLI_PACKAGE))


@pytest.fixture(scope="module")
def shipped_server_findings() -> list[Finding]:
    modules = server_modules()
    defined, cli_errors = _defined_classes(PACKAGE.rglob("*.py"))
    return list(server_findings(modules, defined, cli_errors))


def _server_key(finding: Finding) -> tuple[str, str]:
    return finding.where.rsplit(":", 1)[0], finding.text.split(":", 1)[0]


def test_server_answers_carry_no_exception_text(shipped_server_findings: list[Finding]) -> None:
    offenders = [str(f) for f in shipped_server_findings if _server_key(f) not in SERVER_ALLOWLIST]
    assert not offenders, (
        "an answer's error, message, or summary carries a caught exception's text; write "
        "the reader's sentence there and put the exception in `detail` or the log "
        "(docs/design-system-messages.md):\n  " + "\n  ".join(offenders)
    )


def test_every_server_allowlist_entry_is_still_needed(
    shipped_server_findings: list[Finding],
) -> None:
    found = {_server_key(f) for f in shipped_server_findings}
    stale = sorted(f"{m} {fn}" for m, fn in SERVER_ALLOWLIST if (m, fn) not in found)
    assert not stale, "remove these allowlist entries, which no longer match:\n  " + "\n  ".join(
        stale
    )


SERVER_PLANTED = {
    "helper taking an exception": """
import sqlite3

def classify(exc: sqlite3.Error) -> dict[str, str]:
    return {"error": f"This database could not be read: {exc}"}
""",
    "dict field": """
def handler():
    try:
        read()
    except OSError as exc:
        return {"error": f"This file cannot be read: {exc.strerror}"}
""",
    "keyword field": """
def handler():
    try:
        read()
    except ValueError as exc:
        return Answer(message=str(exc))
""",
    "type name": """
def handler():
    try:
        read()
    except Exception as exc:
        return {"summary": f"{type(exc).__name__}: {exc}"}
""",
    "wrapped in a Metabrowser error": """
class ReadError(Exception):
    pass

def handler():
    try:
        read()
    except OSError as exc:
        raise ReadError(f"This database is damaged: {exc}") from exc
""",
}


@pytest.mark.parametrize("case", sorted(SERVER_PLANTED))
def test_the_server_rule_fails_on_a_planted_violation(tmp_path: Path, case: str) -> None:
    module = tmp_path / "planted.py"
    module.write_text(SERVER_PLANTED[case], encoding="utf-8")
    defined, cli_errors = _defined_classes([module])
    found = list(server_findings([module], defined, cli_errors))
    assert found, f"the server rule did not fire on {case}"


def test_the_server_rule_leaves_the_detail_and_its_own_errors_alone(tmp_path: Path) -> None:
    """`detail` is the agent's; a Metabrowser error's own text is reader copy already; the
    command line's errors are a terminal's."""
    module = tmp_path / "clean.py"
    module.write_text(
        """
class ContentReadError(Exception):
    pass

class CLIError(Exception):
    pass

class OpenInError(CLIError):
    pass

def handler():
    try:
        read()
    except OSError as exc:
        return {"error": "This file cannot be read.", "detail": str(exc)}
    except ContentReadError as exc:
        return {"error": str(exc)}

def command():
    try:
        read()
    except OSError as exc:
        raise OpenInError(f"could not open: {exc}") from exc
""",
        encoding="utf-8",
    )
    defined, cli_errors = _defined_classes([module])
    assert list(server_findings([module], defined, cli_errors)) == []
