from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from metabrowser.builtin_plugins.hosted_review.contracts import HOSTED_REVIEW_CONTRACTS

SCRIPT = Path(__file__).resolve().parent / "dom" / "hosted-review-model-behavior.js"


def test_browser_hosted_review_models_agree_with_the_portable_corpora(tmp_path: Path) -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")

    descriptor: list[dict[str, object]] = []
    expected_case_count = 0
    for contract in HOSTED_REVIEW_CONTRACTS:
        browser_parser = contract.browser_parser
        if browser_parser is None:
            continue
        module_path = tmp_path / f"{browser_parser.module_bytes_sha256}.mjs"
        module_path.write_bytes(browser_parser.module_bytes)
        corpus_path = tmp_path / f"{contract.corpus.payload_sha256}.json"
        corpus_path.write_bytes(contract.corpus.payload)
        descriptor.append(
            {
                "contract_id": contract.contract_id,
                "browser_module_path": str(module_path),
                "browser_parser_export": browser_parser.export_name,
                "corpus_path": str(corpus_path),
                "corpus_record_selectors": contract.corpus_record_selectors,
            }
        )
        corpus = json.loads(contract.corpus.payload)
        selectors = set(contract.corpus_record_selectors)
        case_record_names = {
            test_case.get("record")
            for test_case in corpus["cases"]
            if test_case.get("record") is not None
        }
        assert selectors <= case_record_names
        selected_case_count = sum(
            not selectors or test_case.get("record") in selectors for test_case in corpus["cases"]
        )
        assert selected_case_count > 0
        descriptor[-1]["expected_case_count"] = selected_case_count
        expected_case_count += selected_case_count
    result = subprocess.run(
        ["node", str(SCRIPT), json.dumps(descriptor)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, (
        f"hosted-review model failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert (
        f"hosted review model OK ({len(descriptor)} families, {expected_case_count} cases)"
        in result.stdout
    )
