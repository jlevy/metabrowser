"""The GitHub URL reducer: web, raw, and SSH spellings of one repository.

It claims only ``github.com`` (with or without ``www.``) and
``raw.githubusercontent.com``, and turns a claimed URL into the canonical
``https://github.com/<owner>/<repo>`` clone URL plus a
:class:`~metabrowser.cache.urls.RepositorySelection` naming what the URL pointed at:

| URL | Selection |
| --- | --- |
| ``github.com/<o>/<r>`` (``.git``, trailing slash, ``www.``) | repository |
| ``…/tree/<ref-and-path>`` | tree |
| ``…/blob/<ref-and-path>[#L10][#L10-L20][#L10C5-L20C8]`` (``?plain=1`` kept) | blob |
| ``…/commit/<oid>``, ``…/pull/<n>/commits/<oid>`` | commit |
| ``…/pull/<n>[/files|/commits]`` | pull request |
| ``raw.githubusercontent.com/<o>/<r>/<ref-and-path>`` | blob |
| ``git@github.com:<o>/<r>.git``, ``ssh://git@github.com/<o>/<r>.git`` (``www.``) | repository |

Every other ``github.com`` path, ``http://``, and a reserved owner is refused with a
reason and a message that names the shape and offers the repository URL. Exactly one
trailing ``.git`` is removed from the repository name. The generic
grammar never sees a claimed URL, so this module repeats its control-character,
non-ASCII, backslash, and credentials checks before anything else. Query parameters
other than ``plain=1`` and fragments other than a line anchor are dropped, and no
refusal repeats the argument.

A web URL is read as a browser sends it. A person pastes the decoded form an address
bar shows, such as ``…/docs/雪.md`` or ``…/space name.md``, and a browser sends a
space or a character outside ASCII in a path, query, or fragment percent-encoded as
UTF-8 (the WHATWG URL Standard's path, query, and fragment percent-encode sets); GitHub
answers both spellings alike, so both open the same selection. A character that cannot
be seen, or that a reader cannot tell apart from a space, is still refused, since a
name holding one passes for another (``README<U+3164>.md`` reads as ``README.md``):
controls, whitespace other than a space, format characters such as bidirectional
overrides, default-ignorable characters such as fillers and variation selectors, the
blank braille pattern, and unassigned and private-use code points; so is a trailing
space, which a browser strips, and a ``%`` that starts no percent escape, which a
browser leaves for the server to read. Every character refusal names the code point
and, in a web URL's path, query, or fragment, the encoded spelling to use if the
character belongs in the address. SSH addresses are not browser URLs and keep the
generic checks.

Which code points are unassigned is the running Python's Unicode database: one assigned
in a later Unicode version is refused under an older Python until it is written
percent-encoded.
"""

from __future__ import annotations

import re
import string
import unicodedata
from dataclasses import dataclass, replace
from typing import Final

from metabrowser.cache.urls import (
    LineSelection,
    ReducerOutcome,
    ReducerRejection,
    RepositorySelection,
)
from metabrowser.invisible_chars import is_invisible

CANONICAL_HOST: Final = "github.com"
_WEB_HOSTS: Final = frozenset({"github.com", "www.github.com"})
_RAW_HOST: Final = "raw.githubusercontent.com"

_SCHEME = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*)://")
_SCP = re.compile(r"^(?P<user>[^@/:]+)@(?P<host>[^/:]+):(?P<path>.*)$", re.DOTALL)
OWNER = re.compile(r"^[A-Za-z0-9-]{1,39}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_PULL_REQUEST = re.compile(r"^[1-9][0-9]{0,9}$")
# The resolver's own bound: seven hexadecimal digits is the shortest commit ID Git
# abbreviates to by default and the shortest GitHub shows.
_COMMIT_ID = re.compile(r"^[0-9A-Fa-f]{7,64}$")
_LINE_ANCHOR = re.compile(
    r"^L([1-9][0-9]{0,8})(?:C([1-9][0-9]{0,8}))?(?:-L([1-9][0-9]{0,8})(?:C([1-9][0-9]{0,8}))?)?$"
)
_HEX: Final = frozenset(string.hexdigits)

# Top-level github.com pages whose first path segment would otherwise read as an owner.
# GitHub does not allow an account with these names.
RESERVED_OWNERS: Final[frozenset[str]] = frozenset(
    {
        "about",
        "account",
        "apps",
        "blog",
        "business",
        "codespaces",
        "collections",
        "contact",
        "copilot",
        "customer-stories",
        "dashboard",
        "enterprise",
        "enterprises",
        "events",
        "explore",
        "features",
        "github-copilot",
        "issues",
        "join",
        "login",
        "logout",
        "marketplace",
        "new",
        "notifications",
        "organizations",
        "orgs",
        "pricing",
        "pulls",
        "readme",
        "search",
        "security",
        "sessions",
        "settings",
        "signup",
        "site",
        "sponsors",
        "stars",
        "team",
        "topics",
        "trending",
        "users",
        "watching",
    }
)

# Repository pages this reducer refuses by name. A segment outside this set is not
# echoed, since a path segment of a refused URL is still the user's text.
_NAMED_PAGES: Final[frozenset[str]] = frozenset(
    {
        "actions",
        "activity",
        "archive",
        "blame",
        "branches",
        "commits",
        "compare",
        "contributors",
        "deployments",
        "discussions",
        "edit",
        "find",
        "forks",
        "graphs",
        "issues",
        "labels",
        "milestones",
        "network",
        "packages",
        "projects",
        "pulls",
        "pulse",
        "raw",
        "releases",
        "search",
        "security",
        "settings",
        "stargazers",
        "tags",
        "watchers",
        "wiki",
    }
)


def repository_url(owner: str, repository: str) -> str:
    """The canonical clone and identity URL: lowercase, no ``.git``."""

    return f"https://{CANONICAL_HOST}/{owner.lower()}/{repository.lower()}"


class _Refuse(Exception):
    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True, slots=True)
class _Claimed:
    """A URL whose host this reducer owns, split but not yet validated.

    ``authority`` is the text between ``//`` and the path, as given.
    """

    scheme: str
    authority: str
    userinfo: str | None
    host: str
    port: str | None
    path: str
    query: str
    fragment: str

    @property
    def web(self) -> bool:
        """A URL a browser opens, as opposed to an SSH address."""

        return self.scheme in {"https", "http"}


def _split_url(value: str) -> _Claimed | None:
    match = _SCHEME.match(value)
    if match is not None:
        scheme = match.group(1).lower()
        rest = value[match.end() :]
        cut = min((index for index in (rest.find(c) for c in "/?#") if index >= 0), default=-1)
        authority, tail = (rest, "") if cut < 0 else (rest[:cut], rest[cut:])
        userinfo: str | None = None
        hostport = authority
        if "@" in authority:
            userinfo, _, hostport = authority.rpartition("@")
        host, separator, port = hostport.partition(":")
        host = host.lower()
        owned = host in _WEB_HOSTS or host == _RAW_HOST
        if scheme == "ssh":
            owned = host in _WEB_HOSTS
        if not owned or scheme not in {"https", "http", "ssh"}:
            return None
        before_fragment, _, fragment = tail.partition("#")
        path, _, query = before_fragment.partition("?")
        return _Claimed(
            scheme, authority, userinfo, host, port if separator else None, path, query, fragment
        )
    scp = _SCP.match(value)
    if scp is None or scp.group("host").lower() not in _WEB_HOSTS:
        return None
    authority = f"{scp.group('user')}@{scp.group('host')}"
    return _Claimed(
        "scp", authority, scp.group("user"), CANONICAL_HOST, None, scp.group("path"), "", ""
    )


def _escaped(ch: str) -> str:
    """*ch* percent-encoded as UTF-8, as a browser sends it."""

    return "".join(f"%{byte:02X}" for byte in ch.encode())


def _refusal(ch: str, *, encodable: bool) -> _Refuse | None:
    """Why *ch* may not appear raw in the URL, or ``None`` when it may.

    *encodable* is true in a web URL's path, query, and fragment, where a space and a
    visible character outside ASCII are sent percent-encoded; elsewhere both are refused,
    as the generic grammar refuses them.
    """

    point = f"U+{ord(ch):04X}"
    if ch == " ":
        if encodable:
            return None
        return _Refuse("control_or_whitespace", f"the URL contains {point}, a space")
    if ord(ch) < 0x20 or ord(ch) == 0x7F:
        return _Refuse("control_or_whitespace", f"the URL contains {point}, a control character")
    if ord(ch) < 0x7F:
        return None
    category = unicodedata.category(ch)
    if category == "Cs":
        # An argument that is not UTF-8 reaches Python as lone surrogates.
        return _Refuse("non_ascii", "the URL is not valid UTF-8")
    code = "control_or_whitespace" if ch.isspace() else "non_ascii"
    if category == "Cc":
        return _Refuse(code, f"the URL contains {point}, a control character")
    if ch.isspace():
        kind = "a whitespace character"
    elif not encodable:
        kind = "a character outside ASCII"
    elif category == "Cf" or is_invisible(ch):
        kind = "an invisible character"
    elif category == "Cn":
        kind = "an unassigned character"
    elif category == "Co":
        kind = "a private-use character"
    else:
        return None
    detail = f"the URL contains {point}, {kind}"
    if encodable:
        detail += f"; if it belongs in the address, write it as {_escaped(ch)}"
    return _Refuse(code, detail)


def _common_checks(value: str, claimed: _Claimed) -> None:
    """The generic grammar's character checks, which a claimed URL never reaches.

    A web URL's path, query, and fragment may also hold a space, other than a trailing
    one, and a visible character outside ASCII: :func:`_browser_encoded` sends them as
    a browser does.
    """

    strict = claimed.authority if claimed.web else value
    tail = claimed.path + claimed.query + claimed.fragment if claimed.web else ""
    for text, encodable in ((strict, False), (tail, True)):
        for ch in text:
            if (refused := _refusal(ch, encodable=encodable)) is not None:
                raise refused
    if value.endswith(" "):
        raise _Refuse("control_or_whitespace", "the URL ends with a space; remove it")
    if "\\" in value:
        raise _Refuse("backslash", "the URL contains a backslash")


def _browser_encoded(claimed: _Claimed) -> _Claimed:
    """*claimed* with each space and character outside ASCII percent-encoded as UTF-8.

    What a browser sends for the path, query, and fragment a person pasted, so the raw
    and the encoded spelling of one URL reduce to the same selection.
    """

    def encode(text: str) -> str:
        return "".join(_escaped(ch) if ch == " " or ord(ch) > 0x7F else ch for ch in text)

    return replace(
        claimed,
        path=encode(claimed.path),
        query=encode(claimed.query),
        fragment=encode(claimed.fragment),
    )


def _segments(path: str) -> list[str]:
    parts = path.split("/")
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    if any(part == "" for part in parts):
        raise _Refuse("empty_path_segment", "the URL path has an empty segment")
    return parts


def _reserved(owner: str, host: str) -> _Refuse:
    if host == _RAW_HOST:
        return _Refuse("reserved_owner", f"{owner.lower()} is a GitHub page name, not an account")
    return _Refuse(
        "reserved_owner", f"github.com/{owner.lower()} is a GitHub page, not a repository"
    )


def _owner_and_repository(parts: list[str], *, host: str = CANONICAL_HOST) -> tuple[str, str]:
    """Validate the first two segments; the caller has checked there are two.

    Exactly one trailing ``.git`` is removed, in any letter case, because Git clients
    append one to a repository URL; the repository ``demo.git.git`` is ``demo.git``.
    """

    owner, repository = parts[0], parts[1]
    if owner.lower() in RESERVED_OWNERS:
        raise _reserved(owner, host)
    if not OWNER.match(owner):
        raise _Refuse("invalid_owner", "the owner is not a GitHub account name")
    if repository.lower().endswith(".git"):
        repository = repository[:-4]
    if repository in {"", ".", ".."} or not REPOSITORY.match(repository):
        raise _Refuse("invalid_repository", "the repository name is not a GitHub repository name")
    return owner, repository


def _decode_segment(segment: str) -> bytes:
    out = bytearray()
    index = 0
    while index < len(segment):
        ch = segment[index]
        if ch == "%":
            digits = segment[index + 1 : index + 3]
            if len(digits) != 2 or not set(digits) <= _HEX:
                # A browser leaves such a % as it is and the server decides what it means;
                # a literal one is %25, which GitHub's own links use.
                raise _Refuse(
                    "invalid_percent_encoding",
                    "the URL has a % not followed by two hexadecimal digits; "
                    "write a literal % as %25",
                )
            byte = int(digits, 16)
            if byte < 0x20 or byte == 0x7F:
                raise _Refuse("control_or_whitespace", "the URL path encodes a control character")
            if byte in b"/\\":
                raise _Refuse("encoded_delimiter", "the URL path encodes a path separator")
            out.append(byte)
            index += 3
            continue
        out.append(ord(ch))
        index += 1
    decoded = bytes(out)
    if decoded in {b".", b".."}:
        raise _Refuse("dot_segment", "the URL path has a '.' or '..' segment")
    return decoded


def _lines(fragment: str) -> LineSelection | None:
    """A GitHub line anchor, or ``None`` for any other fragment, which is dropped."""

    match = _LINE_ANCHOR.fullmatch(fragment)
    if match is None:
        return None
    start = int(match.group(1))
    start_column = int(match.group(2)) if match.group(2) else None
    end = int(match.group(3)) if match.group(3) else start
    end_column = int(match.group(4)) if match.group(4) else None
    if end < start:
        start, end, start_column, end_column = end, start, end_column, start_column
    elif end == start and start_column and end_column and end_column < start_column:
        start_column, end_column = end_column, start_column
    return LineSelection(start=start, end=end, start_column=start_column, end_column=end_column)


def _plain(query: str) -> bool:
    return any(pair == "plain=1" for pair in query.split("&"))


def _unsupported(page: str | None, repo_url: str) -> _Refuse:
    shape = f"GitHub {page} pages are" if page in _NAMED_PAGES else "this GitHub page is"
    return _Refuse(
        "unsupported_github_url",
        f"{shape} not opened; open the repository at {repo_url}",
    )


def _repository_selection(
    rest: list[str], query: str, fragment: str, repo_url: str
) -> RepositorySelection:
    if not rest:
        return RepositorySelection()
    page, args = rest[0], rest[1:]
    if page == "tree":
        if not args:
            raise _Refuse("unsupported_github_url", f"a tree URL names a ref; open {repo_url}")
        return RepositorySelection(
            kind="tree", ref_and_path=tuple(_decode_segment(part) for part in args)
        )
    if page == "blob":
        if len(args) < 2:
            raise _Refuse(
                "unsupported_github_url", f"a blob URL names a ref and a file; open {repo_url}"
            )
        return RepositorySelection(
            kind="blob",
            ref_and_path=tuple(_decode_segment(part) for part in args),
            lines=_lines(fragment),
            plain=_plain(query),
        )
    if page == "commit":
        if len(args) != 1:
            raise _unsupported(None, repo_url)
        return RepositorySelection(kind="commit", commit=_commit_id(args[0], repo_url))
    if page == "pull":
        return _pull_selection(args, repo_url)
    raise _unsupported(page, repo_url)


def _commit_id(text: str, repo_url: str) -> str:
    if not _COMMIT_ID.match(text):
        raise _Refuse(
            "invalid_commit_id",
            "a commit URL names a commit ID of 7 to 64 hexadecimal digits; "
            f"open the repository at {repo_url}",
        )
    return text.lower()


def _pull_selection(args: list[str], repo_url: str) -> RepositorySelection:
    if not args or not _PULL_REQUEST.match(args[0]):
        raise _Refuse(
            "invalid_pull_request",
            f"a pull request URL names a positive number; open the repository at {repo_url}",
        )
    number = int(args[0])
    tail = args[1:]
    if tail in ([], ["files"], ["commits"]):
        return RepositorySelection(kind="pull_request", pull_request=number)
    if len(tail) == 2 and tail[0] == "commits":
        return RepositorySelection(
            kind="commit", commit=_commit_id(tail[1], repo_url), pull_request=number
        )
    raise _unsupported(None, repo_url)


def _reduce_claimed(value: str, claimed: _Claimed) -> ReducerOutcome:
    _common_checks(value, claimed)
    if claimed.web:
        claimed = _browser_encoded(claimed)
    if claimed.web and claimed.userinfo is not None:
        raise _Refuse("credentials_in_url", "the URL carries credentials")
    if claimed.scheme in {"ssh", "scp"}:
        if claimed.userinfo is not None and ":" in claimed.userinfo:
            raise _Refuse("credentials_in_url", "the URL carries credentials")
        if claimed.userinfo != "git":
            raise _Refuse("invalid_user", "GitHub's SSH address uses the user git")
    parts = _segments(claimed.path)
    if claimed.scheme == "http":
        try:
            offer = repository_url(*_owner_and_repository(parts))
        except (_Refuse, IndexError):
            offer = "https://github.com/<owner>/<repository>"
        raise _Refuse("insecure_http", f"GitHub is opened over https; use {offer}")
    if not parts:
        raise _Refuse(
            "unsupported_github_url",
            "github.com itself is not a repository; open https://github.com/<owner>/<repository>",
        )
    if len(parts) == 1:
        owner = parts[0]
        if owner.lower() in RESERVED_OWNERS:
            raise _reserved(owner, claimed.host)
        if claimed.host == _RAW_HOST:
            raise _Refuse(
                "unsupported_github_url",
                "a raw URL names an owner, a repository, a ref, and a file",
            )
        if OWNER.match(owner):
            raise _Refuse(
                "unsupported_github_url",
                f"github.com/{owner} is an account page, not a repository",
            )
        raise _Refuse("invalid_owner", "the owner is not a GitHub account name")
    raw = claimed.host == _RAW_HOST
    owner, repository = _owner_and_repository(parts, host=claimed.host)
    repo_url = repository_url(owner, repository)
    standard_port = "22" if claimed.scheme == "ssh" else "443"
    if claimed.port not in {None, "", standard_port}:
        raise _Refuse("unsupported_port", f"GitHub answers on its standard port; use {repo_url}")
    rest = parts[2:]
    if claimed.scheme in {"ssh", "scp"}:
        if rest:
            raise _unsupported(None, repo_url)
        return ReducerOutcome(clone_url=repo_url)
    if raw:
        if len(rest) < 2:
            raise _Refuse(
                "unsupported_github_url", f"a raw URL names a ref and a file; open {repo_url}"
            )
        selection = RepositorySelection(
            kind="blob", ref_and_path=tuple(_decode_segment(part) for part in rest)
        )
        return ReducerOutcome(clone_url=repo_url, selection=selection)
    selection = _repository_selection(rest, claimed.query, claimed.fragment, repo_url)
    return ReducerOutcome(clone_url=repo_url, selection=selection)


class GithubUrlReducer:
    """The installed :class:`~metabrowser.cache.urls.ProviderUrlReducer` for GitHub."""

    def reduce(self, value: str) -> ReducerOutcome | ReducerRejection | None:
        claimed = _split_url(value)
        if claimed is None:
            return None
        try:
            return _reduce_claimed(value, claimed)
        except _Refuse as refused:
            return ReducerRejection(refused.reason, refused.detail)


def parse_repository_url(url: str) -> tuple[str, str] | None:
    """``(owner, repository)`` of a canonical GitHub repository URL, else ``None``."""

    prefix = f"https://{CANONICAL_HOST}/"
    if not url.startswith(prefix):
        return None
    parts = url[len(prefix) :].split("/")
    if len(parts) != 2 or not OWNER.match(parts[0]) or not REPOSITORY.match(parts[1]):
        return None
    if parts[1] in {".", ".."}:
        return None
    return parts[0], parts[1]


__all__ = [
    "CANONICAL_HOST",
    "RESERVED_OWNERS",
    "GithubUrlReducer",
    "parse_repository_url",
    "repository_url",
]
