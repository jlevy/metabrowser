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
    # The innermost named function around it, which an allowlist entry names.
    function: str = "<module>"

    def __str__(self) -> str:
        return f"{self.where}: [{self.rule}] {self.text[:160]!r}"

    @property
    def key(self) -> tuple[str, str, str]:
        return self.where.rsplit(":", 1)[0], self.rule, self.function


# -- Rules for browser literals ---------------------------------------------------------

_TAG = re.compile(r"<[^>]*>")
_PROSE = re.compile(r"[A-Za-z]{2,}\s+[A-Za-z]{2,}")
_PLACEHOLDER = "${…}"

# The guide's "Internal mechanics" list, term for term ("What a Message Never Shows").
MECHANICS = re.compile(
    r"\bmerge[- ]?bases?\b|\brebas(?:e|ed|es|ing)\b|\bforce[- ]push|\bstack ?traces?\b"
    r"|\bTraceback\b|\bcach(?:e|es|ed|ing)\b|\bworkers?\b|\bchild process|\bsubprocess"
    r"|\breader (?:process|pool)|\bqueue(?:s|d)?\b|\bdeadlines?\b|\bbudgets?\b|\bdecompress"
    r"|\bsegments?\b|\benvelopes?\b|\bprotocols?\b|/api/|\bschema version|\bstderr\b",
    re.IGNORECASE,
)
INTERNAL_PATH = re.compile(
    r"(?<![\w@/.-])[\w.-]*\w\.(?:md|py)\b|\b(?:docs|specs|src|plans?)/[\w./-]+"
)
HTTP_STATUS = re.compile(r"\bHTTP\s+[1-5]\d\d\b|\bHTTP\s*\$\{…\}|\(HTTP\b")
# A commit named by its ID: `sha` or `oid` as a name or its last word (`headSha`,
# `headRefOid`, `head_sha`), a merge base, or the first characters of anything.
COMMIT_EXPRESSION = re.compile(
    r"shortCommit\(|(?:^|[.\s(])(?:\w*(?:[a-z]Sha|[a-z]Oid|_sha|_oid)|sha|oid|merge_base)\b"
    r"|\bcommit\.id\b|\.(?:slice|substring|substr)\(\s*0\s*,\s*(?:[4-9]|1[0-2])\s*\)"
)
NOTICE_BUILDER = re.compile(r"notice", re.IGNORECASE)
LIST_TAG = frozenset({"ul", "ol", "li"})
NOTICE_MARKUP_LIST = re.compile(
    r"""class=\\?["'][^"']*\bnotice\b[^"']*["'][\s\S]*<(?:ul|ol|li)\b"""
)
ERROR_NAME = re.compile(r"^(?:String\()?(?:err|error|e|exc|exception|caught|thrown)(?:\.|\))")
# What a failure's detail is called when it is appended: its text, or the status or code
# a server answered.
DETAIL_EXPRESSION = re.compile(
    r"(?:^|[.\s(?])(?:error|message|detail|reason|said|why|cause|failure|status|statusText"
    r"|code)\b"
)
# Class names, such as "git-ref-menu-hit disclosure-toggle", which are not prose.
CLASS_LIST = re.compile(r"\s*[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?:\s+[a-z][a-z0-9]*(?:-[a-z0-9]+)*)*\s*")
SENTENCE_END = re.compile(r"[.!?](?=\s+[A-Z“\"$])")
EXCLAMATION = re.compile(r"[A-Za-z]!(?=\s|$)")
TONE = re.compile(r"\b(?:please|unfortunately|oops)\b|^\s*(?:Failed to\b|Error:)", re.IGNORECASE)


def _visible(text: str) -> str:
    return _TAG.sub(" ", text)


def _is_prose(text: str) -> bool:
    visible = _visible(text)
    if "-" in visible and CLASS_LIST.fullmatch(visible):
        return False
    return bool(_PROSE.search(visible))


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
    """A caught exception's own message, stack, or `String()` read outside a console call,
    or the exception itself written into text."""
    return record["kind"] in ("access", "stringified", "caught-value") and (
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

# A rule that does not apply in one function, and why, keyed by file, rule, and the
# innermost named function ("<module>" outside one). An entry that no longer matches fails
# test_every_browser_allowlist_entry_is_still_needed, so the list only shrinks.
_VALIDATORS = (
    "the validators return a FormatError's location as data for their tests; the views "
    "that call them log it and show a fixed sentence (diff/index.js INVALID_DOCUMENT)"
)
_WORKER_FALLBACK = (
    "asError's fallback names a worker failure for the console; no view shows a "
    "worker error's text (markdown/rendered.js renderKpressError shows fixed copy)"
)
BROWSER_ALLOWLIST: dict[tuple[str, str, str], str] = {
    ("builtin_plugins/diff/diff-model.js", "exception-text", "validateManifest"): _VALIDATORS,
    ("builtin_plugins/diff/diff-model.js", "exception-text", "validateDocument"): _VALIDATORS,
    ("builtin_plugins/fsqlite/store-model.js", "mechanics", "pendingText"): (
        "an fsqlite store's transactions are envelopes in its own format, and the store's "
        "Info view shows the store's state as content, as a database's Info view does "
        '(docs/design-system-messages.md, "Where the Detail Goes")'
    ),
    ("builtin_plugins/markdown/markdown-worker-client.js", "mechanics", "ensureWorker"): (
        _WORKER_FALLBACK
    ),
    ("builtin_plugins/markdown/markdown-worker-client.js", "mechanics", "pump"): _WORKER_FALLBACK,
    ("builtin_plugins/github/pull-readiness.js", "mechanics", "<module>"): (
        "SLOT_LABELS copies the server's readiness labels (pull_readiness.LABELS) to size "
        "the header's slot; 'Leaving queue' names GitHub's merge queue, a feature the "
        "reader uses on github.com, not Metabrowser's own machinery"
    ),
    ("builtin_plugins/markdown/markdown-worker.js", "exception-text", "<module>"): (
        "the worker posts its failure to markdown-worker-client.js, which rejects with it; "
        "the views that await it show their own copy and log the error"
    ),
    ("static/request-error.js", "exception-text", "classifyRequestError"): (
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


# A hang guard, not a speed budget: reading every shipped script took 3.5 s on a laptop
# at a load average near 200 (2026-11-24), and test_suite_gates holds a child's bound
# under the suite's timeout.
EXTRACT_TIMEOUT_S = 30


def extract(paths: Iterable[Path]) -> list[Record]:
    require_node()
    result = subprocess.run(
        ["node", str(EXTRACTOR), *map(str, paths)],
        capture_output=True,
        text=True,
        timeout=EXTRACT_TIMEOUT_S,
        check=False,
    )
    assert result.returncode == 0, f"extractor failed:\n{result.stderr}"
    return json.loads(result.stdout)


def browser_findings(records: Iterable[Record]) -> list[Finding]:
    return [
        Finding(rule, _where(record), record["text"], (record["functions"] or ["<module>"])[0])
        for record in records
        if _readable(record)
        for rule, applies in BROWSER_RULES.items()
        if applies(record)
    ]


@pytest.fixture(scope="module")
def shipped_findings() -> list[Finding]:
    return browser_findings(extract(shipped_scripts()))


def test_reader_messages_in_the_browser_follow_the_guide(shipped_findings: list[Finding]) -> None:
    offenders = [str(f) for f in shipped_findings if f.key not in BROWSER_ALLOWLIST]
    assert not offenders, (
        "reader messages break docs/design-system-messages.md; say what happened and one "
        "remedy, and keep the detail in the route's JSON or the console:\n  "
        + "\n  ".join(offenders)
    )


def test_every_browser_allowlist_entry_is_still_needed(shipped_findings: list[Finding]) -> None:
    found = {f.key for f in shipped_findings}
    stale = sorted(
        f"{file} [{rule}] {function}"
        for file, rule, function in BROWSER_ALLOWLIST
        if (file, rule, function) not in found
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

PLANTED: dict[str, list[str]] = {
    "mechanics": [
        'note.textContent = "Its merge base moved after a rebase.";',
        'note.textContent = "The request waited in the queue past its deadline.";',
        'heading("Not ended in this segment");',
        'note.textContent = " Showing cached pull requests.";',
    ],
    "internal-path": ['note.textContent = "See docs/project/specs/plan.md for why.";'],
    "http-status": ["note.textContent = `Could not list branches (HTTP ${status}).`;"],
    "commit-id": [
        "note.textContent = `The branch is now at ${shortCommit(head)}.`;",
        "function freshnessNotice() { return shortCommit(head); }",
        "note.textContent = `The pull request now ends at ${pull.headSha}.`;",
        "note.textContent = `The branch moved to ${pull.headRefOid.slice(0, 7)}.`;",
        "note.textContent = `The branch moved to ${commit.slice(0, 7)}.`;",
    ],
    "list-in-notice": [
        'function staleNotice() { return element("ul", "", "notice-items"); }',
        "box.innerHTML = '<div class=\"notice\"><ul><li>one</li></ul></div>';",
    ],
    "exception-text": [
        "try { run(); } catch (failure) { note.textContent = failure.message; }",
        "function show(error) { note.textContent = String(error); }",
        "try { run(); } catch (err) { note.textContent = `Could not load the log ${err}`; }",
        "try { run(); } catch (problem) { note.textContent = problem; }",
        'load().catch((why) => { note.textContent = "Could not load. " + why; });',
    ],
    "appended-detail": [
        "note.textContent = `Could not read the log: ${error}`;",
        "note.textContent = `The switch was refused (${said}).`;",
        "note.textContent = `Could not list branches (${response.status}).`;",
        "note.textContent = `Could not switch (${body.code}).`;",
    ],
    "tone": [
        'button.dataset.tipText = "Copied!";',
        'note.textContent = "Failed to load the file. Please reload.";',
    ],
    "too-many-sentences": [
        'note.textContent = "This failed. It was the network. Try again later.";'
    ],
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
    assert PLANTED.get(rule), f"plant a violation of {rule}"
    for index, source in enumerate(PLANTED[rule]):
        found = {finding.rule for finding in _plant(tmp_path, f"{rule}-{index}", source)}
        assert rule in found, f"{rule} did not fire on {source!r}; it found {sorted(found)}"


def test_what_no_reader_sees_is_not_a_message(tmp_path: Path) -> None:
    """Console arguments, built-in errors' arguments, keys, comparisons, and class names are
    code."""
    source = "\n".join(
        [
            'console.warn("merge base moved after a rebase", error.message);',
            'global.console.warn("the worker stopped", `${caught}`);',
            'try { run(); } catch (caught) { window.console.error("the cache failed", caught); }',
            'row.className = "cache-status worker-row";',
            "note.textContent = `Showing ${shown} of ${total} files (${count} new).`;",
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
_REFRESH_STAMP = (
    "the text becomes a GitHub refresh stamp's `message` and the command line's account "
    "(provider.py _unavailable), which are for agents and a terminal; pages show copy.js's "
    "fixed sentence for the stamp's outcome"
)
SERVER_ALLOWLIST: dict[tuple[str, str], str] = {
    ("builtin_plugins/github/pull_catalog.py", "_state"): _REFRESH_STAMP,
    ("builtin_plugins/github/pulls.py", "_git_failure"): _REFRESH_STAMP,
    ("builtin_plugins/github/repository_snapshot.py", "failure_stamp"): _REFRESH_STAMP,
    ("builtin_plugins/github/sidekick.py", "pull_cores_prepare_handler"): (
        "core_request's ValueError is this package's own account of a malformed batch the "
        "pulls panel's code sent; the panel reads only the answer's status and "
        '"preparation" (pulls-panel.js), never its error'
    ),
    ("cache/acquire.py", "_rebind"): (
        "an acquisition error reaches a page only as checkout_store.py's fixed sentence "
        '("the store could not be prepared"); its text is the command line\'s'
    ),
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
    ("server_utils.py", "_listen_addresses"): (
        "UnusableHostError stops `metab` before it serves, and the terminal prints it"
    ),
    ("smoke_probes.py", "safe"): (
        "cmd_health, a developer's `python -m metabrowser.smoke_probes` probe, prints this "
        "JSON to a terminal; no route serves it"
    ),
}


@dataclass(frozen=True)
class Classes:
    """The classes the package defines, by name: all of them, the command line's errors,
    and the errors that give themselves a `reader_message`, whose `str()` is detail
    (content_errors.py)."""

    defined: set[str]
    cli_errors: set[str]
    detailed: set[str]


def _sets_reader_message(node: ast.ClassDef) -> bool:
    """Whether a class gives itself a `reader_message`, as a class attribute or on `self`."""
    for inner in ast.walk(node):
        targets = (
            inner.targets
            if isinstance(inner, ast.Assign)
            else [inner.target]
            if isinstance(inner, ast.AnnAssign)
            else []
        )
        for target in targets:
            if (isinstance(target, ast.Name) and target.id == "reader_message") or (
                isinstance(target, ast.Attribute) and target.attr == "reader_message"
            ):
                return True
    return False


def _with_subclasses(roots: set[str], bases: dict[str, set[str]]) -> set[str]:
    found = set(roots)
    grew = True
    while grew:
        grew = False
        for name, parents in bases.items():
            if name not in found and parents & found:
                found.add(name)
                grew = True
    return found


def _defined_classes(modules: Iterable[Path]) -> Classes:
    """Every class the package defines, its command-line errors, and its errors whose text
    is detail."""
    defined: set[str] = set()
    bases: dict[str, set[str]] = {}
    detailed: set[str] = set()
    for module in modules:
        for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef):
                defined.add(node.name)
                bases[node.name] = {
                    base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
                    for base in node.bases
                }
                if _sets_reader_message(node):
                    detailed.add(node.name)
    return Classes(
        defined, _with_subclasses({"CLIError"}, bases), _with_subclasses(detailed, bases)
    )


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


# An exception's attributes that hold its own words, and the traceback module's functions
# that write an exception out.
EXCEPTION_TEXT_ATTRIBUTES = frozenset({"strerror", "args", "filename", "msg", "message", "stderr"})
TRACEBACK_TEXT = frozenset(
    {"format_exc", "format_exception", "format_exception_only", "format_tb", "format_stack"}
)


def _carries(value: ast.AST, name: str, tainted: frozenset[str] = frozenset()) -> bool:
    """Whether *value* writes the text of the exception bound to *name*: through `str()`,
    `repr()`, an f-string, `format`, `%`, its `strerror` or `args` (`exc.args[0]` too),
    `type(x)`, or `traceback.format_exc()`, or through a local in *tainted* that was set
    from one. Reading another attribute, as `exc.reader_message`, is not its text."""

    def is_name(node: ast.AST) -> bool:
        return isinstance(node, ast.Name) and node.id == name

    def text_of(node: ast.AST) -> bool:
        if is_name(node):
            return True
        if isinstance(node, ast.Attribute) and is_name(node.value):
            return node.attr in EXCEPTION_TEXT_ATTRIBUTES
        if isinstance(node, ast.Subscript):
            return text_of(node.value)
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in {"str", "repr", "type"}:
                return any(text_of(argument) for argument in node.args)
        if isinstance(node, ast.Attribute) and node.attr == "__name__":
            return text_of(node.value)
        return False

    def mentions(node: ast.AST) -> bool:
        exempt = {
            id(inner.value)
            for inner in ast.walk(node)
            if isinstance(inner, ast.Attribute)
            and is_name(inner.value)
            and inner.attr not in EXCEPTION_TEXT_ATTRIBUTES
        }
        return any(text_of(inner) for inner in ast.walk(node) if id(inner) not in exempt)

    for node in ast.walk(value):
        if isinstance(node, ast.Name) and node.id in tainted:
            return True
        if isinstance(node, (ast.Attribute, ast.Subscript)) and text_of(node):
            return True
        if isinstance(node, ast.FormattedValue) and mentions(node.value):
            return True
        if isinstance(node, ast.Call):
            func = node.func
            called = (
                func.id
                if isinstance(func, ast.Name)
                else func.attr
                if isinstance(func, ast.Attribute)
                else ""
            )
            if called in TRACEBACK_TEXT:
                return True
            if called in {"str", "repr"} and node.args and text_of(node.args[0]):
                return True
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "format"
                and any(mentions(argument) for argument in node.args)
            ):
                return True
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) and mentions(node.right):
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


def _text_is_detail(types: list[str], classes: Classes) -> bool:
    """Whether an exception of one of *types* has text that is not reader copy: one
    Metabrowser did not define, or one of its errors with a `reader_message`."""
    return any(kind not in classes.defined or kind in classes.detailed for kind in types)


def _bindings(tree: ast.Module, classes: Classes) -> Iterator[tuple[str, list[ast.stmt]]]:
    """Each name bound to an exception whose text is not reader copy, with the statements
    it is read in: an `except` clause's, or a function's whose parameter is annotated with
    such an exception, as a helper that classifies one is."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.name is not None:
            types = _caught_types(node)
            if not types or _text_is_detail(types, classes):
                yield node.name, node.body
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                types = _annotated_types(argument.annotation)
                if (
                    types
                    and all(
                        kind.endswith(("Error", "Exception")) for kind in types if kind != "None"
                    )
                    and _text_is_detail([kind for kind in types if kind != "None"], classes)
                ):
                    yield argument.arg, node.body


def _answer_helpers(tree: ast.Module) -> dict[str, tuple[set[int], set[str]]]:
    """The module's functions that put a parameter into a reader field, as
    `_refusal(message, code, status)` puts `message` in `error`: for each, the positions
    and names of those parameters, so a call that passes exception text through one is
    read as the field it fills."""
    helpers: dict[str, tuple[set[int], set[str]]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        positional = [argument.arg for argument in (*node.args.posonlyargs, *node.args.args)]
        if positional[:1] in (["self"], ["cls"]):
            positional = positional[1:]
        filled: set[str] = set()
        for inner in ast.walk(node):
            if isinstance(inner, ast.Dict):
                values = [
                    value
                    for key, value in zip(inner.keys, inner.values, strict=True)
                    if isinstance(key, ast.Constant) and key.value in READER_FIELDS
                ]
            elif isinstance(inner, ast.Call):
                values = [
                    keyword.value for keyword in inner.keywords if keyword.arg in READER_FIELDS
                ]
            else:
                continue
            filled |= {value.id for value in values if isinstance(value, ast.Name)}
        names = filled & {*positional, *(argument.arg for argument in node.args.kwonlyargs)}
        if names:
            helpers[node.name] = ({i for i, arg in enumerate(positional) if arg in names}, names)
    return helpers


def _called(node: ast.Call) -> str:
    func = node.func
    return (
        func.id
        if isinstance(func, ast.Name)
        else func.attr
        if isinstance(func, ast.Attribute)
        else ""
    )


def _is_reader_target(target: ast.expr) -> bool:
    """An assignment target that is a reader field: `answer["error"]` or `answer.message`."""
    if isinstance(target, ast.Subscript):
        key = target.slice
        return isinstance(key, ast.Constant) and key.value in READER_FIELDS
    return isinstance(target, ast.Attribute) and target.attr in READER_FIELDS


def _reader_values(
    node: ast.AST,
    helpers: dict[str, tuple[set[int], set[str]]],
    classes: Classes,
    *,
    errors: bool = True,
) -> list[ast.AST]:
    """What *node* writes into a reader field: a dict's value at one, an assignment to one,
    a keyword that is one (`reader_message` too), a helper's argument that fills one, or,
    with *errors*, a Metabrowser error's message where that error's text is reader copy."""
    if isinstance(node, ast.Dict):
        return [
            value
            for key, value in zip(node.keys, node.values, strict=True)
            if isinstance(key, ast.Constant) and key.value in READER_FIELDS
        ]
    if isinstance(node, ast.Assign):
        return [node.value] if any(_is_reader_target(target) for target in node.targets) else []
    if not isinstance(node, ast.Call):
        return []
    values: list[ast.AST] = [
        keyword.value
        for keyword in node.keywords
        if keyword.arg in READER_FIELDS or keyword.arg == "reader_message"
    ]
    called = _called(node)
    if (
        errors
        and called in classes.defined
        and called not in classes.cli_errors
        and called not in classes.detailed
        and called.endswith(("Error", "Exception"))
    ):
        values += node.args
    if called in helpers:
        positions, names = helpers[called]
        values += [arg for i, arg in enumerate(node.args) if i in positions]
        values += [keyword.value for keyword in node.keywords if keyword.arg in names]
    return values


def _relative(module: Path) -> Path:
    return module.relative_to(PACKAGE) if module.is_relative_to(PACKAGE) else Path(module.name)


def server_findings(modules: Iterable[Path], classes: Classes) -> Iterator[Finding]:
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        owner = _function_names(tree)
        helpers = _answer_helpers(tree)
        seen: set[int] = set()
        for name, body in _bindings(tree, classes):
            inner_nodes = [inner for statement in body for inner in ast.walk(statement)]
            # A local set from the exception's text carries it one step on, as
            # `reason = str(exc)` then `{"error": reason}`.
            tainted = frozenset(
                target.id
                for inner in inner_nodes
                if isinstance(inner, ast.Assign) and _carries(inner.value, name)
                for target in inner.targets
                if isinstance(target, ast.Name)
            )
            for node in inner_nodes:
                # A reader field is written by a statement or an expression, which have lines.
                if not isinstance(node, (ast.stmt, ast.expr)):
                    continue
                carried = _reader_values(node, helpers, classes)
                if id(node) not in seen and any(
                    _carries(value, name, tainted) for value in carried
                ):
                    seen.add(id(node))
                    function = owner.get(node, "<module>")
                    yield Finding(
                        "server-exception-text",
                        f"{_relative(module)}:{node.lineno}",
                        f"{function}: {ast.unparse(node)}",
                        function,
                    )


def server_modules() -> list[Path]:
    return sorted(path for path in PACKAGE.rglob("*.py") if not path.is_relative_to(CLI_PACKAGE))


@pytest.fixture(scope="module")
def server_classes() -> Classes:
    return _defined_classes(PACKAGE.rglob("*.py"))


@pytest.fixture(scope="module")
def shipped_server_findings(server_classes: Classes) -> list[Finding]:
    return list(server_findings(server_modules(), server_classes))


def _server_key(finding: Finding) -> tuple[str, str]:
    return finding.where.rsplit(":", 1)[0], finding.function


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
    "passed to a helper that writes the answer": """
def _refusal(message: str, code: str) -> dict[str, str]:
    return {"error": message, "code": code}

def handler():
    try:
        read()
    except ValueError as exc:
        return _refusal(f"This log could not be read: {type(exc).__name__}: {exc}", "bad")
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
    "assigned to a reader field": """
def handler(payload):
    try:
        read()
    except OSError as exc:
        payload["error"] = str(exc)
""",
    "assigned to a reader attribute": """
def handler(answer):
    try:
        read()
    except OSError as exc:
        answer.message = f"Could not read: {exc}"
""",
    "through a local": """
def handler():
    try:
        read()
    except OSError as exc:
        reason = str(exc)
        return {"error": reason}
""",
    "a traceback": """
import traceback

def handler():
    try:
        read()
    except Exception:
        pass
    except ValueError as exc:
        return {"error": traceback.format_exc()}
""",
    "its arguments": """
def handler():
    try:
        read()
    except KeyError as exc:
        return {"error": exc.args[0]}
""",
    # The regression #801 fixed throughout: an error with a reader sentence answered by
    # its own text (review A2).
    "a Metabrowser error's text where it has a reader sentence": """
class ContentReadError(Exception):
    reader_message = "This file could not be read."

def handler():
    try:
        read()
    except ContentReadError as exc:
        return {"error": str(exc)}
""",
    "a subclass's text where its base has a reader sentence": """
class ContentReadError(Exception):
    reader_message = "This file could not be read."

class GitError(ContentReadError):
    def __init__(self, message: str) -> None:
        super().__init__(message)

def handler():
    try:
        read()
    except GitError as exc:
        return {"message": f"Git said: {exc}"}
""",
}


@pytest.mark.parametrize("case", sorted(SERVER_PLANTED))
def test_the_server_rule_fails_on_a_planted_violation(tmp_path: Path, case: str) -> None:
    module = tmp_path / "planted.py"
    module.write_text(SERVER_PLANTED[case], encoding="utf-8")
    found = list(server_findings([module], _defined_classes([module])))
    assert found, f"the server rule did not fire on {case}"


CLEAN_SERVER_MODULE = """
class ContentReadError(Exception):
    reader_message = "This file could not be read."

class SelectionError(Exception):
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
        return {"error": exc.reader_message, "detail": str(exc), "code": exc.code}
    except SelectionError as exc:
        return {"error": str(exc)}

def wrap():
    try:
        read()
    except OSError as exc:
        raise ContentReadError(f"reading the store failed: {exc}") from exc

def command():
    try:
        read()
    except OSError as exc:
        raise OpenInError(f"could not open: {exc}") from exc
"""


def test_the_server_rule_leaves_the_detail_and_its_own_errors_alone(tmp_path: Path) -> None:
    """`detail` is the agent's; the text of a Metabrowser error with no reader sentence is
    reader copy already, and wrapping a failure into one that has one makes it detail; the
    command line's errors are a terminal's."""
    module = tmp_path / "clean.py"
    module.write_text(CLEAN_SERVER_MODULE, encoding="utf-8")
    assert list(server_findings([module], _defined_classes([module]))) == []


# -- Server reader sentences follow the browser's text rules -----------------------------

# The browser rules that read a sentence's words; the others read browser code.
SERVER_TEXT_RULES = {
    rule: BROWSER_RULES[rule]
    for rule in (
        "mechanics",
        "internal-path",
        "http-status",
        "commit-id",
        "appended-detail",
        "tone",
        "too-many-sentences",
    )
}

# A server sentence a page never shows, and why, keyed by module, rule, and function. An
# entry that no longer matches fails test_every_server_text_allowlist_entry_is_still_needed.
_CACHE_ROUTES = (
    "the /api/cache/ routes serve `metab` and agents, and no page calls them; the cache is "
    "their subject"
)
SERVER_TEXT_ALLOWLIST: dict[tuple[str, str, str], str] = {
    ("builtin_plugins/github/sidekick.py", "mechanics", "cache_clear_handler"): (
        "the cache-clear route is the command gh_lists.py offers for a damaged GitHub cache, "
        "run with `metab --api`; no page calls it, and the cache is what it clears"
    ),
    ("cache/projection.py", "mechanics", "_answer"): _CACHE_ROUTES,
    ("cache/projection.py", "mechanics", "_entries_layout"): _CACHE_ROUTES,
    ("cache/projection.py", "mechanics", "_refuse_entries_without_layout"): _CACHE_ROUTES,
    ("event_log_route.py", "mechanics", "read_log"): (
        "the Details panel (static/event-reports.js showDetails) reads only a 2xx answer "
        "and drops a refusal's body, which is for `metab --api`"
    ),
}


def _strings_in(value: ast.AST) -> Iterator[ast.Constant | ast.JoinedStr]:
    """The string literals and f-strings in *value*, an f-string as one."""
    parts = {
        id(part)
        for node in ast.walk(value)
        if isinstance(node, ast.JoinedStr)
        for part in ast.walk(node)
        if part is not node
    }
    for node in ast.walk(value):
        if id(node) in parts:
            continue
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)) or isinstance(
            node, ast.JoinedStr
        ):
            yield node


def _server_record(node: ast.Constant | ast.JoinedStr, module: Path, function: str) -> Record:
    if isinstance(node, ast.Constant):
        kind, text, expressions = "string", str(node.value), []
    else:
        kind, pieces, expressions = "template", [], []
        for part in node.values:
            if isinstance(part, ast.Constant):
                pieces.append(str(part.value))
            elif isinstance(part, ast.FormattedValue):
                pieces.append(_PLACEHOLDER)
                expressions.append(ast.unparse(part.value))
        text = "".join(pieces)
    return Record(
        file=str(module),
        line=node.lineno,
        kind=kind,
        text=text,
        expressions=expressions,
        context="text",
        functions=[function],
        callee="",
        caught=False,
    )


def _class_reader_messages(tree: ast.Module) -> Iterator[ast.AST]:
    """Each value a class gives its `reader_message`."""
    for node in ast.walk(tree):
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
            if isinstance(node, ast.AnnAssign)
            else []
        )
        value = getattr(node, "value", None)
        if value is not None and any(
            isinstance(target, ast.Name) and target.id == "reader_message" for target in targets
        ):
            yield value


def server_text_findings(modules: Iterable[Path], classes: Classes) -> Iterator[Finding]:
    """Each server sentence a reader field holds that breaks a text rule."""
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        owner = _function_names(tree)
        helpers = _answer_helpers(tree)
        # A Metabrowser error's own message reaches the command line and the log as often as
        # a page, so only the fields an answer gives a page are held to the text rules.
        values = [
            value
            for node in ast.walk(tree)
            for value in _reader_values(node, helpers, classes, errors=False)
        ]
        values += list(_class_reader_messages(tree))
        seen: set[int] = set()
        for value in values:
            for literal in _strings_in(value):
                if id(literal) in seen:
                    continue
                seen.add(id(literal))
                function = owner.get(literal, "<module>")
                record = _server_record(literal, module, function)
                for rule, applies in SERVER_TEXT_RULES.items():
                    if applies(record):
                        yield Finding(
                            rule,
                            f"{_relative(module)}:{literal.lineno}",
                            f"{function}: {record['text']}",
                            function,
                        )


@pytest.fixture(scope="module")
def shipped_server_text_findings(server_classes: Classes) -> list[Finding]:
    return list(server_text_findings(server_modules(), server_classes))


def test_server_reader_sentences_follow_the_guide(
    shipped_server_text_findings: list[Finding],
) -> None:
    offenders = [str(f) for f in shipped_server_text_findings if f.key not in SERVER_TEXT_ALLOWLIST]
    assert not offenders, (
        "a server answer's error, message, or summary, or an error's reader_message, breaks "
        "docs/design-system-messages.md; pages show it as it is:\n  " + "\n  ".join(offenders)
    )


def test_every_server_text_allowlist_entry_is_still_needed(
    shipped_server_text_findings: list[Finding],
) -> None:
    found = {f.key for f in shipped_server_text_findings}
    stale = sorted(" ".join(key) for key in SERVER_TEXT_ALLOWLIST if key not in found)
    assert not stale, "remove these allowlist entries, which no longer match:\n  " + "\n  ".join(
        stale
    )


SERVER_TEXT_PLANTED: dict[str, list[str]] = {
    "mechanics": [
        'ANSWER = {"error": "Requested preview window exceeds the stream budget for this blob"}',
    ],
    "internal-path": ['ANSWER = {"message": "See docs/project/specs/plan.md for why."}'],
    "http-status": ['ANSWER = {"error": "GitHub answered (HTTP 502)."}'],
    "commit-id": ['def answer(head_sha):\n    return {"summary": f"The branch is at {head_sha}."}'],
    "appended-detail": ['def answer(reason):\n    return {"error": f"Could not read: {reason}"}'],
    "tone": [
        'ANSWER = {"error": "Failed to read the file. Please reload."}',
        'class GoneError(Exception):\n    reader_message = "This file is gone!"',
    ],
    "too-many-sentences": [
        'def _refusal(message):\n    return {"error": message}\n\n'
        'REFUSED = _refusal("This failed. It was the network. Try again later.")',
    ],
}


@pytest.mark.parametrize("rule", sorted(SERVER_TEXT_RULES))
def test_each_server_text_rule_fails_on_a_planted_violation(tmp_path: Path, rule: str) -> None:
    assert SERVER_TEXT_PLANTED.get(rule), f"plant a server violation of {rule}"
    for index, source in enumerate(SERVER_TEXT_PLANTED[rule]):
        module = tmp_path / f"planted_{index}.py"
        module.write_text(source, encoding="utf-8")
        found = {f.rule for f in server_text_findings([module], _defined_classes([module]))}
        assert rule in found, f"{rule} did not fire on {source!r}; it found {sorted(found)}"


def test_the_server_text_rules_pass_a_plain_sentence(tmp_path: Path) -> None:
    module = tmp_path / "clean.py"
    module.write_text(
        CLEAN_SERVER_MODULE
        + '\nANSWER = {"error": "This part of the file is past what can be shown here.",'
        + ' "detail": "Requested preview window exceeds the stream budget"}\n',
        encoding="utf-8",
    )
    assert list(server_text_findings([module], _defined_classes([module]))) == []
