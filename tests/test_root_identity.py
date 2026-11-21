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

import html
import os
import re
from pathlib import Path
from typing import cast

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.commit_ids import short_commit
from metabrowser.mirror_refresh import MirrorDisplay
from metabrowser.repository_context import RepositoryContext
from metabrowser.root_identity import (
    KIND_LABELS,
    IdentityKind,
    RootIdentity,
    abbreviate_origin,
    checkout_revision_identity,
    folder_identity,
    kind_subject,
    kind_tip,
    mirror_identity,
    user_home,
)
from metabrowser.source_kind_marks import source_kind_svg

HOME = Path("/srv/people/reader")
COMMIT = "42382ea2303b733e1e21b4bd6ddb974ca4e775eb"
# The commit as a line names it (docs/design-system.md, "Short Commit IDs").
SHORT = short_commit(COMMIT)
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
        kind_label="Cloud mirror",
        title=f"{short_name} \u2022 Metabrowser",
    )


def _git(short_name: str, full_name: str) -> RootIdentity:
    return RootIdentity(
        short_name=short_name,
        full_name=full_name,
        kind="git",
        kind_label="Local Git checkout",
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
        # A commit pinned by its ID shows its short ID.
        ("https://github.com/jlevy/tbd", None, _mirror("tbd", f"github.com/jlevy/tbd@{SHORT}")),
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
            _mirror("tbd", f"example.com/owner/tbd@{SHORT}"),
        ),
        (
            "file://~/git/tbd.git",
            "refs/remotes/origin/topic",
            _mirror("tbd", "~/git/tbd.git@topic"),
        ),
        ("file:///srv/git/tbd.git", None, _mirror("tbd", f"/srv/git/tbd.git@{SHORT}")),
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
        ("refs/remotes/origin/topic", _mirror("topic", f"topic@{SHORT}")),
        ("refs/tags/v1", _mirror("v1", f"v1@{SHORT}")),
        (None, _mirror(SHORT, SHORT)),
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
    assert list(answer.json()) == [
        "short_name",
        "full_name",
        "kind",
        "kind_label",
        "title",
        "kind_tip",
        "repository",
    ]
    assert answer.json() == {
        **_folder("a<b>&c", "~/wrk/a<b>&c"),
        "kind_tip": "Local folder",
        "repository": None,
    }
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

    assert client.get("/api/identity").json() == {
        **_folder("elsewhere", str(root.resolve())),
        "kind_tip": "Local folder",
        "repository": None,
    }
    assert "<title>elsewhere \u2022 Metabrowser</title>" in client.get("/view/").text


def _checkout(root: Path, origin: str | None) -> Path:
    """A checkout at *root* whose ``origin`` is *origin*, written as Git writes one."""

    git = root / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git / "refs" / "heads" / "main").write_text(f"{COMMIT}\n", encoding="utf-8")
    remote = "" if origin is None else f'[remote "origin"]\n\turl = {origin}\n'
    (git / "config").write_text(f"[core]\n\tbare = false\n{remote}", encoding="utf-8")
    return root


@pytest.mark.parametrize(
    ("origin", "repository", "tip"),
    [
        # Lowercase, as `metab URL --present --dry-run` names a link's root, in every
        # form an origin on github.com takes; the tip spells the repository as its origin
        # does.
        (
            "git@github.com:Octo/Demo.git",
            "https://github.com/octo/demo",
            "Local Git checkout (GitHub: Octo/Demo)",
        ),
        (
            "https://github.com/octo/demo",
            "https://github.com/octo/demo",
            "Local Git checkout (GitHub: octo/demo)",
        ),
        (
            "ssh://git@github.com/octo/demo.git",
            "https://github.com/octo/demo",
            "Local Git checkout (GitHub: octo/demo)",
        ),
        # No repository on github.com, or no origin: nothing to put a link beside, and
        # nothing for the tip to name.
        ("https://gitlab.com/octo/demo.git", None, "Local Git checkout"),
        (None, None, "Local Git checkout"),
    ],
)
def test_a_checkout_belongs_to_the_github_repository_its_origin_names(
    tmp_path: Path, origin: str | None, repository: str | None, tip: str
) -> None:
    checkout = _checkout(tmp_path / "demo", origin)
    for served in (checkout, checkout / "docs"):
        served.mkdir(exist_ok=True)
        server._set_root_dir(served)

        client = TestClient(server.app)
        answer = client.get("/api/identity").json()

        # A folder below the checkout's root belongs to its repository too.
        assert answer["repository"] == repository, served
        # But it is a checkout's root that is the checkout: a folder served exactly below
        # it is a plain folder, whose Git features are off (docs/project/architecture/
        # arch-open-modes.md, "Resolving a Target to a Root").
        is_root = served == checkout
        assert answer["kind"] == ("git" if is_root else "folder"), served
        assert answer["kind_label"] == KIND_LABELS["git" if is_root else "folder"], served
        assert answer["kind_tip"] == (tip if is_root else "Local folder"), served
        shell = client.get("/view/").text
        details = re.search(r'<details id="root-details"[^>]*>', shell)
        assert details is not None
        assert ("data-repository-url=" in details[0]) == (is_root and repository is not None)
        if is_root and repository is not None:
            assert f'data-repository-url="{repository}"' in details[0]


def _mark(shell: str) -> tuple[str, str]:
    """The kind and the sentence the shell's mark beside the root's name carries."""

    match = re.search(
        r'<span class="header-root-kind" id="header-root-kind" role="img"\s+'
        r'data-root-kind="([a-z]+)" data-tip-text="([^"]*)"\s+aria-label="([^"]*)">'
        r"(<svg .*?</svg>)</span>",
        shell,
    )
    assert match is not None
    # The tooltip and the accessible name are the one sentence.
    assert match.group(2) == match.group(3)
    # The glyph is the kind's, written by the server: no script draws it.
    assert match.group(4) == source_kind_svg(cast(IdentityKind, match.group(1)))
    return match.group(1), html.unescape(match.group(2))


@pytest.mark.parametrize("checkout", [False, True], ids=["plain-folder", "git-checkout"])
def test_the_shells_mark_is_the_kind_and_tip_the_route_answers(
    tmp_path: Path, checkout: bool
) -> None:
    """The page and ``/api/identity`` say a root's kind in the same words, at every address."""

    root = tmp_path / "demo"
    root.mkdir()
    if checkout:
        _checkout(root, "git@github.com:Octo/Demo.git")
    server._set_root_dir(root)
    client = TestClient(server.app)

    answer = client.get("/api/identity").json()

    assert (answer["kind"], answer["kind_tip"]) == (
        ("git", "Local Git checkout (GitHub: Octo/Demo)")
        if checkout
        else ("folder", "Local folder")
    )
    for address in ("/view/", "/pulls", "/pull/7", "/commit/0123456789abcdef"):
        assert _mark(client.get(address).text) == (answer["kind"], answer["kind_tip"]), address


def test_a_tip_escapes_what_a_repository_name_may_hold(tmp_path: Path) -> None:
    """A repository's name is the origin's, so the markup it reaches is escaped."""

    root = _checkout(tmp_path / "demo", "https://github.com/octo/demo")
    server._set_root_dir(root)

    shell = TestClient(server.app).get("/view/").text

    assert _mark(shell) == ("git", "Local Git checkout (GitHub: octo/demo)")
    # No sentence ends the attribute early: both attributes close with a quote and a space
    # or a bracket that _mark matched.
    assert shell.count('id="header-root-kind"') == 1


def test_a_revision_of_a_checkout_is_still_a_git_checkout() -> None:
    """The kind is how the root was opened, and a revision it shows does not change that."""

    shown = checkout_revision_identity(
        HOME / "src" / "tbd", ref="refs/heads/topic", commit=COMMIT, home=HOME
    )

    assert shown["kind"] == "git"
    assert shown["kind_label"] == "Local Git checkout"
    assert shown["full_name"] == "~/src/tbd@topic"


def test_a_folder_is_a_git_checkout_only_when_asked_to_be() -> None:
    assert folder_identity(HOME / "tbd", home=HOME) == _folder("tbd", "~/tbd")
    assert folder_identity(HOME / "tbd", home=HOME, checkout=True) == _git("tbd", "~/tbd")


def _context(owner: str, name: str) -> RepositoryContext:
    return RepositoryContext(
        branch="main",
        branch_on_origin=True,
        host="github.com",
        name=name,
        owner=owner,
        revision=COMMIT,
        served_prefix="",
    )


@pytest.mark.parametrize(
    ("kind", "repository", "tip"),
    [
        ("mirror", _context("jlevy", "tbd"), "Cloud mirror of jlevy/tbd"),
        # A mirror no provider knows names nothing: its origin is the source's address as
        # given, which only the places tests/test_serve_pin.py allows may say.
        ("mirror", None, "Cloud mirror"),
        ("git", _context("jlevy", "tbd"), "Local Git checkout (GitHub: jlevy/tbd)"),
        ("git", None, "Local Git checkout"),
        # A plain folder is of nothing, wherever it stands.
        ("folder", _context("jlevy", "tbd"), "Local folder"),
        ("folder", None, "Local folder"),
    ],
)
def test_a_kind_is_named_with_what_it_is_of(
    kind: IdentityKind, repository: RepositoryContext | None, tip: str
) -> None:
    assert kind_tip(kind, kind_subject(kind, repository)) == tip


def test_the_route_is_a_get(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)

    answer = TestClient(server.app).post("/api/identity", json={})

    assert answer.status_code == 405
