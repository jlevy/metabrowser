"""Re-apply elision patterns after `tryscript run --update` regenerates goldens.

`tryscript run --update` rewrites changed test blocks with literal captured
output, which clobbers the elision patterns the goldens rely on. This script
restores them so `make golden-update` is a single reviewable step:

* `[ROOT_ARG]` for the literal `[ROOT]` metavar in Typer's usage line, which
  tryscript would otherwise substitute with the test-file directory
* `[CWD]` for the sandbox directory in walk envelopes, and after `file://` in the
  address a served mirror says it mirrors
* `[APP_HOME]` for the application home in the location a served mirror's status
  reports, and `[STORE_KEY]` for the store's key in it when the origin is a sandbox
  address, from which the key is derived
* `[BUILTIN]` for the absolute checkout prefix of builtin plugin paths
* `[VERSION]` for the installed package version
* the second copy of the KPress asset manifest in the shell transcript
* the KPress icon sprite at the head of a rendered document, which is tens of
  kilobytes of third-party SVG and would make the transcript unreviewable; the
  rendered article after it stays literal
* `[CLOCK]` for the logger's time of day on the pending-tally diagnostic line
* `[TIMESTAMP]` for a time taken from the wall clock while the transcript or its
  fixture ran: when a one-shot refresh found another process refreshing, when a
  pull request's refresh failed, and when a fixture fetched its mirror. A time a
  fixture pins stays literal, and a time that is neither stops the update
* the watcher's mode, state, and reason, which are host facts and startup
  transients -- the filesystem the served root sits on, the backend that made
  available, and how far selection had got when the request landed
* `[COUNT]` for the engine sequence in the pending-tally diagnostic, which counts
  internal change batches

It also strips trailing whitespace, which `tryscript run --update` preserves
from Rich's padded terminal output but `git diff --check` rejects; tryscript
trims line ends on both sides of a comparison, so stripping is match-safe.
"""

from __future__ import annotations

import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tests import cache_home_fixture, github_pull_fixture, source_mirror_fixture

GOLDEN_DIR = Path(__file__).parent.parent / "tests" / "golden"

_TIME = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ"
_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# The times the fixtures themselves record in the places the rules below look at, read
# from the fixtures, so a fixture that moves its clock moves this with it. One of these
# in a transcript is a pinned value and stays literal.
FIXTURE_TIMES: frozenset[str] = frozenset(
    {
        cache_home_fixture.FETCHED_AT,
        source_mirror_fixture.FETCHED_AT,
        github_pull_fixture.FETCHED_AT.strftime(_TIME_FORMAT),
    }
)
# A time the wall clock gave during this update is at most this old. Anything older
# that is not a fixture's time is neither, and is refused rather than guessed at.
_UPDATE_WINDOW = timedelta(hours=6)
_CLOCK_SKEW = timedelta(minutes=5)


class UnexpectedTime(ValueError):
    """A time where a wall-clock time goes that is neither a fixture's nor this run's."""


FIXUPS: list[tuple[str, str]] = [
    (r"Usage: metab \[OPTIONS\] \[ROOT\]", "Usage: metab [OPTIONS] [ROOT_ARG]"),
    # A served mirror's origin is a file:// address of the sandbox. Its scheme is part
    # of what the status answered and stays; the sandbox rule would take it with the path.
    (r'(file://)[^\s"]*/tryscript-[A-Za-z0-9]+', r"\1[CWD]"),
    # The application home in the location a served mirror's status reports, which is
    # the sandbox's `home`. Its own pattern, ahead of the sandbox rule: what follows it
    # is the layout under the home, which stays literal.
    (
        r'("location": ")[^\s"]*/tryscript-[A-Za-z0-9]+/home(/cache/repository-stores/)',
        r"\1[APP_HOME]\2",
    ),
    # Not \S*: the sandbox path is often quoted in a JSON envelope, and a
    # non-space run swallows the opening quote along with the path.
    (r'[^\s"]*/tryscript-[A-Za-z0-9]+', "[CWD]"),
    # The key of the store in that location, when the mirror's origin is a file://
    # address of the sandbox: the key is derived from the address, so no fixture can
    # pin it. A hosted origin's key is the same on every machine and stays literal.
    (
        r'("origin": "file://\[CWD\][^"\n]*",\n\s*"location": "[^"\n]*/cache/repository-stores/)'
        r'[0-9a-f]{64}(/repository\.git")',
        r"\1[STORE_KEY]\2",
    ),
    (r"/\S*/builtin_plugins", "[BUILTIN]"),
    # The trailing group is the build annotation a checkout adds; see
    # metabrowser.build_version. It varies per commit, so it elides with the
    # version rather than beside it.
    (r"^metab \d+\S*( \([^)]*\))?$", "metab [VERSION]"),
    # The icon sprite KPress inlines ahead of a rendered document: one hidden <svg>
    # of symbols, the same for every document and replaced wholesale by a KPress
    # upgrade. Only its contents are elided. The <article> after it is the render of
    # the document under test and stays literal, which is what shows a POSTed
    # `source_text` reached the renderer.
    (
        r'^(  "html": "<svg xmlns=\\"http://www\.w3\.org/2000/svg\\" style=\\"display: none\\">)'
        r".*?(</svg>\\n<article )",
        r"\1[..]\2",
    ),
    # The logger's time of day on the diagnostic line the pending-tally route writes
    # to stderr. The rest of the line is the client's report and the server's
    # snapshot, which stay literal apart from the change-batch counter below.
    (
        r"^\d\d:\d\d:\d\d( metabrowser\.events_route \| pending folder tallies diagnostic )",
        r"[CLOCK]\1",
    ),
    (r'(pending folder tallies diagnostic .*"version":)\d+', r"\1[COUNT]"),
    # Host facts, not behavior: the filesystem type the served root sits on
    # (apfs here, ext4 on CI) and the watch backend it made available. These
    # were elided by hand once and silently re-pinned by the next
    # `golden-update`, which is the failure this rule exists to stop.
    # Everything around them stays pinned, `mode` included, which is the part
    # a regression would change.
    # The whole watcher trio, not just the host fact in it. A backend is
    # selected and started asynchronously, so `mode` resolves from `auto`,
    # `state` runs from `starting`, and each `metab` invocation in a transcript
    # is its own process with its own startup race -- one test in a file can
    # catch the settled values while the next one does not. Waiting for the
    # index does not settle the watcher, which starts after it.
    #
    # Watcher behaviour is covered by `tests/test_browser_watch_backends.py`,
    # where it can be driven rather than raced.
    (r'"reason": "fs=[^"]*"', '"reason": "[..]"'),
    (r'"reason": "inventory-[^"]*"', '"reason": "[..]"'),
    (
        r'"mode": "[a-z]+",(\n\s+"reason": "\[\.\.\]",\n\s+"state": )"[a-z]+"',
        r'"mode": "[..]",\1"[..]"',
    ),
    (r'"watch_mode": "[a-z]+"', '"watch_mode": "[..]"'),
    (r'"watch_state": "[a-z]+"', '"watch_state": "[..]"'),
    (r'"watch_reason": "[^"]*"', '"watch_reason": "[..]"'),
    # The provider's change-batch counter at the moment the diagnostic ran. It
    # is worth reporting and not worth pinning: no reader depends on the count,
    # and a provider that batches differently would fail the transcript for a
    # difference that is not a defect. Anchored to the line above so the schema
    # versions elsewhere in these goldens keep their exact values.
    (
        r'(^    "contract": "inventory-provider-v1",\n    "version": )\d+',
        r"\1[COUNT]",
    ),
    # The asset manifest of the POSTed render: the same manifest the GET case above it
    # pins line by line, so the second copy is elided rather than pinned twice.
    (
        r"(^\$ metab shellroot --api /api/kpress/render --data shellroot/render\.json\n"
        r'(?:.*\n)*?  "assets": \{\n)(?:.*\n)*?(  \},\n  "diagnostics": )',
        r"\1...\n\2",
    ),
]

# Where a transcript shows a time taken from the wall clock, each with the lines that
# place it. The time itself is the last group.
WALL_CLOCK_SITES: list[str] = [
    # When a one-shot refresh found another process refreshing the store: this
    # process's own clock. The fetch times beside it are the fixture's.
    rf'(^\s+"outcome": "refreshing_elsewhere",\n\s+"at": )"({_TIME})"',
    # When a pull request's refresh failed in the transcript itself. A refresh the
    # fixture ran keeps the fixture's time.
    rf'(^\s+"reset_at": null,\n\s+"at": )"({_TIME})"',
    # When a fixture fetched its mirror while it was being built, and did not then set
    # the recorded fetch to a fixed time: the fixture process's clock.
    rf'(^\s+"last_fetch_at": )"({_TIME})"',
    rf'(^\s+"operation": "acquire",\n\s+"outcome": "succeeded",\n\s+"at": )"({_TIME})"',
]


def _wall_clock(match: re.Match[str], now: datetime) -> str:
    """Keep a fixture's time, pattern this run's, and refuse anything else.

    A time is this run's when it is within the update window before *now*. A time that
    is neither is a value some fixture pins without this module knowing, or a wall
    clock left in a transcript by an earlier run. Patterning the first would hide a
    pinned value, and keeping the second would commit a time that fails tomorrow, so
    neither is done silently.
    """

    stamp = match.group(2)
    if stamp in FIXTURE_TIMES:
        return match.group(0)
    moment = datetime.strptime(stamp, _TIME_FORMAT).replace(tzinfo=UTC)
    if now - _UPDATE_WINDOW <= moment <= now + _CLOCK_SKEW:
        return f'{match.group(1)}"[TIMESTAMP]"'
    raise UnexpectedTime(
        f"{stamp} is neither a fixture's fixed time ({', '.join(sorted(FIXTURE_TIMES))}) nor "
        "a time from this update; if a fixture pins it, add that fixture's constant to "
        "FIXTURE_TIMES, and if it is an old wall-clock time, rerun `make golden-update`"
    )


def fix_text(text: str, *, now: datetime | None = None) -> str:
    """*text* with every elision pattern restored and trailing whitespace stripped.

    *now* is when the update ran, which decides what counts as its wall clock.
    """

    moment = datetime.now(UTC) if now is None else now
    # The frontmatter defines the elision patterns themselves; only the body after
    # the closing "---" holds captured output to patch.
    frontmatter, separator, body = text.partition("\n---\n")
    for pattern, replacement in FIXUPS:
        body = re.sub(pattern, replacement, body, flags=re.MULTILINE)
    for site in WALL_CLOCK_SITES:
        body = re.sub(site, lambda found: _wall_clock(found, moment), body, flags=re.MULTILINE)
    body = re.sub(r"[ \t]+$", "", body, flags=re.MULTILINE)
    return frontmatter + separator + body


def main(golden_dir: Path = GOLDEN_DIR) -> int:
    status = 0
    for path in sorted(golden_dir.glob("*.tryscript.md")):
        text = path.read_text(encoding="utf-8")
        try:
            fixed = fix_text(text)
        except UnexpectedTime as error:
            print(f"{path.name}: {error}", file=sys.stderr)
            status = 1
            continue
        if fixed != text:
            path.write_text(fixed, encoding="utf-8")
            print(f"patterns restored: {path.name}")
    return status


if __name__ == "__main__":
    sys.exit(main())
