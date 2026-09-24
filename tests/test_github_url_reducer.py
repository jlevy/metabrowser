"""The GitHub URL reducer: every accepted shape, every refusal, canonical identity."""

from __future__ import annotations

import pytest

from metabrowser.builtin_plugins.github import urls
from metabrowser.builtin_plugins.github.urls import GithubUrlReducer, parse_repository_url
from metabrowser.cache.urls import (
    GitSource,
    LineSelection,
    RejectedRoot,
    RepositorySelection,
    classify_root_argument,
)

CANONICAL = "https://github.com/octo/demo"
_REDUCERS = (GithubUrlReducer(),)


def _source(value: str) -> GitSource:
    classified = classify_root_argument(value, reducers=_REDUCERS)
    assert isinstance(classified, GitSource), classified
    assert classified.transport == "https"
    return classified


def _refused(value: str) -> RejectedRoot:
    classified = classify_root_argument(value, reducers=_REDUCERS)
    assert isinstance(classified, RejectedRoot), classified
    return classified


@pytest.mark.parametrize(
    "value",
    [
        "https://github.com/octo/demo",
        "https://github.com/Octo/Demo",
        "https://github.com/octo/demo/",
        "https://github.com/octo/demo.git",
        "https://github.com/octo/demo.GIT/",
        "https://www.github.com/octo/demo",
        "HTTPS://GitHub.COM/octo/demo",
        "https://github.com:443/octo/demo",
        "https://github.com/octo/demo?tab=readme-ov-file",
        "https://github.com/octo/demo#readme",
        "git@github.com:octo/demo.git",
        "git@github.com:Octo/Demo",
        "ssh://git@github.com/octo/demo.git",
        "ssh://git@github.com:22/octo/demo",
        "ssh://git@www.github.com/octo/demo.git",
        "git@www.github.com:octo/demo.git",
    ],
)
def test_repository_spellings_share_one_canonical_source(value: str) -> None:
    source = _source(value)
    assert source.normalized == CANONICAL
    assert source.selection == RepositorySelection()
    # The selection is not part of identity: every spelling is one mirror.
    assert source == GitSource(transport="https", form="url", normalized=CANONICAL)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "https://github.com/octo/demo/tree/main",
            RepositorySelection(kind="tree", ref_and_path=(b"main",)),
        ),
        (
            "https://github.com/octo/demo/tree/release/v1/docs/",
            RepositorySelection(kind="tree", ref_and_path=(b"release", b"v1", b"docs")),
        ),
        (
            "https://github.com/octo/demo/blob/main/README.md",
            RepositorySelection(kind="blob", ref_and_path=(b"main", b"README.md")),
        ),
        (
            "https://github.com/octo/demo/blob/main/README.md#L10",
            RepositorySelection(
                kind="blob",
                ref_and_path=(b"main", b"README.md"),
                lines=LineSelection(start=10, end=10),
            ),
        ),
        (
            "https://github.com/octo/demo/blob/main/README.md#L10-L20",
            RepositorySelection(
                kind="blob",
                ref_and_path=(b"main", b"README.md"),
                lines=LineSelection(start=10, end=20),
            ),
        ),
        (
            "https://github.com/octo/demo/blob/main/README.md#L10C5-L20C8",
            RepositorySelection(
                kind="blob",
                ref_and_path=(b"main", b"README.md"),
                lines=LineSelection(start=10, end=20, start_column=5, end_column=8),
            ),
        ),
        (
            "https://github.com/octo/demo/blob/main/README.md#L10C8-L10C5",
            RepositorySelection(
                kind="blob",
                ref_and_path=(b"main", b"README.md"),
                lines=LineSelection(start=10, end=10, start_column=5, end_column=8),
            ),
        ),
        (
            "https://github.com/octo/demo/blob/main/README.md#L20-L10",
            RepositorySelection(
                kind="blob",
                ref_and_path=(b"main", b"README.md"),
                lines=LineSelection(start=10, end=20),
            ),
        ),
        (
            "https://github.com/octo/demo/blob/main/README.md?plain=1&utm_source=x#L3",
            RepositorySelection(
                kind="blob",
                ref_and_path=(b"main", b"README.md"),
                lines=LineSelection(start=3, end=3),
                plain=True,
            ),
        ),
        (
            "https://github.com/octo/demo/blob/main/README.md#readme-section",
            RepositorySelection(kind="blob", ref_and_path=(b"main", b"README.md")),
        ),
        (
            "https://github.com/octo/demo/blob/main/My%20Notes/%E6%97%A5%E6%9C%AC.md",
            RepositorySelection(
                kind="blob", ref_and_path=(b"main", b"My Notes", "日本.md".encode())
            ),
        ),
        (
            "https://github.com/octo/demo/commit/ABCDEF0123",
            RepositorySelection(kind="commit", commit="abcdef0123"),
        ),
        (
            "https://github.com/octo/demo/pull/12",
            RepositorySelection(kind="pull_request", pull_request=12),
        ),
        (
            "https://github.com/octo/demo/pull/12/files",
            RepositorySelection(kind="pull_request", pull_request=12),
        ),
        (
            "https://github.com/octo/demo/pull/12/commits",
            RepositorySelection(kind="pull_request", pull_request=12),
        ),
        (
            "https://github.com/octo/demo/pull/12/commits/abcdef0",
            RepositorySelection(kind="commit", commit="abcdef0", pull_request=12),
        ),
        (
            "https://raw.githubusercontent.com/octo/demo/main/docs/a.md",
            RepositorySelection(kind="blob", ref_and_path=(b"main", b"docs", b"a.md")),
        ),
        (
            "https://raw.githubusercontent.com/Octo/Demo/refs/heads/main/a.md",
            RepositorySelection(kind="blob", ref_and_path=(b"refs", b"heads", b"main", b"a.md")),
        ),
    ],
)
def test_web_url_shapes_carry_their_selection(value: str, expected: RepositorySelection) -> None:
    source = _source(value)
    assert source.normalized == CANONICAL
    assert source.selection == expected


@pytest.mark.parametrize(
    ("value", "reason", "detail"),
    [
        ("http://github.com/octo/demo", "insecure_http", f"use {CANONICAL}"),
        ("http://github.com/", "insecure_http", "https://github.com/<owner>/<repository>"),
        ("https://github.com/", "unsupported_github_url", "github.com itself"),
        ("https://github.com/octo", "unsupported_github_url", "github.com/octo is an account"),
        ("https://github.com/settings/profile", "reserved_owner", "github.com/settings"),
        ("https://github.com/orgs/octo/repositories", "reserved_owner", "github.com/orgs"),
        ("https://github.com/octo/demo/issues/5", "unsupported_github_url", "issues pages"),
        ("https://github.com/octo/demo/actions", "unsupported_github_url", "actions pages"),
        ("https://github.com/octo/demo/zzz-token", "unsupported_github_url", "this GitHub page"),
        ("https://github.com/octo/demo/tree", "unsupported_github_url", "names a ref"),
        ("https://github.com/octo/demo/blob/main", "unsupported_github_url", "a ref and a file"),
        ("https://github.com/octo/demo/commit/xyz", "invalid_commit_id", CANONICAL),
        ("https://github.com/octo/demo/commit/abc", "invalid_commit_id", CANONICAL),
        ("https://github.com/octo/demo/commit/abcdef", "invalid_commit_id", "7 to 64"),
        ("https://github.com/octo/demo/commit/abcdef0/x", "unsupported_github_url", CANONICAL),
        ("https://github.com/octo/demo/pull/0", "invalid_pull_request", CANONICAL),
        ("https://github.com/octo/demo/pull/x", "invalid_pull_request", CANONICAL),
        ("https://github.com/octo/demo/pull/12/checks", "unsupported_github_url", CANONICAL),
        ("https://raw.githubusercontent.com/octo/demo/main", "unsupported_github_url", "raw URL"),
        ("https://github.com/o_o/demo", "invalid_owner", "owner"),
        ("https://github.com/octo/de$mo", "invalid_repository", "repository name"),
        ("https://github.com/octo/..", "invalid_repository", "repository name"),
        ("https://github.com:8443/octo/demo", "unsupported_port", CANONICAL),
        ("git@github.com:octo/demo/extra", "unsupported_github_url", CANONICAL),
        ("deploy@github.com:octo/demo.git", "invalid_user", "user git"),
        ("https://github.com/octo//demo", "empty_path_segment", "empty segment"),
        ("https://github.com/octo/demo/tree/main/%2e%2e/x", "dot_segment", "'..'"),
        ("https://github.com/octo/demo/tree/main%2Fx", "encoded_delimiter", "separator"),
        ("https://github.com/octo/demo/tree/main/%0A", "control_or_whitespace", "control"),
        ("https://github.com/octo/demo/tree/main/%zz", "invalid_percent_encoding", "%25"),
    ],
)
def test_other_shapes_are_refused_with_a_typed_reason(value: str, reason: str, detail: str) -> None:
    refused = _refused(value)
    assert refused.reason == reason
    assert refused.detail is not None and detail in refused.detail


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("https://ghp_secret@github.com/octo/demo", "credentials_in_url"),
        ("https://user:ghp_secret@github.com/octo/demo", "credentials_in_url"),
        (
            "https://raw.githubusercontent.com/octo/demo/main/a?token=ghp_secret#L1\tx",
            "control_or_whitespace",
        ),
        (
            "https://github.com/octo/demo/blob/main/a.md?token=ghp_secret\u202e",
            "non_ascii",
        ),
        ("ssh://git:ghp_secret@github.com/octo/demo.git", "credentials_in_url"),
        ("https://github.com/octo/demo\n", "control_or_whitespace"),
        ("https://github.com:44 3/octo/demo", "control_or_whitespace"),
        ("https://github.com/octo\\demo", "backslash"),
        # SSH addresses are not browser URLs: a raw space or letter outside ASCII stays
        # refused, as the generic grammar refuses it.
        ("git@github.com:octo/my demo.git", "control_or_whitespace"),
        ("ssh://git@github.com/octo/démo.git", "non_ascii"),
    ],
)
def test_the_generic_checks_run_before_the_reducer_parses(value: str, reason: str) -> None:
    refused = _refused(value)
    assert refused.reason == reason
    # A refusal never repeats the argument, so a token in it stays out of the terminal.
    assert "ghp_secret" not in (refused.detail or "")
    assert "token" not in (refused.detail or "")


@pytest.mark.parametrize(
    ("raw", "encoded"),
    [
        (
            "https://github.com/octo/demo/blob/main/docs/雪.md#L1",
            "https://github.com/octo/demo/blob/main/docs/%E9%9B%AA.md#L1",
        ),
        (
            "https://github.com/octo/demo/blob/main/space name.md",
            "https://github.com/octo/demo/blob/main/space%20name.md",
        ),
        (
            "https://github.com/octo/demo/tree/雪/a b",
            "https://github.com/octo/demo/tree/%E9%9B%AA/a%20b",
        ),
        (
            "https://raw.githubusercontent.com/octo/demo/main/docs/résumé notes.md",
            "https://raw.githubusercontent.com/octo/demo/main/docs/r%C3%A9sum%C3%A9%20notes.md",
        ),
        (
            "https://github.com/octo/demo/blob/main/😀.md?plain=1&q=a b#L2-L3",
            "https://github.com/octo/demo/blob/main/%F0%9F%98%80.md?plain=1&q=a%20b#L2-L3",
        ),
        # A combining mark is drawn on the letter before it, so a reader sees it.
        (
            f"https://github.com/octo/demo/blob/main/cafe{chr(0x301)}.md",
            "https://github.com/octo/demo/blob/main/cafe%CC%81.md",
        ),
    ],
)
def test_a_raw_web_url_is_read_as_a_browser_sends_it(raw: str, encoded: str) -> None:
    pasted, sent = _source(raw), _source(encoded)
    assert pasted.normalized == sent.normalized == CANONICAL
    assert pasted.selection == sent.selection
    assert pasted.selection is not None and pasted.selection.kind != "repository"


@pytest.mark.parametrize(
    ("point", "reason", "kind"),
    [
        # Whitespace other than a space.
        (0x00A0, "control_or_whitespace", "a whitespace character"),
        (0x3000, "control_or_whitespace", "a whitespace character"),
        # Format characters: bidirectional controls, joiners, and one that is not
        # default-ignorable (ARABIC NUMBER SIGN).
        (0x202E, "non_ascii", "an invisible character"),
        (0x200D, "non_ascii", "an invisible character"),
        (0x0600, "non_ascii", "an invisible character"),
        # Default-ignorable characters outside Cf: a Hangul filler, the combining grapheme
        # joiner, a variation selector, and a tag-block code point.
        (0x3164, "non_ascii", "an invisible character"),
        (0x034F, "non_ascii", "an invisible character"),
        (0xFE0F, "non_ascii", "an invisible character"),
        (0xE0100, "non_ascii", "an invisible character"),
        (0x2800, "non_ascii", "an invisible character"),
        # Unassigned (U+FFFF is a noncharacter) and private use.
        (0x0378, "non_ascii", "an unassigned character"),
        (0xFFFF, "non_ascii", "an unassigned character"),
        (0xE000, "non_ascii", "a private-use character"),
        (0x10FFFD, "non_ascii", "a private-use character"),
    ],
)
def test_a_character_no_one_can_see_is_refused_with_the_spelling_to_use(
    point: int, reason: str, kind: str
) -> None:
    # README<U+3164>.md reads as README.md.
    refused = _refused(f"https://github.com/octo/demo/blob/main/README{chr(point)}.md")
    encoded = "".join(f"%{byte:02X}" for byte in chr(point).encode())
    assert (refused.reason, refused.detail) == (
        reason,
        f"the URL contains U+{point:04X}, {kind}; if it belongs in the address, "
        f"write it as {encoded}",
    )
    # The spelling it names opens that name.
    written = _source(f"https://github.com/octo/demo/blob/main/README{encoded}.md").selection
    assert written is not None
    assert written.ref_and_path == (b"main", f"README{chr(point)}.md".encode())


@pytest.mark.parametrize(
    ("value", "reason", "detail"),
    [
        (
            f"https://github.com/octo/demo/blob/main/a{chr(0x9B)}b.md",
            "non_ascii",
            "the URL contains U+009B, a control character",
        ),
        (
            f"https://github.com/octo/demo/blob/main/a{chr(0x85)}b.md",
            "control_or_whitespace",
            "the URL contains U+0085, a control character",
        ),
        (
            f"https://github.com/octo/demo/blob/main/a{chr(0x09)}b.md",
            "control_or_whitespace",
            "the URL contains U+0009, a control character",
        ),
        (
            f"https://github.com/octo/demo/blob/main/a{chr(0x1B)}[2Jb.md",
            "control_or_whitespace",
            "the URL contains U+001B, a control character",
        ),
        # Bytes that are not UTF-8 reach Python as lone surrogates.
        (
            f"https://github.com/octo/demo/blob/main/a{chr(0xDCE9)}b.md",
            "non_ascii",
            "the URL is not valid UTF-8",
        ),
        (
            "https://github.com/octo/demo/blob/main/a.md ",
            "control_or_whitespace",
            "the URL ends with a space; remove it",
        ),
        (
            "https://github.com/octo/démo",
            "invalid_repository",
            "the repository name is not a GitHub repository name",
        ),
        # Before the path, and anywhere in an SSH address, nothing is percent-encoded.
        (
            "https://github.com:44 3/octo/demo",
            "control_or_whitespace",
            "the URL contains U+0020, a space",
        ),
        (
            "git@github.com:octo/my demo.git",
            "control_or_whitespace",
            "the URL contains U+0020, a space",
        ),
        (
            "ssh://git@github.com/octo/démo.git",
            "non_ascii",
            "the URL contains U+00E9, a character outside ASCII",
        ),
        (
            f"git@github.com:octo/de{chr(0xA0)}mo.git",
            "control_or_whitespace",
            "the URL contains U+00A0, a whitespace character",
        ),
        # A % that starts no escape: a browser leaves it for the server, so it is
        # ambiguous; a literal % is %25.
        (
            "https://github.com/octo/demo/blob/main/100%.md",
            "invalid_percent_encoding",
            "the URL has a % not followed by two hexadecimal digits; write a literal % as %25",
        ),
        (
            "https://github.com/octo/demo/blob/main/a%zz.md",
            "invalid_percent_encoding",
            "the URL has a % not followed by two hexadecimal digits; write a literal % as %25",
        ),
        (
            "https://github.com/octo/demo/tree/main/50%",
            "invalid_percent_encoding",
            "the URL has a % not followed by two hexadecimal digits; write a literal % as %25",
        ),
    ],
)
def test_raw_characters_a_browser_would_not_show_are_refused_by_code_point(
    value: str, reason: str, detail: str
) -> None:
    refused = _refused(value)
    assert (refused.reason, refused.detail) == (reason, detail)


def test_a_literal_percent_written_as_25_opens() -> None:
    selection = _source("https://github.com/octo/demo/blob/main/100%25.md").selection
    assert selection is not None and selection.ref_and_path == (b"main", b"100%.md")


def test_the_default_ignorable_table_is_sorted_and_disjoint() -> None:
    ranges = urls._DEFAULT_IGNORABLE
    assert all(low <= high for low, high in ranges)
    assert all(ranges[i][1] < ranges[i + 1][0] for i in range(len(ranges) - 1))
    # Unicode 17.0 counts 4,174 default-ignorable code points.
    assert sum(high - low + 1 for low, high in ranges) == 4174


def test_query_parameters_are_dropped_and_never_echoed() -> None:
    source = _source("https://github.com/octo/demo/blob/main/a.md?token=ghp_secret&plain=1")
    assert source.normalized == CANONICAL
    assert "ghp_secret" not in repr(source)


@pytest.mark.parametrize(
    "value",
    [
        "https://gist.github.com/octo/abc",
        "https://github.com.example.com/octo/demo",
        "https://example.com/octo/demo",
        "git://github.com/octo/demo",
        "file:///github.com/octo/demo",
        "/srv/github.com/octo/demo",
    ],
)
def test_other_hosts_and_transports_are_not_claimed(value: str) -> None:
    assert GithubUrlReducer().reduce(value) is None


def test_exactly_one_trailing_git_is_removed() -> None:
    assert _source("https://github.com/octo/demo.git.git").normalized == f"{CANONICAL}.git"
    assert _source("git@github.com:octo/demo.GIT").normalized == CANONICAL
    assert _refused("https://github.com/octo/.git").reason == "invalid_repository"


def test_raw_url_refusals_do_not_name_github_com() -> None:
    for value in (
        "https://raw.githubusercontent.com/settings/x/main/a.md",
        "https://raw.githubusercontent.com/settings",
        "https://raw.githubusercontent.com/octo",
    ):
        refused = _refused(value)
        assert "github.com/" not in (refused.detail or ""), value
    assert _refused("https://raw.githubusercontent.com/settings/x/main/a.md").reason == (
        "reserved_owner"
    )


def test_the_fragment_spelling_round_trips() -> None:
    assert LineSelection(start=10, end=10).fragment() == "L10"
    assert LineSelection(start=10, end=20).fragment() == "L10-L20"
    assert LineSelection(10, 20, start_column=5, end_column=8).fragment() == "L10C5-L20C8"


def test_parse_repository_url_reads_only_canonical_urls() -> None:
    assert parse_repository_url(CANONICAL) == ("octo", "demo")
    assert parse_repository_url(f"{CANONICAL}/tree/main") is None
    assert parse_repository_url("https://example.com/octo/demo") is None
