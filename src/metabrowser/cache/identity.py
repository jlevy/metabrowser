"""Source identity, repository-store identity, and cache slugs.

The rules are frozen in ``tests/fixtures/repository-cache/source-identity.json`` and
replayed against these functions. Every input is already the normalized, credential-free
address the root-argument grammar produces; parsing and normalizing a root argument is
the URL classifier's job, not this module's.

- A source identity is a SHA-256 digest of a domain, the transport, and the normalized
  address, joined with NUL. Transport is part of the material, so an HTTPS and an SSH
  spelling of one hosted repository are two sources.
- A store identity digests the source identity and the object format observed during
  acquisition, so two concurrent acquisitions of one source converge on one store.
- A store key is the readable words a slug has, joined by single dashes, then a dash and
  the first base-36 characters of the store identity's digest, so a store directory reads
  as the repository it holds. The suffix is the shortest of a few widths that no store with
  a different identity holds: a claim under the store lock never shares a name, and takes
  the next width instead.
- A slug is a readable, lowercase ASCII prefix plus the shortest digest suffix no other
  source has claimed. It is recorded in ``source.yml`` at creation and never recomputed.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from typing import Final, Literal
from urllib.parse import unquote_to_bytes

from strif import base36_encode

from metabrowser.git.process import OBJECT_FORMATS, ObjectFormat

type GitTransport = Literal["https", "ssh", "file"]

SOURCE_IDENTITY_DOMAIN: Final = "metabrowser.repository-source.v1"
STORE_IDENTITY_DOMAIN: Final = "metabrowser.repository-store.v1"
IDENTITY_PREFIX: Final = "sha256:"

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

# The single dash that joins a store key's readable words and its suffix. A slug joins its
# words with `--` so a word's own dash shows; a key does not, because its readable part is
# only a name for a person, the suffix makes it unique, and the suffix is simply the last
# token, so no `--` is needed to find where it starts.
STORE_KEY_SEPARATOR: Final = "-"

# The base-36 characters (`0-9a-z`) of a store identity's digest that end a store key,
# shortest first. A key is `<readable>-<suffix>`: the first width names the store, and each
# later one is the name it takes when a store with a different identity already holds the
# shorter name. The suffix is the first characters of the digest read as a fraction of 1
# (:func:`store_key_suffixes`), so each is a prefix of the next, every character is
# uniform, and the last width spells all 256 bits (50 characters are 258.5 bits), so only
# the same identity can share it.
#
# Sizing, by the birthday bound. Two stores can claim one first-choice name only if their
# digests agree on its first b = 11 x log2(36) = 56.9 bits (and, further, share a readable
# part). Among n stores the chance that any two agree is at most n(n - 1) / 2^(b + 1),
# taking every readable part to be the same, which no real cache does:
#
#   13 chars (67.2 bits): n = 10^4 -> 2.9e-13, n = 10^5 -> 2.9e-11
#   12 chars (62.0 bits): n = 10^4 -> 1.1e-11, n = 10^5 -> 1.1e-9
#   11 chars (56.9 bits): n = 10^4 -> 3.8e-10, n = 10^5 -> 3.8e-8
#   10 chars (51.7 bits): n = 10^4 -> 1.4e-8,  n = 10^5 -> 1.4e-6
#
# The target is under 1e-9 at 10^4 stores with the readable part ignored: the cache routes
# list at most MAX_DIRECTORY_ENTRIES = 10,000 stores and refuse a home past it, so that is
# the most a home can hold and still be read, and 11 characters are the shortest that meet
# it. (The first sizing, under 1e-9 at 10^5, took 64 bits, which is 13 characters, and
# left a key longer than a person reading it wants.) With the readable part counted, the
# figure is far lower: stores share one only as other spellings of one repository (its
# transport, a trailing `.git`, path case) and its two object formats, so groups hold a
# handful, and for groups of 8 the 11 characters give 2.7e-13 at 10^4 stores and 2.7e-12 at
# 10^5.
#
# The bound prices a second name, not correctness. A claim reads the identity recorded in
# any store already at a candidate and takes the next width instead of sharing it, a
# lookup does the same, and the identity recorded in `store.yml` is checked whenever a
# store is looked up or listed (`cache.acquire`, `cache.projection`). Someone who chooses
# addresses can grind 2^56 digests to occupy a name and force a longer one; that is all
# they can force. `tests/test_cache_store_keys.py` recomputes the figures above.
STORE_KEY_SUFFIX_CHARS: Final = (11, 19, 25, 50)
STORE_KEY_MAX_BYTES: Final = (
    SLUG_READABLE_MAX_BYTES + len(STORE_KEY_SEPARATOR) + STORE_KEY_SUFFIX_CHARS[-1]
)

TRANSPORTS: Final[frozenset[str]] = frozenset({"https", "ssh", "file"})

_IDENTITY_RE: Final = re.compile(r"^sha256:[0-9a-f]{64}$")
_SLUG_RE: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:--[a-z0-9]+(?:-[a-z0-9]+)*)*$")
# Single-dash tokens, at least two: the readable part's words, and the suffix.
_STORE_KEY_RE: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)+$")
_FOLD_RE: Final = re.compile(r"[^a-z0-9]+")


class SlugCollisionError(RuntimeError):
    """Every permitted slug suffix is already claimed by a different source."""


class StoreKeyCollisionError(RuntimeError):
    """Every permitted store key suffix is already claimed by a different store."""


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
    """Whether *value* spells a store directory key: dash-joined tokens whose last is a suffix.

    The suffix is always the last token and has one of :data:`STORE_KEY_SUFFIX_CHARS`
    characters of ``0-9a-z``, so a readable word that happens to look like one, such as a
    repository named ``abcdefghijk``, is still read as part of the readable part: the key
    that follows it ends in the real suffix. A bare run of characters is no key, so a name
    an older release gave a store, the whole digest, is told from a key, and so is a
    ``--`` name an ``f02`` home gave one.
    """

    return (
        len(value) <= STORE_KEY_MAX_BYTES
        and _STORE_KEY_RE.fullmatch(value) is not None
        and len(value.rpartition(STORE_KEY_SEPARATOR)[2]) in STORE_KEY_SUFFIX_CHARS
    )


def is_slug(value: str) -> bool:
    """Whether *value* has the lowercase ASCII shape and bound of a source slug."""

    return len(value) <= SLUG_MAX_BYTES and _SLUG_RE.fullmatch(value) is not None


def source_identity(transport: GitTransport, normalized_address: str) -> str:
    """Return the identity of the source at *normalized_address* over *transport*."""

    _require_transport(transport)
    _require_address(normalized_address)
    return _digest(f"{SOURCE_IDENTITY_DOMAIN}\0{transport}\0{normalized_address}")


def repository_store_id(source_id: str, object_format: ObjectFormat) -> str:
    """Return the identity of the store a source acquires."""

    if not is_identity(source_id):
        raise ValueError("a source identity is sha256:<64 lowercase hex digits>")
    _require_object_format(object_format)
    return _digest(f"{STORE_IDENTITY_DOMAIN}\0source\0{source_id}\0{object_format}")


def identity_digest(identity: str) -> str:
    """Return the 64 hexadecimal digits of a ``sha256:`` identity."""

    if not is_identity(identity):
        raise ValueError("an identity is sha256:<64 lowercase hex digits>")
    return identity.removeprefix(IDENTITY_PREFIX)


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


def _bounded_readable(tokens: tuple[str, ...], separator: str) -> str:
    readable = separator.join(tokens) or SLUG_EMPTY_READABLE
    if len(readable) > SLUG_READABLE_MAX_BYTES:
        readable = readable[:SLUG_READABLE_MAX_BYTES].rstrip("-")
    return readable


def slug_readable_part(transport: GitTransport, normalized_address: str) -> str:
    """Return the bounded readable prefix of a new slug: its tokens joined by ``--``."""

    return _bounded_readable(slug_tokens(transport, normalized_address), SLUG_TOKEN_SEPARATOR)


def store_readable_part(transport: GitTransport, normalized_address: str) -> str:
    """Return the bounded readable prefix of a store key: the slug's tokens joined by ``-``.

    It is a name for a person and never an identity, so ``jlevy/my-repo`` and
    ``jlevy/my/repo`` may read alike: the suffix tells the stores apart.
    """

    return _bounded_readable(slug_tokens(transport, normalized_address), STORE_KEY_SEPARATOR)


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


def _base36_prefix(digest: str, characters: int) -> str:
    """The first *characters* base-36 digits of *digest* read as a fraction of 1.

    ``digest`` is ``h`` hexadecimal digits, a number ``D`` below ``16^h``, and the
    fraction is ``D / 16^h``. Its first ``n`` base-36 digits are the integer
    ``floor(D * 36^n / 16^h)``, spelled in ``n`` characters with leading zeros kept, so
    the answer has a fixed width, a longer one starts with a shorter one, and every digit
    is uniform. The base-36 spelling of ``D`` itself would have none of that: it varies in
    length, and in 84% of digests its first character is 1 to 6.
    """

    scaled = (int(digest, 16) * 36**characters) >> (4 * len(digest))
    return base36_encode(scaled).rjust(characters, "0")


def store_key_suffixes(store_id: str) -> tuple[str, ...]:
    """Return the suffixes a store may have, one for each of :data:`STORE_KEY_SUFFIX_CHARS`."""

    digest = identity_digest(store_id)
    return tuple(_base36_prefix(digest, characters) for characters in STORE_KEY_SUFFIX_CHARS)


def store_key_candidates_for(readable: str, store_id: str) -> tuple[str, ...]:
    """Return the keys a store may have under the readable part *readable*, first choice first."""

    return tuple(
        f"{readable}{STORE_KEY_SEPARATOR}{suffix}" for suffix in store_key_suffixes(store_id)
    )


def store_key_candidates(
    transport: GitTransport, normalized_address: str, store_id: str
) -> tuple[str, ...]:
    """Return the keys a store of the source at *normalized_address* may have, first choice first.

    The readable part is the words of a slug of the address, joined by single dashes, and
    the suffixes are those of :func:`store_key_suffixes`. A store has the first key no
    other store holds.
    """

    return store_key_candidates_for(store_readable_part(transport, normalized_address), store_id)


def cache_store_key(
    transport: GitTransport,
    normalized_address: str,
    store_id: str,
    *,
    store_owner: Callable[[str], str | None],
) -> str:
    """Return the key of *store_id*: where it is published, or where it would be.

    *store_owner* reports the store identity recorded at a candidate key, or ``None`` when
    nothing is published there. A key already held by *store_id* is that store's, found
    however long it is, so a lookup and a repeated claim agree. Otherwise the result is
    the first candidate nobody holds, and a name held by a different store is skipped,
    never shared. The caller claims the result under the store lock and reads it again
    there.
    """

    free: str | None = None
    for candidate in store_key_candidates(transport, normalized_address, store_id):
        owner = store_owner(candidate)
        if owner == store_id:
            return candidate
        if owner is None and free is None:
            free = candidate
    if free is None:
        raise StoreKeyCollisionError("every store key suffix width is claimed by a different store")
    return free


def store_key_matches_identity(key: str, store_id: str) -> bool:
    """Whether *key* ends in a permitted suffix of *store_id*.

    The readable part is not recomputed, as for :func:`slug_matches_identity`: it says
    which repository, and the suffix says which store.
    """

    if not is_store_key(key) or not is_identity(store_id):
        return False
    return key.rpartition(STORE_KEY_SEPARATOR)[2] in store_key_suffixes(store_id)


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
    "STORE_KEY_MAX_BYTES",
    "STORE_KEY_SEPARATOR",
    "STORE_KEY_SUFFIX_CHARS",
    "TRANSPORTS",
    "GitTransport",
    "ObjectFormat",
    "SlugCollisionError",
    "StoreKeyCollisionError",
    "cache_slug",
    "cache_store_key",
    "identity_digest",
    "is_identity",
    "is_slug",
    "is_store_key",
    "repository_store_id",
    "slug_matches_identity",
    "slug_readable_part",
    "slug_tokens",
    "source_identity",
    "store_key_candidates",
    "store_key_candidates_for",
    "store_key_matches_identity",
    "store_key_suffixes",
    "store_readable_part",
]
