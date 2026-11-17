"""Run the File Rollup conformance corpus through fdu's native registry classification.

Metadata cases become real files in a temporary root, classified by one opened fdu
index carrying Metabrowser's registry document; invalid-registry cases are each handed
to fdu's parser at open. Aggregate cases need a breakdown projection fdu does not have,
so they are reported as not applicable rather than routed through the Python oracle,
which would only compare the oracle with itself.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from adapter import downlevel_registry
from fdu import opened as fdu
from probe import AdapterProbe

from metabrowser.file_type_registry import load_file_type_registry_document

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS = REPO_ROOT / "src/metabrowser/data/file-rollup-format/file-rollup-conformance.json"
_COMPARED = (
    "logical_extension",
    "canonical_extension",
    "kind_id",
    "family_id",
    "group_id",
    "content_family",
)
_NOT_EXPOSED = ("confidence", "detection_source")
# The wording of fdu's refusal that names the defect each invalid case was written for,
# read from fdu's parser messages. `invalid-toml` has none: fdu's dependency-free parser
# reports a structural error, not TOML syntax. A schema-4 document is valid to fdu.
_EXPECTED_REASON: dict[str, str] = {
    "unsupported-schema": "unsupported schema_version",
    "previous-schema-version": "unsupported schema_version",
    "unsupported-components": "max_extension_components",
    "invalid-field": "registry_revision",
    "undeclared-deviation": "requires a deviation",
    "undeclared-chroma-deviation": "requires a deviation",
    "invalid-id": "invalid group id",
    "missing-fallback": "must declare the other group",
    "duplicate-order": "duplicate group order",
    "unknown-group": "unknown group",
    "unknown-family": "unknown family",
    "invalid-content-family": "invalid content_family",
    "invalid-extension": "invalid extension",
    "duplicate-evidence": "belongs to",
    "invalid-hue": "hue must be",
    "linguist-without-color": "linguist and linguist_color",
    "familyless-kind-without-group": "neither family nor group",
    "family-group-mismatch": "group conflicts with family",
    "empty-family": "no declared extension evidence",
    "missing-evidence": "declares no evidence",
}


def _settle(index: fdu.OpenedIndex) -> None:
    for _attempt in range(1_000):
        if index.state().state.phase is not fdu.LifecyclePhase.DISCOVERING:
            return
        time.sleep(0.005)
    raise AssertionError("fdu did not settle on the conformance corpus")


def _classify(names: list[str], registry: str) -> dict[str, fdu.NameClassification | None]:
    with tempfile.TemporaryDirectory(prefix="fdu-spike-rollup-") as raw:
        root = Path(raw)
        for position, name in enumerate(names):
            folder = root / f"case-{position:03d}"
            folder.mkdir()
            (folder / name).write_bytes(b"")
        index = fdu.OpenedIndex.open(
            root,
            fdu.OpenedOptions(prune_hidden=False, exclude_special=True, type_rules=registry),
        )
        try:
            _settle(index)
            found: dict[str, fdu.NameClassification | None] = {}
            page: fdu.Projection = fdu.Flat(
                selection=fdu.EntrySelection(query=fdu.Selection(kinds=(fdu.EntryKind.FILE,))),
                shape=fdu.RowShape.FULL,
                page=fdu.Page(limit=4_096, max_work=1_000_000),
            )
            while True:
                result = index.read(page).results[0]
                assert isinstance(result, fdu.FlatResult)
                for row in result.value.rows:
                    folder = row.portable_path.split("/", 1)[0]
                    found[folder] = row.classification
                if result.value.next is None:
                    break
                page = fdu.Continue(continuation=result.value.next)
        finally:
            index.close()
    return {name: found.get(f"case-{position:03d}") for position, name in enumerate(names)}


def run_corpus(probe: AdapterProbe) -> dict[str, Any]:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    registry = downlevel_registry(load_file_type_registry_document(), probe)
    cases: list[dict[str, Any]] = corpus["metadata_cases"]
    representable = [
        case for case in cases if "/" not in case["name"] and "\x00" not in case["name"]
    ]
    classified = _classify([case["name"] for case in representable], registry)
    rows: list[dict[str, Any]] = []
    field_mismatches: dict[str, int] = dict.fromkeys(_COMPARED, 0)
    for case in representable:
        native = classified[case["name"]]
        expected = case["expected"]
        actual = {name: getattr(native, name) if native is not None else None for name in _COMPARED}
        diffs = {
            name: {"expected": expected.get(name), "fdu": actual[name]}
            for name in _COMPARED
            if (expected.get(name) or None) != (actual[name] or None)
        }
        for name in diffs:
            field_mismatches[name] += 1
        rows.append({"name": case["name"], "agrees": not diffs, "differences": diffs})
    invalid_rows: list[dict[str, Any]] = []
    for case in corpus["invalid_registry_cases"]:
        # The same shim the adapter applies, so a case is not refused merely for being
        # schema 5; then the refusal must name the defect the case was written for.
        document = downlevel_registry(case["toml"], AdapterProbe())
        message: str | None = None
        try:
            with tempfile.TemporaryDirectory(prefix="fdu-spike-registry-") as raw:
                fdu.OpenedIndex.open(raw, fdu.OpenedOptions(type_rules=document)).close()
        except (fdu.OpenedIndexError, ValueError) as error:
            message = str(error)
        keyword = _EXPECTED_REASON.get(case["id"])
        if message is None:
            verdict = "accepted"
        elif keyword is not None and keyword in message:
            verdict = "refused_for_the_case_reason"
        else:
            verdict = "refused_for_another_reason"
        invalid_rows.append(
            {
                "id": case["id"],
                "metabrowser_error": case["error_code"],
                "expected_fdu_wording": keyword,
                "fdu_message": (message or "")[:200],
                "verdict": verdict,
            }
        )
    return {
        "registry": corpus["registry"],
        "metadata_cases": len(cases),
        "metadata_cases_run": len(representable),
        "metadata_agree": sum(row["agrees"] for row in rows),
        "metadata_field_mismatches": field_mismatches,
        "metadata_disagreements": [row for row in rows if not row["agrees"]],
        "fields_not_exposed_by_fdu": list(_NOT_EXPOSED),
        "invalid_registry_cases": len(invalid_rows),
        "invalid_registry_method": (
            "each case down-leveled through the adapter's schema-5 shim, then fdu's refusal "
            "compared with the defect the case names, by the wording in expected_fdu_wording"
        ),
        "invalid_registry_verdicts": {
            verdict: [row["id"] for row in invalid_rows if row["verdict"] == verdict]
            for verdict in (
                "refused_for_the_case_reason",
                "refused_for_another_reason",
                "accepted",
            )
        },
        "invalid_registry_rows": invalid_rows,
        "aggregate_cases": len(corpus["aggregate_cases"]),
        "aggregate_cases_status": (
            "not applicable: fdu 0.6.0 has no file-type breakdown projection; the spike's "
            "rollup is the Python oracle, which would only compare with itself"
        ),
        "platform": os.uname().sysname,
    }


if __name__ == "__main__":
    result = run_corpus(AdapterProbe())
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "invalid_registry_rows"},
            indent=1,
        )[:6000]
    )
