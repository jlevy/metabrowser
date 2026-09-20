"""Immutable registries for installed artifact contracts and resource profiles."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from io import StringIO
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

from frontmatter_format import FmFormatError, FmStyle, new_yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from softschema import SchemaView
from softschema.canonicalize import canonicalize_json_schema
from softschema.enforcement import (
    EnforcementUnsupportedError,
    SchemaGraphError,
    prepare_schema_graph,
)
from softschema.validate import parse_frontmatter_text, parse_yaml_text

from metabrowser.plugin_loader.capability_types import (
    ArtifactContractSpec,
    ArtifactProfile,
    ArtifactValidationContext,
    BrowserParserSpec,
    CapabilitySet,
    ConformanceCorpusSpec,
)
from metabrowser.provider_resources.profiles import ResourceProfileSpec

if TYPE_CHECKING:
    from metabrowser.plugin_loader.capability_discovery import (
        CapabilityDiscoveryResult,
        LoadedCapabilitySet,
    )

type ContractRegistry = Mapping[str, InstalledArtifactContract]
type ResourceProfileRegistry = Mapping[str, ResourceProfileSpec]

_CONTRACT_ID_RE = re.compile(r"^[a-z][a-z0-9.-]*:[A-Za-z][A-Za-z0-9._-]*/v[1-9][0-9]*$")
_STABLE_TOKEN_RE = re.compile(r"^[a-z][a-z0-9._:-]*$")
_SCHEMA_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_BROWSER_MODULE_ID_RE = re.compile(r"^[a-z][a-z0-9._-]*$")
_BROWSER_EXPORT_NAME_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
_ARTIFACT_PROFILES = frozenset({"frontmatter-md", "pure-yaml"})
_ENFORCED_STATUS = "enforced"
_JSON_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
_MAX_SAFE_INTEGER = 9_007_199_254_740_991


class CapabilityRegistryError(RuntimeError):
    """An installed capability set cannot produce one coherent registry.

    This is a failure of the installation, never a defect of a record being
    validated against it. Record-level validators report a defect of their input
    by raising ``ValueError``, and their callers turn that into a semantic
    problem attributed to the input; subclassing ``ValueError`` here let one
    broken third-party entry point be reported as a defect of every valid
    record instead. It shares the base of its sibling
    ``CapabilityInventoryError`` in ``artifact_inventory``.
    """


@dataclass(frozen=True, slots=True)
class InstalledArtifactContract:
    """A contract whose schema and declaration passed registry validation."""

    spec: ArtifactContractSpec
    provider_id: str
    structural_validator: Draft202012Validator
    validation_context: ArtifactValidationContext


@dataclass(frozen=True, slots=True)
class InstalledRegistries:
    """One all-or-nothing snapshot of installed backend capabilities."""

    contracts: ContractRegistry
    resource_profiles: ResourceProfileRegistry


@dataclass(frozen=True, slots=True)
class ValidatedArtifact:
    """A cached artifact validated against an installed contract."""

    contract_id: str
    record: object
    body: str


def _runtime_descriptor_value(value: object) -> object:
    """Erase static declaration types so installed providers are checked at runtime."""
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
        raise CapabilityRegistryError(
            f"artifact contract {field_name} must be a tuple of stable IDs"
        )
    if len(set(values)) != len(values):
        raise CapabilityRegistryError(f"artifact contract {field_name} must be unique")
    return values


def _require_packaged_bytes(
    payload: object,
    digest: object,
    *,
    contract_id: str,
    field_name: str,
) -> bytes:
    if not isinstance(payload, bytes) or not payload:
        raise CapabilityRegistryError(
            f"artifact contract {contract_id!r} {field_name} must be nonempty bytes"
        )
    if (
        not isinstance(digest, str)
        or _SCHEMA_DIGEST_RE.fullmatch(digest) is None
        or hashlib.sha256(payload).hexdigest() != digest
    ):
        raise CapabilityRegistryError(
            f"artifact contract {contract_id!r} {field_name} digest does not match"
        )
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CapabilityRegistryError(
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
        raise CapabilityRegistryError("artifact contract schema requires x-softschema metadata")
    identity_metadata = dict(softschema_metadata)
    identity_metadata.pop("schema_sha256", None)
    digest_input["x-softschema"] = identity_metadata
    canonical = canonicalize_json_schema(digest_input)
    return hashlib.sha256(_canonical_json(canonical).encode()).hexdigest()


def _validated_schema(spec: ArtifactContractSpec) -> dict[str, Any]:
    schema_bytes = _runtime_descriptor_value(spec.schema_bytes)
    if not isinstance(schema_bytes, bytes):
        raise CapabilityRegistryError("artifact contract schema must be immutable bytes")
    schema_bytes_sha256 = _runtime_descriptor_value(spec.schema_bytes_sha256)
    if (
        not isinstance(schema_bytes_sha256, str)
        or _SCHEMA_DIGEST_RE.fullmatch(schema_bytes_sha256) is None
        or hashlib.sha256(schema_bytes).hexdigest() != schema_bytes_sha256
    ):
        raise CapabilityRegistryError(
            f"artifact contract {spec.contract_id!r} schema bytes digest does not match"
        )
    try:
        schema_text = schema_bytes.decode("utf-8").removeprefix("\ufeff")
        decoded = parse_yaml_text(schema_text)
    except UnicodeDecodeError as exc:
        raise CapabilityRegistryError(
            f"artifact contract {spec.contract_id!r} schema is not UTF-8"
        ) from exc
    except ValueError as exc:
        raise CapabilityRegistryError(
            f"artifact contract {spec.contract_id!r} schema is not portable YAML or JSON"
        ) from exc
    if not isinstance(decoded, dict):
        raise CapabilityRegistryError(
            f"artifact contract {spec.contract_id!r} schema must be an object"
        )
    schema = cast(dict[str, Any], decoded)
    view = SchemaView(schema)
    try:
        schema_contract_id = view.contract_id
    except ValueError as exc:
        raise CapabilityRegistryError(
            f"artifact contract {spec.contract_id!r} schema has invalid x-softschema contract"
        ) from exc
    if schema_contract_id != spec.contract_id:
        raise CapabilityRegistryError(
            f"artifact contract {spec.contract_id!r} schema x-softschema contract does not match"
        )
    if schema.get("$schema") != _JSON_SCHEMA_DRAFT:
        raise CapabilityRegistryError(
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
        raise CapabilityRegistryError(
            f"artifact contract {spec.contract_id!r} schema digest does not match its compiled schema"
        )
    invalid_references = [
        reference
        for reference in _iter_schema_references(schema)
        if not reference.startswith("#/$defs/")
    ]
    if invalid_references:
        raise CapabilityRegistryError(
            f"artifact contract {spec.contract_id!r} schema may reference only local $defs"
        )
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise CapabilityRegistryError(
            f"artifact contract {spec.contract_id!r} schema is invalid"
        ) from exc
    try:
        return prepare_schema_graph(schema).root
    except (EnforcementUnsupportedError, SchemaGraphError) as exc:
        raise CapabilityRegistryError(
            f"artifact contract {spec.contract_id!r} schema cannot be enforced: {exc}"
        ) from exc


def _validate_contract_spec(spec: ArtifactContractSpec) -> dict[str, Any]:
    contract_id = _runtime_descriptor_value(spec.contract_id)
    artifact_profile = _runtime_descriptor_value(spec.artifact_profile)
    envelope = _runtime_descriptor_value(spec.envelope)
    validate_record = _runtime_descriptor_value(spec.validate_record)
    dump_record = _runtime_descriptor_value(spec.dump_record)
    corpus = _runtime_descriptor_value(spec.corpus)
    browser_consumed = _runtime_descriptor_value(spec.browser_consumed)
    browser_parser = _runtime_descriptor_value(spec.browser_parser)
    if not isinstance(contract_id, str) or _CONTRACT_ID_RE.fullmatch(contract_id) is None:
        raise CapabilityRegistryError("artifact contract ID must be namespaced and versioned")
    if not isinstance(artifact_profile, str) or artifact_profile not in _ARTIFACT_PROFILES:
        raise CapabilityRegistryError(
            f"artifact contract {spec.contract_id!r} has an unsupported artifact profile"
        )
    if not isinstance(envelope, str) or _STABLE_TOKEN_RE.fullmatch(envelope) is None:
        raise CapabilityRegistryError(
            f"artifact contract {spec.contract_id!r} envelope must be a stable token"
        )
    if not callable(validate_record) or not callable(dump_record):
        raise CapabilityRegistryError(
            f"artifact contract {spec.contract_id!r} requires validator and dumper callables"
        )
    _require_stable_ids(spec.producer_ids, field_name="producer_ids")
    _require_stable_ids(spec.consumer_ids, field_name="consumer_ids")
    if not isinstance(corpus, ConformanceCorpusSpec):
        raise CapabilityRegistryError(
            f"artifact contract {spec.contract_id!r} requires packaged corpus evidence"
        )
    corpus_id = _runtime_descriptor_value(corpus.corpus_id)
    if not isinstance(corpus_id, str) or _STABLE_TOKEN_RE.fullmatch(corpus_id) is None:
        raise CapabilityRegistryError(
            f"artifact contract {spec.contract_id!r} corpus_id must be a stable ID"
        )
    if _runtime_descriptor_value(corpus.media_type) != "application/json":
        raise CapabilityRegistryError(
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
    if type(browser_consumed) is not bool:
        raise CapabilityRegistryError(
            f"artifact contract {spec.contract_id!r} browser_consumed must be a boolean"
        )
    if browser_consumed and browser_parser is None:
        raise CapabilityRegistryError(
            f"browser-consumed artifact contract {spec.contract_id!r} requires browser parser evidence"
        )
    if not browser_consumed and browser_parser is not None:
        raise CapabilityRegistryError(
            f"server-only artifact contract {spec.contract_id!r} cannot declare browser parser evidence"
        )
    if browser_parser is not None:
        if not isinstance(browser_parser, BrowserParserSpec):
            raise CapabilityRegistryError(
                f"artifact contract {spec.contract_id!r} browser parser must name a JS export"
            )
        module_id = _runtime_descriptor_value(browser_parser.module_id)
        export_name = _runtime_descriptor_value(browser_parser.export_name)
        if (
            not isinstance(module_id, str)
            or _BROWSER_MODULE_ID_RE.fullmatch(module_id) is None
            or not isinstance(export_name, str)
            or _BROWSER_EXPORT_NAME_RE.fullmatch(export_name) is None
        ):
            raise CapabilityRegistryError(
                f"artifact contract {spec.contract_id!r} browser parser must name a JS export"
            )
        _require_packaged_bytes(
            _runtime_descriptor_value(browser_parser.module_bytes),
            _runtime_descriptor_value(browser_parser.module_bytes_sha256),
            contract_id=spec.contract_id,
            field_name="browser parser module",
        )
    return _validated_schema(spec)


def build_contract_registry(providers: Sequence[LoadedCapabilitySet]) -> ContractRegistry:
    """Validate all installed declarations and return an immutable contract registry."""
    registry: dict[str, InstalledArtifactContract] = {}
    for provider in providers:
        for declared_spec in provider.capabilities.artifact_contracts:
            spec_object = _runtime_descriptor_value(declared_spec)
            if not isinstance(spec_object, ArtifactContractSpec):
                raise CapabilityRegistryError(
                    f"capability provider {provider.provider_id!r} declared an invalid artifact contract"
                )
            spec = spec_object
            schema = _validate_contract_spec(spec)
            if spec.contract_id in registry:
                raise CapabilityRegistryError(f"duplicate artifact contract {spec.contract_id!r}")
            registry[spec.contract_id] = InstalledArtifactContract(
                spec=spec,
                provider_id=provider.provider_id,
                structural_validator=Draft202012Validator(schema),
                validation_context=ArtifactValidationContext(
                    resource_profiles=MappingProxyType({})
                ),
            )
    return MappingProxyType(registry)


def build_resource_profile_registry(
    providers: Sequence[LoadedCapabilitySet],
    *,
    contracts: ContractRegistry,
) -> ResourceProfileRegistry:
    """Validate profile references and return an immutable profile registry."""
    registry: dict[str, ResourceProfileSpec] = {}
    for provider in providers:
        for declared_profile in provider.capabilities.resource_profiles:
            profile_object = _runtime_descriptor_value(declared_profile)
            if not isinstance(profile_object, ResourceProfileSpec):
                raise CapabilityRegistryError(
                    f"capability provider {provider.provider_id!r} declared an invalid resource profile"
                )
            profile = profile_object
            if profile.profile_id in registry:
                raise CapabilityRegistryError(f"duplicate resource profile {profile.profile_id!r}")
            referenced_contract_ids = {
                collection.artifact_contract_id for collection in profile.collections
            }
            if profile.target_result_contract_id is not None:
                referenced_contract_ids.add(profile.target_result_contract_id)
            missing_contract_ids = sorted(referenced_contract_ids.difference(contracts))
            if missing_contract_ids:
                raise CapabilityRegistryError(
                    f"resource profile {profile.profile_id!r} references unregistered artifact "
                    f"contract {missing_contract_ids[0]!r}"
                )
            foreign_contract_ids = sorted(
                contract_id
                for contract_id in referenced_contract_ids
                if contracts[contract_id].provider_id != provider.provider_id
            )
            if foreign_contract_ids:
                raise CapabilityRegistryError(
                    f"resource profile {profile.profile_id!r} references artifact contract "
                    f"{foreign_contract_ids[0]!r} owned by another capability provider"
                )
            registry[profile.profile_id] = profile
    return MappingProxyType(registry)


def build_installed_registries(
    discovery: CapabilityDiscoveryResult | None = None,
) -> InstalledRegistries:
    """Discover and atomically validate one installed capability snapshot."""
    if discovery is None:
        from metabrowser.plugin_loader.capability_discovery import discover_capability_sets

        discovery = discover_capability_sets()
    if discovery.errors:
        raise CapabilityRegistryError("capability discovery failed: " + "; ".join(discovery.errors))
    contracts = build_contract_registry(discovery.providers)
    profiles = build_resource_profile_registry(discovery.providers, contracts=contracts)
    context = ArtifactValidationContext(resource_profiles=profiles)
    bound_contracts = MappingProxyType(
        {
            contract_id: replace(installed, validation_context=context)
            for contract_id, installed in contracts.items()
        }
    )
    return InstalledRegistries(contracts=bound_contracts, resource_profiles=profiles)


# One process-wide outcome, success or failure. Building the snapshot parses,
# digests, and compiles the enforcement graph of every installed contract
# schema, so it costs roughly one compile per installed contract: eleven warm
# builds of the 16 built-in contracts measured 0.9 s at the minimum and 2.0 s at
# the median on a contended machine, so most of a second even before subtracting
# that contention. Installed capabilities cannot change while the process runs,
# which makes a failure as final as a success, so both are retained. Retaining
# only the success charged that whole build, plus entry-point discovery, to
# every record validated for the rest of a process that had one broken provider.
_installed_snapshot: InstalledRegistries | None = None
_installed_failure: CapabilityRegistryError | None = None


def get_installed_registries() -> InstalledRegistries:
    """Return the process-wide immutable installed capability snapshot."""
    global _installed_snapshot, _installed_failure
    if _installed_failure is not None:
        # Raise a fresh error rather than the retained one, whose traceback
        # would otherwise grow by a frame on every call.
        raise CapabilityRegistryError(str(_installed_failure)) from _installed_failure
    if _installed_snapshot is None:
        try:
            _installed_snapshot = build_installed_registries()
        except CapabilityRegistryError as exc:
            _installed_failure = exc
            raise
    return _installed_snapshot


def reset_installed_registries_for_tests() -> None:
    """Discard the retained snapshot so a test can install other capabilities."""
    global _installed_snapshot, _installed_failure
    _installed_snapshot = None
    _installed_failure = None


def resolve_resource_profile(
    profile_id: str,
    *,
    profiles: ResourceProfileRegistry,
) -> ResourceProfileSpec:
    """Resolve a profile only from an explicitly supplied installed registry."""
    profile = profiles.get(profile_id)
    if profile is None:
        raise ValueError("resource set names an unregistered profile")
    return profile


def _decode_artifact(payload: bytes) -> str:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FmFormatError("artifacts must be UTF-8") from exc
    return text.removeprefix("\ufeff")


def _frontmatter_body(text: str) -> str:
    lines = text.splitlines(keepends=True)
    cursor = len(lines[0]) if lines else 0
    for line in lines[1:]:
        cursor += len(line)
        if line.rstrip() == FmStyle.yaml.end:
            return text[cursor:]
    raise FmFormatError("artifact has no closing frontmatter delimiter")


def _parse_frontmatter(payload: bytes) -> tuple[dict[str, Any], str]:
    text = _decode_artifact(payload)
    try:
        _normalized_body, metadata = parse_frontmatter_text(text, source="<artifact>")
    except ValueError as exc:
        raise FmFormatError("artifact has malformed YAML frontmatter") from exc
    if not isinstance(metadata, dict):
        raise FmFormatError("artifact frontmatter must be a mapping")
    return cast(dict[str, Any], metadata), _frontmatter_body(text)


def _parse_pure_yaml(payload: bytes) -> tuple[dict[str, Any], str]:
    text = _decode_artifact(payload)
    try:
        metadata = parse_yaml_text(text)
    except ValueError as exc:
        raise FmFormatError("artifact has malformed YAML") from exc
    if not isinstance(metadata, dict):
        raise FmFormatError("artifact YAML must be a mapping")
    return cast(dict[str, Any], metadata), ""


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
    if spec.artifact_profile == "frontmatter-md":
        metadata, body = _parse_frontmatter(payload)
    else:
        metadata, body = _parse_pure_yaml(payload)
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
    return ValidatedArtifact(contract_id=contract_id, record=validated, body=body)


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
    return installed.spec.validate_record(values, installed.validation_context)


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
    body: str = "",
) -> bytes:
    """Serialize one validated record with installed contract metadata."""
    installed = contracts.get(contract_id)
    if installed is None:
        raise ValueError(f"artifact slot names an unregistered contract: {contract_id}")
    body_object = _runtime_descriptor_value(body)
    if not isinstance(body_object, str):
        raise TypeError("artifact body must be a string")
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
    if spec.artifact_profile == "frontmatter-md":
        return f"{FmStyle.yaml.start}\n{yaml_text}{FmStyle.yaml.end}\n{body_object}".encode()
    if body_object:
        raise ValueError("pure-YAML artifacts cannot contain a Markdown body")
    return yaml_text.encode()


def contract_inventory(contracts: ContractRegistry) -> tuple[dict[str, object], ...]:
    """Return stable public metadata without provider or Python-module ownership."""
    inventory: list[dict[str, object]] = []
    for contract_id in sorted(contracts):
        spec = contracts[contract_id].spec
        inventory.append(
            {
                "contract_id": spec.contract_id,
                "artifact_profile": spec.artifact_profile,
                "envelope": spec.envelope,
                "schema_bytes_sha256": spec.schema_bytes_sha256,
                "schema_digest": spec.schema_digest,
                "producer_ids": spec.producer_ids,
                "consumer_ids": spec.consumer_ids,
                "corpus_id": spec.corpus.corpus_id,
                "corpus_media_type": spec.corpus.media_type,
                "corpus_payload_sha256": spec.corpus.payload_sha256,
                "corpus_record_selectors": spec.corpus_record_selectors,
                "browser_consumed": spec.browser_consumed,
                "browser_parser_id": (
                    spec.browser_parser.parser_id if spec.browser_parser is not None else None
                ),
                "browser_parser_module_sha256": (
                    spec.browser_parser.module_bytes_sha256
                    if spec.browser_parser is not None
                    else None
                ),
            }
        )
    return tuple(inventory)


__all__ = [
    "ArtifactContractSpec",
    "ArtifactProfile",
    "BrowserParserSpec",
    "CapabilityRegistryError",
    "CapabilitySet",
    "ConformanceCorpusSpec",
    "ContractRegistry",
    "InstalledArtifactContract",
    "InstalledRegistries",
    "ResourceProfileRegistry",
    "ValidatedArtifact",
    "build_contract_registry",
    "build_installed_registries",
    "build_resource_profile_registry",
    "contract_inventory",
    "get_installed_registries",
    "portable_serialization_values_equal",
    "reset_installed_registries_for_tests",
    "resolve_resource_profile",
    "serialize_artifact",
    "validate_artifact",
    "validate_record",
]
