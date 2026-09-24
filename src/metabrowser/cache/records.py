"""Strict records for the application home and the ``f01`` repository cache.

Each YAML family has one Pydantic model and one versioned SoftSchema contract, bound in
:mod:`metabrowser.cache.contracts`. Machine-owned records forbid undeclared fields and
validate strictly, because Metabrowser is their only producer. ``config.yml`` is the one
user-owned record: it allows unknown settings at every level so a compatible older
client preserves what a newer one or the user wrote, while its known fields still
validate and credential-shaped keys are refused anywhere in it.

Identity and mutable state are separate records. ``source.yml`` and ``store.yml`` hold
what an entry is; ``store-alias.yml`` is the generation-checked attachment from a source
to a store; each ``state.yml`` holds what changes.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated, Any, Final, Literal, Self, cast

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from metabrowser.cache.identity import (
    SOURCE_ADDRESS_MAX_BYTES,
    GitTransport,
    ObjectFormat,
    is_slug,
    slug_matches_identity,
    source_identity,
)

CONFIG_CONTRACT_ID: Final = "com.github.jlevy.metabrowser.config:ApplicationConfig/v1"
CACHE_LAYOUT_CONTRACT_ID: Final = "com.github.jlevy.metabrowser.cache:CacheLayout/v1"
REPOSITORY_SOURCE_CONTRACT_ID: Final = "com.github.jlevy.metabrowser.cache:RepositorySource/v1"
REPOSITORY_SOURCE_STATE_CONTRACT_ID: Final = (
    "com.github.jlevy.metabrowser.cache:RepositorySourceState/v1"
)
REPOSITORY_STORE_ALIAS_CONTRACT_ID: Final = (
    "com.github.jlevy.metabrowser.cache:RepositoryStoreAlias/v1"
)
REPOSITORY_STORE_CONTRACT_ID: Final = "com.github.jlevy.metabrowser.cache:RepositoryStore/v1"
REPOSITORY_STORE_STATE_CONTRACT_ID: Final = (
    "com.github.jlevy.metabrowser.cache:RepositoryStoreState/v1"
)

MAX_SAFE_INTEGER: Final = 9_007_199_254_740_991
# A layout format is `f` and at least two decimal digits, so formats order by number.
LAYOUT_FORMAT_PATTERN: Final = r"^f[0-9]{2,}$"
_GIT_REF_MAX_LENGTH: Final = 1024
# Portable across JSON Schema engines, so it is also the structural pattern.
_RFC3339_UTC_PATTERN: Final = (
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{3})?Z$"
)
# A config key naming a secret. Config is user-owned and permissive, so this is the one
# rule that applies to settings Metabrowser does not otherwise know.
_CREDENTIAL_KEY_RE: Final = re.compile(
    r"(?:^|[_.-])(?:token|tokens|password|passwd|secret|secrets|credential|credentials|"
    r"api[_-]?key|private[_-]?key|access[_-]?key)$",
    re.IGNORECASE,
)


def canonical_now() -> str:
    """The current time in the canonical RFC 3339 UTC spelling every record uses."""

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_timestamp(value: str) -> str:
    if re.fullmatch(_RFC3339_UTC_PATTERN, value) is None or value.endswith(".000Z"):
        raise ValueError("timestamps must use canonical RFC 3339 UTC syntax")
    try:
        datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise ValueError("timestamps must use canonical RFC 3339 UTC syntax") from error
    return value


def _require_slug(value: str) -> str:
    if not is_slug(value):
        raise ValueError("a source slug is bounded lowercase ASCII tokens joined by '--'")
    return value


type CanonicalTimestamp = Annotated[
    str,
    StringConstraints(pattern=_RFC3339_UTC_PATTERN),
    AfterValidator(_require_timestamp),
]
type Sha256Identity = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
type SourceSlug = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=162,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:--[a-z0-9]+(?:-[a-z0-9]+)*)*$",
    ),
    AfterValidator(_require_slug),
]
type LayoutFormat = Annotated[str, StringConstraints(pattern=LAYOUT_FORMAT_PATTERN)]
type MetabrowserVersion = Annotated[
    str, StringConstraints(min_length=1, max_length=128, pattern=r"^[0-9A-Za-z.+!_-]+$")
]
# Printable ASCII without whitespace: the credential-free spellings the root-argument
# grammar accepts, bounded exactly as identity derivation bounds them.
type SourceAddress = Annotated[
    str, StringConstraints(min_length=1, max_length=SOURCE_ADDRESS_MAX_BYTES, pattern=r"^[!-~]+$")
]
type GitRefName = Annotated[
    str,
    StringConstraints(min_length=6, max_length=_GIT_REF_MAX_LENGTH, pattern=r"^refs/[!-~]+$"),
]
type GitObjectId = Annotated[str, StringConstraints(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")]
type GitVersion = Annotated[
    str, StringConstraints(min_length=1, max_length=128, pattern=r"^[0-9]+\.[0-9]+[!-~]*$")
]
type Generation = Annotated[int, Field(ge=1, le=MAX_SAFE_INTEGER)]


class _MachineRecord(BaseModel):
    """A record only Metabrowser writes: closed, immutable, and strictly typed."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class _UserRecord(BaseModel):
    """A user-owned record: known fields validate, unknown settings are kept."""

    model_config = ConfigDict(extra="allow", frozen=True, strict=True)


# ── config.yml ─────────────────────────────────────────────────────


class ConfigUpgrade(_UserRecord):
    """One Metabrowser release that migrated the application home."""

    version: MetabrowserVersion
    at: CanonicalTimestamp


class ApplicationConfig(_UserRecord):
    """``config.yml``: the user-owned application configuration.

    ``format`` names the home format this configuration was last published for.
    Migration publishes it last, so a layout ahead of its config marks an interrupted
    migration rather than a user edit.
    """

    format: LayoutFormat
    written_by: MetabrowserVersion
    upgrades: list[ConfigUpgrade]

    @model_validator(mode="before")
    @classmethod
    def _refuse_credentials(cls, data: Any) -> Any:
        pending: list[object] = [data]
        while pending:
            current = pending.pop()
            if isinstance(current, dict):
                for key, value in cast(dict[object, object], current).items():
                    if isinstance(key, str) and _CREDENTIAL_KEY_RE.search(key):
                        raise ValueError(
                            "config.yml must not hold credentials; keep them in the Git or "
                            "provider credential store"
                        )
                    pending.append(value)
            elif isinstance(current, list):
                pending.extend(cast(list[object], current))
        return data


# ── cache/layout.yml ───────────────────────────────────────────────


class CacheLayout(_MachineRecord):
    """``cache/layout.yml``: the directory-semantics format of the cache."""

    format: LayoutFormat
    created_by: MetabrowserVersion


# ── cache/sources/<slug>/ ──────────────────────────────────────────


class RepositorySource(_MachineRecord):
    """``source.yml``: the stable identity of one credential-free Git source."""

    id: Sha256Identity
    slug: SourceSlug
    display_url: SourceAddress
    clone_url: SourceAddress
    transport: GitTransport
    created_at: CanonicalTimestamp

    @model_validator(mode="after")
    def _identity_matches_its_material(self) -> Self:
        if source_identity(self.transport, self.clone_url) != self.id:
            raise ValueError("source id does not match its transport and clone URL")
        if not slug_matches_identity(self.slug, self.id):
            raise ValueError("source slug does not end in a digest suffix of its id")
        return self


class RepositorySourceState(_MachineRecord):
    """A source's ``state.yml``: optional recency bookkeeping, never a correctness input."""

    last_opened_at: CanonicalTimestamp | None


class RepositoryStoreAlias(_MachineRecord):
    """``store-alias.yml``: the generation-checked attachment from a source to a store."""

    source_id: Sha256Identity
    store_id: Sha256Identity
    generation: Generation
    updated_at: CanonicalTimestamp


# ── cache/repository-stores/<store-key>/ ───────────────────────────


class StoreAcquisition(_MachineRecord):
    """How a store's Git database was first populated: a fetch of every object."""

    git_version: GitVersion
    object_format: ObjectFormat


class RepositoryStore(_MachineRecord):
    """``store.yml``: immutable identity and acquisition metadata of a Git database."""

    id: Sha256Identity
    created_at: CanonicalTimestamp
    acquisition: StoreAcquisition


type RecordedOutcome = Literal[
    "succeeded",
    "default_branch_unknown",
    "origin_unavailable",
    "fetch_failed",
    "validation_failed",
]


class StoreOperation(_MachineRecord):
    """The last Git operation that finished against a store, and how, by name.

    A refresh records its typed outcome, so a later start reports what happened rather
    than a bare failure. ``default_branch_unknown`` fetched everything but found no
    branch at the origin's HEAD. An outcome that says why no fetch ran in one process,
    such as another process refreshing the store, is not recorded.
    """

    kind: Literal["acquire", "refresh"]
    outcome: RecordedOutcome
    at: CanonicalTimestamp


class RepositoryStoreState(_MachineRecord):
    """A store's ``state.yml``: mutable Git observations, replaced atomically."""

    default_remote_ref: GitRefName | None
    default_revision: GitObjectId | None
    last_fetch_at: CanonicalTimestamp | None
    last_operation: StoreOperation

    @model_validator(mode="after")
    def _revision_needs_its_ref(self) -> Self:
        if (self.default_remote_ref is None) != (self.default_revision is None):
            raise ValueError("a default revision and its remote ref are recorded together")
        return self


__all__ = [
    "CACHE_LAYOUT_CONTRACT_ID",
    "CONFIG_CONTRACT_ID",
    "LAYOUT_FORMAT_PATTERN",
    "MAX_SAFE_INTEGER",
    "REPOSITORY_SOURCE_CONTRACT_ID",
    "REPOSITORY_SOURCE_STATE_CONTRACT_ID",
    "REPOSITORY_STORE_ALIAS_CONTRACT_ID",
    "REPOSITORY_STORE_CONTRACT_ID",
    "REPOSITORY_STORE_STATE_CONTRACT_ID",
    "ApplicationConfig",
    "CacheLayout",
    "ConfigUpgrade",
    "RecordedOutcome",
    "RepositorySource",
    "RepositorySourceState",
    "RepositoryStore",
    "RepositoryStoreAlias",
    "RepositoryStoreState",
    "StoreAcquisition",
    "StoreOperation",
    "canonical_now",
]
