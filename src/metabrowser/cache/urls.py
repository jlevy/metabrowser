"""Classify a CLI root argument before any ``Path`` is constructed.

The grammar is frozen in ``tests/fixtures/repository-cache/url-grammar.json`` and
replayed against :func:`classify_root_argument`. A local path stays a local path:
``metab /srv/git/repo.git`` serves that directory. Acquisition is requested only with an
explicit ``https``, ``ssh``, or ``file://`` Git source. ``file://`` is the pack
transport; a bare path is never rewritten into one.

Installed provider reducers run first. This module arbitrates their claims and then
applies the generic grammar to every input no reducer reduced. No GitHub reducer ships
here; overlapping claims fail discovery rather than guessing.
"""

from __future__ import annotations

import re
import string
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal, Protocol

from metabrowser.cache.identity import GitTransport

DEFAULT_PORTS: Final[dict[str, str]] = {"https": "443", "ssh": "22"}
GIT_SOURCE_SCHEMES: Final[frozenset[str]] = frozenset({"https", "ssh", "file"})

_SCHEME = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*)://")
_HELPER = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*::")
_MALFORMED = re.compile(r"^(?:https|ssh|file|http|git):(?!//)", re.IGNORECASE)
_SCP = re.compile(
    r"^(?P<user>[^@/:\[\]]+)@(?P<host>\[[^\]/]*\]|[^/:\[\]]*):(?P<path>.*)$", re.DOTALL
)
_LABEL = r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
_REG_NAME = re.compile(rf"^{_LABEL}(?:\.{_LABEL})*$")
_IPV6 = re.compile(r"^\[[0-9a-f:.]+\]$")
_USER = re.compile(r"^[A-Za-z0-9._~-]+$")
_UNRESERVED = frozenset(string.ascii_letters + string.digits + "-._~")
_PCHAR = _UNRESERVED | frozenset("!$&'()*+,;=:@")
_HEX = frozenset(string.hexdigits)


class _Reject(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ReducerArbitrationError(RuntimeError):
    """Two or more installed reducers claimed the same root argument."""


@dataclass(frozen=True, slots=True)
class RepositorySelection:
    """Inert path or line a provider reducer may attach.

    Empty until URL-open consumes it. The generic grammar never invents a selection.
    """

    path: str | None = None
    line: str | None = None


@dataclass(frozen=True, slots=True)
class ReducerOutcome:
    """A provider reducer's claim: a clone URL plus an optional selection."""

    clone_url: str
    selection: RepositorySelection = RepositorySelection()


class ProviderUrlReducer(Protocol):
    """Installed classifier that recognizes one provider's web URL spellings."""

    def reduce(self, value: str) -> ReducerOutcome | None:
        """Return a claim, or ``None`` when this reducer does not recognize *value*."""


@dataclass(frozen=True, slots=True)
class GitSource:
    """A credential-free Git acquisition source."""

    transport: GitTransport
    form: Literal["url", "scp"]
    normalized: str


@dataclass(frozen=True, slots=True)
class LocalPath:
    """A filesystem root to serve. The original argument is kept for Path construction."""

    value: str


@dataclass(frozen=True, slots=True)
class RejectedRoot:
    """A root argument the grammar refuses, named by the fixture's closed reason set."""

    reason: str


type RootClassification = GitSource | LocalPath | RejectedRoot


def classification_as_fixture(classification: RootClassification) -> dict[str, str]:
    """Project a classification into the url-grammar fixture's expected object."""
    match classification:
        case GitSource(transport=transport, form=form, normalized=normalized):
            return {
                "outcome": "git_source",
                "transport": transport,
                "form": form,
                "normalized": normalized,
            }
        case LocalPath():
            return {"outcome": "local_path"}
        case RejectedRoot(reason=reason):
            return {"outcome": "rejected", "reason": reason}


def _common_checks(value: str) -> None:
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F or ch.isspace() for ch in value):
        raise _Reject("control_or_whitespace")
    if any(ord(ch) > 0x7F for ch in value):
        raise _Reject("non_ascii")
    if "\\" in value:
        raise _Reject("backslash")
    if "?" in value:
        raise _Reject("query_not_allowed")
    if "#" in value:
        raise _Reject("fragment_not_allowed")


def _host(host: str) -> str:
    if host == "":
        raise _Reject("missing_host")
    if host.startswith("-"):
        raise _Reject("option_like")
    folded = host.lower()
    pattern = _IPV6 if folded.startswith("[") else _REG_NAME
    if not pattern.match(folded):
        raise _Reject("invalid_host")
    return folded


def _user(user: str) -> str:
    if user.startswith("-"):
        raise _Reject("option_like")
    if not _USER.match(user):
        raise _Reject("invalid_user")
    return user


def _segment(segment: str, *, percent: bool) -> str:
    out: list[str] = []
    index = 0
    while index < len(segment):
        ch = segment[index]
        if ch == "%":
            if not percent:
                raise _Reject("invalid_path_character")
            digits = segment[index + 1 : index + 3]
            if len(digits) != 2 or not set(digits) <= _HEX:
                raise _Reject("invalid_percent_encoding")
            byte = int(digits, 16)
            if byte <= 0x20 or byte == 0x7F:
                raise _Reject("control_or_whitespace")
            if chr(byte) in "/\\":
                raise _Reject("encoded_delimiter")
            out.append(chr(byte) if chr(byte) in _UNRESERVED else "%" + digits.upper())
            index += 3
            continue
        if ch not in _PCHAR:
            raise _Reject("invalid_path_character")
        out.append(ch)
        index += 1
    result = "".join(out)
    if result in {".", ".."}:
        raise _Reject("dot_segment")
    return result


def _path(path: str, *, strip_trailing: bool, percent: bool) -> str:
    segments = path.split("/")
    leading = segments[0] == ""
    if leading:
        segments = segments[1:]
    if segments and segments[-1] == "" and strip_trailing:
        segments = segments[:-1]
    trailing = bool(segments) and segments[-1] == ""
    body = segments[:-1] if trailing else segments
    if not body:
        raise _Reject("missing_repository_path")
    if any(segment == "" for segment in body):
        raise _Reject("empty_path_segment")
    normalized = [_segment(segment, percent=percent) for segment in body]
    return ("/" if leading else "") + "/".join(normalized) + ("/" if trailing else "")


def _classify_grammar(value: str, defaults: Mapping[str, str]) -> RootClassification:
    """The frozen root-argument grammar, in the fixture's declared check order."""
    if value == "":
        return RejectedRoot("empty")
    if value.startswith("-"):
        return RejectedRoot("option_like")
    if _HELPER.match(value):
        return RejectedRoot("remote_helper_syntax")
    scheme_match = _SCHEME.match(value)
    if scheme_match is None:
        if _MALFORMED.match(value):
            return RejectedRoot("malformed_url")
        scp = _SCP.match(value)
        if scp is None:
            return LocalPath(value)
        try:
            _common_checks(value)
            user = _user(scp.group("user"))
            host = _host(scp.group("host"))
            path = scp.group("path")
            if path.startswith("-"):
                raise _Reject("option_like")
            if path in {"", "/"}:
                raise _Reject("missing_repository_path")
            normalized_path = _path(path, strip_trailing=False, percent=False)
        except _Reject as rejected:
            return RejectedRoot(rejected.reason)
        return GitSource(
            transport="ssh",
            form="scp",
            normalized=f"{user}@{host}:{normalized_path}",
        )
    scheme = scheme_match.group(1).lower()
    if scheme not in GIT_SOURCE_SCHEMES:
        return RejectedRoot("unsupported_transport")
    try:
        _common_checks(value)
        rest = value[scheme_match.end() :]
        authority, slash, tail = rest.partition("/")
        path = slash + tail
        userinfo: str | None = None
        hostport = authority
        if "@" in authority:
            userinfo, _, hostport = authority.rpartition("@")
        if scheme == "file":
            if userinfo is not None or hostport.lower() not in {"", "localhost"}:
                raise _Reject("file_authority_not_local")
            prefix = "file://"
        else:
            if userinfo is not None and (scheme == "https" or ":" in userinfo):
                raise _Reject("credentials_in_url")
            user = _user(userinfo) if userinfo is not None else None
            if hostport.startswith("["):
                close = hostport.find("]")
                if close < 0:
                    raise _Reject("invalid_host")
                host_text, after = hostport[: close + 1], hostport[close + 1 :]
                if after and not after.startswith(":"):
                    raise _Reject("invalid_host")
                port: str | None = after[1:] if after else None
            else:
                host_text, separator, port_text = hostport.partition(":")
                port = port_text if separator else None
            host = _host(host_text)
            if port == "":
                port = None
            if port is not None:
                if not (port.isascii() and port.isdigit()) or port.startswith("0"):
                    raise _Reject("invalid_port")
                if not 1 <= int(port) <= 65535:
                    raise _Reject("invalid_port")
                if port == defaults[scheme]:
                    port = None
            prefix = (
                f"{scheme}://" + (f"{user}@" if user else "") + host + (f":{port}" if port else "")
            )
        if path in {"", "/"}:
            raise _Reject("missing_repository_path")
        normalized_path = _path(path, strip_trailing=scheme != "ssh", percent=True)
    except _Reject as rejected:
        return RejectedRoot(rejected.reason)
    transport: GitTransport = (
        "file" if scheme == "file" else "https" if scheme == "https" else "ssh"
    )
    return GitSource(
        transport=transport,
        form="url",
        normalized=prefix + normalized_path,
    )


def classify_root_argument(
    value: str,
    *,
    defaults: Mapping[str, str] | None = None,
    reducers: Sequence[ProviderUrlReducer] = (),
) -> RootClassification:
    """Classify *value* as a Git source, a local path, or a named rejection.

    Reducers that claim *value* run first. Exactly one claim replaces the input with
    that clone URL before the generic grammar runs. Two claims are a discovery error,
    not a user-facing rejection.
    """
    ports = DEFAULT_PORTS if defaults is None else defaults
    claims = [outcome for reducer in reducers if (outcome := reducer.reduce(value)) is not None]
    if len(claims) > 1:
        raise ReducerArbitrationError(f"{len(claims)} provider URL reducers claimed {value!r}")
    if len(claims) == 1:
        return _classify_grammar(claims[0].clone_url, ports)
    return _classify_grammar(value, ports)
