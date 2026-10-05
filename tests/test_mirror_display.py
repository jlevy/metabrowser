"""What a served mirror's page is called and where it says the mirror is kept.

A page of a mirror showed the full commit ID where a folder's page shows the folder's
name, and said nowhere that its files came out of the cache (``mb-fndz``). The name is
now the repository's, as a checkout would have it, and the location is the store's bare
repository with the home directory as ``~``. Both come from
:attr:`metabrowser.cache.served_mirror.StoreMirror.display`, and both are text the
origin's owner can influence, so each odd address here is one an origin can have.

The status envelope and the page that carry them are held in ``tests/test_serve_pin.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from metabrowser.cache.served_mirror import (
    REPOSITORY_NAME_MAX_CHARS,
    UNNAMED_REPOSITORY,
    StoreMirror,
    display_directory,
    display_origin,
    repository_name,
)
from metabrowser.cache.urls import GitSource

_STORE_KEY = "ab" * 32


@pytest.mark.parametrize(
    ("address", "name"),
    [
        # The report: a GitHub repository is called what its checkout is.
        ("https://github.com/jlevy/squares", "squares"),
        ("https://example.com/group/sub/tool.git", "tool"),
        ("file:///srv/git/squares.git", "squares"),
        # A working repository's own Git directory names the directory above it.
        ("file:///srv/work/squares/.git", "squares"),
        ("ssh://git@example.com/team/tool.git", "tool"),
        ("git@example.com:team/tool.git", "tool"),
        ("git@example.com:tool", "tool"),
        # One suffix is the convention; a second is part of the name.
        ("https://example.com/a/tool.git.git", "tool.git"),
        ("https://example.com/a/.github", ".github"),
        # Dots alone are no name, so the suffix that makes one of them stays.
        ("https://example.com/a/..git", "..git"),
        ("https://example.com/a/...git", "...git"),
        ("https://example.com/a/.git.git", ".git"),
        ("https://example.com/a/a..git", "a."),
    ],
)
def test_a_repository_is_named_as_a_checkout_of_it_would_be(address: str, name: str) -> None:
    assert repository_name(address) == name


@pytest.mark.parametrize(
    ("address", "name"),
    [
        # Nothing but ``.git``: the host is what is left to call it by, without its port.
        ("https://example.com/.git", "example.com"),
        ("https://example.com:8443/.git", "example.com"),
        ("https://user@example.com:8443/.git", "example.com"),
        ("https://[::1]:8443/.git", "[::1]"),
        # No host either.
        ("file:///.git", UNNAMED_REPOSITORY),
        ("file:///", UNNAMED_REPOSITORY),
        ("", UNNAMED_REPOSITORY),
    ],
)
def test_an_address_that_names_no_repository_is_called_by_its_host(address: str, name: str) -> None:
    assert repository_name(address) == name


@pytest.mark.parametrize(
    ("address", "name"),
    [
        # A percent-escape reads as what it spells.
        ("https://example.com/docs/%E9%9B%AA.git", "\u96ea"),
        ("https://example.com/a/50%25-off", "50%-off"),
        # U+009B is a one-character CSI on a terminal.
        ("https://example.com/a/ok%C2%9Bname", "ok\ufffdname"),
        # U+202E reorders what follows it; U+200B and U+3164 are drawn as nothing.
        ("https://example.com/a/%E2%80%AEgpj.exe", "\ufffdgpj.exe"),
        ("https://example.com/a/squ%E2%80%8Bares", "squ\ufffdares"),
        ("https://example.com/a/%E3%85%A4", "\ufffd"),
        # Bytes that are not UTF-8.
        ("https://example.com/a/%FF%FE.git", "\ufffd\ufffd"),
        # Markup is the page's to escape, and is still only text here.
        ("https://example.com/a/%3Cb%3Ex%22.git", '<b>x"'),
    ],
)
def test_an_odd_or_hostile_name_is_shown_as_any_untrusted_name_is(address: str, name: str) -> None:
    assert repository_name(address) == name


def test_a_name_longer_than_a_directory_can_be_called_is_cut_with_an_ellipsis() -> None:
    longest = "a" * REPOSITORY_NAME_MAX_CHARS
    assert repository_name(f"https://example.com/{longest}.git") == longest

    name = repository_name("https://example.com/" + "a" * 1900 + ".git")
    assert len(name) == REPOSITORY_NAME_MAX_CHARS
    assert name == "a" * (REPOSITORY_NAME_MAX_CHARS - 1) + "\u2026"


def _mirror(home: Path, address: str = "https://github.com/jlevy/squares") -> StoreMirror:
    return StoreMirror(
        home=home,
        store_key=_STORE_KEY,
        store_id=f"sha256:{_STORE_KEY}",
        source=GitSource(transport="https", form="url", normalized=address),
    )


def test_the_location_is_the_stores_bare_repository_with_the_home_directory_as_a_tilde(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = tmp_path / "user"
    monkeypatch.setenv("HOME", str(user))

    display = _mirror(user / ".cache" / "metabrowser").display

    assert display.name == "squares"
    assert display.origin == "https://github.com/jlevy/squares"
    # The directory Git reads the pages from, not the source's records beside it.
    assert display.location == f"~/.cache/metabrowser/repository-stores/{_STORE_KEY}/repository.git"
    assert (user / ".cache" / "metabrowser" / "sources") not in Path(display.location).parents


def test_a_location_outside_the_home_directory_is_absolute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "user"))
    elsewhere = tmp_path / "elsewhere"

    location = _mirror(elsewhere).display.location

    assert location == str(elsewhere / "repository-stores" / _STORE_KEY / "repository.git")
    assert "~" not in location
    # A sibling whose name only starts like the home directory's is not under it.
    assert display_directory(tmp_path / "user-other" / "x") == str(tmp_path / "user-other" / "x")
    assert display_directory(tmp_path / "user") == "~"


def test_a_file_origin_under_the_home_directory_is_shown_with_a_tilde(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No answer spells out the home directory when it can be abbreviated (mb-fndz).

    The origin is the address the reader gave, and for a ``file://`` source that is a
    path of theirs. It is shown as the location is: under the home directory with ``~``,
    and as it is otherwise. What follows the home directory keeps its escapes.
    """

    home = tmp_path / "home dir" / "user"
    monkeypatch.setenv("HOME", str(home))
    encoded = "file://" + str(tmp_path) + "/home%20dir/user"

    assert display_origin(f"{encoded}/git/squares.git") == "file://~/git/squares.git"
    assert display_origin(f"{encoded}/git/a%3Cb%3E.git") == "file://~/git/a%3Cb%3E.git"
    assert display_origin(encoded) == "file://~"
    # Outside it, a sibling whose name starts like it, and the directory above it.
    for outside in (
        f"file://{tmp_path}/elsewhere/squares.git",
        f"{encoded}-other/squares.git",
        "file://" + str(tmp_path) + "/home%20dir",
        "file:///squares.git",
    ):
        assert display_origin(outside) == outside
    # Only a file:// address is a path. Another host's path is its own.
    https = "https://example.com" + str(tmp_path) + "/home%20dir/user/squares.git"
    assert display_origin(https) == https

    display = _mirror(home / ".metabrowser", f"{encoded}/git/squares.git").display
    assert display.origin == "file://~/git/squares.git"
    assert display.name == "squares"
    assert str(tmp_path) not in "".join((display.name, display.origin, display.location))


def test_a_control_character_in_the_location_or_the_origin_is_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    assert display_directory(tmp_path / "ca\x1bche" / "x") == "~/ca\ufffdche/x"

    display = _mirror(tmp_path, "https://example.com/a/ok%C2%9Bname.git").display
    # The origin is shown as it is addressed, escapes and all; only its name is decoded.
    assert display.origin == "https://example.com/a/ok%C2%9Bname.git"
    assert display.name == "ok\ufffdname"

    # The URL grammar refuses an address with a raw control character, and the display
    # does not rely on that: an escape sequence in one is replaced like any other.
    raw = _mirror(tmp_path, "https://example.com/a/red\x1b[31m.git").display
    assert raw.origin == "https://example.com/a/red\ufffd[31m.git"
    assert display_origin("file:///srv/a\x9bb.git") == "file:///srv/a\ufffdb.git"
