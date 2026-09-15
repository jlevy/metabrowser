from __future__ import annotations

import copy
import json
from importlib.resources import files
from typing import Any


def change_request_case() -> dict[str, Any]:
    resource = files("metabrowser").joinpath(
        "data/hosted-review-format/change-request-conformance.json"
    )
    corpus = json.loads(resource.read_text(encoding="utf-8"))
    return copy.deepcopy(corpus["base_document"])
