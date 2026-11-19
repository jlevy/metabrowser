"""``devtools/check_app_contract.py``: the checker holds, and fails on each kind of drift.

The check reads the macOS app's contract with ``metab`` against the app's Swift sources
and against the golden. Each case here copies what the check reads, makes one change a
contributor could make, and names the problem the check must then report. A check that
passed a tree it should refuse would be worse than none, since the declaration would go
on reading as checked.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from devtools import app_contract, check_app_contract, swift_text
from devtools.app_contract import ContractError
from devtools.check_app_contract import CHANGE_MARK, COPIES, DECLARATION, FIX_MARK, GOLDEN
from tests.test_changelog import _git, _write

ROOT = Path(__file__).resolve().parents[1]
SOURCES = "apps/macos/Sources"
RECENT = f"{SOURCES}/ShellCore/Folders/RecentTargets.swift"
OPEN_TARGET = f"{SOURCES}/ShellCore/Folders/OpenTarget.swift"
CACHE = f"{SOURCES}/ShellCore/Folders/RepositoryCache.swift"
# A behavior pinned by a golden, as one the app's own script relies on in a page is
# pinned by the session or the transcript that shows the page emits it.
PINNED_BY_A_FILE = """
[[behavior]]
id = "page-marker"
source = "Sources/ShellCore/Web/PagePrint.swift"
what = "The page marks the link the app's script looks for."
pinned_by = "tests/golden/cli-serve-exit-on-eof.tryscript.md"
holds = "{holds}"
"""


def _copy(tmp_path: Path) -> Path:
    """What the check reads, copied where a test can change it."""

    root = tmp_path / "tree"
    shutil.copytree(ROOT / SOURCES, root / SOURCES)
    for relative in check_app_contract.referenced_files(app_contract.load()):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    return root


def _append(relative: str, text: str) -> Callable[[Path], None]:
    def change(root: Path) -> None:
        path = root / relative
        path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")

    return change


def _replace(relative: str, old: str, new: str) -> Callable[[Path], None]:
    def change(root: Path) -> None:
        path = root / relative
        text = path.read_text(encoding="utf-8")
        assert text.count(old) >= 1, f"{relative} no longer holds {old!r}"
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    return change


def _new_file(relative: str, text: str) -> Callable[[Path], None]:
    def change(root: Path) -> None:
        (root / relative).write_text(text, encoding="utf-8")

    return change


def _drop_block(scenario: str) -> Callable[[Path], None]:
    def change(root: Path) -> None:
        path = root / GOLDEN
        text = path.read_text(encoding="utf-8")
        end = text.index(f"--- contract ---\n{scenario}\n") + len(f"--- contract ---\n{scenario}\n")
        start = text.rindex("\n# metab ", 0, end) + 1
        path.write_text(text[:start] + text[end:], encoding="utf-8")

    return change


def test_the_repository_passes() -> None:
    assert check_app_contract.check(ROOT) == []


def test_a_copy_of_what_the_check_reads_passes(tmp_path: Path) -> None:
    assert check_app_contract.check(_copy(tmp_path)) == []


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        # A new dependency in the app's sources, undeclared.
        (
            _append(RECENT, '\nlet pinArguments = ["--recent-pin"]\n'),
            "`--recent-pin`, which the contract does not declare",
        ),
        (
            _append(OPEN_TARGET, '\nlet shown = "Try metab \\(root) --check-api in Terminal"\n'),
            "`--check-api`, which the contract does not declare",
        ),
        (
            _append(OPEN_TARGET, '\nfunc extra() -> LaunchSpec { LaunchSpec(executable: "x") }\n'),
            "OpenTarget.swift: builds a command to run (`LaunchSpec(`), and [files.launch] does",
        ),
        (
            _append(RECENT, '\nfunc extra() -> LaunchSpec { LaunchSpec(executable: "x") }\n'),
            "RecentTargets.swift: builds a command in 2 places, and [files.launch] says 1",
        ),
        (
            _append(OPEN_TARGET, '\nlet rollup = "api/rollup"\n'),
            "asks for `/api/rollup`, which the contract does not declare",
        ),
        (
            _append(OPEN_TARGET, '\nlet cache = "METABROWSER_CACHE_DIR"\n'),
            "names `METABROWSER_CACHE_DIR`, which the contract does not declare",
        ),
        (
            _new_file(f"{SOURCES}/ShellCore/Folders/Extra.swift", "let d = JSONDecoder()\n"),
            "Extra.swift: decodes JSON, and [files.json] does not list it",
        ),
        (
            _new_file(f"{SOURCES}/ShellCore/Folders/Extra.swift", "let s = URLSession.shared\n"),
            "Extra.swift: sends a request, and [files.http] does not list it",
        ),
        (
            _new_file(
                f"{SOURCES}/ShellCore/Web/Extra.swift",
                'func run(_ view: WKWebView) { view.evaluateJavaScript("1") }\n',
            ),
            "Extra.swift: scripts a page, and [files.script] does not list it",
        ),
        (
            _new_file(f"{SOURCES}/ShellCore/Folders/Extra.swift", "let child = Process()\n"),
            "Extra.swift: starts a process by itself",
        ),
        # The app's probe and the declared one.
        (
            _replace(
                DECLARATION,
                'argv = ["--exit-on-eof", "--present", "--recent", "--version"]',
                'argv = ["--exit-on-eof", "--present", "--version"]',
            ),
            "the app probes with `--exit-on-eof --present --recent --version`",
        ),
        # A declaration the sources no longer back.
        (
            _replace(
                DECLARATION,
                '"ref_name", "selection_state"]',
                '"ref_name", "selection_state", "pin"]',
            ),
            "source-status: declares the key `pin`, and",
        ),
        (
            _replace(RECENT, '["--recent-clear"]', '["--recent-reset"]'),
            "the contract declares `--recent-clear`, which no Swift source names any more",
        ),
        (
            _replace(DECLARATION, '"commit", "tree", "file"]', '"commit", "tree", "file", "blob"]'),
            "no golden shows `kind` as `blob`",
        ),
        (
            _replace(DECLARATION, "::test_the_port_walk_is_metabs", "::test_no_such_test"),
            "`tests/test_macos_app_pins.py::test_no_such_test` names no test",
        ),
        (
            _replace(DECLARATION, "::aWindowIsNamedAsTheServerNamesIt", "::noSuchTest"),
            "AppContractTests.swift::noSuchTest` names no test",
        ),
        # The golden and the declaration.
        (_drop_block("doctor"), f"command doctor: {GOLDEN} has no block for it"),
        (
            _replace(
                GOLDEN, '  "kind": "pull_request",\n', '  "kind": "pull_request",\n  "page": 1,\n'
            ),
            "`present-dry-run/pull-request`: records keys the contract does not declare",
        ),
        (
            _replace(DECLARATION, '"handoff", "refusal.code"', '"handoff", "page", "refusal.code"'),
            "page: the app reads this key, and the answer does not have it",
        ),
        (
            _replace(GOLDEN, "--no-open --exit-on-eof --host", "--exit-on-eof --no-open --host"),
            "`serve/folder`: runs `metab <ROOT>/served --exit-on-eof --no-open",
        ),
        (
            _replace(GOLDEN, "  [dev build: <STATE>]\n", "  [dev build: <STATE>]\nPlugins: text\n"),
            "records the stdout line `Plugins: text`, which is not the part of a declared",
        ),
        (
            _replace(GOLDEN, "METABROWSER_RECORD_RECENT=0 metab", "METABROWSER_QUIET=1 metab"),
            "sets `METABROWSER_QUIET`, which the contract does not declare",
        ),
        # Text the app only shows is recorded as present, and not word for word.
        (
            _replace(GOLDEN, '"message": "<text>"', '"message": "Issues are not opened"'),
            "records what `refusal.message` says, and the app only shows it",
        ),
        (
            _replace(GOLDEN, "origin.git in <text>", "origin.git in 0.0 s; starting"),
            "which is not the part of a declared line that the app parses",
        ),
        # A value the app copies is a line of the copies golden, and no other is.
        (
            _replace(COPIES, "metabrowser.settings:DEFAULT_BROWSER_PORT = 8411\n", ""),
            f"{COPIES}: has no line for `metabrowser.settings:DEFAULT_BROWSER_PORT`",
        ),
        (
            _append(COPIES, "metabrowser.settings:OTHER = 1\n"),
            "records `metabrowser.settings:OTHER`, which no entry's `values` names",
        ),
        # A key a listed file reads of an answer, by a subscript or a coding key.
        (
            _append(CACHE, '\nfunc slug(_ source: [String: Any]) -> Any? { source["slug"] }\n'),
            "reads the key `slug`, which cache-sources does not declare",
        ),
        (
            _replace(RECENT, 'case openedAt = "opened_at"', 'case openedAt = "opened"'),
            "reads the key `opened`, which recent-list does not declare",
        ),
        # A value that is none of those the app tells apart is recorded as another.
        (
            _replace(GOLDEN, '"publication": "<other>"', '"publication": "unattached"'),
            "records `sources[].publication` as `unattached`, which is none of the values",
        ),
        # A route's block is the status and the answer; a command's stderr, only what a
        # reader of JSON would take.
        (
            _replace(
                GOLDEN, "--- stdout ---\nstatus: 200\n", "--- stdout ---\napi: /x\nstatus: 200\n"
            ),
            "a route's block is `status: N`, the answer, and nothing else",
        ),
        (
            _replace(
                GOLDEN,
                '  "problem": null\n}\n--- stderr ---\n',
                '  "problem": null\n}\n--- stderr ---\n<text>\n',
            ),
            "records the stderr line `<text>`, which no reader of a JSON answer takes",
        ),
        # A `not-contract` comment says why, and sits on a line that reads a key.
        (
            _append(
                RECENT,
                '\nfunc why(_ n: Notification) -> Any? { n.userInfo?["reason"] }  // not-contract:\n',
            ),
            "says `reason` is no key of metab's and not why",
        ),
        (
            _append(RECENT, "\nlet unrelated = 1  // not-contract: nothing here reads a key\n"),
            "says `not-contract:` on a line that reads no key",
        ),
        # The interpreter's variables are named too.
        (
            _append(OPEN_TARGET, '\nlet home = "PYTHONHOME"\n'),
            "names `PYTHONHOME`, which the contract does not declare",
        ),
        # A pin that is a session or a golden holds what the entry depends on.
        (
            _append(DECLARATION, PINNED_BY_A_FILE.format(holds="no such text")),
            "[[behavior]] page-marker: `tests/golden/cli-serve-exit-on-eof.tryscript.md` "
            "does not contain `no such text`",
        ),
        # The app's tests run when the golden changes.
        (
            _replace(check_app_contract.APP_WORKFLOW, f'      - "{GOLDEN}"\n', ""),
            f"its `push` path filter does not name `{GOLDEN}`",
        ),
    ],
)
def test_each_kind_of_drift_is_named(
    change: Callable[[Path], None], expected: str, tmp_path: Path
) -> None:
    root = _copy(tmp_path)
    change(root)
    problems = check_app_contract.check(root)
    assert any(expected in problem for problem in problems), problems


def test_a_flag_in_a_comment_is_prose(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _append(RECENT, "\n// A later release may add --recent-pin, and METABROWSER_PIN.\n")(root)
    _append(RECENT, "\n/// `metab ROOT --api /api/rollup` answers the rollup.\n")(root)
    assert check_app_contract.check(root) == []


def test_a_problem_says_the_line_to_add(tmp_path: Path) -> None:
    """A file the declaration does not list is answered with its line, ready to paste."""

    root = _copy(tmp_path)
    _new_file(f"{SOURCES}/Metabrowser/Popover.swift", "let s = URLSession.shared\n")(root)
    _new_file(
        f"{SOURCES}/ShellCore/Folders/Extra.swift",
        'func extra() -> LaunchSpec { LaunchSpec(executable: "x") }\n',
    )(root)
    problems = "\n".join(check_app_contract.check(root))
    assert (
        f"Add to [files.http] in {DECLARATION}:\n"
        '    "Sources/Metabrowser/Popover.swift" = ["own: <what it requests>"]'
    ) in problems
    assert (
        '    "Sources/ShellCore/Folders/Extra.swift" = '
        '{ sites = 1, runs = ["own: <what it runs>"] }'
    ) in problems
    # Pasting the lines, with what each is, is all it takes.
    declaration = root / DECLARATION
    text = declaration.read_text(encoding="utf-8")
    text = text.replace(
        "[files.http]\n",
        '[files.http]\n"Sources/Metabrowser/Popover.swift" = ["own: a page of the app\'s"]\n',
    ).replace(
        "[files.launch]\n",
        '[files.launch]\n"Sources/ShellCore/Folders/Extra.swift" = '
        '{ sites = 1, runs = ["own: a tool"] }\n',
    )
    declaration.write_text(text, encoding="utf-8")
    assert check_app_contract.check(root) == []


def test_a_key_of_the_apps_own_says_so_on_its_line(tmp_path: Path) -> None:
    """A subscript in a listed file that is no key of metab's answer has a way to say so."""

    root = _copy(tmp_path)
    reads = '\nfunc why(_ note: Notification) -> Any? { note.userInfo?["reason"] }'
    _append(RECENT, reads + "\n")(root)
    problems = check_app_contract.check(root)
    assert len(problems) == 1, problems
    assert "reads the key `reason`, which recent-list does not declare" in problems[0]
    assert "end its line with `// not-contract: <why>`" in problems[0]

    _append(RECENT, reads + "  // not-contract: a notification's userInfo\n")(root)
    _replace(RECENT, reads + "\n", "\n")(root)
    assert check_app_contract.check(root) == []
    contract = app_contract.load(root / DECLARATION)
    listed = check_app_contract.not_contract_keys(contract, check_app_contract.app_sources(root))
    assert len(listed) == 1
    assert listed[0].startswith("Sources/ShellCore/Folders/RecentTargets.swift:")
    assert listed[0].endswith("`reason`: a notification's userInfo")
    assert "not-contract: Sources/ShellCore/Folders/RecentTargets.swift" in (
        check_app_contract.report(contract, check_app_contract.app_sources(root))
    )


def test_a_behavior_is_pinned_by_a_session_or_a_golden_that_holds_it(tmp_path: Path) -> None:
    """What the app's own script relies on in a page has no Python or Swift test to name."""

    root = _copy(tmp_path)
    held = PINNED_BY_A_FILE.format(holds="Stopping Metabrowser: stdin closed.")
    _append(DECLARATION, held)(root)
    assert check_app_contract.check(root) == []

    text = (ROOT / DECLARATION).read_text(encoding="utf-8")
    with pytest.raises(ContractError, match="with what it must contain in `holds`"):
        app_contract.parse(
            text + held.replace('holds = "Stopping Metabrowser: stdin closed."\n', "")
        )
    with pytest.raises(ContractError, match="names a test function"):
        app_contract.parse(
            text + held.replace("cli-serve-exit-on-eof.tryscript.md", "x.tryscript.md::test_x")
        )
    with pytest.raises(ContractError, match="`pinned_by` is a test function"):
        app_contract.parse(text + held.replace("tests/golden/", "docs/"))


def test_a_declaration_with_a_key_the_check_does_not_read_is_refused() -> None:
    text = (ROOT / DECLARATION).read_text(encoding="utf-8")
    with pytest.raises(ContractError, match="keys this check does not read: reads"):
        app_contract.parse(text.replace('stdout = ["version"]', 'reads = ["version"]', 1))
    with pytest.raises(ContractError, match="says why it is here in `because`"):
        app_contract.parse(text.replace("app_runs = false\n", "", 1))
    with pytest.raises(ContractError, match="shown names `page`, which `json` does not list"):
        app_contract.parse(text.replace('shown = ["refusal.message"]', 'shown = ["page"]', 1))
    with pytest.raises(ContractError, match="`metabrowser.settings` names no definition"):
        app_contract.parse(
            text.replace('"metabrowser.settings:DEFAULT_BROWSER_PORT"', '"metabrowser.settings"', 1)
        )


# ── Projection ──────────────────────────────────────────────────────


def test_projection_keeps_the_declared_keys_and_refuses_a_missing_one() -> None:
    answer = {
        "targets": [{"mode": "folder", "root": "/a", "target": None}],
        "limit": 50,
        "problem": None,
        "refusal": None,
    }
    paths = ["targets[].mode", "targets[].root", "problem", "refusal.code"]
    assert app_contract.project(answer, paths) == {
        "targets": [{"mode": "folder", "root": "/a"}],
        "problem": None,
        "refusal": None,
    }
    with pytest.raises(ContractError, match=r"targets\[0\]\.opened_at: the app reads this key"):
        app_contract.project(answer, ["targets[].opened_at"])
    assert app_contract.values_at(answer, "targets[].mode") == ["folder"]


def test_text_the_app_only_shows_is_recorded_as_present() -> None:
    answer = {"targets": [{"root": "/a", "opened_at": "2026-11-18T03:14:15Z"}], "problem": None}
    paths = ["targets[].root", "targets[].opened_at", "problem"]
    masks = app_contract.Recording(
        {"targets[].opened_at": app_contract.OPAQUE, "problem": app_contract.TEXT}
    )
    assert app_contract.project(answer, paths, masks) == {
        "targets": [{"root": "/a", "opened_at": "<opaque>"}],
        "problem": None,
    }
    said = app_contract.project({**answer, "problem": "The file is damaged."}, paths, masks)
    assert cast("dict[str, object]", said)["problem"] == "<text>"
    with pytest.raises(ContractError, match="problem: is declared as text"):
        app_contract.project({**answer, "problem": 3}, paths, masks)


def test_a_value_the_app_does_not_tell_apart_is_recorded_as_another() -> None:
    """The app asks only whether a source is published, so which other state it is in is
    the cache's to choose and no part of what the app reads."""

    page = {
        "sources": [
            {"publication": "published"},
            {"publication": "unattached"},
            {"publication": None},
        ]
    }
    told_apart = app_contract.Recording(choices={"sources[].publication": ("published",)})
    assert app_contract.project(page, ["sources[].publication"], told_apart) == {
        "sources": [{"publication": "published"}, {"publication": "<other>"}, {"publication": None}]
    }


def test_a_line_is_recorded_as_the_part_the_app_parses() -> None:
    cloned = re.compile(r"^cloned \S+://\S+ in ")
    option = re.compile(r"--no-such-option")
    printed = (
        "cloned https://github.com/octo/demo in 104 s (742.0 MiB); starting the server\n"
        "Plugins: text\n"
        "│ No such option: --no-such-option      │\n"
    )
    read = app_contract.read_lines(printed, [cloned, option])
    assert read == "cloned https://github.com/octo/demo in <text>\n<text>--no-such-option<text>\n"
    assert all(app_contract.is_read_line(line, [cloned, option]) for line in read.splitlines())
    assert not app_contract.is_read_line("cloned https://github.com/octo/demo in 104 s", [cloned])


def test_a_json_answer_keeps_the_framing_it_was_printed_in() -> None:
    """The app finds an answer by its lines, so the golden records them as printed."""

    answer = {"targets": [], "limit": 50, "problem": "café"}
    for indent, ensure_ascii in ((2, False), (2, True), (None, False)):
        raw = json.dumps(answer, indent=indent, ensure_ascii=ensure_ascii)
        before, found, text, after = app_contract.split_json(f"warning\n{raw}\n")
        assert (before, found, text, after) == ("warning\n", answer, raw, "\n")
        framing = app_contract.framing_of(text, found)
        assert (framing.indent, framing.ensure_ascii) == (indent, ensure_ascii)
        read = app_contract.project(found, ["targets", "problem"])
        assert app_contract.dump(read, framing) == json.dumps(
            {"targets": [], "problem": "café"}, indent=indent, ensure_ascii=ensure_ascii
        )
    with pytest.raises(ContractError, match="a framing this driver does not know"):
        app_contract.framing_of(json.dumps(answer, indent="\t"), answer)
    # What a reader of both streams would take as part of an answer is kept as written,
    # and a line it passes over is not recorded at all.
    assert app_contract.framing_lines('a warning\n{\n  {"x": 1}\n}\n') == '{\n  {"x": 1}\n}\n'


def test_a_command_line_is_held_to_the_declared_words() -> None:
    declared = ["{folder}", "--api", "/api/cache/sources?limit={limit}{after}", "--format", "json"]
    route = "/api/cache/sources?limit=2&after=slug"
    assert app_contract.matches_argv(["/f", "--api", route, "--format", "json"], declared)
    assert not app_contract.matches_argv(["/f", "--api", route, "--format", "yaml"], declared)
    assert not app_contract.matches_argv(["/f", "--api", route, "--format"], declared)
    assert not app_contract.matches_argv(
        ["/f", "--api", "/api/cache/stores", "--format", "json"], declared
    )


# ── Swift as text ───────────────────────────────────────────────────


def test_swift_text_tells_literals_from_comments_and_code() -> None:
    source = (
        'let a = "--one" // "--in-a-comment"\n'
        '/* a block /* nested */ "--still-a-comment" */\n'
        'let b = "see \\(flag ? "--inner" : other) --after"\n'
        'let c = #"raw "--quoted" \\#(x) --raw"#\n'
        'let d = #/^https://("--in-a-regex")/#\n'
        'let e = """\n    --multi\n    line\n    """\n'
        'let url = "https://example.com/a" + "--two"\n'
    )
    literals = [segment.text for segment in swift_text.strings(source)]
    flags = sorted({flag for text in literals for flag in check_app_contract._FLAG.findall(text)})
    assert flags == ["--after", "--inner", "--multi", "--one", "--quoted", "--raw", "--two"]
    code = swift_text.code(source)
    assert "--" not in code and "let url" in code and "other" in code


def test_the_probes_flags_are_read_from_the_apps_constants() -> None:
    sources = check_app_contract.app_sources(ROOT)
    assert check_app_contract.required_flags(sources) == ["--exit-on-eof", "--present", "--recent"]


# ── The changelog ───────────────────────────────────────────────────

CHANGELOG = """\
# Changelog

## Unreleased

New entries live in [`changelog.d/`](changelog.d/README.md) until a release adds them.

## 0.13.1

- An ordinary fix.
{patch}
## 0.13.0

- **App contract:** `metab --recent --json` lists the recent targets.
"""


def test_a_patch_release_holds_no_change_to_the_contract() -> None:
    change = f"{CHANGE_MARK} `--recent --json` renames `opened_at`.\n"
    fix = f"{FIX_MARK} `--recent --json` prints `opened_at` in UTC again.\n"
    assert check_app_contract.release_problems(CHANGELOG.format(patch=fix)) == []
    problems = check_app_contract.release_problems(CHANGELOG.format(patch=change))
    assert len(problems) == 1
    assert "0.13.1 is a patch release" in problems[0] and "release this as 0.14.0" in problems[0]


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(
        root,
        {
            DECLARATION: (ROOT / DECLARATION).read_text(encoding="utf-8"),
            GOLDEN: "# the golden\n",
            COPIES: "metabrowser.server_utils:DEFAULT_PORT_SEARCH_COUNT = 32\n",
            "CHANGELOG.md": CHANGELOG.format(patch=""),
            "changelog.d/README.md": "# Changelog Fragments\n",
            "changelog.d/mb-old1.md": "- An entry already on main.\n",
        },
    )
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    _git(root, "checkout", "-qb", "topic")
    return root


def test_a_branch_that_changes_the_contract_names_the_change(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    assert check_app_contract.change_problems(root, "main") == []

    # The same surface, answered differently: a change, or a fix.
    _write(root, {GOLDEN: "# the golden, changed\n"})
    problems = check_app_contract.change_problems(root, "main")
    assert len(problems) == 1 and GOLDEN in problems[0]
    assert CHANGE_MARK in problems[0] and FIX_MARK in problems[0]
    _write(root, {"changelog.d/mb-new1.md": "- The list shows a new field.\n"})
    assert check_app_contract.change_problems(root, "main")
    _write(root, {"changelog.d/mb-new1.md": f"{FIX_MARK} `--recent --json` is UTC again.\n"})
    assert check_app_contract.change_problems(root, "main") == []
    _write(root, {"changelog.d/mb-new1.md": f"{CHANGE_MARK} `--recent --json` gains `pinned`.\n"})
    assert check_app_contract.change_problems(root, "main") == []


def test_a_change_to_the_declared_surface_is_not_a_fix(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    declaration = (ROOT / DECLARATION).read_text(encoding="utf-8")

    # A note, a comment, and the test that pins an entry are no part of the surface.
    reworded = declaration.replace('note = "File > Open Recent and the Dock menu."', 'note = "x"')
    assert reworded != declaration
    _write(root, {DECLARATION: reworded + "\n# A comment.\n"})
    assert check_app_contract.change_problems(root, "main") == []

    # A key the app begins to read is, and a fix does not name it.
    wider = declaration.replace(
        '"targets[].opened_at", "problem"]', '"targets[].opened_at", "limit", "problem"]'
    )
    assert wider != declaration
    _write(root, {DECLARATION: wider})
    problems = check_app_contract.change_problems(root, "main")
    assert len(problems) == 1 and "declares a different surface" in problems[0]
    _write(root, {"changelog.d/mb-new1.md": f"{FIX_MARK} `--recent --json` is UTC again.\n"})
    problems = check_app_contract.change_problems(root, "main")
    assert len(problems) == 1 and "a fix keeps what the app reads" in problems[0]
    _write(root, {"changelog.d/mb-new1.md": f"{CHANGE_MARK} The app reads `limit`.\n"})
    assert check_app_contract.change_problems(root, "main") == []


def test_a_copied_value_and_a_behavior_are_part_of_the_contract(tmp_path: Path) -> None:
    """A port walk that shrinks changes no command and no answer, and an installed app
    still holds the old number."""

    root = _repository(tmp_path)
    _write(root, {COPIES: "metabrowser.server_utils:DEFAULT_PORT_SEARCH_COUNT = 16\n"})
    problems = check_app_contract.change_problems(root, "main")
    assert len(problems) == 1 and "a different value for one the app copies" in problems[0]
    # An app already installed keeps the old number, so it is no fix either.
    _write(root, {"changelog.d/mb-new1.md": f"{FIX_MARK} The port walk tries 16 ports.\n"})
    assert check_app_contract.change_problems(root, "main")
    _write(root, {"changelog.d/mb-new1.md": f"{CHANGE_MARK} The port walk tries 16 ports.\n"})
    assert check_app_contract.change_problems(root, "main") == []

    # A behavior the app begins to rely on is a different surface, whatever the goldens say.
    (root / "changelog.d/mb-new1.md").unlink()
    _write(root, {COPIES: "metabrowser.server_utils:DEFAULT_PORT_SEARCH_COUNT = 32\n"})
    declaration = (ROOT / DECLARATION).read_text(encoding="utf-8")
    _write(root, {DECLARATION: declaration + PINNED_BY_A_FILE.format(holds="x")})
    problems = check_app_contract.change_problems(root, "main")
    assert len(problems) == 1 and "declares a different surface" in problems[0]

    # So is the text a pin file must hold: it is the page's marker that the app looks for.
    marker = 'holds = \'"data-view-on-github": "open"\''
    assert marker in declaration
    renamed = declaration.replace(marker, marker.replace('"open"', '"main"'))
    _write(root, {DECLARATION: renamed})
    problems = check_app_contract.change_problems(root, "main")
    assert len(problems) == 1 and "declares a different surface" in problems[0]


def test_a_name_or_an_order_is_no_part_of_the_contract(tmp_path: Path) -> None:
    """A refactor that moves a constant, and tidying the declaration, change nothing the
    app reads, so neither is asked for a changelog entry."""

    root = _repository(tmp_path)
    declaration = (ROOT / DECLARATION).read_text(encoding="utf-8")

    def unchanged(text: str, copies: str | None = None) -> None:
        assert text != declaration
        _write(root, {DECLARATION: text})
        if copies is not None:
            _write(root, {COPIES: copies})
        assert check_app_contract.change_problems(root, "main") == []

    # A copied definition moves to another module, with its value.
    here = "metabrowser.server_utils:DEFAULT_PORT_SEARCH_COUNT"
    there = "metabrowser.settings:DEFAULT_PORT_SEARCH_COUNT"
    assert here in declaration
    unchanged(declaration.replace(here, there), f"{there} = 32\n")
    _write(root, {COPIES: f"{here} = 32\n"})

    # Two entries change places, and the keys of one do.
    first = declaration.index('[[command]]\nid = "recent-add"')
    second = declaration.index('[[command]]\nid = "recent-forget"')
    third = declaration.index('[[command]]\nid = "recent-clear"')
    unchanged(
        declaration[:first]
        + declaration[second:third]
        + declaration[first:second]
        + declaration[third:]
    )
    unchanged(
        declaration.replace(
            '["short_name", "full_name", "kind", "kind_label", "title"]',
            '["title", "kind_label", "kind", "full_name", "short_name"]',
        )
    )

    # The app renames the constant that holds a copy.
    unchanged(
        declaration.replace(
            'swift = "RepositoryCache.pageLimit"', 'swift = "RepositoryCache.limit"'
        )
    )


def test_a_change_main_made_is_not_this_branchs(tmp_path: Path) -> None:
    """In the middle of merging main in, ``HEAD`` is still the commit before the merge."""

    root = _repository(tmp_path)
    _git(root, "checkout", "-q", "main")
    _write(root, {GOLDEN: "# the golden, changed on main\n"})
    _git(root, "commit", "-qam", "main changes the contract")
    _git(root, "checkout", "-q", "topic")
    _write(root, {GOLDEN: "# the golden, changed on main\n"})
    assert check_app_contract.change_problems(root, "main") == []


# ── Asking a metab ──────────────────────────────────────────────────


def _stand_in(tmp_path: Path, body: str) -> str:
    path = tmp_path / "metab"
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


@pytest.mark.skipif(os.name != "posix", reason="the stand-in is a shell script")
def test_a_metab_is_asked_about_every_command_the_app_runs(tmp_path: Path) -> None:
    contract = app_contract.load()
    commands = check_app_contract.probe_commands(contract)
    assert all(argv[-1] == "--version" or "--version" in argv for _, argv in commands)
    assert {surface.id for surface, _ in commands} >= {"serve", "recent-list", "doctor"}
    assert not any(surface.id in ("acquire", "serve-path") for surface, _ in commands)

    current = _stand_in(tmp_path, 'echo "metab 0.13.0"')
    assert check_app_contract.accepts(contract, current) == []
    older = _stand_in(
        tmp_path,
        'for word in "$@"; do if [ "$word" = --recent ]; then'
        ' echo "No such option: --recent" >&2; exit 2; fi; done; echo "metab 0.12.0"',
    )
    refused = check_app_contract.accepts(contract, older)
    assert [line.partition(":")[0] for line in refused] == ["version-probe", "recent-list"]
    assert all("exited 2: No such option: --recent" in line for line in refused)
