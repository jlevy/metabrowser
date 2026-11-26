"""Compare SoftSchema's guarded C and pure readers on the same collection.

Run `uv --config-file uv.toml run --frozen --extra yaml-accelerator python -m
devtools.bench_softschema_collection` for generated records, or pass a collection root.
Report wall times with a warm filesystem cache
and a cold validator cache per trial. Read only; the generated corpus lives in TMPDIR.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from softschema import (
    Contract,
    SchemaProfile,
    clear_validator_cache,
    parse_schema_metadata,
    read_frontmatter_doc,
    read_yaml_doc,
    validate_artifact,
    yaml_parser_mode,
)

RECORD_SUFFIXES = frozenset({".md", ".yaml", ".yml", ".json"})
SCHEMA_SUFFIXES = (".schema.yaml", ".schema.yml", ".schema.json")
PURE_YAML = "SOFTSCHEMA_PURE_YAML"


@dataclass(slots=True)
class Trial:
    walk_seconds: float
    read_seconds: float
    validate_seconds: float
    candidates: int
    counts: dict[str, int]
    digest: str


def _candidates(root: Path) -> list[Path]:
    paths: list[Path] = []
    for folder, dirs, files in os.walk(root):
        directory = Path(folder)
        dirs[:] = sorted(
            name
            for name in dirs
            if not name.startswith(".") and not (directory / name).is_symlink()
        )
        for name in sorted(files):
            path = directory / name
            if (
                not name.startswith(".")
                and not name.endswith(SCHEMA_SUFFIXES)
                and path.suffix in RECORD_SUFFIXES
                and path.is_file()
                and not path.is_symlink()
            ):
                paths.append(path)
    return paths


def _trial(root: Path) -> Trial:
    clear_validator_cache()
    started = perf_counter()
    paths = _candidates(root)
    walked = perf_counter()
    records: list[tuple[Path, Contract, dict[str, Any]]] = []
    counts = {"read_error": 0, "malformed": 0, "unbound": 0, "valid": 0, "invalid": 0}
    for path in paths:
        is_markdown = path.suffix == ".md"
        try:
            document = read_frontmatter_doc(path)[1] if is_markdown else read_yaml_doc(path)
        except (OSError, ValueError):
            counts["read_error"] += 1
            continue
        if not isinstance(document, dict) or "softschema" not in document:
            continue
        try:
            metadata = parse_schema_metadata(document["softschema"])
        except ValueError:
            counts["malformed"] += 1
            continue
        if metadata is None or metadata.status is None or metadata.schema_ref is None:
            counts["unbound"] += 1
            continue
        try:
            schema = (path.parent / metadata.schema_ref).resolve(strict=True)
        except (OSError, ValueError):
            counts["unbound"] += 1
            continue
        if not schema.is_relative_to(root) or not schema.is_file():
            counts["unbound"] += 1
            continue
        contract = Contract(
            id=metadata.contract_id,
            envelope_key=metadata.envelope,
            profile=SchemaProfile.frontmatter_md if is_markdown else SchemaProfile.pure_yaml,
            schema_path=schema,
            status=metadata.status,
        )
        records.append((path, contract, cast(dict[str, Any], document)))
    read = perf_counter()
    digest = hashlib.sha256()
    for path, contract, document in records:
        result = validate_artifact(
            path, contract=contract, document=document, require=("structural",)
        )
        counts["valid" if result.ok else "invalid"] += 1
        digest.update(
            json.dumps(
                [path.relative_to(root).as_posix(), document, result.outcome],
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
    validated = perf_counter()
    return Trial(
        walked - started, read - walked, validated - read, len(paths), counts, digest.hexdigest()
    )


def _measure(root: Path, repeats: int) -> dict[str, object]:
    settings = (("c-first", "0"), ("pure", "1"))
    samples: dict[str, list[Trial]] = {mode: [] for mode, _ in settings}
    previous = os.environ.get(PURE_YAML)
    try:
        for index in range(repeats):
            for expected, setting in settings if index % 2 == 0 else reversed(settings):
                os.environ[PURE_YAML] = setting
                actual = yaml_parser_mode()
                if actual != expected:
                    raise SystemExit(
                        f"Expected {expected} parser, found {actual}. Run metab --doctor."
                    )
                samples[expected].append(_trial(root))
    finally:
        if previous is None:
            os.environ.pop(PURE_YAML, None)
        else:
            os.environ[PURE_YAML] = previous
    reference = samples["c-first"][0]
    if any(
        (trial.candidates, trial.counts, trial.digest)
        != (reference.candidates, reference.counts, reference.digest)
        for trials in samples.values()
        for trial in trials
    ):
        raise SystemExit("Parser runs examined different data or returned different results.")
    return {
        "candidates": reference.candidates,
        "counts": reference.counts,
        "repeats": repeats,
        "seconds": {
            mode: {
                "walk": round(statistics.median(t.walk_seconds for t in trials), 3),
                "read_and_bind": round(statistics.median(t.read_seconds for t in trials), 3),
                "validate_and_hash": round(
                    statistics.median(t.validate_seconds for t in trials), 3
                ),
            }
            for mode, trials in samples.items()
        },
    }


def _generate(root: Path, count: int) -> None:
    # These files are private benchmark inputs in a fresh TemporaryDirectory.
    schema = {
        "type": "object",
        "properties": {"id": {"type": "string"}, "title": {"type": "string"}},
        "required": ["id", "title"],
        "x-softschema": {"contract": "bench:Record/v1"},
    }
    # write-contract: private staging -- benchmark inputs in an isolated temporary directory
    (root / "record.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    for index in range(count):
        # write-contract: private staging -- benchmark inputs in an isolated temporary directory
        (root / f"record-{index:06}.md").write_text(
            "---\nsoftschema:\n  contract: bench:Record/v1\n  schema: record.schema.json\n"
            f"  envelope: record\n  status: enforced\nrecord:\n  id: 'rec:{index}'\n"
            f"  title: Record {index}\n---\n\nExample reader-facing text.\n",
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, help="existing collection to read")
    parser.add_argument("--records", type=int, default=2_000, help="generated record count")
    parser.add_argument("--repeats", type=int, default=3, help="trials per parser")
    args = parser.parse_args()
    if args.records < 1 or args.repeats < 1:
        parser.error("--records and --repeats must be positive")
    if args.root is not None:
        root = args.root.resolve()
        if not root.is_dir():
            parser.error("root must be a directory")
        result = _measure(root, args.repeats)
    else:
        with tempfile.TemporaryDirectory(prefix="softschema-collection-") as folder:
            root = Path(folder).resolve()
            _generate(root, args.records)
            result = _measure(root, args.repeats)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
