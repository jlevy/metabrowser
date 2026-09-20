"""Source identity, repository-store identity, and cache slugs.

The rules are frozen in ``tests/fixtures/repository-cache/source-identity.json`` and
replayed against these functions. Every input is already the normalized, credential-free
address the root-argument grammar produces; parsing and normalizing a root argument is
the URL classifier's job, not this module's.

- A source identity is a SHA-256 digest of a domain, the transport, and the normalized
  address, joined with NUL. Transport is part of the material, so an HTTPS and an SSH
  spelling of one hosted repository are two sources until a provider binding attaches
  both to one store.
- A generic store identity digests the source identity and the object format observed
  during acquisition, so two concurrent acquisitions of one source converge on one store.
  A provider store identity is domain-separated from every generic one and carries no
  authorization context.
- A store key is all 64 hexadecimal digits of its identity, so store directories cannot
  collide.
- A slug is a readable, lowercase ASCII prefix plus the shortest digest suffix no other
  source has claimed. It is recorded in ``source.yml`` at creation and never recomputed.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from typing import Final, Literal
from urllib.parse import unquote_to_bytes

type GitTransport = Literal["https", "ssh", "file"]
type ObjectFormat = Literal["sha1", "sha256"]

SOURCE_IDENTITY_DOMAIN: Final = "metabrowser.repository-source.v1"
STORE_IDENTITY_DOMAIN: Final = "metabrowser.repository-store.v1"
IDENTITY_PREFIX: Final = "sha256:"
STORE_KEY_HEX_DIGITS: Final = 64

# The bound the record and its packaged schema hold `display_url` and `clone_url` to.
# Deriving an identity from an address no record could carry would publish an entry that
# can be created and never read back, so both refuse the same addresses.
SOURCE_ADDRESS_MAX_BYTES: Final = 2048

SLUG_TOKEN_SEPARATOR: Final = "--"
SLUG_READABLE_MAX_BYTES: Final = 96
SLUG_EMPTY_READABLE: Final = "source"
SLUG_SUFFIX_HEX_DIGITS: Final = (12, 16, 24, 32, 64)
# The readable part, its separator, and the widest suffix.
SLUG_MAX_BYTES: Final = SLUG_READABLE_MAX_BYTES + len(SLUG_TOKEN_SEPARATOR) + 64

TRANSPORTS: Final[frozenset[str]] = frozenset({"https", "ssh", "file"})
OBJECT_FORMATS: Final[frozenset[str]] = frozenset({"sha1", "sha256"})

_IDENTITY_RE: Final = re.compile(r"^sha256:[0-9a-f]{64}$")
_STORE_KEY_RE: Final = re.compile(r"^[0-9a-f]{64}$")
_SLUG_RE: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:--[a-z0-9]+(?:-[a-z0-9]+)*)*$")
_FOLD_RE: Final = re.compile(r"[^a-z0-9]+")


class SlugCollisionError(RuntimeError):
    """Every permitted slug suffix is already claimed by a different source."""


def _digest(material: str) -> str:
    return IDENTITY_PREFIX + hashlib.sha256(material.encode("utf-8")).hexdigest()


def _require_address(normalized_address: str) -> None:
    if (
        not normalized_address
        or not normalized_address.isascii()
        or len(normalized_address) > SOURCE_ADDRESS_MAX_BYTES
        or any(ord(character) < 0x21 or ord(character) == 0x7F for character in normalized_address)
    ):
        raise ValueError(
            "a normalized source address is nonempty printable ASCII without whitespace"
        )


def _require_transport(transport: str) -> None:
    if transport not in TRANSPORTS:
        raise ValueError(f"unsupported Git transport {transport!r}")


def _require_object_format(object_format: str) -> None:
    if object_format not in OBJECT_FORMATS:
        raise ValueError(f"unsupported Git object format {object_format!r}")


def is_identity(value: str) -> bool:
    """Whether *value* is a ``sha256:<64 lowercase hex digits>`` identity."""

    return _IDENTITY_RE.fullmatch(value) is not None


def is_store_key(value: str) -> bool:
    """Whether *value* spells a store directory key."""

    return _STORE_KEY_RE.fullmatch(value) is not None


def is_slug(value: str) -> bool:
    """Whether *value* has the lowercase ASCII shape and bound of a source slug."""

    return len(value) <= SLUG_MAX_BYTES and _SLUG_RE.fullmatch(value) is not None


def source_identity(transport: GitTransport, normalized_address: str) -> str:
    """Return the identity of the source at *normalized_address* over *transport*."""

    _require_transport(transport)
    _require_address(normalized_address)
    return _digest(f"{SOURCE_IDENTITY_DOMAIN}\0{transport}\0{normalized_address}")


def repository_store_id(source_id: str, object_format: ObjectFormat) -> str:
    """Return the store identity a source acquires before any provider resolution."""

    if not is_identity(source_id):
        raise ValueError("a source identity is sha256:<64 lowercase hex digits>")
    _require_object_format(object_format)
    return _digest(f"{STORE_IDENTITY_DOMAIN}\0source\0{source_id}\0{object_format}")


def provider_repository_store_id(
    provider_kind: str,
    provider_instance: str,
    repository_opaque_id: str,
    object_format: ObjectFormat,
) -> str:
    """Return the store identity proven by stable provider repository identity.

    The canonical spelling of *provider_instance* belongs to the provider plan; this
    function only guarantees domain separation from every generic store.
    """

    _require_object_format(object_format)
    for name, value in (
        ("provider kind", provider_kind),
        ("provider instance", provider_instance),
        ("repository opaque id", repository_opaque_id),
    ):
        if not value or "\0" in value:
            raise ValueError(f"{name} must be nonempty and contain no NUL")
    material = "\0".join(
        (
            STORE_IDENTITY_DOMAIN,
            "provider",
            provider_kind,
            provider_instance,
            repository_opaque_id,
            object_format,
        )
    )
    return _digest(material)


def store_key(store_id: str) -> str:
    """Return the directory key for *store_id*: all of its hexadecimal digits."""

    if not is_identity(store_id):
        raise ValueError("a store identity is sha256:<64 lowercase hex digits>")
    return store_id.removeprefix(IDENTITY_PREFIX)[:STORE_KEY_HEX_DIGITS]


def _fold(token: str) -> str:
    return _FOLD_RE.sub("-", token.lower()).strip("-")


def slug_tokens(transport: GitTransport, normalized_address: str) -> tuple[str, ...]:
    """Return the readable slug tokens of a normalized address.

    Tokens are the host, with a non-default port appended, then the path segments. SSH
    users are not tokens, and a ``file`` source contributes only ``local`` and its final
    path segment, so an absolute local path never becomes a directory name.
    """

    _require_transport(transport)
    _require_address(normalized_address)
    if transport == "ssh" and not normalized_address.startswith("ssh://"):
        user_host, _, path = normalized_address.partition(":")
        raw = [user_host.rpartition("@")[2], *path.split("/")]
    elif transport == "file":
        segments = [
            segment for segment in normalized_address.removeprefix("file://").split("/") if segment
        ]
        raw = ["local", segments[-1]] if segments else ["local"]
    else:
        rest = normalized_address.split("://", 1)[1]
        authority, _, path = rest.partition("/")
        hostport = authority.rpartition("@")[2]
        if not hostport.startswith("["):
            hostport = hostport.replace(":", "-")
        raw = [hostport, *path.split("/")]
    segments = [segment for segment in raw if segment]
    if len(segments) > 1 and segments[-1].endswith(".git") and segments[-1] != ".git":
        segments[-1] = segments[-1].removesuffix(".git")
    decoded = [unquote_to_bytes(segment).decode("utf-8", errors="replace") for segment in segments]
    return tuple(folded for folded in (_fold(token) for token in decoded) if folded)


def slug_readable_part(transport: GitTransport, normalized_address: str) -> str:
    """Return the bounded readable prefix of a new slug."""

    readable = SLUG_TOKEN_SEPARATOR.join(slug_tokens(transport, normalized_address))
    readable = readable or SLUG_EMPTY_READABLE
    if len(readable) > SLUG_READABLE_MAX_BYTES:
        readable = readable[:SLUG_READABLE_MAX_BYTES].rstrip("-")
    return readable


def cache_slug(
    transport: GitTransport,
    normalized_address: str,
    source_id: str,
    *,
    slug_owner: Callable[[str], str | None],
) -> str:
    """Return the slug for a source, extending its suffix past slugs others claimed.

    *slug_owner* reports the source identity recorded for an existing slug, or ``None``
    when the slug is unclaimed. A slug already owned by *source_id* is reused. The caller
    claims the result under the source-alias lock with no-replace publication.
    """

    if not is_identity(source_id):
        raise ValueError("a source identity is sha256:<64 lowercase hex digits>")
    if source_identity(transport, normalized_address) != source_id:
        raise ValueError("the source identity does not match its transport and address")
    readable = slug_readable_part(transport, normalized_address)
    digest = source_id.removeprefix(IDENTITY_PREFIX)
    for width in SLUG_SUFFIX_HEX_DIGITS:
        candidate = f"{readable}{SLUG_TOKEN_SEPARATOR}{digest[:width]}"
        owner = slug_owner(candidate)
        if owner is None or owner == source_id:
            return candidate
    raise SlugCollisionError("every slug suffix width is claimed by a different source")


def slug_matches_identity(slug: str, source_id: str) -> bool:
    """Whether *slug* ends in a permitted digest suffix of *source_id*.

    The readable part is deliberately not recomputed: it is recorded at creation, so its
    bound may change later without orphaning entries.
    """

    if not is_slug(slug) or not is_identity(source_id):
        return False
    readable, separator, suffix = slug.rpartition(SLUG_TOKEN_SEPARATOR)
    digest = source_id.removeprefix(IDENTITY_PREFIX)
    return (
        bool(separator)
        and bool(readable)
        and len(suffix) in SLUG_SUFFIX_HEX_DIGITS
        and digest.startswith(suffix)
    )


__all__ = [
    "IDENTITY_PREFIX",
    "OBJECT_FORMATS",
    "SLUG_EMPTY_READABLE",
    "SLUG_MAX_BYTES",
    "SLUG_READABLE_MAX_BYTES",
    "SLUG_SUFFIX_HEX_DIGITS",
    "SLUG_TOKEN_SEPARATOR",
    "SOURCE_ADDRESS_MAX_BYTES",
    "SOURCE_IDENTITY_DOMAIN",
    "STORE_IDENTITY_DOMAIN",
    "STORE_KEY_HEX_DIGITS",
    "TRANSPORTS",
    "GitTransport",
    "ObjectFormat",
    "SlugCollisionError",
    "cache_slug",
    "is_identity",
    "is_slug",
    "is_store_key",
    "provider_repository_store_id",
    "repository_store_id",
    "slug_matches_identity",
    "slug_readable_part",
    "slug_tokens",
    "source_identity",
    "store_key",
]
