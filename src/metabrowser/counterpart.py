"""The github.com page that shows what a Metabrowser page shows: ``GET /api/counterpart``.

A page has a counterpart when the served repository is on github.com and github.com has
a page for the same thing: a file or a folder at a commit github.com has, a pull
request's tab, a commit, or the repository's pull requests. ``GET
/api/counterpart?page=<page>`` answers which, so a page's View on GitHub control and
``metab --api`` read one answer, and no page builds a github.com URL itself. :data:`PAGES`
is the mapping; ``docs/design-system.md``, "Where It Appears", restates it, and
``tests/test_counterpart.py`` holds the two together.

*page* is the page's address as the browser's ``location.pathname`` spells it,
percent-encoded, read by the parsers the shell's own routes read it by
(``view_routes.py``, and on a pin ``decode_git_view_path``): an address the shell would
refuse has no counterpart. The answer is ``{"page", "counterpart", "reason"}``, with
``counterpart`` the provider, the link's label, and the URL, or ``null`` and a
:data:`CounterpartReason` saying why not. A request without a page, or with one longer
than :data:`MAX_PAGE_CHARS`, is refused with 400, and a Git failure that is no answer,
such as a timeout, with the status its error names, as a Git route's is.

**Which repository.** The one the Pulls tab is drawn for: a served checkout's ``origin``
on github.com (:func:`~metabrowser.repository_context.discover_repository_context`), or
the repository a served mirror's provider names
(:func:`~metabrowser.cache.providers.repository_context_for`). Only a github.com
repository has one today, so the URL, its label, and its provider are the GitHub
plugin's (``builtin_plugins/github/urls.py``), and every URL is built by its
:meth:`~metabrowser.builtin_plugins.github.urls.GithubUrlReducer.web_url`, but for the
list of pull requests, which no selection names (``pulls_url``). That module is
imported only once a repository is found, as ``cache/providers.py`` imports it, so a
plain folder's server never loads it.

**Which commit a file or folder is at.** The one ``/api/file`` reads it from: a pin's
commit, or else the working tree.

- A mirror's pin is its commit. A mirror holds only its origin's commits.
- A revision of a checkout (``metab PATH --ref NAME``, or the ref selector) is its
  commit, when origin has that commit.
- The working tree is ``HEAD``'s commit, when origin has it and the item is what it is
  there: a file tracked at ``HEAD`` with no change in the index or the working tree, or a
  folder in ``HEAD``'s tree. Untracked and ignored files inside a folder do not change
  the folder's page on github.com, so they do not stop it from mapping; a folder that
  ``HEAD`` lacks is ``untracked`` or ``ignored`` by what it holds.

"Origin has it" means a ``refs/remotes/origin/*`` ref reaches the commit, as the
checkout last fetched it, and in a mirror any of its refs, which are all its origin's.
Nothing is fetched to ask. A pull request's pages and the list map whenever the
repository is on github.com, and a commit's page when origin has the commit.

A file's reason is asked before its commit's, since an untracked file stays untracked
once its commit is pushed. Each question is one Git command, under the request-path
deadline and output bound of :mod:`metabrowser.git.process`: what the commit holds at
the path (``ls-tree``, or a pin's own tree reader), how the working tree differs there
(``status``, asked only of a file in the commit and of a path the commit lacks), and
whether origin has the commit (``rev-list``). With no Git installed origin cannot be
asked, and a page that needs it answers ``not_on_origin``.

There is no commits-list page to map: a pull request's page has no Commits tab
(``PULL_ROUTE_TABS``), and the Commits tab is a pane, not an address.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal, TypedDict

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from metabrowser.checkout_revisions import checkout_revisions
from metabrowser.git.process import (
    GIT_NO_HOOK_ARGS,
    GitCommandError,
    GitError,
    GitLocation,
    failure_detail,
    git_executable,
    run_git_at,
)
from metabrowser.git.wire import is_full_revision
from metabrowser.mirror_refresh import MirrorSession, mirror_session
from metabrowser.repository_context import RepositoryContext, discover_repository_context
from metabrowser.source import RepositorySubject, as_git_revision_subject, get_source_session
from metabrowser.view_routes import (
    VIEW_ROUTE_PREFIX,
    decode_safe_commit_route,
    decode_safe_pull_route,
    decode_safe_view_path,
    parse_pulls_selection,
)

if TYPE_CHECKING:
    from metabrowser.cache.urls import RepositorySelection
    from metabrowser.git.tree_source import GitRevisionSubject

log = logging.getLogger(__name__)

# The longest page address read. A page's address is its path percent-encoded: a served
# path of Linux's ``PATH_MAX``, 4096 bytes, each escaped as three characters, is about
# 12 KiB with its route, and this holds that.
MAX_PAGE_CHARS: Final = 16 * 1024

type CounterpartReason = Literal[
    # The served folder or mirror has no repository on github.com: a plain folder, a
    # checkout whose ``origin`` is elsewhere or missing, or a mirror of another host.
    "no_repository",
    # The address is not a page this route maps: not one of :data:`PAGES`, one the
    # shell's parser refuses, or a commit's page named by anything but a full commit ID,
    # which the commit page refuses too.
    "not_a_page",
    # The file differs from the commit in the index or the working tree, or the path is
    # in the index only, staged and not committed.
    "uncommitted",
    # The file or folder is not tracked; a folder the commit lacks holds an untracked
    # file.
    "untracked",
    # The file or folder is ignored; a folder the commit lacks holds nothing else.
    "ignored",
    # Origin is not known to have the commit the page shows: no ref of origin reaches it,
    # the repository lacks it, or no Git is installed to ask.
    "not_on_origin",
    # The commit has nothing at the path and the working tree has nothing there either:
    # a deleted file, an entry inside a container file such as a patch, or an empty
    # folder, which Git does not track.
    "missing",
]
# Every reason, in the order the design system's table lists them.
REASONS: Final[tuple[CounterpartReason, ...]] = (
    "no_repository",
    "not_a_page",
    "uncommitted",
    "untracked",
    "ignored",
    "not_on_origin",
    "missing",
)

type PageKind = Literal[
    "file", "folder", "root", "pull", "pull_file", "commit", "commit_file", "pulls"
]


@dataclass(frozen=True, slots=True)
class PageCounterpart:
    """One kind of page, the shape of its github.com counterpart, and when it has none.

    ``page`` is the address's shape, ``counterpart`` the URL's after
    ``https://github.com/<owner>/<repository>/``, and ``reasons`` the reasons this kind
    of page can have no counterpart besides ``no_repository``, which every page can.
    """

    page: str
    counterpart: str
    reasons: tuple[CounterpartReason, ...]


# The mapping, which ``docs/design-system.md`` ("Where It Appears") restates row for row.
# A file and a folder are told apart by the commit's tree, not by a trailing slash.
PAGES: Final[dict[PageKind, PageCounterpart]] = {
    "file": PageCounterpart(
        "/view/<path>",
        "blob/<sha>/<repo path>",
        ("uncommitted", "untracked", "ignored", "missing", "not_on_origin"),
    ),
    "folder": PageCounterpart(
        "/view/<path>/",
        "tree/<sha>/<repo path>",
        ("uncommitted", "untracked", "ignored", "missing", "not_on_origin"),
    ),
    "root": PageCounterpart(
        "/view/",
        "tree/<sha>/<served prefix>, or tree/<sha> at the repository root",
        ("uncommitted", "untracked", "ignored", "missing", "not_on_origin"),
    ),
    "pull": PageCounterpart(
        "/pull/<n>, /pull/<n>/files, /pull/<n>/checks",
        "pull/<n>, pull/<n>/files, pull/<n>/checks",
        (),
    ),
    "pull_file": PageCounterpart("/pull/<n>/files/<path>", "pull/<n>/files#diff-<hash>", ()),
    "commit": PageCounterpart("/commit/<sha>", "commit/<sha>", ("not_on_origin",)),
    "commit_file": PageCounterpart(
        "/commit/<sha>/<path>", "commit/<sha>#diff-<hash>", ("not_on_origin",)
    ),
    "pulls": PageCounterpart("/pulls", "pulls", ()),
}

# The refs that say origin has a commit: a checkout's remote-tracking branches of
# ``origin``, and every ref of a mirror, whose refs are all its origin's.
_CHECKOUT_ORIGIN_REFS: Final = ("--remotes=origin",)
_MIRROR_ORIGIN_REFS: Final = ("--all",)


class Counterpart(TypedDict):
    """A page's github.com counterpart: who hosts it, what its link says, and where it goes."""

    provider: str
    label: str
    url: str


class CounterpartAnswer(TypedDict):
    """The envelope of ``GET /api/counterpart``: a counterpart, or why there is none."""

    page: str
    counterpart: Counterpart | None
    reason: CounterpartReason | None


@dataclass(frozen=True, slots=True)
class _Page:
    """A page address, parsed: which kind of page, and what it names.

    ``path`` is a file's or a folder's path below the served root as bytes, and
    ``logical`` the same path as the served folder spells it, which ``status`` reads;
    ``inside_file`` marks a pin's address of an entry inside a container file.
    """

    kind: Literal["view", "pull", "pull_file", "commit", "commit_file", "pulls"]
    path: tuple[bytes, ...] = ()
    logical: str = ""
    inside_file: bool = False
    number: int = 0
    tab: str = ""
    commit: str = ""


@dataclass(frozen=True, slots=True)
class _Repository:
    """The served repository on github.com, and where to ask Git about its commits.

    ``origin_refs`` are the ``rev-list`` arguments naming what origin has, and
    ``pin_on_origin`` says a pin's commit is origin's without asking, as a mirror's is.
    """

    context: RepositoryContext
    location: GitLocation
    origin_refs: tuple[str, ...]
    pin: GitRevisionSubject | None
    pin_on_origin: bool


async def page_counterpart(page: str, mirror: MirrorSession | None) -> CounterpartAnswer:
    """What *page* maps to on github.com, for the subject served now.

    Raises :class:`~metabrowser.git.process.GitError` for a Git failure that is not an
    answer, such as a timeout.
    """

    subject = get_source_session().subject
    pin = as_git_revision_subject(subject)
    parsed = _parse(page, pin)
    if parsed is None:
        return _none(page, "not_a_page")
    repository = await _served_repository(subject, pin, mirror)
    if repository is None:
        return _none(page, "no_repository")
    selection = await _selection(parsed, repository)
    if isinstance(selection, str):
        return _none(page, selection)
    from metabrowser.builtin_plugins.github.urls import (
        COUNTERPART_LABEL,
        COUNTERPART_PROVIDER,
        GithubUrlReducer,
        pulls_url,
        repository_url,
    )

    clone_url = repository_url(repository.context["owner"], repository.context["name"])
    if selection is None:
        url = pulls_url(clone_url)
    else:
        url = GithubUrlReducer().web_url(clone_url, selection)
    if url is None:
        # An owner or a name the github.com grammar does not admit.
        return _none(page, "no_repository")
    return CounterpartAnswer(
        page=page,
        counterpart=Counterpart(provider=COUNTERPART_PROVIDER, label=COUNTERPART_LABEL, url=url),
        reason=None,
    )


def _none(page: str, reason: CounterpartReason) -> CounterpartAnswer:
    return CounterpartAnswer(page=page, counterpart=None, reason=reason)


def _parse(page: str, pin: GitRevisionSubject | None) -> _Page | None:
    """*page* as one of the pages :data:`PAGES` maps, or ``None`` for any other address."""

    if parse_pulls_selection(page) is not False:
        return _Page("pulls")
    try:
        raw = page.encode("utf-8")
    except UnicodeEncodeError:
        return None
    pull = decode_safe_pull_route(raw)
    if pull is not None:
        if pull.file:
            return _Page("pull_file", path=(pull.file.encode("utf-8"),), number=pull.number)
        return _Page("pull", number=pull.number, tab=pull.tab)
    commit_route = decode_safe_commit_route(raw)
    if commit_route is not None:
        commit, inner = commit_route
        if not is_full_revision(commit):
            return None
        if inner:
            return _Page("commit_file", path=(inner.encode("utf-8"),), commit=commit)
        return _Page("commit", commit=commit)
    if not raw.startswith(VIEW_ROUTE_PREFIX.encode()):
        return None
    if pin is not None:
        # Imported for a pin only, as every revision module is (docs/development.md,
        # "Deferred Imports").
        from metabrowser.git.content_routes import decode_git_view_path
        from metabrowser.git.tree_source import split_git_container_wire

        wire = decode_git_view_path(raw)
        if wire is None:
            return None
        path, inner = split_git_container_wire(wire)
        return _Page("view", path=path.segments, inside_file=bool(inner))
    logical = decode_safe_view_path(raw)
    if logical is None:
        return None
    logical = logical.rstrip("/")
    path = tuple(os.fsencode(logical).split(b"/")) if logical else ()
    return _Page("view", path=path, logical=logical)


async def _served_repository(
    subject: RepositorySubject, pin: GitRevisionSubject | None, mirror: MirrorSession | None
) -> _Repository | None:
    """The served subject's repository on github.com, or ``None`` when it has none."""

    if pin is None:
        root = subject.filesystem_root
        if root is None:
            return None
        context = await asyncio.to_thread(discover_repository_context, root)
        if context is None:
            return None
        return _Repository(
            context, GitLocation.filesystem(root), _CHECKOUT_ORIGIN_REFS, None, False
        )
    location = GitLocation.revision(pin.command_target, pin.commit_oid)
    checkout = checkout_revisions()
    if checkout is not None and checkout.serves(pin):
        context = await asyncio.to_thread(discover_repository_context, checkout.root)
        if context is None:
            return None
        return _Repository(context, location, _CHECKOUT_ORIGIN_REFS, pin, False)
    if mirror is None:
        return None
    from metabrowser.git.tree_source import ref_branch_name

    context = mirror.mirror.repository_context(
        revision=pin.commit_oid, branch=ref_branch_name(pin.ref)
    )
    if context is None:
        return None
    return _Repository(context, location, _MIRROR_ORIGIN_REFS, pin, True)


async def _selection(
    page: _Page, repository: _Repository
) -> RepositorySelection | CounterpartReason | None:
    """*page*'s counterpart as a selection, ``None`` for the list, or why it has none."""

    from metabrowser.builtin_plugins.github.urls import file_anchor
    from metabrowser.cache.urls import RepositorySelection

    match page.kind:
        case "pulls":
            return None
        case "pull":
            return RepositorySelection(
                kind="pull_request", pull_request=page.number, pull_tab=page.tab
            )
        case "pull_file":
            return RepositorySelection(
                kind="pull_request",
                pull_request=page.number,
                pull_tab="files",
                pull_file=file_anchor(page.path[0]),
            )
        case "commit" | "commit_file":
            if not await _on_origin(repository, page.commit):
                return "not_on_origin"
            anchor = file_anchor(page.path[0]) if page.kind == "commit_file" else None
            return RepositorySelection(kind="commit", commit=page.commit, pull_file=anchor)
        case "view":
            return await _item_selection(page, repository)


async def _item_selection(
    page: _Page, repository: _Repository
) -> RepositorySelection | CounterpartReason:
    """A file's or a folder's counterpart, at the commit the page shows it from."""

    from metabrowser.cache.urls import RepositorySelection

    pin = repository.pin
    if pin is not None:
        found = await _pinned_kind(page, pin)
        commit = pin.commit_oid
        path = page.path
    else:
        if git_executable() is None:
            return "not_on_origin"
        commit = repository.context["revision"]
        prefix = repository.context["served_prefix"]
        path = (*(os.fsencode(prefix).split(b"/") if prefix else ()), *page.path)
        found = await _working_tree_kind(repository.location, commit, path, page.logical)
    if found not in ("blob", "tree"):
        return found
    if not repository.pin_on_origin and not await _on_origin(repository, commit):
        return "not_on_origin"
    return RepositorySelection(kind=found, ref_and_path=(commit.encode("ascii"), *path))


async def _pinned_kind(
    page: _Page, pin: GitRevisionSubject
) -> Literal["blob", "tree"] | CounterpartReason:
    """What a pin's commit holds at *page*'s path, read through the pin's own tree reader."""

    from metabrowser.git.tree_source import GitPath

    if page.inside_file:
        return "missing"
    entry = await pin.tree_source.resolve_path(GitPath(page.path))
    if entry is None:
        return "missing"
    # A submodule's entry maps as a folder does, as the working tree's does.
    return "blob" if entry.is_blob else "tree"


async def _working_tree_kind(
    location: GitLocation, commit: str, path: tuple[bytes, ...], logical: str
) -> Literal["blob", "tree"] | CounterpartReason:
    """What ``HEAD``'s *commit* holds at *path*, and whether the working tree agrees.

    *path* is the repository path, *logical* the same item's path below the served root,
    which ``status`` reads it by. ``"blob"`` and ``"tree"`` map; anything else is why not.
    """

    kind = await _tree_kind(location, commit, path)
    if kind == "tree":
        return "tree"
    changes = await _status_codes(location, logical or ".")
    if kind == "blob":
        return "uncommitted" if changes else "blob"
    if any(code not in (b"??", b"!!") for code in changes):
        return "uncommitted"
    if b"??" in changes:
        return "untracked"
    if b"!!" in changes:
        return "ignored"
    return "missing"


async def _tree_kind(
    location: GitLocation, commit: str, path: tuple[bytes, ...]
) -> Literal["blob", "tree"] | None:
    """What *commit* holds at the repository path *path*: one ``ls-tree`` of that entry.

    A submodule's entry, a ``commit``, is a folder on disk and maps as one.
    """

    if not path:
        return "tree"
    wanted = b"/".join(path)
    out = await run_git_at(
        ["--literal-pathspecs", "ls-tree", "-z", "--full-tree", commit, "--", os.fsdecode(wanted)],
        location,
    )
    for record in out.split(b"\0"):
        meta, tab, name = record.partition(b"\t")
        if tab and name == wanted:
            return "blob" if meta.split(b" ")[1:2] == [b"blob"] else "tree"
    return None


async def _status_codes(location: GitLocation, pathspec: str) -> list[bytes]:
    """The two-letter ``status`` codes of the working tree at *pathspec*: one ``status``.

    ``??`` is untracked and ``!!`` ignored; any other code is a change the index or the
    working tree holds. An untracked or an ignored folder is one entry, so the output is a
    line per changed file at most. Read with no optional lock, so nothing is written, and
    with no ``core.fsmonitor`` program, which a checkout's configuration can name.
    """

    out = await run_git_at(
        [
            *GIT_NO_HOOK_ARGS,
            "--literal-pathspecs",
            "status",
            "--porcelain=v1",
            "-z",
            "--ignored=traditional",
            "--untracked-files=normal",
            "--",
            pathspec,
        ],
        location,
    )
    codes: list[bytes] = []
    fields = iter(out.split(b"\0"))
    for field in fields:
        if len(field) < 4:
            continue
        code = field[:2]
        codes.append(code)
        if b"R" in code or b"C" in code:
            # A rename or a copy names the path it came from in the next field.
            next(fields, None)
    return codes


async def _on_origin(repository: _Repository, commit: str) -> bool:
    """Whether a ref of origin reaches *commit*: one ``rev-list`` that prints it if not.

    *commit* is a full object ID, so it is never read as an option or as revision syntax.
    A commit the repository does not have is not known to be on origin.
    """

    if git_executable() is None:
        return False
    try:
        out = await run_git_at(
            ["rev-list", "-n", "1", commit, "--not", *repository.origin_refs, "--"],
            repository.location,
        )
    except GitCommandError as exc:
        log.debug("rev-list could not read %s: %s", commit, failure_detail(exc))
        return False
    return not out.strip()


async def api_counterpart(request: Request) -> JSONResponse:
    """``GET /api/counterpart?page=<page>`` -- *page*'s github.com counterpart, or why none."""

    page = request.query_params.get("page", "")
    if not page or len(page) > MAX_PAGE_CHARS:
        return JSONResponse(
            {
                "error": f'"page" is a page\'s address, at most {MAX_PAGE_CHARS} characters',
                "code": "invalid_request",
            },
            status_code=400,
        )
    try:
        answer = await page_counterpart(page, mirror_session(request.app))
    except GitError as exc:
        # Git's own text names local paths, so it is logged and only the code is answered.
        log.warning("counterpart: git failed: %s", failure_detail(exc))
        return JSONResponse(
            {"error": "git could not answer", "code": exc.code}, status_code=exc.http_status
        )
    return JSONResponse(dict(answer))


COUNTERPART_ROUTES: Final = [Route("/api/counterpart", api_counterpart)]


__all__ = [
    "COUNTERPART_ROUTES",
    "MAX_PAGE_CHARS",
    "PAGES",
    "REASONS",
    "Counterpart",
    "CounterpartAnswer",
    "CounterpartReason",
    "PageCounterpart",
    "PageKind",
    "api_counterpart",
    "page_counterpart",
]
