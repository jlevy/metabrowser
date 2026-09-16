from __future__ import annotations

import copy
import json
from importlib.resources import files
from typing import Any


def load_hosted_review_corpus(filename: str) -> dict[str, Any]:
    resource = files("metabrowser").joinpath(f"data/hosted-review-format/{filename}")
    return json.loads(resource.read_text(encoding="utf-8"))


def apply_case_changes(
    base_document: dict[str, Any], changes: list[dict[str, Any]]
) -> dict[str, Any]:
    document = copy.deepcopy(base_document)
    for change in changes:
        target: Any = document
        for part in change["path"][:-1]:
            target = target[part]
        target[change["path"][-1]] = change["value"]
    return document


def change_request_case() -> dict[str, Any]:
    corpus = load_hosted_review_corpus("change-request-conformance.json")
    return copy.deepcopy(corpus["base_document"])
