from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

import pytest
from pydantic import ValidationError

from metabrowser.builtin_plugins.hosted_review.models import validate_change_request


def _corpus() -> dict[str, Any]:
    resource = files("metabrowser").joinpath(
        "data/hosted-review-format/change-request-conformance.json"
    )
    return json.loads(resource.read_text(encoding="utf-8"))


def _apply_changes(base_document: dict[str, Any], changes: list[dict[str, Any]]) -> dict[str, Any]:
    document = json.loads(json.dumps(base_document))
    for change in changes:
        target = document
        for part in change["path"][:-1]:
            target = target[part]
        target[change["path"][-1]] = change["value"]
    return document


def test_python_change_request_model_agrees_with_the_portable_corpus() -> None:
    corpus = _corpus()

    for case in corpus["cases"]:
        document = _apply_changes(corpus["base_document"], case["changes"])
        if case["expect"] == "valid":
            validate_change_request(document)
        else:
            with pytest.raises(ValidationError):
                validate_change_request(document)
