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
- A slug and a store key have one grammar, ``<readable>-<suffix>``: the repository's
  words joined by single dashes, a dash, and the first base-36 characters of an identity's
  digest, so a directory reads as the repository it holds. A slug's suffix is the source
  identity's and a key's is the store identity's. The suffix is the shortest of a few
  widths that no entry with a different identity holds: a claim under the entry's lock
  never shares a name, and takes the next width instead. A slug is recorded in
  ``source.yml`` at creation and never recomputed.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from typing import Final, Literal
from urllib.parse import unquote_to_bytes

from metabrowser.git.process import OBJECT_FORMATS, ObjectFormat

type GitTransport = Literal["https", "ssh", "file"]

SOURCE_IDENTITY_DOMAIN: Final = "metabrowser.repository-source.v1"
STORE_IDENTITY_DOMAIN: Final = "metabrowser.repository-store.v1"
IDENTITY_PREFIX: Final = "sha256:"

# The bound the record and its packaged schema hold `display_url` and `clone_url` to.
# Deriving an identity from an address no record could carry would publish an entry that
# can be created and never read back, so both refuse the same addresses.
SOURCE_ADDRESS_MAX_BYTES: Final = 2048

# The readable part of a slug or a store key, bounded.
READABLE_MAX_BYTES: Final = 96
EMPTY_READABLE: Final = "source"

# The single dash that joins a name's readable words and its suffix. The readable part is
# only a name for a person, the suffix makes it unique, and the suffix is simply the last
# token, so nothing wider than a dash is needed to find where it starts.
NAME_SEPARATOR: Final = "-"

# The base-36 characters (`0-9a-z`) of an identity's digest that end a slug or a store key,
# shortest first. A name is `<readable>-<suffix>`: the first width names the entry, and each
# later one is the name it takes when an entry with a different identity already holds the
# shorter name. The suffix is the first characters of the digest read as a fraction of 1
# (:func:`name_suffixes`), so each is a prefix of the next, every character is uniform, and
# the last width spells all 256 bits (50 characters are 258.5 bits), so only the same
# identity can share it.
#
# Sizing, by the birthday bound. Two entries can claim one first-choice name only if their
# digests agree on its first b = 11 x log2(36) = 56.9 bits (and, further, share a readable
# part). Among n entries the chance that any two agree is at most n(n - 1) / 2^(b + 1),
# taking every readable part to be the same, which no real cache does:
#
#   13 chars (67.2 bits): n = 10^4 -> 2.9e-13, n = 10^5 -> 2.9e-11
#   12 chars (62.0 bits): n = 10^4 -> 1.1e-11, n = 10^5 -> 1.1e-9
#   11 chars (56.9 bits): n = 10^4 -> 3.8e-10, n = 10^5 -> 3.8e-8
#   10 chars (51.7 bits): n = 10^4 -> 1.4e-8,  n = 10^5 -> 1.4e-6
#
# The target is under 1e-9 at 10^4 entries with every readable part taken to be the same,
# and 11 characters are the shortest that meet it. 10^4 is what the cache routes list
# (MAX_DIRECTORY_ENTRIES) and the layout migration accepts, which is not a cap on entries:
# acquisition finds an entry by name and lists nothing, so a larger home works, and a very
# large one gets 3.8e-8 at 10^5 in the worst case above. The sizing can be that loose
# because a collision costs a longer name and nothing else: a claim skips a name another
# identity holds and a lookup finds its own at any width, and the identity recorded in
# `source.yml` or `store.yml` is read before a name is trusted. (The first sizing, under
# 1e-9 at 10^5, took 64 bits, which is 13 characters, and left a key longer than a person
# reading it wants.)
#
# With the readable part counted the figure is lower, but not by as much as a handful of
# spellings would give. Entries share a readable part as other spellings of one repository
# (its transport, a trailing `.git`, path case) and its two object formats, and for groups
# of 8 the 11 characters give 2.7e-13 at 10^4 entries and 2.7e-12 at 10^5. A `file://`
# source is the exception: its readable part is `local-<last path segment>`, so every local
# clone whose directory is called `origin.git` shares one. They are told apart by their
# suffix all the same, and a collision among them costs the same longer name.
#
# The bound prices a second name, not correctness. A claim reads the identity recorded in
# any entry already at a candidate and takes the next width instead of sharing it, a
# lookup does the same, and the identity recorded in `source.yml` or `store.yml` is checked
# whenever an entry is looked up or listed (`cache.acquire`, `cache.projection`). Someone
# who chooses addresses can grind 2^56 digests to occupy a name and force a longer one;
# that is all they can force. `tests/test_cache_store_keys.py` recomputes the figures above.
NAME_SUFFIX_CHARS: Final = (11, 19, 25, 50)
NAME_MAX_BYTES: Final = READABLE_MAX_BYTES + len(NAME_SEPARATOR) + NAME_SUFFIX_CHARS[-1]

TRANSPORTS: Final[frozenset[str]] = frozenset({"https", "ssh", "file"})

_BASE36_DIGITS: Final = "0123456789abcdefghijklmnopqrstuvwxyz"

_IDENTITY_RE: Final = re.compile(r"^sha256:[0-9a-f]{64}$")
# Single-dash tokens, at least two: the readable part's words, and the suffix.
_NAME_RE: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)+$")
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


def _has_name_shape(value: str) -> bool:
    return (
        len(value) <= NAME_MAX_BYTES
        and _NAME_RE.fullmatch(value) is not None
        and len(value.rpartition(NAME_SEPARATOR)[2]) in NAME_SUFFIX_CHARS
    )


def is_store_key(value: str) -> bool:
    """Whether *value* spells a store directory key: dash-joined tokens whose last is a suffix.

    The suffix is always the last token and has one of :data:`NAME_SUFFIX_CHARS`
    characters of ``0-9a-z``, so a readable word that happens to look like one, such as a
    repository named ``abcdefghijk``, is still read as part of the readable part: the key
    that follows it ends in the real suffix. The whole digest an older release used as a
    directory name has no dash, so it is distinct from a key.
    """

    return _has_name_shape(value)


def is_slug(value: str) -> bool:
    """Whether *value* has the shape and bound of a source slug, which is a key's.

    A slug and a store key have one grammar and differ in the identity their suffix
    digests, which :func:`slug_matches_identity` and :func:`store_key_matches_identity`
    check, so shape alone never says which an entry is.
    """

    return _has_name_shape(value)


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


def readable_part(transport: GitTransport, normalized_address: str) -> str:
    """Return the bounded readable part of a slug or a store key: its tokens joined by ``-``.

    It is a name for a person and never an identity, so ``jlevy/my-repo`` and
    ``jlevy/my/repo`` may read alike: the suffix tells the entries apart.
    """

    readable = NAME_SEPARATOR.join(slug_tokens(transport, normalized_address)) or EMPTY_READABLE
    if len(readable) > READABLE_MAX_BYTES:
        readable = readable[:READABLE_MAX_BYTES].rstrip("-")
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
    for candidate in slug_candidates(transport, normalized_address, source_id):
        owner = slug_owner(candidate)
        if owner is None or owner == source_id:
            return candidate
    raise SlugCollisionError("every slug suffix width is claimed by a different source")


def slug_matches_identity(slug: str, source_id: str) -> bool:
    """Whether *slug* ends in a permitted suffix of *source_id*.

    The readable part is deliberately not recomputed: it is recorded at creation, so its
    bound may change later without orphaning entries.
    """

    if not is_slug(slug) or not is_identity(source_id):
        return False
    return slug.rpartition(NAME_SEPARATOR)[2] in name_suffixes(source_id)


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
    # The digits are written here, four lines, because they are the name of a directory on
    # disk and no library's spelling of base 36 should be able to change one.
    digits: list[str] = []
    for _ in range(characters):
        scaled, digit = divmod(scaled, 36)
        digits.append(_BASE36_DIGITS[digit])
    return "".join(reversed(digits))


def name_suffixes(identity: str) -> tuple[str, ...]:
    """Return the suffixes an entry of *identity* may have, one for each of :data:`NAME_SUFFIX_CHARS`."""

    digest = identity_digest(identity)
    return tuple(_base36_prefix(digest, characters) for characters in NAME_SUFFIX_CHARS)


def name_candidates_for(readable: str, identity: str) -> tuple[str, ...]:
    """Return the names an entry may have under the readable part *readable*, first choice first."""

    return tuple(f"{readable}{NAME_SEPARATOR}{suffix}" for suffix in name_suffixes(identity))


def slug_candidates(
    transport: GitTransport, normalized_address: str, source_id: str
) -> tuple[str, ...]:
    """Return the slugs a source at *normalized_address* may have, first choice first."""

    return name_candidates_for(readable_part(transport, normalized_address), source_id)


def store_key_candidates_for(readable: str, store_id: str) -> tuple[str, ...]:
    """Return the keys a store may have under the readable part *readable*, first choice first."""

    return name_candidates_for(readable, store_id)


def store_key_candidates(
    transport: GitTransport, normalized_address: str, store_id: str
) -> tuple[str, ...]:
    """Return the keys a store of the source at *normalized_address* may have, first choice first.

    The readable part is the words of a slug of the address, joined by single dashes, and
    the suffixes are those of :func:`name_suffixes`. A store has the first key no other
    store holds.
    """

    return store_key_candidates_for(readable_part(transport, normalized_address), store_id)


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
    return key.rpartition(NAME_SEPARATOR)[2] in name_suffixes(store_id)


__all__ = [
    "EMPTY_READABLE",
    "IDENTITY_PREFIX",
    "NAME_MAX_BYTES",
    "NAME_SEPARATOR",
    "NAME_SUFFIX_CHARS",
    "OBJECT_FORMATS",
    "READABLE_MAX_BYTES",
    "SOURCE_ADDRESS_MAX_BYTES",
    "SOURCE_IDENTITY_DOMAIN",
    "STORE_IDENTITY_DOMAIN",
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
    "name_candidates_for",
    "name_suffixes",
    "readable_part",
    "repository_store_id",
    "slug_candidates",
    "slug_matches_identity",
    "slug_tokens",
    "source_identity",
    "store_key_candidates",
    "store_key_candidates_for",
    "store_key_matches_identity",
]
