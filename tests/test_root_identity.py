"""What the served subject is called: ``RootIdentity``, ``/api/identity``, and the title.

The derivation is pure, so most of this file calls it directly with a home folder it
chooses: a folder under the home folder, the home folder itself, the file system's root,
paths elsewhere, names that need replacing, and mirror origins in every form the cache
holds, pinned to a branch, a tag, a commit, and a pull request's head. The last tests
serve a folder and read the route and the shell's ``<title>``; a served mirror's are in
``tests/test_serve_pin.py``, and the transcripts are ``cli-api-shell.tryscript.md``,
``cli-api-source.tryscript.md``, and ``cli-github-pull.tryscript.md``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.mirror_refresh import MirrorDisplay
from metabrowser.root_identity import (
    RootIdentity,
    abbreviate_origin,
    folder_identity,
    mirror_identity,
    user_home,
)

HOME = Path("/srv/people/reader")
COMMIT = "42382ea2303b733e1e21b4bd6ddb974ca4e775eb"
REPLACED = "\ufffd"


def _folder(short_name: str, full_name: str) -> RootIdentity:
    return RootIdentity(
        short_name=short_name,
        full_name=full_name,
        kind="folder",
        kind_label="Local folder",
        title=f"{short_name} \u2022 Metabrowser",
    )


def _mirror(short_name: str, full_name: str) -> RootIdentity:
    return RootIdentity(
        short_name=short_name,
        full_name=full_name,
        kind="mirror",
        kind_label="Cached mirror",
        title=f"{short_name} \u2022 Metabrowser",
    )


def _display(origin: str, name: str = "tbd") -> MirrorDisplay:
    return MirrorDisplay(name=name, origin=origin, location="~/.cache/metabrowser/store")


# ── Folders ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("root", "home", "expected"),
    [
        # The example the native app is built against.
        (HOME / "wrk/github/fdu", HOME, _folder("fdu", "~/wrk/github/fdu")),
        (HOME / "notes", HOME, _folder("notes", "~/notes")),
        # The home folder itself is `~`, in both names.
        (HOME, HOME, _folder("~", "~")),
        # The file system's root has no name of its own.
        (Path("/"), HOME, _folder("/", "/")),
        # Outside the home folder the path is absolute.
        (Path("/srv/data/reports"), HOME, _folder("reports", "/srv/data/reports")),
        (Path("/srv"), HOME, _folder("srv", "/srv")),
        # A sibling that shares the home folder's spelling as a prefix is not under it.
        (Path("/srv/people/reader2/notes"), HOME, _folder("notes", "/srv/people/reader2/notes")),
        # With no home folder to compare against, every path is absolute.
        (HOME / "notes", None, _folder("notes", "/srv/people/reader/notes")),
        (Path("/"), None, _folder("/", "/")),
    ],
    ids=[
        "nested",
        "under-home",
        "home",
        "filesystem-root",
        "elsewhere",
        "top-level",
        "home-prefix-sibling",
        "no-home",
        "root-no-home",
    ],
)
@pytest.mark.skipif(os.name == "nt", reason="POSIX paths")
def test_a_folder_is_called_by_its_own_name_and_its_path(
    root: Path, home: Path | None, expected: RootIdentity
) -> None:
    assert folder_identity(root, home=home) == expected


@pytest.mark.parametrize(
    ("name", "shown"),
    [
        # U+202E RIGHT-TO-LEFT OVERRIDE would reorder the title around it.
        ("a\u202eb", f"a{REPLACED}b"),
        # An escape sequence must not reach a terminal or a window title.
        ("a\x1b[2Jb", f"a{REPLACED}[2Jb"),
        # Drawn as nothing: ZERO WIDTH SPACE and HANGUL FILLER.
        ("re\u200bad\u3164me", f"re{REPLACED}ad{REPLACED}me"),
        # A space other than the ASCII one passes for one.
        ("a\u00a0b", f"a{REPLACED}b"),
        # Markup is text: the shell escapes it, the route answers it as written.
        ("a<b>&c", "a<b>&c"),
        # Names in other scripts, and an emoji with its variation selector, are kept.
        ("\u65e5\u672c \u2764\ufe0f", "\u65e5\u672c \u2764\ufe0f"),
    ],
    ids=["bidi-override", "escape", "invisible", "nbsp", "markup", "kept"],
)
@pytest.mark.skipif(os.name == "nt", reason="POSIX paths")
def test_a_folder_name_is_display_text(name: str, shown: str) -> None:
    identity = folder_identity(HOME / "wrk" / name, home=HOME)

    assert identity == _folder(shown, f"~/wrk/{shown}")


@pytest.mark.skipif(os.name == "nt", reason="POSIX filenames retain undecodable bytes")
def test_an_undecodable_folder_name_shows_the_replacement_character() -> None:
    name = os.fsdecode(b"a\xffb")

    identity = folder_identity(Path("/srv") / name / "c", home=HOME)

    assert identity == _folder("c", f"/srv/a{REPLACED}b/c")
    assert folder_identity(Path("/srv") / name, home=HOME) == _folder(
        f"a{REPLACED}b", f"/srv/a{REPLACED}b"
    )


def test_the_title_is_the_short_name_a_bullet_and_the_app() -> None:
    identity = folder_identity(HOME / "fdu", home=HOME)

    assert identity["title"] == "fdu \u2022 Metabrowser"
    assert identity["title"].encode() == b"fdu \xe2\x80\xa2 Metabrowser"


def test_the_home_folder_is_resolved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A served root is resolved, so the home folder it is compared with is too."""

    real = tmp_path / "real-home"
    (real / "notes").mkdir(parents=True)
    link = tmp_path / "home-link"
    link.symlink_to(real)
    monkeypatch.setenv("HOME", str(link))

    home = user_home()

    assert home == real.resolve()
    assert folder_identity((link / "notes").resolve(), home=home) == _folder("notes", "~/notes")


# ── Mirror origins ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("origin", "abbreviated"),
    [
        # https: the scheme and a trailing `.git` go.
        ("https://github.com/jlevy/tbd", "github.com/jlevy/tbd"),
        ("https://github.com/jlevy/tbd.git", "github.com/jlevy/tbd"),
        ("https://www.example.com/owner/repo.git", "example.com/owner/repo"),
        # A port other than the default names another server, so it stays.
        ("https://git.example.org:8443/group/sub/repo.git", "git.example.org:8443/group/sub/repo"),
        ("https://192.0.2.10/repo.git", "192.0.2.10/repo"),
        # A trailing `/.git` names the repository above it, as `git clone` reads it.
        ("https://example.com/owner/repo/.git", "example.com/owner/repo"),
        # A segment that is only dots before `.git` keeps its suffix: `.` is no name.
        ("https://example.com/owner/..git", "example.com/owner/..git"),
        # ssh://: the user goes too.
        ("ssh://git@example.com/owner/repo.git", "example.com/owner/repo"),
        ("ssh://example.com/owner/repo.git", "example.com/owner/repo"),
        ("ssh://git@example.com/owner/repo.git/", "example.com/owner/repo"),
        ("ssh://git@example.com/~alice/repo.git", "example.com/~alice/repo"),
        ("ssh://git@[2001:db8::1]:2222/owner/repo.git", "[2001:db8::1]:2222/owner/repo"),
        # git@host:owner/repo, the scp-like form, reads as host/owner/repo.
        ("git@github.com:jlevy/tbd.git", "github.com/jlevy/tbd"),
        ("git@github.com:jlevy/tbd", "github.com/jlevy/tbd"),
        ("git@example.com:/srv/git/repo.git", "example.com/srv/git/repo"),
        ("git@[2001:db8::1]:owner/repo.git", "[2001:db8::1]/owner/repo"),
        ("deploy@www.example.com:owner/repo.git", "example.com/owner/repo"),
        # A percent-escape is decoded, so the name reads as written.
        ("https://example.com/owner/r%C3%A9po.git", "example.com/owner/r\u00e9po"),
    ],
)
def test_a_remote_origin_is_abbreviated(origin: str, abbreviated: str) -> None:
    assert abbreviate_origin(origin, home=HOME) == abbreviated


@pytest.mark.parametrize(
    ("origin", "abbreviated"),
    [
        # The form `MirrorDisplay.origin` already gives a file:// origin under the home.
        ("file://~/git/squares.git", "~/git/squares.git"),
        # One it did not abbreviate is, when it is under the home folder after all.
        ("file:///srv/people/reader/git/squares.git", "~/git/squares.git"),
        # Elsewhere a path stays absolute, and whole: it names a place on this machine.
        ("file:///srv/git/repo.git", "/srv/git/repo.git"),
        ("file:///srv/squares/.git", "/srv/squares/.git"),
        ("file:///srv/my%20repo", "/srv/my repo"),
        # A local path, as a display might give one.
        ("/srv/git/repo.git", "/srv/git/repo.git"),
        ("/srv/people/reader/src/tbd", "~/src/tbd"),
        ("~/src/tbd", "~/src/tbd"),
    ],
)
@pytest.mark.skipif(os.name == "nt", reason="POSIX paths")
def test_a_local_origin_is_its_path(origin: str, abbreviated: str) -> None:
    assert abbreviate_origin(origin, home=HOME) == abbreviated


@pytest.mark.parametrize(
    ("origin", "abbreviated"),
    [
        # The origin's owner chose its name. U+202E, escaped and then decoded, is replaced.
        ("file://~/git/a%3Cb%3E&%E2%80%AEx.git", f"~/git/a<b>&{REPLACED}x.git"),
        # U+009B is a one-character CSI, which an address can spell as %C2%9B.
        ("https://example.com/owner/a%C2%9Bb.git", f"example.com/owner/a{REPLACED}b"),
        # Bytes that are not UTF-8.
        ("https://example.com/owner/a%FFb", f"example.com/owner/a{REPLACED}b"),
        # Already replaced by the display: kept as it is.
        (f"https://example.com/owner/a{REPLACED}b", f"example.com/owner/a{REPLACED}b"),
    ],
    ids=["bidi-override", "c1-control", "not-utf8", "already-replaced"],
)
def test_an_origin_is_display_text(origin: str, abbreviated: str) -> None:
    assert abbreviate_origin(origin, home=HOME) == abbreviated


def test_an_unrecognized_origin_is_shown_as_it_is() -> None:
    assert abbreviate_origin("example.com/a\u202eb", home=HOME) == f"example.com/a{REPLACED}b"


# ── Mirrors and what they are pinned to ─────────────────────────────


@pytest.mark.parametrize(
    ("origin", "ref", "expected"),
    [
        # A branch, by the name the origin knows it by.
        (
            "https://github.com/jlevy/tbd",
            "refs/remotes/origin/stable",
            _mirror("tbd", "github.com/jlevy/tbd@stable"),
        ),
        # A branch whose name has a slash keeps it.
        (
            "https://github.com/jlevy/tbd",
            "refs/remotes/origin/feature/x",
            _mirror("tbd", "github.com/jlevy/tbd@feature/x"),
        ),
        (
            "https://github.com/jlevy/tbd",
            "refs/tags/v1.0.0",
            _mirror("tbd", "github.com/jlevy/tbd@v1.0.0"),
        ),
        # A commit pinned by its ID shows its first twelve hex digits.
        ("https://github.com/jlevy/tbd", None, _mirror("tbd", "github.com/jlevy/tbd@42382ea2303b")),
        # A pull request's head is named as GitHub writes a pull request.
        (
            "https://github.com/jlevy/tbd",
            "refs/pull/123/head",
            _mirror("tbd #123", "github.com/jlevy/tbd#123"),
        ),
        (
            "git@github.com:jlevy/tbd.git",
            "refs/remotes/origin/stable",
            _mirror("tbd", "github.com/jlevy/tbd@stable"),
        ),
        (
            "ssh://git@example.com/owner/tbd.git",
            None,
            _mirror("tbd", "example.com/owner/tbd@42382ea2303b"),
        ),
        (
            "file://~/git/tbd.git",
            "refs/remotes/origin/topic",
            _mirror("tbd", "~/git/tbd.git@topic"),
        ),
        ("file:///srv/git/tbd.git", None, _mirror("tbd", "/srv/git/tbd.git@42382ea2303b")),
        # Another ref keeps its full spelling rather than being guessed at.
        (
            "https://github.com/jlevy/tbd",
            "refs/notes/commits",
            _mirror("tbd", "github.com/jlevy/tbd@refs/notes/commits"),
        ),
    ],
    ids=[
        "branch",
        "branch-with-slash",
        "tag",
        "commit",
        "pull-request",
        "scp-branch",
        "ssh-commit",
        "file-under-home",
        "file-commit",
        "other-ref",
    ],
)
def test_a_mirror_is_called_by_its_repository_and_named_by_origin_and_pin(
    origin: str, ref: str | None, expected: RootIdentity
) -> None:
    identity = mirror_identity(display=_display(origin), ref=ref, commit=COMMIT, home=HOME)

    assert identity == expected


def test_a_mirror_full_name_never_names_the_cache() -> None:
    display = _display("https://github.com/jlevy/tbd")

    identity = mirror_identity(display=display, ref=None, commit=COMMIT, home=HOME)

    assert display.location not in identity["full_name"]
    assert "cache" not in identity["full_name"]


def test_a_ref_name_the_origin_chose_is_display_text() -> None:
    identity = mirror_identity(
        display=_display("https://github.com/jlevy/tbd"),
        ref="refs/remotes/origin/ma\u202ein",
        commit=COMMIT,
        home=HOME,
    )

    assert identity == _mirror("tbd", f"github.com/jlevy/tbd@ma{REPLACED}in")


def test_a_mirror_name_is_display_text() -> None:
    """``MirrorDisplay`` replaces what its name needs; the identity replaces it again."""

    identity = mirror_identity(
        display=_display("https://github.com/jlevy/tbd", name="t\u200bbd"),
        ref="refs/pull/7/head",
        commit=COMMIT,
        home=HOME,
    )

    assert identity == _mirror(f"t{REPLACED}bd #7", "github.com/jlevy/tbd#7")


@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        ("refs/remotes/origin/topic", _mirror("topic", "topic@42382ea2303b")),
        ("refs/tags/v1", _mirror("v1", "v1@42382ea2303b")),
        (None, _mirror("42382ea2303b", "42382ea2303b")),
    ],
    ids=["branch", "tag", "commit"],
)
def test_a_pin_with_no_mirror_is_named_by_its_ref_and_commit(
    ref: str | None, expected: RootIdentity
) -> None:
    assert mirror_identity(display=None, ref=ref, commit=COMMIT, home=HOME) == expected


# ── The route and the shell ─────────────────────────────────────────


def test_the_route_and_the_shell_name_a_served_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "wrk" / "a<b>&c"
    root.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    server._set_root_dir(root)
    client = TestClient(server.app)

    answer = client.get("/api/identity")

    assert answer.status_code == 200
    # The contract the native app reads, in its order.
    assert list(answer.json()) == ["short_name", "full_name", "kind", "kind_label", "title"]
    assert answer.json() == _folder("a<b>&c", "~/wrk/a<b>&c")
    for address in ("/view/", "/pulls", "/pull/7"):
        shell = client.get(address)
        assert shell.status_code == 200, address
        # The same title, escaped as HTML, on every address of the folder.
        assert "<title>a&lt;b&gt;&amp;c \u2022 Metabrowser</title>" in shell.text, address


def test_the_shell_titles_a_folder_outside_the_home_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    root = tmp_path / "elsewhere"
    root.mkdir()
    monkeypatch.setenv("HOME", str(home))
    server._set_root_dir(root)
    client = TestClient(server.app)

    assert client.get("/api/identity").json() == _folder("elsewhere", str(root.resolve()))
    assert "<title>elsewhere \u2022 Metabrowser</title>" in client.get("/view/").text


def test_the_route_is_a_get(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)

    answer = TestClient(server.app).post("/api/identity", json={})

    assert answer.status_code == 405
