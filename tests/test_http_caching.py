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

import os
import re
from pathlib import Path

import pytest
from starlette.datastructures import Headers
from starlette.responses import Response

from metabrowser import http_caching
from metabrowser.http_caching import (
    BUILD_TAG,
    _newest_source_change,
    build_scoped_etag,
    etag_headers,
    matches_if_none_match,
    store_tag,
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
    assert re.fullmatch(rf'"{BUILD_TAG}-[0-9a-f]{{64}}"', tag)
    # The content identity cannot introduce a delimiter inside the quoted validator.
    assert tag.count('"') == 2


def test_the_same_content_under_a_different_build_is_a_different_tag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The property the whole module exists for."""
    tag = build_scoped_etag("unchanged-file")
    assert BUILD_TAG in tag
    other_build = "0" * len(BUILD_TAG)
    monkeypatch.setattr(http_caching, "BUILD_TAG", other_build)
    changed = build_scoped_etag("unchanged-file")
    assert changed.startswith(f'"{other_build}-')
    assert changed != tag


@pytest.mark.parametrize(
    "identity",
    ["rollup-/folder/雪", 'quoted-"identity"', "line\r\nbreak", "back\\slash", "\ud800", ""],
    ids=["unicode", "quote", "controls", "backslash", "surrogate", "empty"],
)
def test_arbitrary_content_identities_produce_valid_opaque_headers(identity: str) -> None:
    tag = build_scoped_etag(identity)
    assert tag == build_scoped_etag(identity)
    assert re.fullmatch(rf'"{BUILD_TAG}-[0-9a-f]{{64}}"', tag)
    assert tag.isascii()
    response = Response(headers=etag_headers(tag))
    assert response.headers["etag"] == tag
    assert response.raw_headers[0] == (b"etag", tag.encode("ascii"))


def test_encoding_preserves_distinct_identities_without_normalizing_them() -> None:
    identities = ["雪", "雨", "é", "e\u0301", "\ud800", "\ud801", "line\n", "line\r", ""]
    tags = [build_scoped_etag(identity) for identity in identities]
    assert len(set(tags)) == len(identities)


def test_a_store_tag_names_the_store_and_not_its_path(tmp_path: Path) -> None:
    """The token a page sends with every comparison address (review of #284, B1 and C2):
    different for two stores, moved by `info/attributes`, and never the path itself."""
    one = tmp_path / "one.git"
    two = tmp_path / "two.git"
    for store in (one, two):
        (store / "info").mkdir(parents=True)
    tag = store_tag(one)
    assert re.fullmatch(r"[0-9a-f]{16}", tag)
    assert tag != store_tag(two)
    assert tag == store_tag(one), "stable for the same store"
    assert "one" not in tag and str(tmp_path) not in tag
    (one / "info" / "attributes").write_text("*.py -diff\n")
    assert store_tag(one) != tag, "attributes Git reads whatever is isolated are an input"
    assert store_tag(tmp_path / "absent.git") != tag, "a store with no info directory has a tag"


def test_a_store_tag_is_read_once_and_follows_every_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The tag is asked for on every comparison request and every page serve (review of
    #284, D5), so the attributes file is read when its stat changes and not otherwise; and
    a file past the bound the digest reads is named by its size and time as well, so an
    edit past the first MiB moves the tag too (Qodo's comment on `_ATTRIBUTES_TAG_BYTES`)."""
    store = tmp_path / "store.git"
    attributes = store / "info" / "attributes"
    attributes.parent.mkdir(parents=True)
    reads = 0
    real = http_caching._attributes_bytes

    def counted(path: Path) -> bytes:
        nonlocal reads
        reads += 1
        return real(path)

    monkeypatch.setattr(http_caching, "_attributes_bytes", counted)
    none = store_tag(store)
    assert store_tag(store) == none and reads == 1, "a stat says nothing changed"
    attributes.write_text("*.py -diff\n")
    small = store_tag(store)
    assert small != none and reads == 2
    assert store_tag(store) == small and reads == 2
    bound = http_caching._ATTRIBUTES_TAG_BYTES
    attributes.write_bytes(b"# padding\n" * (bound // 10 + 1) + b"*.py -diff\n")
    assert attributes.stat().st_size > bound
    large = store_tag(store)
    assert large not in (none, small)
    # Past the bound: the same first MiB, one more rule at the end, and a different size.
    attributes.write_bytes(b"# padding\n" * (bound // 10 + 1) + b"*.py -diff\n*.md -diff\n")
    appended = store_tag(store)
    assert appended != large, "an edit past the first MiB moves the tag"
    # The same first MiB and the same size, with the rule past the bound rewritten.
    attributes.write_bytes(b"# padding\n" * (bound // 10 + 1) + b"*.py -diff\n*.rs -diff\n")
    os.utime(attributes, ns=(attributes.stat().st_atime_ns, attributes.stat().st_mtime_ns + 1))
    assert store_tag(store) not in (large, appended)


def test_an_editable_install_folds_its_newest_change_into_the_build() -> None:
    """Whether this checkout is editable is not the test's to say; the salt is digits when
    it is and nothing when it is not, and the tag is a digest either way."""
    salt = _newest_source_change()
    assert salt == "" or salt.isdigit()
    assert re.fullmatch(r"[0-9a-f]{12}", BUILD_TAG)


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
