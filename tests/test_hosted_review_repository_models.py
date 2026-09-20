from __future__ import annotations

import copy
from typing import Any

import pytest
from hosted_review_cases import apply_case_changes, load_hosted_review_corpus

from metabrowser.builtin_plugins.hosted_review import models as hosted_review

_OTHER_SOURCE_ID = "sha256:2222222222222222222222222222222222222222222222222222222222222222"


def _corpus() -> dict[str, Any]:
    return load_hosted_review_corpus("hosted-repository-conformance.json")


def _repository_api(record_name: str) -> tuple[Any, Any]:
    names = {
        "provider_binding": ("validate_provider_binding", "dump_provider_binding"),
        "hosted_repository": (
            "validate_hosted_repository",
            "dump_hosted_repository",
        ),
    }
    validator_name, dumper_name = names[record_name]
    return getattr(hosted_review, validator_name), getattr(hosted_review, dumper_name)


def _materialize(references: dict[str, Any]) -> dict[str, Any]:
    """Resolve base-record names in a relationship fixture into concrete documents."""
    records = _corpus()["base_records"]

    def resolve(value: Any) -> Any:
        if isinstance(value, str) and value in records:
            return copy.deepcopy(records[value])
        if isinstance(value, list):
            return [resolve(item) for item in value]
        return copy.deepcopy(value)

    return {name: resolve(value) for name, value in references.items()}


def _validate_binding_set(document: dict[str, Any]) -> None:
    hosted_review.validate_provider_bindings(
        tuple(
            hosted_review.validate_provider_binding(value)
            for value in document["provider_bindings"]
        )
    )


def _validate_binding_successor(document: dict[str, Any]) -> None:
    hosted_review.validate_provider_binding_successor(
        hosted_review.validate_provider_binding(document["previous"]),
        hosted_review.validate_provider_binding(document["successor"]),
    )


def _validate_binding_provenance(document: dict[str, Any]) -> None:
    hosted_review.validate_provider_binding_provenance(
        hosted_review.validate_provider_binding(document["provider_binding"]),
        document["retrieval_snapshot_id"],
        hosted_review.validate_retrieval(document["retrieval"]),
    )


def test_repository_models_agree_with_the_portable_corpus() -> None:
    corpus = _corpus()

    for case in corpus["cases"]:
        document = apply_case_changes(corpus["base_records"][case["record"]], case["changes"])
        validator, dumper = _repository_api(case["record"])
        if case["expect"] == "valid":
            assert dumper(validator(document)) == document
        else:
            with pytest.raises(ValueError):
                validator(document)


@pytest.mark.parametrize(
    ("fixture", "cases", "validate"),
    [
        ("binding_set", "binding_set_cases", _validate_binding_set),
        ("binding_successor", "binding_successor_cases", _validate_binding_successor),
        ("binding_provenance", "binding_provenance_cases", _validate_binding_provenance),
    ],
)
def test_binding_relationships_agree_with_the_portable_corpus(
    fixture: str, cases: str, validate: Any
) -> None:
    corpus = _corpus()
    assert corpus[cases]
    assert {case["expect"] for case in corpus[cases]} == {"valid", "invalid"}

    for case in corpus[cases]:
        document = apply_case_changes(_materialize(corpus[fixture]), case["changes"])
        if case["expect"] == "valid":
            validate(document)
        else:
            with pytest.raises(ValueError):
                validate(document)


def test_binding_records_a_conservative_source_rather_than_a_cache_entry() -> None:
    document = _corpus()["base_records"]["provider_binding"]
    binding = hosted_review.validate_provider_binding(document)

    assert set(hosted_review.ProviderBinding.model_fields) == {
        "source_id",
        "repository",
        "provenance",
    }
    assert binding.source_id == document["source_id"]

    superseded = copy.deepcopy(document)
    superseded["entry_id"] = superseded.pop("source_id")
    with pytest.raises(ValueError, match="source_id"):
        hosted_review.validate_provider_binding(superseded)


def test_binding_retrieval_target_names_the_bound_source() -> None:
    records = _corpus()["base_records"]
    binding = hosted_review.validate_provider_binding(records["provider_binding"])
    storage = load_hosted_review_corpus("provider-storage-conformance.json")["base_records"]
    retrieval_document = copy.deepcopy(storage["retrieval"])
    retrieval_document["target"] = {
        "kind": "provider_binding",
        "source_id": binding.source_id,
        "repository": binding.repository.model_dump(mode="json"),
    }

    retrieval = hosted_review.validate_retrieval(retrieval_document)

    assert isinstance(retrieval.target, hosted_review.ProviderBindingRetrievalTarget)
    assert set(hosted_review.ProviderBindingRetrievalTarget.model_fields) == {
        "kind",
        "source_id",
        "repository",
    }
    superseded = copy.deepcopy(retrieval_document)
    superseded["target"]["entry_id"] = superseded["target"].pop("source_id")
    with pytest.raises(ValueError, match="source_id"):
        hosted_review.validate_retrieval(superseded)


def test_repository_rename_preserves_provider_identity() -> None:
    previous_document = _corpus()["base_records"]["hosted_repository"]
    renamed_document = copy.deepcopy(previous_document)
    renamed_document["owner"]["handle"] = "renamed-team"
    renamed_document["owner"]["url"] = "https://code.example/renamed-team"
    renamed_document["name"] = "renamed-project"
    renamed_document["url"] = "https://code.example/renamed-team/renamed-project"
    renamed_document["clone_url"] = "https://code.example/renamed-team/renamed-project.git"
    renamed_document["updated_at"] = "2026-09-15T12:30:00Z"

    previous = hosted_review.validate_hosted_repository(previous_document)
    renamed = hosted_review.validate_hosted_repository(renamed_document)

    hosted_review.validate_repository_successor(previous, renamed)


def test_repository_successor_rejects_silent_rebinding() -> None:
    previous_document = _corpus()["base_records"]["hosted_repository"]
    rebound_document = copy.deepcopy(previous_document)
    rebound_document["provider_ref"]["opaque_id"] = "repo-other"
    rebound_document["updated_at"] = "2026-09-15T12:30:00Z"

    previous = hosted_review.validate_hosted_repository(previous_document)
    rebound = hosted_review.validate_hosted_repository(rebound_document)

    with pytest.raises(ValueError):
        hosted_review.validate_repository_successor(previous, rebound)


def test_repository_successor_does_not_order_provider_update_times() -> None:
    previous_document = _corpus()["base_records"]["hosted_repository"]
    earlier_document = copy.deepcopy(previous_document)
    earlier_document["updated_at"] = previous_document["created_at"]

    previous = hosted_review.validate_hosted_repository(previous_document)
    earlier = hosted_review.validate_hosted_repository(earlier_document)

    assert hosted_review.validate_repository_successor(previous, earlier) == earlier


def test_binding_identity_does_not_change_with_repository_coordinates() -> None:
    corpus = _corpus()["base_records"]
    binding = hosted_review.validate_provider_binding(corpus["provider_binding"])
    repository = hosted_review.validate_hosted_repository(corpus["hosted_repository"])

    assert binding.repository == hosted_review.hosted_repository_ref(repository)


def test_binding_provenance_resolves_a_successful_exact_binding_target() -> None:
    document = _materialize(_corpus()["binding_provenance"])
    binding = hosted_review.validate_provider_binding(document["provider_binding"])
    retrieval = hosted_review.validate_retrieval(document["retrieval"])
    assert binding.provenance is not None
    retrieval_snapshot_id = binding.provenance.retrieval_snapshot_id

    assert (
        hosted_review.validate_provider_binding_provenance(
            binding, retrieval_snapshot_id, retrieval
        )
        is binding
    )

    wrong_source_document = copy.deepcopy(document["retrieval"])
    wrong_source_document["target"]["source_id"] = _OTHER_SOURCE_ID
    wrong_source = hosted_review.validate_retrieval(wrong_source_document)
    with pytest.raises(ValueError, match="another binding"):
        hosted_review.validate_provider_binding_provenance(
            binding, retrieval_snapshot_id, wrong_source
        )

    wrong_repository_document = copy.deepcopy(document["retrieval"])
    wrong_repository_document["target"]["repository"]["opaque_id"] = "repo-other"
    wrong_repository = hosted_review.validate_retrieval(wrong_repository_document)
    with pytest.raises(ValueError, match="another binding"):
        hosted_review.validate_provider_binding_provenance(
            binding, retrieval_snapshot_id, wrong_repository
        )

    failed_document = copy.deepcopy(document["retrieval"])
    failed_document["outcome"] = {"kind": "failed", "reason": "provider_error"}
    failed = hosted_review.validate_retrieval(failed_document)
    with pytest.raises(ValueError, match="successful retrieval"):
        hosted_review.validate_provider_binding_provenance(binding, retrieval_snapshot_id, failed)


def test_repository_resource_set_resolves_the_exact_snapshot() -> None:
    repository = hosted_review.validate_hosted_repository(
        _corpus()["base_records"]["hosted_repository"]
    )
    storage = load_hosted_review_corpus("provider-storage-conformance.json")["base_records"]
    resource_set = hosted_review.validate_resource_set(storage["resource_set"])
    snapshot_id = resource_set.collections[0].artifacts[0].snapshot_id

    hosted_review.validate_hosted_repository_resource_set(resource_set, repository, snapshot_id)

    with pytest.raises(ValueError):
        hosted_review.validate_hosted_repository_resource_set(
            resource_set,
            repository,
            "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider", "other-forge"),
        ("instance", "other.example"),
        ("opaque_id", "repo-other"),
    ],
)
def test_one_source_cannot_rebind_to_another_repository(field: str, value: str) -> None:
    document = _corpus()["base_records"]["provider_binding"]
    rebound_document = copy.deepcopy(document)
    rebound_document["repository"][field] = value
    previous = hosted_review.validate_provider_binding(document)
    rebound = hosted_review.validate_provider_binding(rebound_document)

    with pytest.raises(ValueError, match="rebind conflict"):
        hosted_review.validate_provider_binding_successor(previous, rebound)
    with pytest.raises(ValueError, match="rebind conflict"):
        hosted_review.validate_provider_bindings((previous, rebound))


def test_many_sources_may_bind_one_repository() -> None:
    document = _corpus()["base_records"]["provider_binding"]
    other_source_document = copy.deepcopy(document)
    other_source_document["source_id"] = _OTHER_SOURCE_ID
    other_source_document["provenance"] = None
    bindings = (
        hosted_review.validate_provider_binding(document),
        hosted_review.validate_provider_binding(other_source_document),
    )

    assert hosted_review.validate_provider_bindings(bindings) == bindings
    assert hosted_review.validate_provider_bindings(()) == ()


def test_binding_set_holds_one_record_per_source() -> None:
    document = _corpus()["base_records"]["provider_binding"]
    refreshed_document = copy.deepcopy(document)
    refreshed_document["provenance"] = None
    binding = hosted_review.validate_provider_binding(document)
    refreshed = hosted_review.validate_provider_binding(refreshed_document)

    with pytest.raises(ValueError, match="one binding per source ID"):
        hosted_review.validate_provider_bindings((binding, binding))
    with pytest.raises(ValueError, match="one binding per source ID"):
        hosted_review.validate_provider_bindings((binding, refreshed))


def test_binding_successor_keeps_identity_and_may_replace_provenance() -> None:
    document = _corpus()["base_records"]["provider_binding"]
    previous = hosted_review.validate_provider_binding(document)

    for provenance in (
        {"retrieval_snapshot_id": f"sha256:{'b' * 64}"},
        None,
    ):
        successor_document = copy.deepcopy(document)
        successor_document["provenance"] = provenance
        successor = hosted_review.validate_provider_binding(successor_document)
        assert hosted_review.validate_provider_binding_successor(previous, successor) is successor
    assert hosted_review.validate_provider_binding_successor(previous, previous) is previous

    other_source_document = copy.deepcopy(document)
    other_source_document["source_id"] = _OTHER_SOURCE_ID
    other_source = hosted_review.validate_provider_binding(other_source_document)
    with pytest.raises(ValueError, match="another source"):
        hosted_review.validate_provider_binding_successor(previous, other_source)
