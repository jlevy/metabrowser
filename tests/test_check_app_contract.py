"""``devtools/check_app_contract.py``: the checker holds, and fails on each kind of drift.

The check reads the macOS app's contract with ``metab`` against the app's Swift sources
and against the golden. Each case here copies what the check reads, makes one change a
contributor could make, and names the problem the check must then report. A check that
passed a tree it should refuse would be worse than none, since the declaration would go
on reading as checked.
"""

from __future__ import annotations

import os
import shutil
import stat
from collections.abc import Callable
from pathlib import Path

import pytest

from devtools import app_contract, check_app_contract, swift_text
from devtools.app_contract import ContractError
from devtools.check_app_contract import CHANGE_MARK, DECLARATION, FIX_MARK, GOLDEN
from tests.test_changelog import _git, _write

ROOT = Path(__file__).resolve().parents[1]
SOURCES = "apps/macos/Sources"
RECENT = f"{SOURCES}/ShellCore/Folders/RecentTargets.swift"
OPEN_TARGET = f"{SOURCES}/ShellCore/Folders/OpenTarget.swift"


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
            "records the stdout line `Plugins: text`, which is none of the lines",
        ),
        (
            _replace(GOLDEN, "METABROWSER_RECORD_RECENT=0 metab", "METABROWSER_QUIET=1 metab"),
            "sets `METABROWSER_QUIET`, which the contract does not declare",
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


def test_a_declaration_with_a_key_the_check_does_not_read_is_refused() -> None:
    text = (ROOT / DECLARATION).read_text(encoding="utf-8")
    with pytest.raises(ContractError, match="keys this check does not read: reads"):
        app_contract.parse(text.replace('stdout = ["version"]', 'reads = ["version"]', 1))
    with pytest.raises(ContractError, match="says why it is here in `because`"):
        app_contract.parse(text.replace("app_runs = false\n", "", 1))


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
            DECLARATION: "# the declaration\n",
            GOLDEN: "# the golden\n",
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

    _write(root, {GOLDEN: "# the golden, changed\n"})
    problems = check_app_contract.change_problems(root, "main")
    assert len(problems) == 1 and GOLDEN in problems[0] and CHANGE_MARK in problems[0]

    # An unmarked entry, and a marked one in a fragment this branch did not write.
    _write(root, {"changelog.d/mb-new1.md": "- The list shows a new field.\n"})
    assert check_app_contract.change_problems(root, "main")
    _write(root, {"changelog.d/mb-new1.md": f"{CHANGE_MARK} `--recent --json` gains `pinned`.\n"})
    assert check_app_contract.change_problems(root, "main") == []
    _write(root, {"changelog.d/mb-new1.md": f"{FIX_MARK} `--recent --json` is UTC again.\n"})
    assert check_app_contract.change_problems(root, "main") == []


def test_a_change_main_made_is_not_this_branchs(tmp_path: Path) -> None:
    """In the middle of merging main in, ``HEAD`` is still the commit before the merge."""

    root = _repository(tmp_path)
    _git(root, "checkout", "-q", "main")
    _write(root, {DECLARATION: "# the declaration, changed on main\n"})
    _git(root, "commit", "-qam", "main changes the contract")
    _git(root, "checkout", "-q", "topic")
    _write(root, {DECLARATION: "# the declaration, changed on main\n"})
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
