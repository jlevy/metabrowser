"""The github.com page that shows what a Metabrowser page shows: ``GET /api/counterpart``.

A page has a counterpart when the served repository is on github.com and github.com has
a page for the same thing: a repository, a file or a folder origin has, a pull
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
(:func:`~metabrowser.cache.providers.repository_context_for`). The provider that hosts
it names the URL, the link's label, and itself
(:func:`~metabrowser.cache.providers.counterpart_host_for`), so this module names no
provider; only GitHub's has one today (``builtin_plugins/github/urls.py``). It is
imported only once a repository is found, so a plain folder's server never loads it.

**Which commit a file or folder is at.** The one ``/api/file`` reads it from: a pin's
commit, or else the working tree.

- A mirror's pin is its commit. A mirror holds only its origin's commits.
- A revision of a checkout (``metab PATH --ref NAME``, or the ref selector) is its
  commit, when origin has that commit.
- The working tree is the newest commit origin has in ``HEAD``'s history: ``HEAD``'s
  own commit when origin has it, and otherwise its merge base with ``HEAD``'s upstream
  branch, or else with origin's default branch (``refs/remotes/origin/HEAD``), when
  origin has that. A file or a folder in ``HEAD``'s tree maps there when that commit has
  it too, so neither a file's local edits, staged or not, nor commits not yet pushed
  take a page's button away: it links to the version origin has, as a folder holding
  untracked or ignored files links to the folder origin has. A path that ``HEAD``
  lacks is ``uncommitted``, ``untracked``, ``ignored``, or ``missing`` by what the
  working tree holds there, and one that only commits origin lacks hold is
  ``not_on_origin``.

"Origin has it" means a ``refs/remotes/origin/*`` ref reaches the commit, as the
checkout last fetched it, and in a mirror any of its refs, which are all its origin's.
Nothing is fetched to ask. A named origin ref is used when it still contains the item.
Otherwise a file or folder uses its commit. A repository root uses the repository URL
for the default branch or without a named origin ref. A pull request's pages and the
list map whenever the repository is on github.com, and a commit's page when origin
has the commit.

A path's reason comes before its commit's, since an untracked file stays untracked once
its commit is pushed. Each question is one Git command, under the request-path
deadline and output bound of :mod:`metabrowser.git.process`: what the commit holds at
the path (``ls-tree``, or a pin's own tree reader), what the working tree holds at a
path ``HEAD`` lacks (``status``), whether origin has the commit (``rev-list``), and, for
a working tree whose ``HEAD`` origin lacks, each merge base (``merge-base``, then
``rev-list``) until origin has one, and what it holds at the path (``ls-tree``). For the
working tree, what ``HEAD`` holds and where origin's copy is are asked at once. With no
Git installed origin cannot be asked, and a page that needs it answers
``not_on_origin``.

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
    from metabrowser.cache.providers import CounterpartHost
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
    # The path is in the index only: staged, and in no commit. A file the index or the
    # working tree changes maps to the version origin has.
    "uncommitted",
    # The file or folder is not tracked; a folder the commit lacks holds an untracked
    # file.
    "untracked",
    # The file or folder is ignored; a folder the commit lacks holds nothing else.
    "ignored",
    # Origin is not known to have the commit the page shows: no ref of origin reaches it,
    # the repository lacks it, or no Git is installed to ask. For the working tree, only
    # commits origin lacks hold the path, or ``HEAD`` has no merge base origin has.
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
        "blob/<ref>/<repo path>",
        ("uncommitted", "untracked", "ignored", "missing", "not_on_origin"),
    ),
    "folder": PageCounterpart(
        "/view/<path>/",
        "tree/<ref>/<repo path>",
        ("uncommitted", "untracked", "ignored", "missing", "not_on_origin"),
    ),
    "root": PageCounterpart(
        "/view/",
        "tree/<ref>/<served prefix>, or repository URL or tree/<name> at the repository root",
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
_ORIGIN_REF_PREFIX: Final = "refs/remotes/origin/"
_LOCAL_BRANCH_PREFIX: Final = "refs/heads/"
_TAG_PREFIX: Final = "refs/tags/"

# What a working tree whose ``HEAD`` origin lacks maps at instead, in order: its merge
# base with ``HEAD``'s upstream branch, and with origin's default branch. An upstream can
# be another remote's branch or a local one, so origin is asked about each merge base.
# A detached ``HEAD`` has no upstream, and a clone made by ``git init`` and ``git fetch``
# has no ``origin/HEAD``; each is skipped then.
_MERGE_BASE_REFS: Final = ("HEAD@{upstream}", "refs/remotes/origin/HEAD")


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

    ``origin_refs`` are the ``rev-list`` arguments naming what origin has. The mirror
    records the origin's default branch and holds only its refs.
    """

    context: RepositoryContext
    location: GitLocation
    origin_refs: tuple[str, ...]
    pin: GitRevisionSubject | None
    mirror: MirrorSession | None


@dataclass(frozen=True, slots=True)
class _OriginRef:
    """A verified origin ref, its current commit, and its name in the web URL."""

    commit: str
    url_path: tuple[bytes, ...]
    default: bool = False


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
    # Imported once a repository is found, so a plain folder's server loads no provider
    # module (tests/test_plugin_public_api.py).
    from metabrowser.cache.providers import counterpart_host_for

    hosted = counterpart_host_for(repository.context)
    if hosted is None:
        # No provider hosts it, or its owner or name is not one the provider admits.
        return _none(page, "no_repository")
    host, clone_url = hosted
    selection = await _selection(parsed, repository, host)
    if isinstance(selection, str):
        return _none(page, selection)
    # The list of pull requests is the one page no selection names.
    url = host.pulls_url(clone_url) if selection is None else host.web_url(clone_url, selection)
    if url is None:
        return _none(page, "no_repository")
    return CounterpartAnswer(
        page=page,
        counterpart=Counterpart(provider=host.provider, label=host.label, url=url),
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
        return _Repository(context, GitLocation.filesystem(root), _CHECKOUT_ORIGIN_REFS, None, None)
    location = GitLocation.revision(pin.command_target, pin.commit_oid)
    checkout = checkout_revisions()
    if checkout is not None and checkout.serves(pin):
        context = await asyncio.to_thread(discover_repository_context, checkout.root)
        if context is None:
            return None
        return _Repository(context, location, _CHECKOUT_ORIGIN_REFS, pin, None)
    if mirror is None:
        return None
    from metabrowser.git.tree_source import ref_branch_name

    context = mirror.mirror.repository_context(
        revision=pin.commit_oid, branch=ref_branch_name(pin.ref)
    )
    if context is None:
        return None
    return _Repository(context, location, _MIRROR_ORIGIN_REFS, pin, mirror)


async def _selection(
    page: _Page, repository: _Repository, host: CounterpartHost
) -> RepositorySelection | CounterpartReason | None:
    """*page*'s counterpart as a selection, ``None`` for the list, or why it has none."""

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
                pull_file=host.file_anchor(page.path[0]),
            )
        case "commit" | "commit_file":
            if not await _on_origin(repository, page.commit):
                return "not_on_origin"
            anchor = host.file_anchor(page.path[0]) if page.kind == "commit_file" else None
            return RepositorySelection(kind="commit", commit=page.commit, pull_file=anchor)
        case "view":
            return await _item_selection(page, repository)


async def _item_selection(
    page: _Page, repository: _Repository
) -> RepositorySelection | CounterpartReason:
    """The published name of a view, or a commit for an item without a matching ref."""

    from metabrowser.cache.urls import RepositorySelection

    pin = repository.pin
    if not page.path and not page.inside_file and not repository.context["served_prefix"]:
        # The repo URL needs identity, not proof that origin has a private local commit.
        if (
            repository.mirror is not None
            and pin is not None
            and pin.ref is not None
            and pin.ref == await repository.mirror.mirror.default_ref()
        ):
            return RepositorySelection()
        named = await _origin_ref(repository, root=True)
        if named is None or named.default:
            return RepositorySelection()
        return RepositorySelection(kind="tree", ref_and_path=named.url_path)

    if pin is not None:
        kind = await _pinned_kind(page, pin)
        if kind not in ("blob", "tree"):
            return kind
        if repository.mirror is None and not await _on_origin(repository, pin.commit_oid):
            return "not_on_origin"
        commit = pin.commit_oid
        path = page.path
    else:
        if git_executable() is None:
            return "not_on_origin"
        prefix = repository.context["served_prefix"]
        path = (*(os.fsencode(prefix).split(b"/") if prefix else ()), *page.path)
        located = await _working_tree_item(repository, path, page.logical)
        if isinstance(located, str):
            return located
        commit, kind = located

    named = await _origin_ref(repository)
    if named is not None and (
        named.commit == commit or await _tree_kind(repository.location, named.commit, path) == kind
    ):
        return RepositorySelection(kind=kind, ref_and_path=(*named.url_path, *path))
    return RepositorySelection(kind=kind, ref_and_path=(commit.encode("ascii"), *path))


async def _origin_ref(repository: _Repository, *, root: bool = False) -> _OriginRef | None:
    """The hosted branch or tag selected by the view, as last fetched."""

    from metabrowser.cache.resolve import is_valid_ref_name

    if git_executable() is None:
        return None
    if repository.pin is None:
        branch = repository.context["branch"]
        ref = _LOCAL_BRANCH_PREFIX + branch if branch is not None else None
    else:
        ref = repository.pin.ref
    if ref is None or not is_valid_ref_name(ref):
        return None

    location = repository.location
    if ref.startswith(_LOCAL_BRANCH_PREFIX):
        branch = ref.removeprefix(_LOCAL_BRANCH_PREFIX)
        upstream = await _ref_value(
            location,
            [
                "rev-parse",
                "--symbolic-full-name",
                "--verify",
                "--quiet",
                "--end-of-options",
                f"{branch}@{{upstream}}",
            ],
        )
        ref = upstream or _ORIGIN_REF_PREFIX + branch
    if ref == _ORIGIN_REF_PREFIX + "HEAD":
        ref = await _ref_value(location, ["symbolic-ref", "--quiet", ref]) or ""
    if ref.startswith(_ORIGIN_REF_PREFIX):
        return await _origin_branch(
            location, ref, include_default=root and repository.mirror is None
        )
    if repository.mirror is not None and ref.startswith(_TAG_PREFIX):
        tip = await _ref_value(
            location, ["rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}"]
        )
        if tip is not None and is_full_revision(tip):
            return _OriginRef(tip, tuple(os.fsencode(ref).split(b"/")))
    return None


async def _origin_branch(
    location: GitLocation, ref: str, *, include_default: bool
) -> _OriginRef | None:
    """Read the branch, its same-named tag, and optionally origin HEAD together."""

    name = ref.removeprefix(_ORIGIN_REF_PREFIX)
    tag = _TAG_PREFIX + name
    head = _ORIGIN_REF_PREFIX + "HEAD"
    wanted = [ref, tag, *([head] if include_default else [])]
    lines = await _ref_value(
        location,
        ["for-each-ref", "--count=8", "--format=%(refname)%00%(objectname)%00%(symref)", *wanted],
    )
    refs = {}
    for line in (lines or "").splitlines():
        fields = line.split("\0")
        if len(fields) == 3 and fields[0] in wanted:
            refs[fields[0]] = (fields[1], fields[2])
    tip, _symbolic = refs.get(ref, ("", ""))
    if not is_full_revision(tip):
        return None
    url_path = tuple(os.fsencode(name).split(b"/"))
    if (
        tag in refs
        or url_path[:2] in ((b"refs", b"heads"), (b"refs", b"tags"))
        or is_full_revision(name)
    ):
        url_path = (b"refs", b"heads", *url_path)
    return _OriginRef(tip, url_path, default=refs.get(head, ("", ""))[1] == ref)


async def _ref_value(location: GitLocation, args: list[str]) -> str | None:
    """Read an optional ref or its tip without fetching."""

    try:
        raw = await run_git_at(args, location)
    except GitCommandError as exc:
        log.debug("counterpart ref not available: %s", failure_detail(exc))
        return None
    return os.fsdecode(raw).strip() or None


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


async def _working_tree_item(
    repository: _Repository, path: tuple[bytes, ...], logical: str
) -> tuple[str, Literal["blob", "tree"]] | CounterpartReason:
    """The commit origin has that a working tree's item maps at, and what it is there.

    *path* is the repository path, *logical* the same item's path below the served root,
    which ``status`` reads it by. The item maps when ``HEAD``'s commit has it and so does
    :func:`_origin_base`'s commit, whatever the index and the working tree hold.
    """

    location = repository.location
    head = repository.context["revision"]
    # Asked at once, since neither answer waits for the other: a file's page was answered
    # in 34 ms asked one after the other and 19 ms asked at once, medians of 3 and 5 on a
    # machine at a load average near 8 (2026-11-18), and the button waits for the answer.
    kind, base = await asyncio.gather(
        _tree_kind(location, head, path), _origin_base(repository, head)
    )
    if kind is None:
        return await _absent_reason(location, logical)
    if base is None:
        return "not_on_origin"
    if base != head:
        kind = await _tree_kind(location, base, path)
        if kind is None:
            # Added by a commit origin does not have yet.
            return "not_on_origin"
    return base, kind


async def _origin_base(repository: _Repository, head: str) -> str | None:
    """The newest commit origin has in *head*'s history, or ``None`` when none is found.

    *head* itself when origin has it, and otherwise the first merge base of
    :data:`_MERGE_BASE_REFS` that origin has.
    """

    if await _on_origin(repository, head):
        return head
    for ref in _MERGE_BASE_REFS:
        try:
            out = await run_git_at(["merge-base", head, ref], repository.location)
        except GitCommandError as exc:
            # No such branch, no upstream, a detached HEAD, or histories with no common
            # commit (exit status 1).
            log.debug("merge-base with %s: %s", ref, failure_detail(exc))
            continue
        base = out.decode("ascii", errors="replace").strip()
        if is_full_revision(base) and await _on_origin(repository, base):
            return base
    return None


async def _absent_reason(location: GitLocation, logical: str) -> CounterpartReason:
    """Why a path ``HEAD``'s commit lacks has no counterpart, by the working tree there."""

    changes = await _status_codes(location, logical or ".")
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
