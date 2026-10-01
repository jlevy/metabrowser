"""One synthetic artifact contract, shared by the tests of the contract layer.

The registry, the corpus evidence engine, and the architecture-table gate are tested
against a contract small enough that a refusal has a single cause: one required string,
one semantic rule, and a corpus of one valid case and two invalid ones on one base
record. ``contract(**fields)`` returns it with any field of the declaration replaced,
``schema(**changes)`` returns the three schema fields for the same schema with keywords
changed, and ``corpus(*cases)`` returns packaged evidence holding other cases.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any, cast

from metabrowser.plugin_loader.artifact_contracts import (
    ArtifactContractSpec,
    ConformanceCorpusSpec,
)

CONTRACT_ID = "example.test:Item/v1"
DRAFT = "https://json-schema.org/draft/2020-12/schema"
# The one name the semantic validator refuses; the schema alone admits it.
RESERVED_NAME = "reserved"


def item_schema(**changes: Any) -> dict[str, Any]:
    """A closed object with one required ``name``; a keyword set to ``None`` is dropped."""

    keywords: dict[str, Any] = {
        "$schema": DRAFT,
        "type": "object",
        "properties": {"name": {"type": "string", "minLength": 1}},
        "required": ["name"],
        "additionalProperties": False,
        "x-softschema": {"contract": CONTRACT_ID},
        **changes,
    }
    return {keyword: value for keyword, value in keywords.items() if value is not None}


def compact_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def compiled(document: dict[str, Any]) -> bytes:
    """Stamp the logical digest into the schema, as compiling it does, and encode it."""

    canonical = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    document["x-softschema"]["schema_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    return compact_json(document)


def declared(schema_bytes: bytes, *, schema_digest: str | None = None) -> dict[str, Any]:
    """The three fields a declaration carries for its schema, each consistent with it."""

    if schema_digest is None:
        schema_digest = json.loads(schema_bytes)["x-softschema"]["schema_sha256"]
    return {
        "schema_bytes": schema_bytes,
        "schema_bytes_sha256": hashlib.sha256(schema_bytes).hexdigest(),
        "schema_digest": schema_digest,
    }


def schema(**changes: Any) -> dict[str, Any]:
    return declared(compiled(item_schema(**changes)))


VALID_CASE: dict[str, Any] = {"name": "valid", "record": "item", "changes": [], "expect": "valid"}
EMPTY_NAME_CASE = VALID_CASE | {
    "name": "empty-name",
    "changes": [{"path": ["name"], "value": ""}],
    "expect": "invalid",
}
RESERVED_NAME_CASE = EMPTY_NAME_CASE | {
    "name": "reserved-name",
    "changes": [{"path": ["name"], "value": RESERVED_NAME}],
}


def corpus(*cases: dict[str, Any], **bases: Any) -> ConformanceCorpusSpec:
    """Packaged evidence: the three cases above on the base record ``item``, unless given."""

    document = {
        "cases": list(cases or (VALID_CASE, EMPTY_NAME_CASE, RESERVED_NAME_CASE)),
        **(bases or {"base_records": {"item": {"name": "accepted"}}}),
    }
    payload = compact_json(document)
    return ConformanceCorpusSpec(
        corpus_id="item-conformance",
        media_type="application/json",
        payload=payload,
        payload_sha256=hashlib.sha256(payload).hexdigest(),
    )


def _validate(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("name") == RESERVED_NAME:
        raise ValueError("reserved item name")
    return dict(value)


def _dump(value: object) -> dict[str, Any]:
    return dict(cast(dict[str, Any], value))


def contract(**fields: Any) -> ArtifactContractSpec:
    """The item contract, with any field of its declaration replaced."""

    base = ArtifactContractSpec(
        contract_id=CONTRACT_ID,
        artifact_profile="pure-yaml",
        envelope="item",
        **schema(),
        validate_record=_validate,
        dump_record=_dump,
        producer_ids=("example-provider",),
        consumer_ids=("example-browser", "example-store"),
        corpus=corpus(),
        corpus_record_selectors=("item",),
    )
    return replace(base, **fields)
