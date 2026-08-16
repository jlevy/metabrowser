"""Contract checks for HTTP cache validators.

Every conditional response in the package derives its validator from
``metabrowser.http_caching``. That is the whole point of the module: a rule
about what belongs in an ETag is only worth stating if it cannot be restated
differently three files away.

It was, four times over. The shell, the binary sidekick, the structured plugin,
and the plugin static-asset route each built their own tag from a file's mtime
hash — one of them under a comment claiming it matched the others while using a
different prefix. When the body of a response stopped being a function of the
file alone, fixing that in one of them fixed one of them: small binaries moved
from the text fallback to the Bytes view, and browsers holding a cached
rendering kept replaying a field of U+FFFD, because the file's mtime had not
changed and the server answered 304.
"""

from __future__ import annotations

import re
from pathlib import Path

from starlette.datastructures import Headers

from metabrowser.http_caching import (
    BUILD_TAG,
    build_scoped_etag,
    etag_headers,
    matches_if_none_match,
)

SRC = Path(__file__).resolve().parents[1] / "src" / "metabrowser"
THIS_MODULE = SRC / "http_caching.py"

# An f-string whose whole value is a quoted interpolation — `f'"{x}"'` — is an
# ETag literal by shape. Matching on shape rather than on the word "etag"
# matters: the first version of this check only inspected lines mentioning
# etag, and a helper named `_sneaky_etag` whose body was just the literal
# slipped straight through it.
HANDROLLED_ETAG_RE = re.compile(r"""f(['"])\\?"\{[^{}]*\}\\?"\1""")


class _FakeRequest:
    def __init__(self, if_none_match: str | None = None) -> None:
        raw = [(b"if-none-match", if_none_match.encode())] if if_none_match else []
        self.headers = Headers(raw=raw)


def test_tag_is_quoted_once_and_carries_the_build() -> None:
    tag = build_scoped_etag("abc123")
    assert tag == f'"{BUILD_TAG}-abc123"'
    # Quoted per RFC 7232, and exactly once — a version string with a quote in
    # it must not be able to break the header.
    assert tag.count('"') == 2


def test_the_same_content_under_a_different_build_is_a_different_tag() -> None:
    """The property the whole module exists for."""
    tag = build_scoped_etag("unchanged-file")
    assert BUILD_TAG in tag
    stale = f'"{"0" * len(BUILD_TAG)}-unchanged-file"'
    assert stale != tag


def test_headers_require_revalidation() -> None:
    """`no-cache` means "revalidate", which is what makes the tag load-bearing.

    Without it a client may serve its copy without asking, and no validator —
    however well scoped — gets consulted at all.
    """
    headers = etag_headers('"x"')
    assert headers["ETag"] == '"x"'
    assert headers["Cache-Control"] == "no-cache"


def test_conditional_match_is_read_case_insensitively() -> None:
    tag = build_scoped_etag("abc")
    assert matches_if_none_match(_FakeRequest(tag), tag)  # pyright: ignore[reportArgumentType]
    assert not matches_if_none_match(_FakeRequest('"other"'), tag)  # pyright: ignore[reportArgumentType]
    assert not matches_if_none_match(_FakeRequest(None), tag)  # pyright: ignore[reportArgumentType]


def test_no_module_builds_its_own_validator() -> None:
    """One definition of the rule, so fixing it once fixes it everywhere."""
    offenders: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        if path == THIS_MODULE:
            continue
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if HANDROLLED_ETAG_RE.search(line):
                rel = path.relative_to(SRC.parent.parent)
                offenders.append(f"{rel}:{number}: {line.strip()}")
    assert not offenders, (
        "build validators with metabrowser.http_caching.build_scoped_etag:\n  "
        + "\n  ".join(offenders)
    )


def test_conditional_routes_read_the_header_through_the_helper() -> None:
    """One reader too, so call sites cannot disagree on the header spelling."""
    offenders: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        if path == THIS_MODULE:
            continue
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if re.search(r"""headers\.get\(\s*["']if-none-match""", line, re.IGNORECASE):
                rel = path.relative_to(SRC.parent.parent)
                offenders.append(f"{rel}:{number}: {line.strip()}")
    assert not offenders, (
        "compare conditionals with metabrowser.http_caching.matches_if_none_match:\n  "
        + "\n  ".join(offenders)
    )


def test_a_validator_identifies_the_response_not_just_the_file() -> None:
    """Distinct windows of one file must not share a tag.

    The binary chunk route keyed its tag on the file alone, so every byte
    window of a file carried the same validator. That was inert only because
    nothing checked it; a helper that makes checking easy is exactly what turns
    a latent trap into served-wrong-bytes.
    """
    file_identity = "some_file_1234_abcdef"
    first = build_scoped_etag(f"{file_identity}-0-65536")
    second = build_scoped_etag(f"{file_identity}-65536-65536")
    assert first != second
    # Same window, same tag — the caching still works.
    assert first == build_scoped_etag(f"{file_identity}-0-65536")
