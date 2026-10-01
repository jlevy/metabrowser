"""The immutable registry of artifact contracts and the codecs that validate against it."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from io import StringIO
from types import MappingProxyType
from typing import Any, Literal, cast

from frontmatter_format import new_yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from softschema import SchemaView
from softschema.canonicalize import canonicalize_json_schema
from softschema.enforcement import (
    EnforcementUnsupportedError,
    SchemaGraphError,
    prepare_schema_graph,
)
from softschema.validate import parse_yaml_text

type ArtifactProfile = Literal["pure-yaml"]
type ContractRegistry = Mapping[str, InstalledArtifactContract]

_CONTRACT_ID_RE = re.compile(r"^[a-z][a-z0-9.-]*:[A-Za-z][A-Za-z0-9._-]*/v[1-9][0-9]*$")
_STABLE_TOKEN_RE = re.compile(r"^[a-z][a-z0-9._:-]*$")
_SCHEMA_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_ARTIFACT_PROFILES = frozenset({"pure-yaml"})
_ENFORCED_STATUS = "enforced"
_JSON_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
_MAX_SAFE_INTEGER = 9_007_199_254_740_991


class ContractRegistryError(RuntimeError):
    """The declared contracts cannot produce one coherent registry.

    This is a failure of the installation, never a defect of a record being
    validated against it. Record-level validators report a defect of their input
    by raising ``ValueError``, and their callers turn that into a semantic
    problem attributed to the input; subclassing ``ValueError`` here would let
    one broken declaration be reported as a defect of every valid record
    instead. It shares the base of its sibling ``ContractInventoryError`` in
    ``artifact_inventory``.
    """


@dataclass(frozen=True, slots=True)
class ConformanceCorpusSpec:
    """Immutable packaged corpus evidence for one or more contracts."""

    corpus_id: str
    media_type: Literal["application/json"]
    payload: bytes
    payload_sha256: str


@dataclass(frozen=True, slots=True)
class ArtifactContractSpec:
    """Trusted declaration for one versioned artifact contract."""

    contract_id: str
    artifact_profile: ArtifactProfile
    envelope: str
    schema_bytes: bytes
    schema_bytes_sha256: str
    schema_digest: str
    validate_record: Callable[[dict[str, Any]], object]
    dump_record: Callable[[object], dict[str, Any]]
    producer_ids: tuple[str, ...]
    consumer_ids: tuple[str, ...]
    corpus: ConformanceCorpusSpec
    corpus_record_selectors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InstalledArtifactContract:
    """A contract whose schema and declaration passed registry validation."""

    spec: ArtifactContractSpec
    structural_validator: Draft202012Validator


@dataclass(frozen=True, slots=True)
class ValidatedArtifact:
    """A cached artifact validated against an installed contract."""

    contract_id: str
    record: object


def _runtime_descriptor_value(value: object) -> object:
    """Erase static declaration types so each declaration is checked at runtime."""
    return value


def _require_stable_ids(
    values: object,
    *,
    field_name: str,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if (
        not isinstance(values, tuple)
        or (not allow_empty and not values)
        or any(
            not isinstance(value, str) or _STABLE_TOKEN_RE.fullmatch(value) is None
            for value in values
        )
    ):
        raise ContractRegistryError(f"artifact contract {field_name} must be a tuple of stable IDs")
    if len(set(values)) != len(values):
        raise ContractRegistryError(f"artifact contract {field_name} must be unique")
    return values


def _require_packaged_bytes(
    payload: object,
    digest: object,
    *,
    contract_id: str,
    field_name: str,
) -> bytes:
    if not isinstance(payload, bytes) or not payload:
        raise ContractRegistryError(
            f"artifact contract {contract_id!r} {field_name} must be nonempty bytes"
        )
    if (
        not isinstance(digest, str)
        or _SCHEMA_DIGEST_RE.fullmatch(digest) is None
        or hashlib.sha256(payload).hexdigest() != digest
    ):
        raise ContractRegistryError(
            f"artifact contract {contract_id!r} {field_name} digest does not match"
        )
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractRegistryError(
            f"artifact contract {contract_id!r} {field_name} must be UTF-8"
        ) from exc
    return payload


def _iter_schema_references(value: object) -> Sequence[str]:
    references: list[str] = []
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            reference = current.get("$ref")
            if isinstance(reference, str):
                references.append(reference)
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
    return references


def _canonical_json(value: object) -> str:
    """Encode SoftSchema's documented portable RFC 8785 value domain."""
    if value is None:
        return "null"
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if type(value) is int:
        integer = value
        if abs(integer) > _MAX_SAFE_INTEGER:
            raise TypeError("canonical JSON integer exceeds the portable safe range")
        return str(integer)
    if type(value) is float:
        number = value
        if not math.isfinite(number):
            raise TypeError("canonical JSON requires finite numbers")
        if number == 0:
            return "0"
        magnitude = abs(number)
        text = repr(number).lower()
        if number.is_integer() and magnitude < 1e21:
            return format(Decimal(text), "f").split(".", 1)[0]
        if 1e-6 <= magnitude < 1e21 and "e" in text:
            return format(Decimal(text), "f")
        if "e" not in text:
            return text
        mantissa, exponent = text.split("e")
        sign = "+" if not exponent.startswith("-") else "-"
        digits = exponent.lstrip("+-0") or "0"
        return f"{mantissa}e{sign}{digits}"
    if type(value) is list:
        items = cast(list[object], value)
        return "[" + ",".join(_canonical_json(item) for item in items) + "]"
    if type(value) is dict:
        mapping = cast(dict[object, object], value)
        if any(type(key) is not str for key in mapping):
            raise TypeError("canonical JSON object keys must be strings")
        keys = sorted(cast(dict[str, object], mapping), key=lambda key: key.encode("utf-16be"))
        return (
            "{"
            + ",".join(f"{_canonical_json(key)}:{_canonical_json(mapping[key])}" for key in keys)
            + "}"
        )
    raise TypeError(f"canonical JSON does not support {type(value).__name__}")


def _logical_schema_digest(schema: dict[str, Any]) -> str:
    digest_input = dict(schema)
    softschema_metadata = digest_input.get("x-softschema")
    if not isinstance(softschema_metadata, dict):
        raise ContractRegistryError("artifact contract schema requires x-softschema metadata")
    identity_metadata = dict(softschema_metadata)
    identity_metadata.pop("schema_sha256", None)
    digest_input["x-softschema"] = identity_metadata
    canonical = canonicalize_json_schema(digest_input)
    return hashlib.sha256(_canonical_json(canonical).encode()).hexdigest()


def _validated_schema(spec: ArtifactContractSpec) -> dict[str, Any]:
    schema_bytes = _runtime_descriptor_value(spec.schema_bytes)
    if not isinstance(schema_bytes, bytes):
        raise ContractRegistryError("artifact contract schema must be immutable bytes")
    schema_bytes_sha256 = _runtime_descriptor_value(spec.schema_bytes_sha256)
    if (
        not isinstance(schema_bytes_sha256, str)
        or _SCHEMA_DIGEST_RE.fullmatch(schema_bytes_sha256) is None
        or hashlib.sha256(schema_bytes).hexdigest() != schema_bytes_sha256
    ):
        raise ContractRegistryError(
            f"artifact contract {spec.contract_id!r} schema bytes digest does not match"
        )
    try:
        schema_text = schema_bytes.decode("utf-8").removeprefix("\ufeff")
        decoded = parse_yaml_text(schema_text)
    except UnicodeDecodeError as exc:
        raise ContractRegistryError(
            f"artifact contract {spec.contract_id!r} schema is not UTF-8"
        ) from exc
    except ValueError as exc:
        raise ContractRegistryError(
            f"artifact contract {spec.contract_id!r} schema is not portable YAML or JSON"
        ) from exc
    if not isinstance(decoded, dict):
        raise ContractRegistryError(
            f"artifact contract {spec.contract_id!r} schema must be an object"
        )
    schema = cast(dict[str, Any], decoded)
    view = SchemaView(schema)
    try:
        schema_contract_id = view.contract_id
    except ValueError as exc:
        raise ContractRegistryError(
            f"artifact contract {spec.contract_id!r} schema has invalid x-softschema contract"
        ) from exc
    if schema_contract_id != spec.contract_id:
        raise ContractRegistryError(
            f"artifact contract {spec.contract_id!r} schema x-softschema contract does not match"
        )
    if schema.get("$schema") != _JSON_SCHEMA_DRAFT:
        raise ContractRegistryError(
            f"artifact contract {spec.contract_id!r} schema must declare Draft 2020-12"
        )
    embedded_digest = view.schema_sha256
    schema_digest = _runtime_descriptor_value(spec.schema_digest)
    if (
        not isinstance(schema_digest, str)
        or _SCHEMA_DIGEST_RE.fullmatch(schema_digest) is None
        or embedded_digest != schema_digest
        or _logical_schema_digest(schema) != schema_digest
    ):
        raise ContractRegistryError(
            f"artifact contract {spec.contract_id!r} schema digest does not match its compiled schema"
        )
    invalid_references = [
        reference
        for reference in _iter_schema_references(schema)
        if not reference.startswith("#/$defs/")
    ]
    if invalid_references:
        raise ContractRegistryError(
            f"artifact contract {spec.contract_id!r} schema may reference only local $defs"
        )
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ContractRegistryError(
            f"artifact contract {spec.contract_id!r} schema is invalid"
        ) from exc
    try:
        return prepare_schema_graph(schema).root
    except (EnforcementUnsupportedError, SchemaGraphError) as exc:
        raise ContractRegistryError(
            f"artifact contract {spec.contract_id!r} schema cannot be enforced: {exc}"
        ) from exc


def _validate_contract_spec(spec: ArtifactContractSpec) -> dict[str, Any]:
    contract_id = _runtime_descriptor_value(spec.contract_id)
    artifact_profile = _runtime_descriptor_value(spec.artifact_profile)
    envelope = _runtime_descriptor_value(spec.envelope)
    validate_record = _runtime_descriptor_value(spec.validate_record)
    dump_record = _runtime_descriptor_value(spec.dump_record)
    corpus = _runtime_descriptor_value(spec.corpus)
    if not isinstance(contract_id, str) or _CONTRACT_ID_RE.fullmatch(contract_id) is None:
        raise ContractRegistryError("artifact contract ID must be namespaced and versioned")
    if not isinstance(artifact_profile, str) or artifact_profile not in _ARTIFACT_PROFILES:
        raise ContractRegistryError(
            f"artifact contract {spec.contract_id!r} has an unsupported artifact profile"
        )
    if not isinstance(envelope, str) or _STABLE_TOKEN_RE.fullmatch(envelope) is None:
        raise ContractRegistryError(
            f"artifact contract {spec.contract_id!r} envelope must be a stable token"
        )
    if not callable(validate_record) or not callable(dump_record):
        raise ContractRegistryError(
            f"artifact contract {spec.contract_id!r} requires validator and dumper callables"
        )
    _require_stable_ids(spec.producer_ids, field_name="producer_ids")
    _require_stable_ids(spec.consumer_ids, field_name="consumer_ids")
    if not isinstance(corpus, ConformanceCorpusSpec):
        raise ContractRegistryError(
            f"artifact contract {spec.contract_id!r} requires packaged corpus evidence"
        )
    corpus_id = _runtime_descriptor_value(corpus.corpus_id)
    if not isinstance(corpus_id, str) or _STABLE_TOKEN_RE.fullmatch(corpus_id) is None:
        raise ContractRegistryError(
            f"artifact contract {spec.contract_id!r} corpus_id must be a stable ID"
        )
    if _runtime_descriptor_value(corpus.media_type) != "application/json":
        raise ContractRegistryError(
            f"artifact contract {spec.contract_id!r} corpus must use application/json"
        )
    _require_packaged_bytes(
        _runtime_descriptor_value(corpus.payload),
        _runtime_descriptor_value(corpus.payload_sha256),
        contract_id=spec.contract_id,
        field_name="corpus payload",
    )
    _require_stable_ids(
        spec.corpus_record_selectors,
        field_name="corpus_record_selectors",
        allow_empty=True,
    )
    return _validated_schema(spec)


def build_contract_registry(specs: Sequence[ArtifactContractSpec]) -> ContractRegistry:
    """Validate every declaration and return an immutable contract registry."""
    registry: dict[str, InstalledArtifactContract] = {}
    for declared_spec in specs:
        spec_object = _runtime_descriptor_value(declared_spec)
        if not isinstance(spec_object, ArtifactContractSpec):
            raise ContractRegistryError("an artifact contract declaration is invalid")
        spec = spec_object
        schema = _validate_contract_spec(spec)
        if spec.contract_id in registry:
            raise ContractRegistryError(f"duplicate artifact contract {spec.contract_id!r}")
        registry[spec.contract_id] = InstalledArtifactContract(
            spec=spec,
            structural_validator=Draft202012Validator(schema),
        )
    return MappingProxyType(registry)


def _parse_pure_yaml(payload: bytes) -> dict[str, Any]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("artifacts must be UTF-8") from exc
    try:
        metadata = parse_yaml_text(text.removeprefix("\ufeff"))
    except ValueError as exc:
        raise ValueError("artifact has malformed YAML") from exc
    if not isinstance(metadata, dict):
        raise ValueError("artifact YAML must be a mapping")
    return cast(dict[str, Any], metadata)


def _artifact_identity(metadata: Mapping[str, Any]) -> tuple[str, str]:
    softschema = metadata.get("softschema")
    if not isinstance(softschema, dict) or set(softschema) != {
        "contract",
        "envelope",
        "status",
    }:
        raise ValueError("softschema metadata must contain contract, envelope, and status")
    contract_id = softschema.get("contract")
    envelope = softschema.get("envelope")
    status = softschema.get("status")
    if not isinstance(contract_id, str) or not contract_id:
        raise ValueError("softschema contract must be a nonempty string")
    if not isinstance(envelope, str) or not envelope:
        raise ValueError("softschema envelope must be a nonempty string")
    if status != _ENFORCED_STATUS:
        raise ValueError("artifacts must use enforced contracts")
    return contract_id, envelope


def validate_artifact(
    payload: bytes,
    *,
    expected_contract_id: str,
    contracts: ContractRegistry,
) -> ValidatedArtifact:
    """Validate bytes against the installed contract selected by the trusted caller."""
    installed = contracts.get(expected_contract_id)
    if installed is None:
        raise ValueError(f"artifact slot names an unregistered contract: {expected_contract_id}")
    spec = installed.spec
    metadata = _parse_pure_yaml(payload)
    contract_id, envelope = _artifact_identity(metadata)
    if contract_id != expected_contract_id:
        raise ValueError("artifact metadata does not match its expected contract")
    if envelope != spec.envelope:
        raise ValueError(f"artifact contract {contract_id!r} requires the {spec.envelope} envelope")
    if set(metadata) != {"softschema", envelope}:
        raise ValueError("artifact metadata must contain only softschema and its declared envelope")
    record = metadata.get(envelope)
    if not isinstance(record, dict):
        raise ValueError("the declared artifact envelope must contain a mapping")
    validated = validate_record(
        cast(dict[str, Any], record),
        contract_id=contract_id,
        contracts=contracts,
    )
    return ValidatedArtifact(contract_id=contract_id, record=validated)


def validate_record(
    values: Mapping[str, Any],
    *,
    contract_id: str,
    contracts: ContractRegistry,
) -> object:
    """Validate one record through its installed structural and semantic contract."""
    installed = contracts.get(contract_id)
    if installed is None:
        raise ValueError(f"record slot names an unregistered contract: {contract_id}")
    if not isinstance(values, dict):
        values = dict(values)
    try:
        installed.structural_validator.validate(values)
    except ValidationError as exc:
        raise ValueError(f"record does not satisfy contract {contract_id!r}") from exc
    return installed.spec.validate_record(values)


def portable_serialization_values_equal(original: object, decoded: object) -> bool:
    """Compare serialized portable values without cross-type numeric coercion."""
    if type(original) is not type(decoded):
        return False
    if type(original) is dict:
        original_mapping = cast(dict[object, object], original)
        decoded_mapping = cast(dict[object, object], decoded)
        return (
            len(original_mapping) == len(decoded_mapping)
            and all(type(key) is str for key in original_mapping)
            and all(
                key in decoded_mapping
                and portable_serialization_values_equal(value, decoded_mapping[key])
                for key, value in original_mapping.items()
            )
        )
    if type(original) is list:
        original_list = cast(list[object], original)
        decoded_list = cast(list[object], decoded)
        return len(original_list) == len(decoded_list) and all(
            portable_serialization_values_equal(left, right)
            for left, right in zip(original_list, decoded_list, strict=True)
        )
    return type(original) in {str, int, float, bool, type(None)} and original == decoded


def serialize_artifact(
    record: object,
    *,
    contract_id: str,
    contracts: ContractRegistry,
) -> bytes:
    """Serialize one validated record with installed contract metadata."""
    installed = contracts.get(contract_id)
    if installed is None:
        raise ValueError(f"artifact slot names an unregistered contract: {contract_id}")
    spec = installed.spec
    dumped_object = _runtime_descriptor_value(spec.dump_record(record))
    if not isinstance(dumped_object, dict):
        raise TypeError("artifact contract dumper must return a mapping")
    dumped = cast(dict[str, Any], dumped_object)
    validate_record(dumped, contract_id=contract_id, contracts=contracts)
    metadata = {
        "softschema": {
            "contract": contract_id,
            "envelope": spec.envelope,
            "status": _ENFORCED_STATUS,
        },
        spec.envelope: dumped,
    }
    stream = StringIO()
    new_yaml(typ="safe", allow_aliases=False, suppress_vals=None).dump(metadata, stream)
    yaml_text = stream.getvalue()
    try:
        decoded_metadata = parse_yaml_text(yaml_text)
    except ValueError as exc:
        raise ValueError("artifact contract dumper produced non-portable YAML values") from exc
    if not portable_serialization_values_equal(metadata, decoded_metadata):
        raise ValueError("artifact contract dumper produced non-portable YAML values")
    return yaml_text.encode()


__all__ = [
    "ArtifactContractSpec",
    "ArtifactProfile",
    "ConformanceCorpusSpec",
    "ContractRegistry",
    "ContractRegistryError",
    "InstalledArtifactContract",
    "ValidatedArtifact",
    "build_contract_registry",
    "portable_serialization_values_equal",
    "serialize_artifact",
    "validate_artifact",
    "validate_record",
]
