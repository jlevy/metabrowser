"""Typed, validated access to the packaged file-type registry."""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from functools import cache
from importlib.resources import files
from types import MappingProxyType
from typing import Any, Literal, cast

from metabrowser.color_oklch import BAND_CENTER, TonePosition, band_positions

FILE_TYPE_REGISTRY_SCHEMA = "file-type-registry-v4"
FILE_TYPE_REGISTRY_SCHEMA_VERSION = 4
FILE_TYPE_REGISTRY_RESOURCE = "data/file-rollup-format/recommended-file-types.toml"
FILE_TYPE_FAMILY_KEY_PREFIX = "family:"
FILE_TYPE_NO_EXTENSION_KEY = "(none)"
FILE_TYPE_REMAINING_KEY = ""

_VALID_ID = re.compile(r"^[a-z][a-z0-9-]*$")
_VALID_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_VALID_EXTENSION_COMPONENT = re.compile(r"^[a-z0-9]{1,12}$")

type DetectionSource = Literal["basename", "extension", "suffix", "unknown"]
type DetectionConfidence = Literal["exact", "suffix", "unknown"]


class ContentFamily(StrEnum):
    """Analyzer-oriented content identity, independent of display grouping."""

    code = "code"
    prose = "prose"
    markup = "markup"
    data = "data"
    binary = "binary"
    unknown = "unknown"


class FileTypeRegistryError(ValueError):
    """A stable validation failure suitable for shared conformance fixtures."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        table_id: str | None = None,
        field_name: str | None = None,
        value: object = None,
    ) -> None:
        self.code = code
        self.table_id = table_id
        self.field_name = field_name
        self.value = value
        context = ", ".join(
            part
            for part in (
                f"table={table_id!r}" if table_id is not None else "",
                f"field={field_name!r}" if field_name is not None else "",
                f"value={value!r}" if value is not None else "",
            )
            if part
        )
        super().__init__(f"{code}: {message}" + (f" ({context})" if context else ""))


@dataclass(frozen=True, slots=True)
class FileTypeGroup:
    """One ordered top-level product grouping."""

    id: str
    label: str
    order: int
    icon: str
    """The shape every family in this group takes unless it declares its own.

    Required here so a family always resolves to something. The split follows
    the rule the file tree already states: the icon is the major type and the
    colour is the subtype, which is why 56 families need only six shapes and a
    handful of overrides."""


@dataclass(frozen=True, slots=True)
class FileTypeFamily:
    """One ordered display family and its complete declared extensions."""

    id: str
    label: str
    group_id: str
    order: int
    extensions: tuple[str, ...]
    hue: float
    """The family's colour, in oklch hue degrees.

    A hue and not a colour: lightness and chroma belong to whichever theme is
    painting, so a family is the same hue everywhere and no theme has to
    re-derive an identity. See :mod:`metabrowser.color_oklch`."""
    linguist: str | None
    """The language in GitHub's linguist this hue came from, or ``None`` where
    GitHub names no colour for the family and the hue came from a free gap."""
    linguist_color: str | None
    """That language's upstream sRGB hex, recorded beside the name so the hue's
    provenance is auditable in one diff and checkable without a clone of
    linguist. Present exactly when ``linguist`` is."""
    deviation: str | None
    """Why this family does not paint where its upstream colour says it should.

    Present exactly when the family leaves GitHub's placement deliberately —
    a ``hue`` that is not ``linguist_color``'s, a ``lightness_rank`` of its
    own, or both. It is prose because the reason is the point: a deviation is
    a judgement someone made, and the next reader needs it to tell a decision
    from a mistake. ``linguist`` and ``linguist_color`` stay either way, so
    provenance survives the deviation."""
    lightness_rank: float | None
    """Where in the band the family sits, overriding its upstream rank.

    Normally ``None`` and derived across the whole registry. A declared value
    may fall outside ``[0, 1]``, which places the family outside the band — the
    one way to leave it, and only with a ``deviation`` saying why, because the
    band is what bounds how much a stacked-bar segment can read heavier than
    its size."""
    icon: str | None
    """This family's own shape, or ``None`` to take the group's.

    Declared only where the format reads as its own thing rather than as a
    member of its group -- tabular data against a list, a log stream against a
    document. A family that looks like its neighbours should look like them."""

    @property
    def distribution_key(self) -> str:
        """Return the stable palette identity shared by every family member."""

        return f"{FILE_TYPE_FAMILY_KEY_PREFIX}{self.id}"


@dataclass(frozen=True, slots=True)
class FileTypeKind:
    """One metadata classifier declaration."""

    id: str
    family_id: str | None
    group_id: str
    content_family: ContentFamily
    extensions: tuple[str, ...]
    filenames: tuple[str, ...]
    shebangs: tuple[str, ...]
    priority: int


@dataclass(frozen=True, slots=True)
class FileTypeMatch:
    """The winning kind and evidence for a known file."""

    kind: FileTypeKind
    canonical_extension: str | None
    detection_source: DetectionSource
    confidence: DetectionConfidence


@dataclass(frozen=True, slots=True)
class FileTypeClassification:
    """Portable metadata classification for one file observation."""

    logical_extension: str | None
    canonical_extension: str | None
    kind_id: str | None
    family_id: str | None
    group_id: str
    content_family: ContentFamily
    detection_source: DetectionSource
    confidence: DetectionConfidence
    registry_revision: int
    registry_fingerprint: str


@dataclass(frozen=True, slots=True)
class _FamilyDeclaration:
    id: str
    label: str
    group_id: str
    order: int
    hue: float
    linguist: str | None
    linguist_color: str | None
    deviation: str | None
    lightness_rank: float | None
    icon: str | None


@dataclass(frozen=True, slots=True)
class FileTypeRegistry:
    """Immutable validated registry with precomputed metadata indexes."""

    schema_version: int
    revision: int
    max_extension_components: int
    groups: tuple[FileTypeGroup, ...]
    families: tuple[FileTypeFamily, ...]
    kinds: tuple[FileTypeKind, ...]
    fingerprint: str
    _groups_by_id: Mapping[str, FileTypeGroup] = field(init=False, repr=False, compare=False)
    _families_by_id: Mapping[str, FileTypeFamily] = field(init=False, repr=False, compare=False)
    _exact_extensions: Mapping[str, FileTypeKind] = field(init=False, repr=False, compare=False)
    _suffixes: tuple[tuple[str, FileTypeKind], ...] = field(init=False, repr=False, compare=False)
    _filenames: Mapping[str, FileTypeKind] = field(init=False, repr=False, compare=False)
    _tone_positions: Mapping[str, TonePosition] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        exact_extensions = {
            f".{extension}": kind for kind in self.kinds for extension in kind.extensions
        }
        suffixes = tuple(
            sorted(
                exact_extensions.items(),
                key=lambda item: (
                    -item[0].count("."),
                    -len(item[0]),
                    -item[1].priority,
                    item[0],
                    item[1].id,
                ),
            )
        )
        object.__setattr__(
            self,
            "_groups_by_id",
            MappingProxyType({group.id: group for group in self.groups}),
        )
        object.__setattr__(
            self,
            "_families_by_id",
            MappingProxyType({family.id: family for family in self.families}),
        )
        object.__setattr__(self, "_exact_extensions", MappingProxyType(exact_extensions))
        object.__setattr__(self, "_suffixes", suffixes)
        object.__setattr__(
            self,
            "_filenames",
            MappingProxyType(
                {filename.lower(): kind for kind in self.kinds for filename in kind.filenames}
            ),
        )
        # Derived here, once, because a position is relative to the whole set:
        # a family's rank among upstream lightnesses is not a property of that
        # family alone, so it cannot be declared beside one. A family that
        # declares its own rank overrides only that axis, and keeps the chroma
        # its upstream colour earned.
        derived = band_positions([family.linguist_color for family in self.families])
        positions: dict[str, TonePosition] = {}
        for family, position in zip(self.families, derived, strict=True):
            positions[family.id] = (
                position
                if family.lightness_rank is None
                else TonePosition(
                    lightness_rank=family.lightness_rank,
                    chroma_ratio=position.chroma_ratio,
                )
            )
        object.__setattr__(self, "_tone_positions", MappingProxyType(positions))

    def group(self, group_id: str) -> FileTypeGroup | None:
        """Look up a group by stable ID."""

        return self._groups_by_id.get(group_id)

    def family(self, family_id: str) -> FileTypeFamily | None:
        """Look up a family by stable ID."""

        return self._families_by_id.get(family_id)

    def tone_position(self, family_id: str) -> TonePosition:
        """Where this family sits inside either theme's band.

        Read with a theme's :class:`~metabrowser.color_oklch.ToneBand` to get a
        finished color. An unknown ID sits at the band centre, which is also
        where a family GitHub names no color for sits.
        """

        return self._tone_positions.get(family_id, BAND_CENTER)

    def match(self, name: str, logical_extension: str) -> FileTypeMatch | None:
        """Select basename, exact-extension, then longest-suffix evidence."""

        basename = name.replace("\\", "/").rsplit("/", maxsplit=1)[-1].lower()
        basename_kind = self._filenames.get(basename)
        if basename_kind is not None:
            return FileTypeMatch(basename_kind, None, "basename", "exact")
        extension = normalize_logical_extension(logical_extension)
        if not extension:
            return None
        exact_kind = self._exact_extensions.get(extension)
        if exact_kind is not None:
            return FileTypeMatch(exact_kind, extension, "extension", "exact")
        for suffix, kind in self._suffixes:
            if extension.endswith(suffix):
                return FileTypeMatch(kind, suffix, "suffix", "suffix")
        return None

    def classify(self, name: str, logical_extension: str) -> FileTypeClassification:
        """Return stable classification fields without presentation state."""

        extension = normalize_logical_extension(logical_extension)
        match = self.match(name, extension)
        if match is None:
            return FileTypeClassification(
                logical_extension=extension or None,
                canonical_extension=None,
                kind_id=None,
                family_id=None,
                group_id="other",
                content_family=ContentFamily.unknown,
                detection_source="unknown",
                confidence="unknown",
                registry_revision=self.revision,
                registry_fingerprint=self.fingerprint,
            )
        return FileTypeClassification(
            logical_extension=extension or None,
            canonical_extension=match.canonical_extension,
            kind_id=match.kind.id,
            family_id=match.kind.family_id,
            group_id=match.kind.group_id,
            content_family=match.kind.content_family,
            detection_source=match.detection_source,
            confidence=match.confidence,
            registry_revision=self.revision,
            registry_fingerprint=self.fingerprint,
        )

    def projection(self) -> dict[str, object]:
        """Return the complete immutable registry as JSON-compatible values."""

        return {
            "schema": FILE_TYPE_REGISTRY_SCHEMA,
            "schema_version": self.schema_version,
            "revision": self.revision,
            "fingerprint": self.fingerprint,
            "max_extension_components": self.max_extension_components,
            "groups": tuple(
                {"id": group.id, "label": group.label, "order": group.order, "icon": group.icon}
                for group in self.groups
            ),
            "families": tuple(
                {
                    "id": family.id,
                    "label": family.label,
                    "group_id": family.group_id,
                    "order": family.order,
                    "extensions": family.extensions,
                    "hue": family.hue,
                    "linguist": family.linguist,
                    "linguist_color": family.linguist_color,
                    "icon": family.icon,
                    "deviation": family.deviation,
                    "lightness_rank": family.lightness_rank,
                }
                for family in self.families
            ),
            "kinds": tuple(
                {
                    "id": kind.id,
                    "family_id": kind.family_id,
                    "group_id": kind.group_id,
                    "content_family": kind.content_family.value,
                    "extensions": tuple(f".{extension}" for extension in kind.extensions),
                    "filenames": kind.filenames,
                    "shebangs": kind.shebangs,
                    "priority": kind.priority,
                }
                for kind in self.kinds
            ),
        }


def normalize_logical_extension(extension: str) -> str:
    """Normalize a logical extension to a lowercase leading-dot identity."""

    normalized = extension.strip().lower()
    if not normalized or normalized == FILE_TYPE_REMAINING_KEY:
        return FILE_TYPE_REMAINING_KEY
    if normalized == FILE_TYPE_NO_EXTENSION_KEY:
        return FILE_TYPE_NO_EXTENSION_KEY
    return normalized if normalized.startswith(".") else f".{normalized}"


def load_file_type_registry_from_text(text: str) -> FileTypeRegistry:
    """Parse and validate a file-type definition TOML document."""

    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise FileTypeRegistryError("invalid-toml", str(error)) from error
    schema_version = _required_positive_int(raw, "schema_version")
    if schema_version != FILE_TYPE_REGISTRY_SCHEMA_VERSION:
        raise FileTypeRegistryError(
            "unsupported-schema-version",
            "unsupported registry schema version",
            field_name="schema_version",
            value=schema_version,
        )
    revision = _required_positive_int(raw, "registry_revision")
    max_components = _required_positive_int(raw, "max_extension_components")
    if max_components != 2:
        raise FileTypeRegistryError(
            "unsupported-extension-components",
            "the recommended file-type profile requires two extension components",
            field_name="max_extension_components",
            value=max_components,
        )

    groups = _parse_groups(_table_list(raw, "group"))
    family_declarations = _parse_families(_table_list(raw, "family"), groups)
    kinds = _parse_kinds(
        _table_list(raw, "kind"),
        groups,
        family_declarations,
        max_components,
    )
    families = _materialize_families(family_declarations, kinds)
    fingerprint = _registry_fingerprint(
        schema_version,
        revision,
        max_components,
        groups,
        families,
        kinds,
    )
    return FileTypeRegistry(
        schema_version=schema_version,
        revision=revision,
        max_extension_components=max_components,
        groups=groups,
        families=families,
        kinds=kinds,
        fingerprint=fingerprint,
    )


@cache
def load_file_type_registry() -> FileTypeRegistry:
    """Load the packaged registry once per process."""

    resource = files("metabrowser").joinpath(FILE_TYPE_REGISTRY_RESOURCE)
    return load_file_type_registry_from_text(resource.read_text(encoding="utf-8"))


def _required_positive_int(raw: Mapping[str, Any], field_name: str) -> int:
    value = raw.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise FileTypeRegistryError(
            "invalid-field",
            "expected a positive integer",
            field_name=field_name,
            value=value,
        )
    return value


def _table_list(raw: Mapping[str, Any], field_name: str) -> list[Mapping[str, Any]]:
    value = raw.get(field_name)
    if not isinstance(value, list):
        raise FileTypeRegistryError(
            "invalid-field",
            "expected an array of tables",
            field_name=field_name,
            value=value,
        )
    tables: list[Mapping[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise FileTypeRegistryError(
                "invalid-field",
                "expected a table",
                field_name=field_name,
                value=item,
            )
        tables.append(cast(Mapping[str, Any], item))
    return tables


def _required_string(raw: Mapping[str, Any], field_name: str, table_id: str) -> str:
    value = raw.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise FileTypeRegistryError(
            "invalid-field",
            "expected a nonempty string",
            table_id=table_id,
            field_name=field_name,
            value=value,
        )
    return value


def _required_integer(raw: Mapping[str, Any], field_name: str, table_id: str) -> int:
    value = raw.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise FileTypeRegistryError(
            "invalid-field",
            "expected an integer",
            table_id=table_id,
            field_name=field_name,
            value=value,
        )
    return value


def _parse_linguist(raw: Mapping[str, Any], table_id: str) -> tuple[str | None, str | None]:
    """The upstream language name and its hex, which are present together or not at all.

    Together, because a name without its colour cannot be checked and a colour
    without its name cannot be traced.
    """

    name, color = raw.get("linguist"), raw.get("linguist_color")
    if name is None and color is None:
        return None, None
    if not isinstance(name, str) or not name.strip():
        raise FileTypeRegistryError(
            "invalid-linguist",
            "family linguist name must be a non-empty string",
            table_id=table_id,
            field_name="linguist",
            value=name,
        )
    if not isinstance(color, str) or not _VALID_HEX.fullmatch(color):
        raise FileTypeRegistryError(
            "invalid-linguist",
            "family linguist_color must be a six-digit hex color",
            table_id=table_id,
            field_name="linguist_color",
            value=color,
        )
    return name.strip(), color.lower()


def _parse_deviation(raw: Mapping[str, Any], table_id: str) -> tuple[str | None, float | None]:
    """Read the deliberate departure from where upstream would put a family.

    ``lightness_rank`` requires a ``deviation``, and not the other way round: a
    hue can leave GitHub's on its own, but leaving the band is never something
    that should be readable as a typo.
    """

    deviation = raw.get("deviation")
    rank = raw.get("lightness_rank")
    if deviation is not None and (not isinstance(deviation, str) or not deviation.strip()):
        raise FileTypeRegistryError(
            "invalid-field",
            "family deviation must be a nonempty string saying why",
            table_id=table_id,
            field_name="deviation",
            value=deviation,
        )
    if rank is not None:
        if isinstance(rank, bool) or not isinstance(rank, int | float):
            raise FileTypeRegistryError(
                "invalid-field",
                "expected a number",
                table_id=table_id,
                field_name="lightness_rank",
                value=rank,
            )
        if deviation is None:
            raise FileTypeRegistryError(
                "undeclared-deviation",
                "family lightness_rank needs a deviation recording why it leaves "
                "the rank its upstream colour gives it",
                table_id=table_id,
                field_name="lightness_rank",
                value=rank,
            )
    return (
        deviation.strip() if isinstance(deviation, str) else None,
        float(rank) if rank is not None else None,
    )


def _required_hue(raw: Mapping[str, Any], table_id: str) -> float:
    """A hue in degrees, half-open on 360 so one hue has one spelling."""

    value = raw.get("hue")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FileTypeRegistryError(
            "invalid-field", "expected a number", table_id=table_id, field_name="hue", value=value
        )
    if not 0.0 <= float(value) < 360.0:
        raise FileTypeRegistryError(
            "invalid-hue",
            "family hue must be in [0, 360) degrees",
            table_id=table_id,
            field_name="hue",
            value=value,
        )
    return float(value)


def _string_tuple(raw: Mapping[str, Any], field_name: str, table_id: str) -> tuple[str, ...]:
    value = raw.get(field_name)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise FileTypeRegistryError(
            "invalid-field",
            "expected an array of strings",
            table_id=table_id,
            field_name=field_name,
            value=value,
        )
    return tuple(cast(list[str], value))


def _validate_id(value: str, table_name: str) -> None:
    if not _VALID_ID.fullmatch(value):
        raise FileTypeRegistryError(
            "invalid-id",
            f"invalid {table_name} id",
            table_id=value,
            field_name="id",
            value=value,
        )


def _parse_groups(raw_groups: list[Mapping[str, Any]]) -> tuple[FileTypeGroup, ...]:
    groups: list[FileTypeGroup] = []
    ids: set[str] = set()
    orders: set[int] = set()
    for raw in raw_groups:
        group_id = _required_string(raw, "id", "group")
        _validate_id(group_id, "group")
        if group_id in ids:
            raise FileTypeRegistryError("duplicate-id", "duplicate group id", table_id=group_id)
        label = _required_string(raw, "label", group_id).strip()
        order = _required_integer(raw, "order", group_id)
        icon = _required_string(raw, "icon", group_id).strip()
        if order in orders:
            raise FileTypeRegistryError(
                "duplicate-order", "duplicate group order", table_id=group_id, value=order
            )
        ids.add(group_id)
        orders.add(order)
        groups.append(FileTypeGroup(group_id, label, order, icon))
    if "other" not in ids:
        raise FileTypeRegistryError("missing-fallback", "registry must declare the other group")
    return tuple(sorted(groups, key=lambda group: (group.order, group.id)))


def _parse_families(
    raw_families: list[Mapping[str, Any]],
    groups: tuple[FileTypeGroup, ...],
) -> tuple[_FamilyDeclaration, ...]:
    group_ids = {group.id for group in groups}
    ids: set[str] = set()
    orders: set[tuple[str, int]] = set()
    declarations: list[_FamilyDeclaration] = []
    for raw in raw_families:
        family_id = _required_string(raw, "id", "family")
        _validate_id(family_id, "family")
        if family_id in ids:
            raise FileTypeRegistryError("duplicate-id", "duplicate family id", table_id=family_id)
        label = _required_string(raw, "label", family_id).strip()
        group_id = _required_string(raw, "group", family_id)
        if group_id not in group_ids:
            raise FileTypeRegistryError(
                "unknown-group",
                "family references an unknown group",
                table_id=family_id,
                field_name="group",
                value=group_id,
            )
        order = _required_integer(raw, "order", family_id)
        order_key = (group_id, order)
        if order_key in orders:
            raise FileTypeRegistryError(
                "duplicate-order", "duplicate family order", table_id=family_id, value=order
            )
        hue = _required_hue(raw, family_id)
        linguist, linguist_color = _parse_linguist(raw, family_id)
        deviation, lightness_rank = _parse_deviation(raw, family_id)
        raw_icon = raw.get("icon")
        if raw_icon is not None and (not isinstance(raw_icon, str) or not raw_icon.strip()):
            raise FileTypeRegistryError(
                "invalid-icon",
                "family icon must be a non-empty string when declared",
                table_id=family_id,
                field_name="icon",
                value=raw_icon,
            )
        icon = raw_icon.strip() if isinstance(raw_icon, str) else None
        ids.add(family_id)
        orders.add(order_key)
        declarations.append(
            _FamilyDeclaration(
                family_id,
                label,
                group_id,
                order,
                hue,
                linguist,
                linguist_color,
                deviation,
                lightness_rank,
                icon,
            )
        )
    group_order = {group.id: group.order for group in groups}
    return tuple(
        sorted(
            declarations,
            key=lambda family: (group_order[family.group_id], family.order, family.id),
        )
    )


def _parse_kinds(
    raw_kinds: list[Mapping[str, Any]],
    groups: tuple[FileTypeGroup, ...],
    families: tuple[_FamilyDeclaration, ...],
    max_components: int,
) -> tuple[FileTypeKind, ...]:
    group_ids = {group.id for group in groups}
    family_groups = {family.id: family.group_id for family in families}
    ids: set[str] = set()
    extensions: dict[str, str] = {}
    filenames: dict[str, str] = {}
    kinds: list[FileTypeKind] = []
    for raw in raw_kinds:
        kind_id = _required_string(raw, "id", "kind")
        _validate_id(kind_id, "kind")
        if kind_id in ids:
            raise FileTypeRegistryError("duplicate-id", "duplicate kind id", table_id=kind_id)
        raw_family = raw.get("family")
        if raw_family is not None and not isinstance(raw_family, str):
            raise FileTypeRegistryError(
                "invalid-field",
                "family must be a string when present",
                table_id=kind_id,
                field_name="family",
                value=raw_family,
            )
        family_id = raw_family
        if family_id is not None and family_id not in family_groups:
            raise FileTypeRegistryError(
                "unknown-family",
                "kind references an unknown family",
                table_id=kind_id,
                field_name="family",
                value=family_id,
            )
        raw_group = raw.get("group")
        if raw_group is not None and not isinstance(raw_group, str):
            raise FileTypeRegistryError(
                "invalid-field",
                "group must be a string when present",
                table_id=kind_id,
                field_name="group",
                value=raw_group,
            )
        if family_id is not None:
            group_id = family_groups[family_id]
            if raw_group is not None and raw_group != group_id:
                raise FileTypeRegistryError(
                    "group-mismatch",
                    "kind group conflicts with its family's group",
                    table_id=kind_id,
                    field_name="group",
                    value=raw_group,
                )
        else:
            group_id = _required_string(raw, "group", kind_id)
        if group_id not in group_ids:
            raise FileTypeRegistryError(
                "unknown-group",
                "kind references an unknown group",
                table_id=kind_id,
                field_name="group",
                value=group_id,
            )
        raw_content_family = _required_string(raw, "content_family", kind_id)
        try:
            content_family = ContentFamily(raw_content_family)
        except ValueError as error:
            raise FileTypeRegistryError(
                "invalid-content-family",
                "unknown content family",
                table_id=kind_id,
                field_name="content_family",
                value=raw_content_family,
            ) from error
        kind_extensions = _string_tuple(raw, "extensions", kind_id)
        kind_filenames = _string_tuple(raw, "filenames", kind_id)
        shebangs = _string_tuple(raw, "shebangs", kind_id)
        priority = _required_integer(raw, "priority", kind_id)
        if not kind_extensions and not kind_filenames and not shebangs:
            raise FileTypeRegistryError(
                "missing-evidence", "kind must declare supported evidence", table_id=kind_id
            )
        for extension in kind_extensions:
            components = extension.split(".")
            if (
                extension.startswith(".")
                or extension != extension.lower()
                or not 1 <= len(components) <= max_components
                or any(not _VALID_EXTENSION_COMPONENT.fullmatch(part) for part in components)
            ):
                raise FileTypeRegistryError(
                    "invalid-extension",
                    "extension is not normalized file-type registry evidence",
                    table_id=kind_id,
                    field_name="extensions",
                    value=extension,
                )
            prior = extensions.get(extension)
            if prior is not None:
                raise FileTypeRegistryError(
                    "duplicate-evidence",
                    "extension belongs to more than one kind",
                    table_id=kind_id,
                    field_name="extensions",
                    value=extension,
                )
            extensions[extension] = kind_id
        for filename in kind_filenames:
            normalized = filename.lower()
            if not normalized or filename != normalized:
                raise FileTypeRegistryError(
                    "invalid-filename",
                    "filename evidence must be lowercase",
                    table_id=kind_id,
                    field_name="filenames",
                    value=filename,
                )
            prior = filenames.get(normalized)
            if prior is not None:
                raise FileTypeRegistryError(
                    "duplicate-evidence",
                    "filename belongs to more than one kind",
                    table_id=kind_id,
                    field_name="filenames",
                    value=filename,
                )
            filenames[normalized] = kind_id
        ids.add(kind_id)
        kinds.append(
            FileTypeKind(
                kind_id,
                family_id,
                group_id,
                content_family,
                kind_extensions,
                kind_filenames,
                shebangs,
                priority,
            )
        )
    return tuple(kinds)


def _materialize_families(
    declarations: tuple[_FamilyDeclaration, ...],
    kinds: tuple[FileTypeKind, ...],
) -> tuple[FileTypeFamily, ...]:
    family_extensions: dict[str, list[str]] = {family.id: [] for family in declarations}
    for kind in kinds:
        if kind.family_id is not None:
            family_extensions[kind.family_id].extend(
                f".{extension}" for extension in kind.extensions
            )
    families: list[FileTypeFamily] = []
    for declaration in declarations:
        extensions = tuple(family_extensions[declaration.id])
        if not extensions:
            raise FileTypeRegistryError(
                "empty-family",
                "family has no declared extension evidence",
                table_id=declaration.id,
            )
        families.append(
            FileTypeFamily(
                declaration.id,
                declaration.label,
                declaration.group_id,
                declaration.order,
                extensions,
                declaration.hue,
                declaration.linguist,
                declaration.linguist_color,
                declaration.deviation,
                declaration.lightness_rank,
                declaration.icon,
            )
        )
    return tuple(families)


def _registry_fingerprint(
    schema_version: int,
    revision: int,
    max_components: int,
    groups: tuple[FileTypeGroup, ...],
    families: tuple[FileTypeFamily, ...],
    kinds: tuple[FileTypeKind, ...],
) -> str:
    """Hash normalized declarations for cross-package drift and cache identity."""

    normalized = {
        "schema_version": schema_version,
        "registry_revision": revision,
        "max_extension_components": max_components,
        "groups": [
            {"id": group.id, "label": group.label, "order": group.order, "icon": group.icon}
            for group in groups
        ],
        "families": [
            {
                "id": family.id,
                "label": family.label,
                "group": family.group_id,
                "order": family.order,
                "hue": family.hue,
                # Everything the painted colour depends on has to be in here.
                # A hue no longer determines a family's colour on its own, so a
                # fingerprint over hues alone could report two different
                # palettes as the same registry — and comparing this identity
                # before combining a rollup with colours is exactly what
                # consumers are told to do.
                "linguist_color": family.linguist_color,
                "deviation": family.deviation,
                "lightness_rank": family.lightness_rank,
            }
            for family in families
        ],
        "kinds": [
            {
                "id": kind.id,
                "family": kind.family_id,
                "group": kind.group_id,
                "content_family": kind.content_family.value,
                "extensions": list(kind.extensions),
                "filenames": list(kind.filenames),
                "shebangs": list(kind.shebangs),
                "priority": kind.priority,
            }
            for kind in kinds
        ],
    }
    payload = json.dumps(
        normalized,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "FILE_TYPE_FAMILY_KEY_PREFIX",
    "FILE_TYPE_NO_EXTENSION_KEY",
    "FILE_TYPE_REGISTRY_SCHEMA",
    "FILE_TYPE_REGISTRY_SCHEMA_VERSION",
    "FILE_TYPE_REMAINING_KEY",
    "ContentFamily",
    "FileTypeClassification",
    "FileTypeFamily",
    "FileTypeGroup",
    "FileTypeKind",
    "FileTypeMatch",
    "FileTypeRegistry",
    "FileTypeRegistryError",
    "load_file_type_registry",
    "load_file_type_registry_from_text",
    "normalize_logical_extension",
]
