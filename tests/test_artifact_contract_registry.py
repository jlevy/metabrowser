"""The contract registry: which declarations it installs, and which payloads it reads.

The repository cache builds this registry from its packaged schemas and reads and writes
every record through it (``metabrowser/cache/contracts.py``, ``cache/atomic.py``). These
cases use the one synthetic contract in ``tests/artifact_contract_fixture.py``, so each
refusal has a single cause. The cache's own contracts go through the same functions in
``tests/test_cache_records.py``, which also holds the refusal of a status other than
``enforced``, and ``tests/test_cache_atomic.py`` holds the turn of a refusal into a
``RecordError``.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from typing import Any, cast

import pytest

from metabrowser.plugin_loader.artifact_contracts import (
    ContractRegistryError,
    build_contract_registry,
    serialize_artifact,
    validate_artifact,
    validate_record,
)
from tests.artifact_contract_fixture import (
    CONTRACT_ID,
    DRAFT,
    RESERVED_NAME,
    compact_json,
    contract,
    declared,
    schema,
)

# ── Declarations ───────────────────────────────────────────────────────────────

_NO_DIGEST = "0" * 64
_DRAFT_07 = "http://json-schema.org/draft-07/schema#"
# A schema whose text changed after it was compiled, so it embeds the old digest.
_EDITED = json.loads(schema()["schema_bytes"]) | {"description": "added afterwards"}


def _yaml_schema(properties: str) -> dict[str, Any]:
    """A schema written as YAML, which has to stay inside the portable subset."""

    text = (
        f"$schema: {DRAFT}\ntype: object\nproperties:\n{properties}"
        f"x-softschema:\n  contract: {CONTRACT_ID}\n  schema_sha256: {_NO_DIGEST}\n"
    )
    return declared(text.encode(), schema_digest=_NO_DIGEST)


_REFUSED_DECLARATIONS: dict[str, tuple[str, dict[str, Any]]] = {
    "contract-id-is-not-a-string": ("contract ID", {"contract_id": []}),
    "profile-the-registry-does-not-read": (
        "unsupported artifact profile",
        {"artifact_profile": "frontmatter-md"},
    ),
    "schema-bytes-changed-after-hashing": (
        "schema bytes digest",
        {"schema_bytes": schema()["schema_bytes"] + b"\n"},
    ),
    "declared-digest-is-wrong": ("schema digest", {"schema_digest": _NO_DIGEST}),
    "schema-edited-without-recompiling": ("schema digest", declared(compact_json(_EDITED))),
    "schema-names-another-contract": (
        "x-softschema contract",
        schema(**{"x-softschema": {"contract": "example.test:Wrong/v1"}}),
    ),
    "remote-reference": (r"local \$defs", schema(**{"$ref": "https://schemas.example/item.json"})),
    "unresolved-reference": ("cannot be enforced", schema(**{"$ref": "#/$defs/Missing"})),
    "dynamic-reference": (
        "cannot be enforced",
        schema(**{"$dynamicRef": "https://example.invalid/item"}),
    ),
    "no-dialect": ("must declare Draft 2020-12", schema(**{"$schema": None})),
    "draft-07": ("must declare Draft 2020-12", schema(**{"$schema": _DRAFT_07})),
    "yaml-anchor": (
        "schema is not portable",
        _yaml_schema("  name: &name_schema\n    type: string\n"),
    ),
    "integer-past-the-safe-range": (
        "schema is not portable",
        _yaml_schema("  count:\n    minimum: 9007199254740993\n"),
    ),
    "corpus-changed-after-hashing": (
        "corpus payload digest",
        {"corpus": replace(contract().corpus, payload=b'{"changed":true}')},
    ),
    "repeated-selector": ("must be unique", {"corpus_record_selectors": ("item", "item")}),
}


@pytest.mark.parametrize(
    ("match", "fields"), _REFUSED_DECLARATIONS.values(), ids=_REFUSED_DECLARATIONS
)
def test_a_declaration_the_registry_cannot_enforce_is_refused(
    match: str, fields: dict[str, Any]
) -> None:
    with pytest.raises(ContractRegistryError, match=match):
        build_contract_registry((contract(**fields),))


def test_duplicate_contract_ids_fail_even_when_declarations_match() -> None:
    with pytest.raises(ContractRegistryError, match="duplicate artifact contract"):
        build_contract_registry((contract(), contract()))


def test_the_registry_cannot_be_changed_after_it_is_built() -> None:
    contracts = build_contract_registry((contract(),))

    with pytest.raises(TypeError):
        cast(dict[str, object], contracts)[CONTRACT_ID] = object()


# ── Payloads ───────────────────────────────────────────────────────────────────

_PAYLOAD = (
    b"softschema:\n"
    b"  contract: example.test:Item/v1\n"
    b"  envelope: item\n"
    b"  status: enforced\n"
    b"item:\n"
    b"  name: accepted\n"
)


@pytest.mark.parametrize(
    "payload",
    [_PAYLOAD, b"\xef\xbb\xbf" + _PAYLOAD.replace(b"\n", b"\r\n")],
    ids=["plain", "byte-order-mark-and-crlf"],
)
def test_a_payload_is_read_against_the_contract_its_slot_installs(payload: bytes) -> None:
    registry = build_contract_registry((contract(),))

    artifact = validate_artifact(payload, expected_contract_id=CONTRACT_ID, contracts=registry)

    assert artifact.contract_id == CONTRACT_ID
    assert artifact.record == {"name": "accepted"}


_REFUSED_PAYLOADS: dict[str, tuple[str, bytes]] = {
    "not-utf-8": ("must be UTF-8", b"\xff\xfe"),
    "yaml-anchor": ("malformed YAML", _PAYLOAD.replace(b"name: ", b"name: &name ")),
    "root-is-a-list": ("must be a mapping", b"- softschema\n- item\n"),
    "metadata-is-not-a-mapping": (
        "contract, envelope, and status",
        b"softschema: [contract, envelope, status]\nitem:\n  name: accepted\n",
    ),
    "supplies-its-own-schema": (
        "contract, envelope, and status",
        _PAYLOAD.replace(b"item:\n", b"  schema: ./attacker.schema.json\nitem:\n"),
    ),
    "another-envelope": (
        "requires the item envelope",
        _PAYLOAD.replace(b"envelope: item", b"envelope: other").replace(b"item:", b"other:"),
    ),
    "extra-top-level-key": ("only softschema and its declared envelope", _PAYLOAD + b"extra: 1\n"),
    "envelope-is-not-a-mapping": (
        "must contain a mapping",
        _PAYLOAD.replace(b"item:\n  name: accepted\n", b"item: accepted\n"),
    ),
    "breaks-the-schema": ("does not satisfy contract", _PAYLOAD.replace(b"accepted", b'""')),
    "breaks-the-semantic-rule": (
        "reserved item name",
        _PAYLOAD.replace(b"accepted", RESERVED_NAME.encode()),
    ),
}


@pytest.mark.parametrize(("match", "payload"), _REFUSED_PAYLOADS.values(), ids=_REFUSED_PAYLOADS)
def test_a_payload_outside_its_contract_is_refused(match: str, payload: bytes) -> None:
    registry = build_contract_registry((contract(),))

    with pytest.raises(ValueError, match=match):
        validate_artifact(payload, expected_contract_id=CONTRACT_ID, contracts=registry)


def test_a_payload_naming_another_installed_contract_is_refused_whatever_its_envelope() -> None:
    """Two of the cache's contracts share the envelope ``state``; only the ID parts them."""

    other_id = "example.test:Other/v1"
    other = contract(contract_id=other_id, **schema(**{"x-softschema": {"contract": other_id}}))
    registry = build_contract_registry((contract(), other))
    assert registry[other_id].spec.envelope == registry[CONTRACT_ID].spec.envelope

    with pytest.raises(ValueError, match="does not match its expected contract"):
        validate_artifact(
            _PAYLOAD.replace(CONTRACT_ID.encode(), other_id.encode()),
            expected_contract_id=CONTRACT_ID,
            contracts=registry,
        )


def test_enforced_record_validation_closes_an_open_source_schema() -> None:
    registry = build_contract_registry((contract(**schema(additionalProperties=None)),))

    with pytest.raises(ValueError, match="does not satisfy contract"):
        validate_record(
            {"name": "accepted", "undeclared": True},
            contract_id=CONTRACT_ID,
            contracts=registry,
        )


def test_a_record_outside_its_contract_is_not_written() -> None:
    registry = build_contract_registry((contract(),))

    with pytest.raises(ValueError, match="does not satisfy contract"):
        serialize_artifact({"name": ""}, contract_id=CONTRACT_ID, contracts=registry)


@pytest.mark.parametrize(
    "nonportable_value",
    [float("nan"), 9_007_199_254_740_992, date(2026, 9, 15), ("tuple",)],
)
def test_artifact_serialization_rejects_nonportable_values(nonportable_value: object) -> None:
    any_value = schema(properties={"value": {}}, required=["value"])
    registry = build_contract_registry((contract(**any_value),))

    with pytest.raises(ValueError, match="non-portable YAML values"):
        serialize_artifact(
            {"value": nonportable_value},
            contract_id=CONTRACT_ID,
            contracts=registry,
        )
