from __future__ import annotations

import copy
from typing import Any

import pytest
from hosted_review_cases import apply_case_changes, load_hosted_review_corpus

from metabrowser.builtin_plugins.hosted_review import models as hosted_review


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


def test_binding_identity_does_not_change_with_repository_coordinates() -> None:
    corpus = _corpus()["base_records"]
    binding = hosted_review.validate_provider_binding(corpus["provider_binding"])
    repository = hosted_review.validate_hosted_repository(corpus["hosted_repository"])

    assert binding.repository == hosted_review.hosted_repository_ref(repository)


def test_binding_provenance_resolves_a_successful_exact_binding_target() -> None:
    records = _corpus()["base_records"]
    binding = hosted_review.validate_provider_binding(records["provider_binding"])
    storage = load_hosted_review_corpus("provider-storage-conformance.json")["base_records"]
    retrieval_document = copy.deepcopy(storage["retrieval"])
    retrieval_document["target"] = {
        "kind": "provider_binding",
        "entry_id": binding.entry_id,
        "repository": binding.repository.model_dump(mode="json"),
    }
    retrieval = hosted_review.validate_retrieval(retrieval_document)
    assert binding.provenance is not None
    retrieval_snapshot_id = binding.provenance.retrieval_snapshot_id

    hosted_review.validate_provider_binding_provenance(
        binding,
        retrieval_snapshot_id,
        retrieval,
    )

    wrong_target_document = copy.deepcopy(retrieval_document)
    wrong_target_document["target"]["repository"]["opaque_id"] = "repo-other"
    wrong_target = hosted_review.validate_retrieval(wrong_target_document)
    with pytest.raises(ValueError):
        hosted_review.validate_provider_binding_provenance(
            binding,
            retrieval_snapshot_id,
            wrong_target,
        )

    failed_document = copy.deepcopy(retrieval_document)
    failed_document["outcome"] = {"kind": "failed", "reason": "provider_error"}
    failed = hosted_review.validate_retrieval(failed_document)
    with pytest.raises(ValueError):
        hosted_review.validate_provider_binding_provenance(
            binding,
            retrieval_snapshot_id,
            failed,
        )


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


def test_binding_successor_requires_an_explicit_rebind_for_another_repository() -> None:
    document = _corpus()["base_records"]["provider_binding"]
    rebound_document = copy.deepcopy(document)
    rebound_document["repository"]["opaque_id"] = "repo-other"
    previous = hosted_review.validate_provider_binding(document)
    rebound = hosted_review.validate_provider_binding(rebound_document)

    with pytest.raises(ValueError):
        hosted_review.validate_provider_binding_successor(previous, rebound)
