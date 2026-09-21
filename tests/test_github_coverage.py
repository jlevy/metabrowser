from __future__ import annotations

import json
import re
import tomllib
from enum import Enum
from pathlib import Path
from types import UnionType
from typing import Any, Literal, TypeAliasType, get_args, get_origin
from urllib.parse import urlsplit

from pydantic import BaseModel

from metabrowser.builtin_plugins.hosted_review import models as hosted_review

ROOT = Path(__file__).resolve().parents[1]
ORACLE = ROOT / "tests" / "fixtures" / "github" / "oracle"
DISPOSITIONS = {"observed", "derived", "metabrowser_owned", "optional_unavailable"}
ALLOWED_PUBLIC_HOSTS = {
    "api.github.com",
    "docs.github.com",
    "github.com",
    "results.pre-commit.ci",
}


def _load(name: str) -> dict[str, Any]:
    return json.loads((ORACLE / name).read_text(encoding="utf-8"))


def _resolve_pointer(document: Any, pointer: str) -> Any:
    value = document
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        raise ValueError("JSON Pointer must be empty or begin with '/'")
    for raw_token in pointer[1:].split("/"):
        if re.search(r"~(?:[^01]|$)", raw_token):
            raise ValueError(f"invalid JSON Pointer escape: {raw_token!r}")
        token = raw_token
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            if token == "-" or re.fullmatch(r"0|[1-9][0-9]*", token) is None:
                raise ValueError(f"invalid JSON Pointer array index: {token!r}")
            value = value[int(token)]
        elif isinstance(value, dict):
            value = value[token]
        else:
            raise TypeError(f"cannot traverse {type(value).__name__} at {token!r}")
    return value


def _assert_reduced_shape(value: Any, schema: Any, path: str = "") -> None:
    if schema == "type-ref":
        assert isinstance(value, dict), path
        assert set(value) == {"kind", "name", "ofType"}, path
        assert type(value["kind"]) is str, path
        assert value["name"] is None or type(value["name"]) is str, path
        if value["ofType"] is not None:
            _assert_reduced_shape(value["ofType"], "type-ref", f"{path}/ofType")
        return
    if isinstance(schema, tuple) and schema[0] == "nullable":
        if value is not None:
            _assert_reduced_shape(value, schema[1], path)
        return
    if isinstance(schema, tuple):
        assert type(value) in schema, path
        return
    if isinstance(schema, type):
        assert type(value) is schema, path
        return
    if schema is None:
        assert value is None, path
        return
    if isinstance(schema, list):
        assert isinstance(value, list), path
        if not schema:
            assert value == [], path
            return
        assert len(schema) == 1
        for index, item in enumerate(value):
            _assert_reduced_shape(item, schema[0], f"{path}/{index}")
        return
    assert isinstance(schema, dict), path
    assert isinstance(value, dict), path
    assert set(value) == set(schema), path
    for key, child_schema in schema.items():
        _assert_reduced_shape(value[key], child_schema, f"{path}/{key}")


ACTOR_REST_SCHEMA = {"id": int, "node_id": str, "login": str, "html_url": str}
REPOSITORY_ID_SCHEMA = {"id": int, "node_id": str, "full_name": str}
REVISION_SCHEMA = {"ref": str, "sha": str, "repo": REPOSITORY_ID_SCHEMA}
INDEX_REVISION_SCHEMA = {
    "label": str,
    "ref": str,
    "sha": str,
    "repo": REPOSITORY_ID_SCHEMA,
}
INDEX_ROW_SCHEMA = {
    "id": int,
    "node_id": str,
    "number": int,
    "html_url": str,
    "title": str,
    "state": str,
    "draft": bool,
    "created_at": str,
    "updated_at": str,
    "closed_at": str,
    "merged_at": str,
    "user": ACTOR_REST_SCHEMA,
    "base": INDEX_REVISION_SCHEMA,
    "head": INDEX_REVISION_SCHEMA,
}
REST_CORE_SCHEMA = {
    "recorded_from_public_api": bool,
    "responses": {
        "repository": {
            "id": int,
            "node_id": str,
            "name": str,
            "full_name": str,
            "private": bool,
            "visibility": str,
            "html_url": str,
            "clone_url": str,
            "default_branch": str,
            "created_at": str,
            "updated_at": str,
            "owner": ACTOR_REST_SCHEMA,
        },
        "pull_request_index_first_page": {
            "request_page": int,
            "items_per_page": int,
            "link_relations": {"next": int, "last": int},
            "items": [INDEX_ROW_SCHEMA],
        },
        "pull_request_index_terminal_page": {
            "request_page": int,
            "items_per_page": int,
            "link_relations": {"previous": int, "first": int},
            "items": [INDEX_ROW_SCHEMA],
        },
        "pull_request": {
            "id": int,
            "node_id": str,
            "number": int,
            "html_url": str,
            "title": str,
            "body": str,
            "state": str,
            "draft": bool,
            "locked": bool,
            "created_at": str,
            "updated_at": str,
            "closed_at": str,
            "merged_at": str,
            "merge_commit_sha": str,
            "commits": int,
            "comments": int,
            "review_comments": int,
            "base": REVISION_SCHEMA,
            "head": REVISION_SCHEMA,
            "user": ACTOR_REST_SCHEMA,
            "labels": [],
            "assignees": [ACTOR_REST_SCHEMA],
            "milestone": None,
            "requested_reviewers": [ACTOR_REST_SCHEMA],
            "requested_teams": [],
        },
        "check_suites": {
            "total_count": int,
            "check_suites": [
                {
                    "id": int,
                    "node_id": str,
                    "status": str,
                    "conclusion": str,
                    "created_at": str,
                    "updated_at": str,
                    "latest_check_runs_count": int,
                    "head_sha": str,
                    "url": str,
                    "app": {"id": int, "node_id": str, "slug": str, "html_url": str},
                }
            ],
        },
        "check_runs": {
            "total_count": int,
            "check_runs": [
                {
                    "id": int,
                    "node_id": str,
                    "name": str,
                    "status": str,
                    "conclusion": str,
                    "started_at": str,
                    "completed_at": str,
                    "html_url": str,
                    "details_url": str,
                    "head_sha": str,
                    "check_suite": {"id": int},
                }
            ],
        },
        "commit_status": {
            "state": str,
            "sha": str,
            "total_count": int,
            "statuses": [
                {
                    "id": int,
                    "node_id": str,
                    "state": str,
                    "description": str,
                    "target_url": str,
                    "context": str,
                    "created_at": str,
                    "updated_at": str,
                }
            ],
        },
    },
}

ACTOR_GRAPHQL_SCHEMA = {
    "__typename": str,
    "id": str,
    "login": str,
    "url": str,
}
REVIEW_SCHEMA = {
    "id": str,
    "fullDatabaseId": str,
    "url": str,
    "body": str,
    "createdAt": str,
    "state": str,
    "submittedAt": str,
    "updatedAt": str,
    "commit": {"oid": str},
    "author": ACTOR_GRAPHQL_SCHEMA,
}
REVIEW_COMMENT_SCHEMA = {
    "id": str,
    "fullDatabaseId": str,
    "subjectType": str,
    "url": str,
    "body": str,
    "createdAt": str,
    "updatedAt": str,
    "state": str,
    "isMinimized": bool,
    "minimizedReason": (str, type(None)),
    "path": str,
    "line": int,
    "originalLine": int,
    "startLine": int,
    "originalStartLine": int,
    "outdated": bool,
    "author": ACTOR_GRAPHQL_SCHEMA,
    "replyTo": ("nullable", {"id": str}),
    "commit": {"oid": str},
    "originalCommit": {"oid": str},
    "pullRequestReview": REVIEW_SCHEMA,
}
GRAPHQL_REVIEW_SCHEMA = {
    "recorded_from_public_api": bool,
    "data": {
        "repository": {
            "id": str,
            "pullRequest": {
                "id": str,
                "number": int,
                "baseRefName": str,
                "baseRefOid": str,
                "headRefName": str,
                "headRefOid": str,
                "reviewDecision": str,
                "reviews": {"totalCount": int},
                "reviewThreads": {
                    "totalCount": int,
                    "nodes": [
                        {
                            "id": str,
                            "subjectType": str,
                            "isResolved": bool,
                            "isOutdated": bool,
                            "path": str,
                            "line": int,
                            "originalLine": int,
                            "startLine": int,
                            "originalStartLine": int,
                            "diffSide": str,
                            "startDiffSide": str,
                            "resolvedBy": ("nullable", ACTOR_GRAPHQL_SCHEMA),
                            "comments": {
                                "totalCount": int,
                                "nodes": [REVIEW_COMMENT_SCHEMA],
                            },
                        }
                    ],
                },
            },
        },
        "commentEvidence": {
            "id": str,
            "pullRequest": {
                "comments": {
                    "totalCount": int,
                    "nodes": [
                        {
                            "id": str,
                            "fullDatabaseId": str,
                            "url": str,
                            "body": str,
                            "createdAt": str,
                            "updatedAt": str,
                            "isMinimized": bool,
                            "minimizedReason": (str, type(None)),
                            "author": ACTOR_GRAPHQL_SCHEMA,
                        }
                    ],
                },
            },
        },
    },
}


def _schema_capture_schema(*aliases: str) -> dict[str, Any]:
    return {
        "recorded_from_public_api": bool,
        "data": {
            alias: {
                "name": str,
                "fields": [{"name": str, "type": "type-ref"}],
            }
            for alias in aliases
        },
    }


SCHEMA_FIELD_NAMES = {
    "pullRequest": ["author", "headRefName", "headRefOid", "headRepository", "reviews"],
    "reviewComment": [
        "author",
        "commit",
        "originalCommit",
        "pullRequestReview",
        "subjectType",
    ],
    "checkSuite": [
        "app",
        "branch",
        "checkRuns",
        "commit",
        "conclusion",
        "createdAt",
        "creator",
        "databaseId",
        "id",
        "matchingPullRequests",
        "push",
        "repository",
        "resourcePath",
        "status",
        "updatedAt",
        "url",
        "workflowRun",
    ],
    "issueComment": [
        "author",
        "body",
        "createdAt",
        "isMinimized",
        "minimizedReason",
        "updatedAt",
        "url",
    ],
}


def _model_closure(root_names: list[str]) -> tuple[set[type[BaseModel]], set[type[Enum]]]:
    seen: set[int] = set()
    model_types: set[type[BaseModel]] = set()
    enum_types: set[type[Enum]] = set()

    def visit(annotation: Any) -> None:
        if id(annotation) in seen:
            return
        seen.add(id(annotation))
        if isinstance(annotation, TypeAliasType):
            visit(annotation.__value__)
            return
        if isinstance(annotation, type) and issubclass(annotation, Enum):
            enum_types.add(annotation)
            return
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            if (
                annotation.__module__ == hosted_review.__name__
                and not annotation.__name__.startswith("_")
            ):
                model_types.add(annotation)
            for field in annotation.model_fields.values():
                visit(field.annotation)
            return
        if isinstance(annotation, UnionType) or get_args(annotation):
            for argument in get_args(annotation):
                visit(argument)

    for root_name in root_names:
        visit(getattr(hosted_review, root_name))
    return model_types, enum_types


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _walk_strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _walk_strings(item)]
    return []


def _walk_items(value: Any) -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        return list(value.items()) + [
            nested for item in value.values() for nested in _walk_items(item)
        ]
    if isinstance(value, list):
        return [nested for item in value for nested in _walk_items(item)]
    return []


def _root_selection_names(document: str) -> set[str]:
    names: set[str] = set()
    for match in re.finditer(
        r"^  (?:(?P<alias>[A-Za-z_]\w*)\s*:\s*)?(?P<field>[A-Za-z_]\w*)\s*\(",
        document,
        re.MULTILINE,
    ):
        names.add(match.group("alias") or match.group("field"))
    return names


def _resolve_evidence_reference(
    reference: str,
    *,
    captures: dict[str, dict[str, Any]],
    external_inputs: set[str],
    constants: dict[str, Any],
) -> Any:
    if reference.startswith("model:"):
        model_name, field_name = reference.removeprefix("model:").split(".", 1)
        assert field_name in getattr(hosted_review, model_name).model_fields
        return reference
    if reference.startswith("external:"):
        assert reference.removeprefix("external:") in external_inputs
        return reference
    if reference.startswith("constant:"):
        return constants[reference.removeprefix("constant:")]
    source, pointer = reference.split("#", 1)
    request_evidence = source.endswith("@request")
    source = source.removesuffix("@request")
    capture = captures[source]
    evidence_document = (
        capture["request"]
        if request_evidence
        else _resolve_pointer(_load(capture["file"]), capture["json_pointer"])
    )
    return _resolve_pointer(evidence_document, pointer)


def test_oracle_manifest_resolves_every_bounded_public_capture() -> None:
    manifest = _load("manifest.json")
    capture_ids: set[str] = set()

    assert set(manifest) == {
        "oracle_version",
        "captured_on",
        "purpose",
        "authority",
        "recorded_files",
        "synthetic_files",
        "global_scrubbing",
        "captures",
    }

    assert {path.name for path in ORACLE.iterdir()} == {
        "README.md",
        "field-inventory.json",
        "graphql-review-thread.json",
        "hostile-synthetic.json",
        "manifest.json",
        "rest-core.json",
        "review-threads.graphql",
        "schema-nullability-a.graphql",
        "schema-nullability-a.json",
        "schema-nullability-b.graphql",
        "schema-nullability-b.json",
    }
    assert manifest["authority"] == "test_evidence_only"
    assert set(manifest["recorded_files"]) == {
        "rest-core.json",
        "graphql-review-thread.json",
        "schema-nullability-a.json",
        "schema-nullability-b.json",
    }
    assert manifest["synthetic_files"] == ["hostile-synthetic.json"]
    for capture in manifest["captures"]:
        expected_capture_keys = {
            "id",
            "file",
            "json_pointer",
            "public_resource",
            "request",
            "selection",
        }
        if "scrubbed_fields" in capture:
            expected_capture_keys.add("scrubbed_fields")
        assert set(capture) == expected_capture_keys
        assert capture["id"] not in capture_ids
        capture_ids.add(capture["id"])
        assert capture["file"] in manifest["recorded_files"]
        assert _resolve_pointer(_load(capture["file"]), capture["json_pointer"]) is not None
        request = capture["request"]
        expected_request_keys = {"transport", "method", "host", "path"}
        if request["transport"] == "github_rest":
            expected_request_keys |= {"accept", "api_version"}
        else:
            expected_request_keys |= {"document", "variables"}
        assert set(request) == expected_request_keys
        assert request["method"] in {"GET", "POST"}
        assert request["host"] == "api.github.com"
        assert request["path"].startswith("/")
        public_resource = urlsplit(capture["public_resource"])
        assert public_resource.hostname in {"docs.github.com", "github.com"}
        for name, value in request.get("variables", {}).items():
            if name.casefold().endswith("limit"):
                assert isinstance(value, int) and 0 < value <= 5
        if match := re.search(r"(?:\?|&)per_page=(\d+)", request["path"]):
            assert 0 < int(match.group(1)) <= 5
        if document_name := request.get("document"):
            document = (ORACLE / document_name).read_text(encoding="utf-8")
            declared_variables = set(re.findall(r"\$(\w+)\s*:", document))
            assert declared_variables == set(request["variables"])
            assert 'repository(owner: "' not in document

    assert capture_ids == {capture["id"] for capture in manifest["captures"]}


def test_recorded_responses_match_exact_reduced_schemas_and_query_roots() -> None:
    _assert_reduced_shape(_load("rest-core.json"), REST_CORE_SCHEMA)
    _assert_reduced_shape(_load("graphql-review-thread.json"), GRAPHQL_REVIEW_SCHEMA)
    _assert_reduced_shape(
        _load("schema-nullability-a.json"),
        _schema_capture_schema("pullRequest", "reviewComment"),
    )
    _assert_reduced_shape(
        _load("schema-nullability-b.json"),
        _schema_capture_schema("checkSuite", "issueComment"),
    )
    schema_data = {
        **_load("schema-nullability-a.json")["data"],
        **_load("schema-nullability-b.json")["data"],
    }
    assert {
        alias: [field["name"] for field in schema_data[alias]["fields"]]
        for alias in SCHEMA_FIELD_NAMES
    } == SCHEMA_FIELD_NAMES

    manifest = _load("manifest.json")
    documents: dict[str, tuple[str, str]] = {}
    for capture in manifest["captures"]:
        if document_name := capture["request"].get("document"):
            current = (capture["file"], capture["json_pointer"].split("/data", 1)[0] + "/data")
            assert documents.setdefault(document_name, current) == current
    for document_name, (response_name, data_pointer) in documents.items():
        document = (ORACLE / document_name).read_text(encoding="utf-8")
        response_roots = set(_resolve_pointer(_load(response_name), data_pointer))
        assert _root_selection_names(document) == response_roots


def test_json_pointer_resolution_is_strict_rfc_6901() -> None:
    document = {"a/b": {"m~n": ["zero", "one"]}}
    assert _resolve_pointer(document, "/a~1b/m~0n/1") == "one"
    for invalid in ("relative", "/a~2b", "/a~", "/a~1b/m~0n/01", "/a~1b/m~0n/-"):
        try:
            _resolve_pointer(document, invalid)
        except (KeyError, TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"accepted invalid JSON Pointer: {invalid!r}")


def test_field_inventory_is_the_exact_transitive_model_and_state_closure() -> None:
    inventory = _load("field-inventory.json")
    assert set(inventory) == {
        "inventory_version",
        "model_module",
        "model_roots",
        "closed_over_models",
        "constants",
        "consumer_classification",
        "derivation_recipes",
        "field_derivations",
        "positional_schema_evidence",
        "models",
        "value_states",
        "literal_states",
        "value_metadata",
        "external_inputs",
        "field_evidence",
        "artifact_bodies",
    }
    model_types, enum_types = _model_closure(inventory["model_roots"])
    expected_models = {model.__name__ for model in model_types}

    assert set(inventory["closed_over_models"]) == expected_models
    assert {entry["name"] for entry in inventory["models"]} == expected_models
    for entry in inventory["models"]:
        assert entry["consumers"]
        model = getattr(hosted_review, entry["name"])
        inventoried_fields = [field for group in entry["field_groups"] for field in group["fields"]]
        assert len(inventoried_fields) == len(set(inventoried_fields))
        assert set(inventoried_fields) == set(model.model_fields)
        for group in entry["field_groups"]:
            disposition = group["disposition"]
            assert disposition in DISPOSITIONS
            if disposition == "observed":
                assert group["sources"]
            elif disposition == "derived":
                assert group["derivation"]
            elif disposition == "metabrowser_owned":
                assert group["owner_reason"]
            else:
                assert group["sources"] and group["unavailable_when"]

    classification = inventory["consumer_classification"]
    current_prefixes = tuple(classification["current_validated_prefixes"])
    planned_prefixes = tuple(classification["planned_prefixes"])
    planned_labels = set(classification["planned_labels"])
    for consumer in {consumer for entry in inventory["models"] for consumer in entry["consumers"]}:
        statuses = {
            status
            for status, matches in (
                ("current", consumer.startswith(current_prefixes)),
                ("planned", consumer.startswith(planned_prefixes) or consumer in planned_labels),
            )
            if matches
        }
        assert len(statuses) == 1, consumer

    states = {entry["name"]: entry for entry in inventory["value_states"]}
    assert set(states) == {enum.__name__ for enum in enum_types}
    for enum in enum_types:
        assert set(states[enum.__name__]["values"]) == {member.value for member in enum}
    for entry in states.values():
        assert set(entry["values"].values()) <= DISPOSITIONS

    literal_states = {entry["field"]: entry for entry in inventory["literal_states"]}
    expected_literals = {
        f"{model.__name__}.{field_name}": set(get_args(field.annotation))
        for model in model_types
        for field_name, field in model.model_fields.items()
        if get_origin(field.annotation) is Literal
    }
    assert set(literal_states) == set(expected_literals)
    for field_name, values in expected_literals.items():
        assert set(literal_states[field_name]["values"]) == values
        assert set(literal_states[field_name]["values"].values()) <= DISPOSITIONS

    expected_metadata = {
        f"{entry['name']}.{value}": disposition
        for entry in inventory["value_states"]
        for value, disposition in entry["values"].items()
    } | {
        f"{entry['field']}={value}": disposition
        for entry in inventory["literal_states"]
        for value, disposition in entry["values"].items()
    }
    actual_metadata: dict[str, str] = {}
    for entry in inventory["value_metadata"]:
        assert entry["disposition"] in DISPOSITIONS
        for target in entry["targets"]:
            assert target not in actual_metadata
            actual_metadata[target] = entry["disposition"]
        if entry["disposition"] == "observed":
            assert entry["evidence"]
        elif entry["disposition"] == "derived":
            assert entry["recipe"] and entry["inputs"]
        elif entry["disposition"] == "metabrowser_owned":
            assert entry["owner_reason"]
        else:
            assert entry["condition"] and entry["rationale"]
    assert actual_metadata == expected_metadata


def test_inventory_sources_are_declared_captures_and_bodies_are_explicit() -> None:
    manifest = _load("manifest.json")
    inventory = _load("field-inventory.json")
    captures = {capture["id"]: capture for capture in manifest["captures"]}
    capture_ids = set(captures)

    for entry in inventory["models"]:
        for group in entry["field_groups"]:
            assert set(group.get("sources", ())) <= capture_ids
    for entry in inventory["value_states"]:
        assert set(entry.get("sources", ())) <= capture_ids

    dispositions = {
        (entry["name"], field): group["disposition"]
        for entry in inventory["models"]
        for group in entry["field_groups"]
        for field in group["fields"]
    }
    expected_evidence_fields = {
        key for key, disposition in dispositions.items() if disposition != "metabrowser_owned"
    }
    evidence_fields = {
        (entry["model"], field)
        for entry in inventory["field_evidence"]
        for field in entry["fields"]
    }
    assert len({entry["model"] for entry in inventory["field_evidence"]}) == len(
        inventory["field_evidence"]
    )
    assert evidence_fields == expected_evidence_fields

    external_inputs = {
        f"{entry['id']}.{field}"
        for entry in inventory["external_inputs"]
        for field in entry["fields"]
    }
    assert all(entry["producer"] for entry in inventory["external_inputs"])
    constants = inventory["constants"]
    for entry in inventory["field_evidence"]:
        model = getattr(hosted_review, entry["model"])
        assert set(entry["fields"]) <= set(model.model_fields)
        for references in entry["fields"].values():
            assert references
            for reference in references:
                _resolve_evidence_reference(
                    reference,
                    captures=captures,
                    external_inputs=external_inputs,
                    constants=constants,
                )

    recipes = {entry["id"]: entry for entry in inventory["derivation_recipes"]}
    assert {entry["id"] for entry in inventory["derivation_recipes"]} == {
        "provider_object_ref",
        "repository_ref",
        "canonical_change_request_id",
        "provider_entity_id",
        "check_parent_normalized_id",
        "reuse_normalized_identity",
        "activity_item_id",
    }
    expected_recipe_inputs = {
        "provider_object_ref": {"provider", "instance", "object_kind", "provider_opaque_id"},
        "repository_ref": {"provider", "instance", "repository_opaque_id"},
        "canonical_change_request_id": {
            "provider",
            "instance",
            "repository_opaque_id",
            "id_kind",
            "number",
        },
        "provider_entity_id": {"provider_opaque_id"},
        "check_parent_normalized_id": {
            "run_parent_suite_database_id",
            "suite_database_id",
            "suite_provider_opaque_id",
        },
        "reuse_normalized_identity": {"normalized_identity"},
        "activity_item_id": {"id_kind", "number"},
    }
    assert {
        recipe_id: set(recipe["inputs"]) for recipe_id, recipe in recipes.items()
    } == expected_recipe_inputs
    for recipe in recipes.values():
        operation = recipe["operation"]
        assert operation["kind"] in {"record", "format", "identity", "unique_lookup"}
        if operation["kind"] == "record":
            assert set(operation["fields"].values()) == set(recipe["inputs"])
        elif operation["kind"] == "format":
            assert set(re.findall(r"\{([^{}]+)\}", operation["template"])) == set(recipe["inputs"])
        elif operation["kind"] == "identity":
            assert operation["result_input"] in recipe["inputs"]
        else:
            assert {
                operation["match_left"],
                operation["match_right"],
                operation["result_input"],
            } == set(recipe["inputs"])
    derivation_keys: set[tuple[str, str]] = set()
    for entry in inventory["field_derivations"]:
        model_name, field_name = entry["field"].split(".", 1)
        assert field_name in getattr(hosted_review, model_name).model_fields
        key = (entry["field"], entry.get("variant", ""))
        assert key not in derivation_keys
        derivation_keys.add(key)
        recipe = recipes[entry["recipe"]]
        assert set(entry["inputs"]) == set(recipe["inputs"])
        for reference in entry["inputs"].values():
            _resolve_evidence_reference(
                reference,
                captures=captures,
                external_inputs=external_inputs,
                constants=constants,
            )

    assert derivation_keys == {
        ("HostedRepository.provider_ref", ""),
        ("ChangeRequest.id", ""),
        ("ChangeRequest.provider_ref", ""),
        ("ChangeRequest.repository", ""),
        ("ChangeRequestIndexRow.provider_ref", ""),
        ("ChangeRequestIndexRow.repository", ""),
        ("ChangeRequestComment.id", ""),
        ("ChangeRequestComment.provider_ref", ""),
        ("ChangeRequestComment.repository", ""),
        ("ChangeRequestComment.change_request_id", ""),
        ("Review.id", ""),
        ("Review.provider_ref", ""),
        ("Review.repository", ""),
        ("Review.change_request_id", ""),
        ("ReviewThread.id", ""),
        ("ReviewThread.provider_ref", ""),
        ("ReviewThread.repository", ""),
        ("ReviewThread.change_request_id", ""),
        ("ReviewComment.id", ""),
        ("ReviewComment.provider_ref", ""),
        ("ReviewComment.repository", ""),
        ("ReviewComment.change_request_id", ""),
        ("ReviewComment.thread_id", ""),
        ("ReviewComment.review_id", ""),
        ("ReviewComment.in_reply_to_id", ""),
        ("Check.provider_ref", "suite"),
        ("Check.provider_ref", "run"),
        ("Check.repository", ""),
        ("Check.parent_check_id", ""),
        ("CommitStatus.provider_ref", ""),
        ("CommitStatus.repository", ""),
        ("ChangeRequestActivityDetail.change_request_id", ""),
        ("ChangeRequestActivityDetail.provider_ref", ""),
        ("ChangeRequestActivityDetail.repository", ""),
        ("ActivityItem.id", ""),
    }

    required_relationships = {
        f"{model}.{field}"
        for model in ("ChangeRequestComment", "Review", "ReviewThread", "ReviewComment")
        for field in ("provider_ref", "repository", "change_request_id")
    }
    derived_fields = {entry["field"] for entry in inventory["field_derivations"]}
    assert required_relationships <= derived_fields

    for entry in inventory["value_metadata"]:
        references = entry.get("evidence", ()) or entry.get("inputs", ())
        for reference in references:
            _resolve_evidence_reference(
                reference,
                captures=captures,
                external_inputs=external_inputs,
                constants=constants,
            )
        if entry["disposition"] == "observed":
            resolved_values = [
                _resolve_evidence_reference(
                    reference,
                    captures=captures,
                    external_inputs=external_inputs,
                    constants=constants,
                )
                for reference in entry["evidence"]
            ]
            for target in entry["targets"]:
                expected_value = target.rsplit(".", 1)[1]
                assert expected_value in resolved_values

    positional_references = {
        reference
        for entry in inventory["field_evidence"]
        for references in entry["fields"].values()
        for reference in references
        if re.search(r"/fields/\d+$", reference)
    }
    assert positional_references == set(inventory["positional_schema_evidence"])
    for reference, expected_name in inventory["positional_schema_evidence"].items():
        value = _resolve_evidence_reference(
            reference,
            captures=captures,
            external_inputs=external_inputs,
            constants=constants,
        )
        assert value["name"] == expected_name

    assert {entry["contract"] for entry in inventory["artifact_bodies"]} == {
        "ChangeRequest/v1",
        "ChangeRequestComment/v1",
        "Review/v1",
        "ReviewComment/v1",
    }
    assert {entry["source"] for entry in inventory["artifact_bodies"]} <= capture_ids


def test_check_parent_numeric_join_resolves_to_the_normalized_suite_id() -> None:
    responses = _load("rest-core.json")["responses"]
    suites = responses["check_suites"]["check_suites"]
    parent_database_id = responses["check_runs"]["check_runs"][0]["check_suite"]["id"]
    matches = [suite for suite in suites if suite["id"] == parent_database_id]
    assert len(matches) == 1
    normalized_suite_checks = {suite["id"]: suite["node_id"] for suite in suites}
    assert len(normalized_suite_checks) == len(suites)
    normalized_suite_id = matches[0]["node_id"]
    assert matches[0]["head_sha"] == responses["check_runs"]["check_runs"][0]["head_sha"]
    recipe = next(
        entry
        for entry in _load("field-inventory.json")["derivation_recipes"]
        if entry["id"] == "check_parent_normalized_id"
    )
    operation = recipe["operation"]
    assert operation == {
        "kind": "unique_lookup",
        "match_left": "run_parent_suite_database_id",
        "match_right": "suite_database_id",
        "result_input": "suite_provider_opaque_id",
    }
    normalized_run_parent_id = normalized_suite_checks[parent_database_id]
    assert normalized_run_parent_id == normalized_suite_id


def test_canonical_change_request_id_recipe_is_executable_and_complete() -> None:
    inventory = _load("field-inventory.json")
    manifest = _load("manifest.json")
    captures = {capture["id"]: capture for capture in manifest["captures"]}
    external_inputs = {
        f"{entry['id']}.{field}"
        for entry in inventory["external_inputs"]
        for field in entry["fields"]
    }
    derivation = next(
        entry for entry in inventory["field_derivations"] if entry["field"] == "ChangeRequest.id"
    )
    recipe = next(
        entry for entry in inventory["derivation_recipes"] if entry["id"] == derivation["recipe"]
    )
    assert recipe["operation"]["kind"] == "format"
    values = {
        name: _resolve_evidence_reference(
            reference,
            captures=captures,
            external_inputs=external_inputs,
            constants=inventory["constants"],
        )
        for name, reference in derivation["inputs"].items()
    }
    normalized_id = recipe["operation"]["template"].format(**values)
    assert normalized_id == "github:github.com:MDEwOlJlcG9zaXRvcnkyMTI2MTMwNDk=:pull:14430"
    assert inventory["constants"]["change_request_id_kind"] == "pull"
    assert (
        inventory["constants"]["change_request_id_kind"]
        != inventory["constants"]["pull_request_kind"]
    )


def test_activity_item_id_recipe_matches_the_portable_repository_activity_corpus() -> None:
    inventory = _load("field-inventory.json")
    recipe = next(
        entry for entry in inventory["derivation_recipes"] if entry["id"] == "activity_item_id"
    )
    corpus_path = (
        ROOT
        / "src"
        / "metabrowser"
        / "data"
        / "hosted-review-format"
        / "repository-activity-conformance.json"
    )
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))["base_document"]
    item = next(entry for entry in corpus["items"] if entry["kind"] == "change_request")
    normalized_id = recipe["operation"]["template"].format(
        id_kind=inventory["constants"]["activity_change_request_id_kind"],
        number=item["detail"]["number"],
    )
    assert normalized_id == item["id"] == "change-request:17"


def test_recorded_evidence_is_scrubbed_public_and_synthetic_inputs_stay_separate() -> None:
    manifest = _load("manifest.json")
    public_url_prefixes = (
        "https://api.github.com/repos/cli/cli/",
        "https://docs.github.com/graphql",
        "https://github.com/apps/",
        "https://github.com/cli",
        "https://github.com/jlevy",
        "https://github.com/niik",
        "https://github.com/pypa/pip",
        "https://github.com/vilmibm",
        "https://github.com/williammartin",
        "https://results.pre-commit.ci/run/github/",
    )
    private_value_patterns = (
        re.compile(r"gh[pousr]_[A-Za-z0-9_]{12,}"),
        re.compile(r"github_pat_[A-Za-z0-9_]{12,}"),
        re.compile(r"\bBearer\s+[A-Za-z0-9._~-]+", re.IGNORECASE),
        re.compile(r"/(?:Users|home)/[^/\s]+/"),
        re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    )
    forbidden_raw_key_parts = {
        "authorization",
        "cookie",
        "oauth",
        "password",
        "permission",
        "rate_limit",
        "ratelimit",
        "request-id",
        "request_id",
        "requestid",
        "scope",
        "secret",
        "trace-id",
        "trace_id",
        "traceid",
        "traceparent",
    }
    forbidden_raw_keys = {"documentation_url", "error", "errors", "message"}
    url_key_pattern = re.compile(r"(?:^|_)(?:url|uri)$|url$|^public_resource$", re.IGNORECASE)
    non_synthetic_files = {
        path for path in ORACLE.iterdir() if path.name not in set(manifest["synthetic_files"])
    }
    assert non_synthetic_files
    for path in non_synthetic_files:
        text = path.read_text(encoding="utf-8")
        assert all(pattern.search(text) is None for pattern in private_value_patterns), path.name
        for url in re.findall(r"\b[A-Za-z][A-Za-z0-9+.-]*://[^\s)\]`\"']+", text):
            parsed = urlsplit(url.rstrip(".,;"))
            assert parsed.scheme == "https" and parsed.hostname in ALLOWED_PUBLIC_HOSTS
            assert parsed.username is None and parsed.password is None
            assert url.startswith(public_url_prefixes), (path.name, url)
        if path.suffix == ".json":
            document = _load(path.name)
            for key, value in _walk_items(document):
                normalized_key = key.casefold()
                if path.name in {*manifest["recorded_files"], "manifest.json"}:
                    assert normalized_key not in forbidden_raw_keys, (path.name, key)
                    assert not any(part in normalized_key for part in forbidden_raw_key_parts), (
                        path.name,
                        key,
                    )
                if url_key_pattern.search(key) and isinstance(value, str):
                    parsed = urlsplit(value)
                    assert parsed.scheme == "https"
                    assert parsed.hostname in ALLOWED_PUBLIC_HOSTS
                    assert parsed.username is None and parsed.password is None
                    assert value.startswith(public_url_prefixes), (path.name, key, value)

    for file_name in manifest["recorded_files"]:
        document = _load(file_name)
        assert document["recorded_from_public_api"] is True
        for key, value in _walk_items(document):
            if key == "body":
                assert value in {"", "[scrubbed public body]"}

    synthetic = _load("hostile-synthetic.json")
    assert synthetic["recorded_from_public_api"] is False
    assert synthetic["origin"] == "synthetic"
    assert synthetic["values"]["unsafe_url"].startswith("javascript:")
    assert "\u202e" in synthetic["values"]["bidi_actor"]
    assert "\u0007" in synthetic["values"]["control_text"]
    assert "<script>" in synthetic["values"]["hostile_markdown"]
    assert len(synthetic["values"]["oversized_token"]) > 100
    assert all(name not in manifest["recorded_files"] for name in manifest["synthetic_files"])


def test_oracle_proves_nullable_boundaries_without_claiming_unseen_variants() -> None:
    core_schema = _load("schema-nullability-a.json")["data"]
    supplementary_schema = _load("schema-nullability-b.json")["data"]
    pull_request_fields = {
        field["name"]: field["type"] for field in core_schema["pullRequest"]["fields"]
    }
    review_comment_fields = {
        field["name"]: field["type"] for field in core_schema["reviewComment"]["fields"]
    }
    check_suite_fields = {field["name"] for field in supplementary_schema["checkSuite"]["fields"]}

    assert pull_request_fields["author"]["kind"] == "INTERFACE"
    assert pull_request_fields["headRepository"]["kind"] == "OBJECT"
    assert pull_request_fields["headRefName"]["kind"] == "NON_NULL"
    assert pull_request_fields["headRefOid"]["kind"] == "NON_NULL"
    assert review_comment_fields["originalCommit"]["kind"] == "OBJECT"
    assert review_comment_fields["pullRequestReview"]["kind"] == "OBJECT"
    assert not {"name", "startedAt", "completedAt"} & check_suite_fields

    graphql = _load("graphql-review-thread.json")["data"]
    pull_request = graphql["repository"]["pullRequest"]
    thread = pull_request["reviewThreads"]["nodes"][0]
    first_comment = thread["comments"]["nodes"][0]
    review = first_comment["pullRequestReview"]
    issue_comment = graphql["commentEvidence"]["pullRequest"]["comments"]["nodes"][0]
    assert pull_request["reviews"]["totalCount"] == 8
    assert thread["subjectType"] == first_comment["subjectType"] == "LINE"
    assert (thread["startLine"], thread["line"]) == (74, 78)
    assert thread["isResolved"] is thread["isOutdated"] is False
    assert {"url", "body", "createdAt", "updatedAt"} <= review.keys()
    assert issue_comment["isMinimized"] is False and issue_comment["minimizedReason"] is None


def test_rest_evidence_covers_visibility_continuation_and_exhaustion() -> None:
    responses = _load("rest-core.json")["responses"]
    assert responses["repository"]["visibility"] == "public"
    assert responses["repository"]["private"] is False

    first_page = responses["pull_request_index_first_page"]
    terminal_page = responses["pull_request_index_terminal_page"]
    assert first_page["request_page"] == 1
    assert first_page["link_relations"]["next"] == 2
    assert first_page["link_relations"]["last"] == terminal_page["request_page"]
    assert "next" not in terminal_page["link_relations"]
    assert terminal_page["link_relations"]["previous"] == terminal_page["request_page"] - 1
    assert len(first_page["items"]) == first_page["items_per_page"]
    assert 0 < len(terminal_page["items"]) < terminal_page["items_per_page"]


def test_oracle_is_not_a_runtime_input_or_wheel_package() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    wheel_packages = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    assert wheel_packages == ["src/metabrowser"]
    assert not ORACLE.is_relative_to(ROOT / "src" / "metabrowser")

    forbidden_references = {
        "fixtures/github/oracle",
        "field-inventory.json",
        "graphql-review-thread.json",
        "rest-core.json",
        "schema-nullability-a.json",
        "schema-nullability-b.json",
    }
    runtime_files = [
        path
        for path in (ROOT / "src").rglob("*")
        if path.is_file() and path.suffix in {".py", ".js", ".json", ".toml"}
    ]
    for path in runtime_files:
        text = path.read_text(encoding="utf-8")
        assert all(reference not in text for reference in forbidden_references)

    other_tests = [
        path for path in (ROOT / "tests").rglob("*.py") if path.name != "test_github_coverage.py"
    ]
    for path in other_tests:
        text = path.read_text(encoding="utf-8")
        assert all(reference not in text for reference in forbidden_references)
