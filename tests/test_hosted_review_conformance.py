from __future__ import annotations

import pytest
from hosted_review_cases import apply_case_changes, load_hosted_review_corpus
from pydantic import ValidationError

from metabrowser.builtin_plugins.hosted_review.models import validate_change_request


def test_python_change_request_model_agrees_with_the_portable_corpus() -> None:
    corpus = load_hosted_review_corpus("change-request-conformance.json")

    for case in corpus["cases"]:
        document = apply_case_changes(corpus["base_document"], case["changes"])
        if case["expect"] == "valid":
            validate_change_request(document)
        else:
            with pytest.raises(ValidationError):
                validate_change_request(document)
