"""The values the user guides state, held to the code that sets them.

Values live in code, and a document names the constant rather than restating it. A user
guide is the exception for a value its reader needs as a fact (the file cap, the
compressed-file suffixes, the default port, the exit statuses), because a reader of
`docs/browsing-files.md` should not have to open `settings.py` to learn how large a tree
Metabrowser indexes. This test is what lets a guide restate one: every value below is
read from its source, each copy a guide states is compared with it, and a change to the
source fails here until the guide says the new value.

`tests/test_installation_requirements.py` does the same for the platform requirements in
`docs/installation.md`, and `tests/test_keymap.py` for the keyboard table.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import get_args

import click
from watchfiles import DefaultFilter

from metabrowser.builtin_plugins.github.gh_status import GH_MINIMUM_LABEL
from metabrowser.cache.free_space import FREE_SPACE_RESERVE_ENV, FREE_SPACE_RESERVE_MB
from metabrowser.cli.exit_codes import (
    INTERRUPTED_EXIT_CODE,
    PRESENT_BLOCKED_EXIT_CODE,
    PRESENT_NO_APP_EXIT_CODE,
    PRESENT_REFUSED_EXIT_CODE,
)
from metabrowser.cli.hangup import HANGUP_EXIT_STATUS, TERMINATION_EXIT_STATUS
from metabrowser.cli.present import (
    ANY_APP_LOCATION_ENV,
    APP_BUNDLE_NAME,
    APP_INSTALL_LOCATIONS,
    BUNDLE_ID_ENV,
    OPENS_URLS_KEY,
    DeliveryCode,
    PresentKind,
)
from metabrowser.commit_ids import SHORT_COMMIT_CHARS
from metabrowser.constants import LOGS_DIR, STATE_DIR
from metabrowser.dotenv import ALLOWED_KEYS
from metabrowser.file_extensions import BROWSER_TRACKABLE_EXTS
from metabrowser.file_type_legend import LEGEND_MINIMUM_SHARE_PERCENT, LEGEND_TYPE_LIMIT
from metabrowser.git.file_ages import file_ages_version_label
from metabrowser.git.log import TRUNK_BRANCH_NAMES, TRUNK_REMOTES
from metabrowser.git.process import ACQUISITION_MINIMUM
from metabrowser.gz_io import GZIP_SUFFIX, ZLIB_SUFFIX
from metabrowser.home import application_cache, configuration_directory
from metabrowser.inventory_engine.factory import InventoryProvider
from metabrowser.logutil.parsing import registered_log_adapters
from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S
from metabrowser.settings import (
    DEFAULT_BROWSER_PORT,
    INVENTORY_MAX_FILES,
    LIVE_FILE_WINDOW_S,
    RECENT_DEFAULT_LIMIT,
    SLOW_OPERATION_LOG_SECONDS,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src" / "metabrowser"
APP_SOURCES = REPO_ROOT / "apps" / "macos" / "Sources" / "ShellCore"
AGENT_LOG_MANIFEST = SRC / "builtin_plugins" / "agents" / "manifest.toml"

# What a guide calls each JSONL adapter. A new adapter fails here until it has a name, so
# that the guides can be told about it. Codex's two formats share a name.
AGENT_NAMES = {
    "claude": "Claude Code",
    "gemini": "Gemini CLI",
    "pi": "Pi",
    "codex": "Codex",
    "codex-rollout": "Codex",
}

# The examples docs/browsing-files.md gives of directories the watcher does not observe.
# They come from `watchfiles.DefaultFilter`, which `run_watcher` leaves in place; a
# watchfiles release that drops one, or a filter of our own, fails here.
UNWATCHED_EXAMPLES = ("node_modules", ".venv", "__pycache__")

_NUMBER_WORDS = {
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
}


@dataclass(frozen=True)
class Stated:
    """One value as *guide* states it: each match of *pattern* must read *expected*."""

    guide: str
    what: str
    pattern: str
    expected: tuple[str, ...]


def _swift(path: Path, pattern: str) -> re.Match[str]:
    match = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    assert match, f"{path.relative_to(REPO_ROOT)} no longer matches {pattern!r}"
    return match


def _home_relative(path: Path) -> str:
    return "~/" + path.relative_to(Path.home()).as_posix()


def _series(names: list[str], conjunction: str = "and") -> str:
    """``a, b, and c`` as a guide writes a list."""

    if len(names) <= 2:
        return f" {conjunction} ".join(names)
    return ", ".join(names[:-1]) + f", {conjunction} " + names[-1]


def _manifest_adapters() -> set[str]:
    manifest = tomllib.loads(AGENT_LOG_MANIFEST.read_text(encoding="utf-8"))
    # The rules that name an adapter; a rule that claims a file by its path, such as a
    # compressed rollout's, names none.
    return {
        str(kind["match"]["adapter"]) for kind in manifest["kind"] if "adapter" in kind["match"]
    }


def _charted_agents() -> str:
    names = [AGENT_NAMES[name] for name in sorted(_manifest_adapters())]
    return _series(list(dict.fromkeys(names)))


def stated_values() -> list[Stated]:
    """Every value a user guide restates, with what its source sets now."""

    app_minimum = _swift(
        APP_SOURCES / "Setup" / "MetabVersion.swift",
        r"static let minimumRelease = \[(\d+), (\d+), (\d+)\]",
    )
    live_tabs = int(
        _swift(
            APP_SOURCES / "Web" / "TabDiscardPolicy.swift",
            r"static let defaultLiveBackgroundTabs = (\d+)",
        ).group(1)
    )
    budget = _swift(
        APP_SOURCES / "Folders" / "SavedSession.swift",
        r"static let standard = RestoreBudget\(windows: (\d+), tabs: (\d+)\)",
    )
    cap = f"{INVENTORY_MAX_FILES:,}"
    return [
        Stated("README.md", "the file cap", r"Indexing stops at ([\d,]+) files", (cap,)),
        Stated(
            "docs/browsing-files.md", "the file cap", r"The index stops at ([\d,]+) files", (cap,)
        ),
        Stated(
            "docs/browsing-files.md",
            "the compressed-file suffixes",
            r"whose name ends in `([^`]+)` or `([^`]+)`",
            (GZIP_SUFFIX, ZLIB_SUFFIX),
        ),
        Stated(
            "docs/browsing-files.md",
            "the Live window",
            r"Live means changed in the last (\d+) seconds",
            (str(int(LIVE_FILE_WINDOW_S)),),
        ),
        Stated(
            "docs/browsing-files.md",
            "the Recent view's limit",
            r"The view holds at most ([\d,]+) files",
            (f"{RECENT_DEFAULT_LIMIT:,}",),
        ),
        Stated(
            "docs/browsing-files.md",
            "the watched folders",
            r"in a folder named `([^`]+)` or `([^`]+)`",
            (LOGS_DIR, STATE_DIR),
        ),
        Stated(
            "docs/browsing-files.md",
            "the watched extensions",
            r"whose names end in\s+((?:`\.\w+`(?:,?\s+(?:or\s+)?)?)+)",
            (_series([f"`{ext}`" for ext in sorted(BROWSER_TRACKABLE_EXTS)], "or"),),
        ),
        Stated(
            "docs/browsing-files.md",
            "the directories the watcher skips",
            r"the file watcher skips, such as\s+`([^`]+)`, `([^`]+)`, or `([^`]+)`",
            tuple(name for name in UNWATCHED_EXAMPLES if name in DefaultFilter.ignore_dirs),
        ),
        Stated(
            "docs/browsing-files.md",
            "the charted agents",
            r"the session logs of ([^,]+(?:, [^,]+)*?), Metabrowser shows",
            (_charted_agents(),),
        ),
        Stated(
            "docs/browsing-history.md",
            "the trunk branches",
            r"the trunk\s+branches `(\w+)` and `(\w+)`, locally and on `(\w+)`",
            (*TRUNK_BRANCH_NAMES, *TRUNK_REMOTES),
        ),
        Stated(
            "docs/browsing-history.md",
            "the short commit ID's length",
            r"the\s+short\s+ID,\s+its\s+first\s+(\w+)\s+characters,\s+as\s+GitHub",
            (_NUMBER_WORDS.get(SHORT_COMMIT_CHARS, str(SHORT_COMMIT_CHARS)),),
        ),
        Stated(
            "docs/working-with-agents.md",
            "the default port",
            r"the first free one from (\d+)",
            (str(DEFAULT_BROWSER_PORT),),
        ),
        Stated(
            "docs/working-with-agents.md",
            "the charted agents",
            r"the session logs of ([^,]+(?:, [^,]+)*?) open with",
            (_charted_agents(),),
        ),
        Stated(
            "docs/reviewing-pull-requests.md",
            "the freshness window",
            r"current for (\d+) seconds after its fetch",
            (str(int(FRESHNESS_WINDOW_S)),),
        ),
        Stated(
            "docs/command-line.md",
            "the default port",
            r"the first port to try, (\d+) by default",
            (str(DEFAULT_BROWSER_PORT),),
        ),
        Stated(
            "docs/command-line.md",
            "the usage-error status",
            r"^\| (\d+) \| A usage error",
            (str(click.UsageError.exit_code),),
        ),
        Stated(
            "docs/command-line.md",
            "the hangup and interrupt statuses",
            r"^\| (\d+), (\d+) \| Stopped by a terminal hangup or Ctrl-C",
            (str(HANGUP_EXIT_STATUS), str(INTERRUPTED_EXIT_CODE)),
        ),
        Stated(
            "docs/command-line.md",
            "the --present refusal status",
            r"^\| (\d+) \| `--present`: ROOT cannot be presented",
            (str(PRESENT_REFUSED_EXIT_CODE),),
        ),
        Stated(
            "docs/command-line.md",
            "the --present status when no app takes the target",
            r"^\| (\d+) \| `--present`: no app takes the target",
            (str(PRESENT_NO_APP_EXIT_CODE),),
        ),
        Stated(
            "docs/command-line.md",
            "the --present status when LaunchServices is blocked",
            r"^\| (\d+) \| `--present`: LaunchServices could not be asked",
            (str(PRESENT_BLOCKED_EXIT_CODE),),
        ),
        Stated(
            "docs/command-line.md",
            "the variable that names the app --present looks for",
            r"^\| `(\w+)` \| The app `--present` hands a target to",
            (BUNDLE_ID_ENV,),
        ),
        Stated(
            "docs/command-line.md",
            "where --present finds an installed app",
            r"it is at `([^`]+)` or\s+`([^`]+)`",
            APP_INSTALL_LOCATIONS,
        ),
        Stated(
            "docs/command-line.md",
            "the name an installed app's Info.plist gives it",
            r"its `Info.plist` names it `(\w+)`",
            (APP_BUNDLE_NAME,),
        ),
        Stated(
            "docs/command-line.md",
            "the setting that lifts the install-location check",
            r"(?:^\| `|\bsets\s+`)(METABROWSER_ALLOW_\w+)",
            (ANY_APP_LOCATION_ENV,),
        ),
        Stated(
            "docs/project/qa/qa-macos-app-hand-checks.md",
            "the setting the --present hand checks use",
            r"\b(METABROWSER_ALLOW_\w+)=1",
            (ANY_APP_LOCATION_ENV,),
        ),
        Stated(
            "docs/command-line.md",
            "the key an app that takes what --present sends declares",
            r"`Info.plist`\s+declares\s+`(\w+)`\s+true",
            (OPENS_URLS_KEY,),
        ),
        Stated(
            "docs/command-line.md",
            "the termination status",
            r"^\| (\d+) \| Stopped by `SIGTERM`",
            (str(TERMINATION_EXIT_STATUS),),
        ),
        Stated(
            "docs/command-line.md",
            "the default cache directory",
            r"^\| Cache: mirrors and pull-request records \| `([^`]+)`",
            (_home_relative(application_cache({})),),
        ),
        Stated(
            "docs/command-line.md",
            "the default configuration directory",
            r"^\| Configuration: `config.yml` \| `([^`]+)`",
            (_home_relative(configuration_directory({})),),
        ),
        Stated(
            "docs/command-line.md",
            "the keys a .env file supplies",
            r"takes only `(\w+)` and `(\w+)` from them",
            tuple(sorted(ALLOWED_KEYS)),
        ),
        Stated(
            "docs/command-line.md",
            "the slow-request threshold",
            r"logged as slow, ([\d,]+) by default",
            (f"{int(SLOW_OPERATION_LOG_SECONDS * 1000):,}",),
        ),
        Stated(
            "docs/command-line.md",
            "the inventory engines",
            r"this build ships `(\w+)` alone, the default",
            tuple(provider.value for provider in InventoryProvider),
        ),
        Stated(
            "docs/command-line.md",
            "the first-clone free-space reserve",
            r"^\| `(\w+)` \| The free space, in megabytes, a first clone leaves",
            (FREE_SPACE_RESERVE_ENV,),
        ),
        Stated(
            "docs/command-line.md",
            "the default first-clone free-space reserve",
            r"a first clone leaves on the cache volume, (\d+) by default",
            (str(FREE_SPACE_RESERVE_MB),),
        ),
        Stated(
            "docs/installation.md",
            "the Git security floor",
            r"a Git older than (\d+\.\d+\.\d+)",
            (".".join(str(part) for part in ACQUISITION_MINIMUM),),
        ),
        Stated(
            "docs/browsing-files.md",
            "the Git release that reads file ages",
            r"which needs Git (\d+\.\d+) or newer",
            (file_ages_version_label(),),
        ),
        Stated(
            "docs/command-line.md",
            "the Git release that reads file ages",
            r"\(`git last-modified`, Git (\d+\.\d+)\)",
            (file_ages_version_label(),),
        ),
        Stated(
            "docs/installation.md",
            "the GitHub CLI minimum",
            r"the doctor.s GitHub check, need `gh` (\d+\.\d+\.\d+) or later",
            (GH_MINIMUM_LABEL,),
        ),
        Stated(
            "docs/installation.md",
            "the app's minimum metab",
            r"the app needs `metab` (\d+\.\d+\.\d+) or later",
            (".".join(app_minimum.groups()),),
        ),
        Stated(
            "docs/macos-app.md",
            "the app's minimum metab",
            r"the app runs `metab` (\d+\.\d+\.\d+) or later",
            (".".join(app_minimum.groups()),),
        ),
        Stated(
            "skills/metabrowser/SKILL.md",
            "the app's minimum metab",
            r"the app needs `metab` (\d+\.\d+\.\d+) or later",
            (".".join(app_minimum.groups()),),
        ),
        Stated(
            "docs/browsing-files.md",
            "the legend's family limit",
            r"largest file-type families, such as Python, Markdown, and JSON, up to (\w+),",
            (_NUMBER_WORDS.get(LEGEND_TYPE_LIMIT, str(LEGEND_TYPE_LIMIT)),),
        ),
        Stated(
            "docs/browsing-files.md",
            "the legend's share floor",
            r"each at least (\d+)% of what is shown",
            (str(LEGEND_MINIMUM_SHARE_PERCENT),),
        ),
        Stated(
            "docs/macos-app.md",
            "the live background tabs",
            r"and so do the (\w+)\s+background tabs shown most recently",
            (_NUMBER_WORDS.get(live_tabs, str(live_tabs)),),
        ),
        Stated(
            "docs/macos-app.md",
            "the restore budget",
            r"rebuilds at most the front (\d+) windows and (\d+) tabs",
            budget.groups(),
        ),
    ]


def findings(text: str, stated: Stated) -> list[str]:
    """What *text* states for *stated* that its source does not set, or that it omits."""

    # A space in a pattern matches any run of whitespace, since the formatter rewraps prose.
    matches = re.findall(stated.pattern.replace(" ", r"\s+"), text, re.MULTILINE)
    if not matches:
        return [f"{stated.guide} states no {stated.what}; its source sets {stated.expected}"]
    found = []
    for match in matches:
        parts = match if isinstance(match, tuple) else (match,)
        values = tuple(" ".join(part.split()) for part in parts)
        if values != stated.expected:
            found.append(
                f"{stated.guide} states {stated.what} as {values} where its source sets "
                f"{stated.expected}"
            )
    return found


def test_user_guides_state_the_values_the_code_sets() -> None:
    problems = [
        problem
        for stated in stated_values()
        for problem in findings((REPO_ROOT / stated.guide).read_text(encoding="utf-8"), stated)
    ]
    assert not problems, "\n".join(problems)


def test_every_jsonl_adapter_has_a_name_the_guides_can_use() -> None:
    adapters = frozenset(registered_log_adapters())
    assert _manifest_adapters() <= adapters
    unnamed = sorted(adapters - AGENT_NAMES.keys())
    assert not unnamed, f"name {unnamed} in AGENT_NAMES, then say which guides list it"
    # docs/working-with-agents.md says every recognized agent's logs open with Charts.
    uncharted = sorted(adapters - _manifest_adapters())
    assert not uncharted, (
        f"{uncharted} parse without Charts: say so in docs/working-with-agents.md and pin it"
    )


def test_the_watcher_keeps_the_filter_the_guide_describes() -> None:
    """`watchfiles.awatch` applies `DefaultFilter` only when it is given no filter."""

    source = (SRC / "watch_backends.py").read_text(encoding="utf-8")
    assert "awatch(" in source
    assert "watch_filter" not in source, (
        "run_watcher now passes its own watch_filter: update UNWATCHED_EXAMPLES and the "
        "unwatched directories in docs/browsing-files.md"
    )


def test_cli_release_docs_keep_the_preview_runtime_guidance_conditional() -> None:
    installation = (REPO_ROOT / "docs/installation.md").read_text(encoding="utf-8")
    app_section = installation.split("## The macOS App\n", 1)[1].split("\n## ", 1)[0]
    app_section = " ".join(app_section.split())
    assert "If the published CLI meets the app’s minimum" in app_section
    assert "`uv tool install metabrowser`" in app_section
    assert "If your preview needs a newer runtime" in app_section
    assert "`.venv/bin/metab`" in app_section
    skill = (REPO_ROOT / "skills/metabrowser/SKILL.md").read_text(encoding="utf-8")
    assert "a skill installed from a release tag matches that release" in skill
    assert "If you need an unreleased feature" in skill


def _reason_codes(guide: str, heading: str) -> list[str]:
    """The backticked names in the first column of every table under *heading*."""

    section = guide[guide.index(f"\n## {heading}\n") :]
    section = section[: section.find("\n## ", 1)]
    codes = []
    for line in section.splitlines():
        if line.startswith("| `"):
            codes += re.findall(r"`([a-z_]+)`", line.split(" | ")[0])
    return codes


def test_every_failure_reason_the_guide_names_is_one_the_code_reports() -> None:
    guide = (REPO_ROOT / "docs/reviewing-pull-requests.md").read_text(encoding="utf-8")
    codes = _reason_codes(guide, "When Something Does Not Open")
    assert len(codes) > 20
    source = "\n".join(path.read_text(encoding="utf-8") for path in SRC.rglob("*.py"))
    missing = [code for code in codes if f'"{code}"' not in source]
    assert not missing, f"docs/reviewing-pull-requests.md names reasons no code reports: {missing}"


def test_the_values_check_sees_what_it_must() -> None:
    stated = Stated("guide.md", "the file cap", r"stops at ([\d,]+) files", ("500,000",))
    assert findings("It stops at 500,000 files.", stated) == []
    assert findings("It stops at 400,000 files.", stated) == [
        "guide.md states the file cap as ('400,000',) where its source sets ('500,000',)"
    ]
    assert findings("No figure.", stated) == [
        "guide.md states no the file cap; its source sets ('500,000',)"
    ]
    pair = Stated("guide.md", "the suffixes", r"ends in `([^`]+)` or `([^`]+)`", (".gz", ".zlib"))
    assert findings("ends in `.gz` or `.zlib`", pair) == []
    assert findings("ends in `.gz` or `.bz2`", pair)
    assert _series(["a", "b", "c"]) == "a, b, and c"
    assert _series(["a", "b"]) == "a and b"


_PRESENT_SECTION = "Presenting a Target: `--present`"


def test_the_present_guide_names_every_delivery_code_and_kind() -> None:
    guide = (REPO_ROOT / "docs/command-line.md").read_text(encoding="utf-8")
    section = guide[guide.index(f"\n## {_PRESENT_SECTION}\n") :]
    section = section[: section.find("\n## ", 1)]
    table = [match.group(1) for match in re.finditer(r"^\| `([a-z_]+)` \| ", section, re.MULTILINE)]
    kinds = re.search(r"^- \*\*`kind`:\*\* (.+?)\. ", section, re.MULTILINE)

    assert table == list(get_args(DeliveryCode.__value__)), "update the guide's code table"
    assert kinds is not None
    named = re.findall(r"`([a-z_]+)`", kinds.group(1))
    assert sorted(named) == sorted(get_args(PresentKind.__value__)), "update the kind list"
