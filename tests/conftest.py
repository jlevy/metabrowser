"""Shared Metabrowser test fixtures."""

from __future__ import annotations

import os
from collections.abc import Generator
from html.parser import HTMLParser
from typing import NamedTuple
from urllib.parse import urljoin

import pytest

from metabrowser.git.process import _REPO_PINNING_GIT_VARS

# Test discovery imports the server from several module scopes. Never let an
# operator's shell or dotenv configuration alter collection or load external plugins.
os.environ["METABROWSER_PLUGINS_DIRS"] = ""
for _capability_env in ("METAB_UNTRUSTED", "METAB_ACTIVE_CONTENT", "METAB_ALLOW_EDITS"):
    os.environ.pop(_capability_env, None)

# The pre-push gate runs this suite inside a githook, and from a linked worktree git
# exports GIT_DIR there. It outranks the working directory and `git -C`, so a fixture
# that spawns git with the inherited environment acts on the developer's repository:
# its `git init` writes core.bare = true into the configuration every worktree
# shares. Scrub once, here, before any test module is imported, so a fixture that
# forgets to scrub its own calls cannot do that. A test that needs a poisoned GIT_DIR
# sets one itself. tests/test_git_hook_environment.py pins this.
for _name in _REPO_PINNING_GIT_VARS:
    os.environ.pop(_name, None)


# No test reaches the gh a developer is signed in to. A real ``gh auth git-credential``,
# ``gh auth status``, or ``gh api`` call reads the keychain and can print or send a
# token, so every test runs with a failing stand-in first on PATH, which each call
# looks gh up on. The stand-in logs each call, with the test that made it, to
# GH_GUARD_LOG, and the terminal summary reports them. A test that needs gh installs
# its own fake later, which comes first; only the opt-in live smoke test, marked
# ``live_github`` and run with METABROWSER_LIVE_GITHUB=1, sees the real one.
_FAKE_GH = """#!/bin/sh
printf '%s\\t%s\\n' "${PYTEST_CURRENT_TEST:-unknown}" "$*" >> "$METABROWSER_TEST_GH_LOG"
echo "gh is not available to tests; install a fake gh for this test" >&2
exit 1
"""
GH_GUARD_LOG_ENV = "METABROWSER_TEST_GH_LOG"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "live_github: an opt-in test that talks to github.com with the real gh"
    )


@pytest.fixture(scope="session")
def _gh_guard_bin(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, str]:  # pyright: ignore[reportUnusedFunction]
    directory = tmp_path_factory.mktemp("no-real-gh")
    gh = directory / "gh"
    gh.write_text(_FAKE_GH, encoding="utf-8")
    gh.chmod(0o755)
    return str(directory), str(directory / "calls.log")


@pytest.fixture(autouse=True)
def _no_real_gh(  # pyright: ignore[reportUnusedFunction]
    request: pytest.FixtureRequest, _gh_guard_bin: tuple[str, str]
) -> Generator[None, None, None]:
    """Put the failing stand-in gh first on PATH, except for the opt-in live smoke test.

    Its own ``MonkeyPatch``, not the ``monkeypatch`` fixture: requesting that here would
    set it up before every module's own autouse fixtures, so a test's patches would be
    undone only after those fixtures' teardown had run against them.
    """

    live = request.node.get_closest_marker("live_github") is not None
    if live and os.environ.get("METABROWSER_LIVE_GITHUB") == "1":
        yield
        return
    directory, log = _gh_guard_bin
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("PATH", directory + os.pathsep + os.environ.get("PATH", ""))
        patch.setenv(GH_GUARD_LOG_ENV, log)
        yield


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    """Say which tests would have run gh, so a new one is noticed."""

    basetemp = terminalreporter.config._tmp_path_factory.getbasetemp()  # pyright: ignore[reportAttributeAccessIssue]
    # pytest also links ``no-real-ghcurrent`` to the numbered directory; read each once.
    logs = {log.resolve() for log in basetemp.glob("no-real-gh*/calls.log")}
    calls = [line for log in sorted(logs) for line in log.read_text(encoding="utf-8").splitlines()]
    if calls:
        tests = sorted({line.split("\t", 1)[0].rsplit(" ", 1)[0] for line in calls})
        terminalreporter.write_line(
            f"gh guard: {len(calls)} gh call(s) reached the failing stand-in, "
            f"from {len(tests)} test(s): " + ", ".join(tests)
        )


@pytest.fixture(autouse=True)
def _reset_capabilities() -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """Keep the process capability block isolated between tests."""
    from metabrowser.capabilities import DEFAULT_CAPABILITIES, set_capabilities

    set_capabilities(DEFAULT_CAPABILITIES)
    yield
    set_capabilities(DEFAULT_CAPABILITIES)


@pytest.fixture(autouse=True)
def _reset_served_mirror() -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """Never let a mirror one test served reach the next test's application lifespan."""
    from metabrowser.mirror_refresh import serve_mirror

    serve_mirror(None)
    yield
    serve_mirror(None)


@pytest.fixture(autouse=True)
def _reset_browser_response_caches() -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """Keep route response caches isolated between tests."""
    yield
    try:
        from metabrowser.server import reset_response_caches_for_tests

        reset_response_caches_for_tests()
    except Exception:
        # Defensive: never let cleanup failure mask a test failure.
        pass


class DocumentReference(NamedTuple):
    """One URL a browser would fetch or follow from a served document."""

    tag: str
    attribute: str
    value: str
    resolved: str


# The attributes whose value is a URL the browser resolves against the
# document's own address. Enough for the static pages these tests serve;
# a fixture that needs another element adds it here.
_REFERENCE_ATTRIBUTES: dict[str, str] = {
    "a": "href",
    "embed": "src",
    "frame": "src",
    "iframe": "src",
    "img": "src",
    "link": "href",
    "script": "src",
    "source": "src",
}


class _ReferenceCollector(HTMLParser):
    def __init__(self, document_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self._document_url = document_url
        self.references: list[DocumentReference] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if name == "base":
            # Resolution below is relative to the document URL. A document
            # that moves its base would make every answer here wrong, so
            # refuse rather than report a plausible lie.
            assert not any(key.lower() == "href" for key, _ in attrs), (
                "document_references does not honour <base href>"
            )
            return
        attribute = _REFERENCE_ATTRIBUTES.get(name)
        if attribute is None:
            return
        for key, value in attrs:
            if key.lower() == attribute and value:
                self.references.append(
                    DocumentReference(
                        tag=name,
                        attribute=attribute,
                        value=value,
                        resolved=urljoin(self._document_url, value),
                    )
                )


def document_references(document: str, document_url: str) -> list[DocumentReference]:
    """Resolve the URLs a browser would request from a served document.

    ``urljoin`` performs the same RFC 3986 resolution a browser applies to
    a relative reference against the document's own URL, so this answers
    "where would the next request go" without running a browser. It says
    nothing about whether a browser issues those requests or what it does
    with the bytes; only the address is derived here.
    """

    collector = _ReferenceCollector(document_url)
    collector.feed(document)
    collector.close()
    return collector.references


class SyntheticIndexWriter:
    """Dict-like façade for building a Python provider handle in tests.

    Several rollup tests assemble an index in memory instead of on disk. The
    index keeps derived structures alongside ``_entries`` (the parent/child
    grouping and the subtree-aggregate memo), so assigning into ``_entries``
    directly would leave those out of sync and produce empty rollups. Writing
    through the real store path keeps a synthetic index behaving like a
    walked one.
    """

    __slots__ = ("_index",)

    def __init__(self, index: object) -> None:
        self._index = index

    def __setitem__(self, path: str, entry: object) -> None:
        assert getattr(entry, "path", None) == path, "entry.path must match its key"
        self._index._replace_index_entry(entry)  # type: ignore[attr-defined]
