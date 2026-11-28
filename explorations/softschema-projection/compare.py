"""Compare the eager folder table with a narrow SQLite projection on a trusted corpus."""

# The reproduction pins both repositories and exercises their private reader and projection.
# pyright: reportPrivateUsage=false

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import sqlite3
import subprocess
import sys
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any
from unittest.mock import patch

import softschema.collection as api
from softschema import yaml_parser_mode

from metabrowser.builtin_plugins.softschema import source as tables

PAGE_SIZE = 25
MAX_FILE_BYTES = 1024**2
MAX_TOTAL_BYTES = 64 * 1024**2
Row = tuple[str, str, str, str | None, str, str]
Stats = dict[str, Any]
READ = api._read


def elapsed_ms(start: float) -> float:
    return round(1000 * (perf_counter() - start), 3)


def digest(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(data).hexdigest()


def row_for(record: api.CollectionRecord) -> Row:
    assert record.metadata and record.values is not None
    row = tables._Row(record.path, record.values)
    return (
        record.path,
        record.metadata.contract_id,
        row.key,
        record.values.get("id"),
        tables._label(row),
        record.state,
    )


def record_digest(record: api.CollectionRecord) -> str:
    return digest([row_for(record), record.host, record.body, record.values, record.execution])


@dataclass
class SourceReads:
    opens: int = 0
    size: int = 0

    def full(self, path: Path, status: os.stat_result, limit: int) -> str:
        text = READ(path, status, limit)
        self.opens += 1
        self.size += status.st_size
        return text

    def metadata(self, path: Path, status: os.stat_result) -> str:
        if path.suffix.lower() != ".md":
            return self.full(path, status, status.st_size)
        # The sample uses ordinary LF fences. Other forms go through the full parser.
        self.opens += 1
        data = bytearray()
        with path.open("rb", buffering=0) as source:
            while block := source.read(2048):
                offset = max(0, len(data) - 4)
                data.extend(block)
                self.size += len(block)
                if len(data) > MAX_FILE_BYTES:
                    raise ValueError("Markdown file changed or exceeds the trial limit")
                if data.startswith(b"---\n"):
                    end = data.find(b"\n---\n", max(3, offset))
                    if end >= 0:
                        return data[: end + 5].decode("utf-8-sig")
        return data.decode("utf-8-sig")


def summarize(
    stats: Stats, rows: list[Row], page: list[Row], selected: api.CollectionRecord
) -> Stats:
    stats.update(
        records=len(rows),
        tables=len({row[1] for row in rows}),
        row_digest=digest(sorted(rows)),
        page_digest=digest(page),
        selected_digest=record_digest(selected),
        selected_body_bytes=len(selected.body.encode()),
    )
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    stats["peak_rss_mib"] = round(peak / (1024**2 if sys.platform == "darwin" else 1024), 2)
    return stats


def eager(root: Path, database: Path, table: str, prefix: str) -> Stats:
    reads = SourceReads()
    started = perf_counter()
    with patch.object(api, "_read", reads.full):
        scan = api.scan_collection(root)
    assert scan.complete
    groups = tables._group(scan)
    locations = tables._locations(groups)
    for name, group in groups.items():
        tables._schema(scan, name, group, locations)
    rows = sorted(
        row_for(row.record)
        for name, group in groups.items()
        if name != "$problems"
        for row in group
        if row.record is not None
    )
    page = [row for row in rows if row[1] == table and row[0].startswith(prefix)][:PAGE_SIZE]
    assert len(page) == PAGE_SIZE, "the target table and folder need at least one full page"
    stats = {
        "first_page_ms": elapsed_ms(started),
        "first_page_opens": reads.opens,
        "first_page_bytes": reads.size,
        "build_opens": reads.opens,
        "build_bytes": reads.size,
    }
    with closing(sqlite3.connect(database)) as writer:
        writer.execute("CREATE TABLE snapshots (contents TEXT)")
        writer.execute("INSERT INTO snapshots VALUES (?)", (scan.snapshot_json(),))
        writer.commit()
    stats.update(durable_build_ms=elapsed_ms(started), database_bytes=database.stat().st_size)
    mark = perf_counter()
    selected = next(row.record for row in groups[table] if row.path == page[0][0])
    assert selected is not None
    stats.update(selected_ms=elapsed_ms(mark), selected_opens=0, selected_bytes=0)
    return summarize(stats, rows, page, selected)


def page_from_disk(database: Path, table: str, prefix: str) -> list[Row]:
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as reader:
        return reader.execute(
            "SELECT * FROM rows WHERE kind=? AND substr(path,1,length(?))=? ORDER BY path LIMIT ?",
            (table, prefix, prefix, PAGE_SIZE),
        ).fetchall()


def projection(root: Path, database: Path, table: str, prefix: str) -> Stats:
    started = perf_counter()
    files, walked = api._walk(root, 50_000, None, [])
    assert walked and all(st.st_size <= MAX_FILE_BYTES for _, st in files)
    assert sum(st.st_size for _, st in files) <= MAX_TOTAL_BYTES, (
        "eager scan cannot cover this scope"
    )
    stats: Stats = {
        "refs_ms": elapsed_ms(started),
        "ref_count": len(files),
        "ref_opens": 0,
        "ref_bytes": 0,
    }
    stamps = dict(files)
    reads = SourceReads()
    schemas: dict[str, tuple[api.CollectionSchema, str]] = {}
    by_contract: dict[str, dict[str, str]] = defaultdict(dict)
    for path, st in files:
        if path.lower().endswith(api._SCHEMA_SUFFIXES):
            text = reads.full(root / path, st, st.st_size)
            file = api._scan_file(path, api._fingerprint(st), text)
            assert file.schema and file.schema_text is not None, "trial needs a complete catalogue"
            schemas[path] = (file.schema, file.schema_text)
            if file.schema.contract:
                by_contract[file.schema.contract].setdefault(file.schema.digest, path)
    stats.update(
        schema_catalog_ms=elapsed_ms(started), schema_opens=reads.opens, schema_bytes=reads.size
    )

    def bound_record(path: str, text: str) -> api.CollectionRecord | None:
        file = api._scan_file(path, api._fingerprint(stamps[path]), text)
        if file.record:
            return api._bind(file.record, file.record_yaml, schemas, by_contract, True, None)
        return None

    with closing(sqlite3.connect(database)) as writer:
        writer.execute(
            "CREATE TABLE rows (path TEXT PRIMARY KEY, kind TEXT, key TEXT, id TEXT, label TEXT, state TEXT)"
        )
        writer.execute("CREATE INDEX by_kind_path ON rows(kind,path)")
        writer.execute("CREATE INDEX by_id ON rows(id)")
        matches = 0
        preview = []
        for path, st in sorted(files, key=lambda pair: (not pair[0].startswith(prefix), pair[0])):
            if path in schemas:
                continue
            record = bound_record(path, reads.metadata(root / path, st))
            if record is None or record.metadata is None or record.values is None:
                continue
            row = row_for(record)
            writer.execute("INSERT INTO rows VALUES (?,?,?,?,?,?)", row)
            if row[1] == table and path.startswith(prefix):
                matches += 1
                if matches == PAGE_SIZE:
                    writer.commit()
                    preview = page_from_disk(database, table, prefix)
                    stats.update(
                        first_page_ms=elapsed_ms(started),
                        first_page_opens=reads.opens,
                        first_page_bytes=reads.size,
                    )
        writer.commit()
    stats.update(
        durable_build_ms=elapsed_ms(started),
        build_opens=reads.opens,
        build_bytes=reads.size,
        database_bytes=database.stat().st_size,
    )
    mark = perf_counter()
    page = page_from_disk(database, table, prefix)
    stats["reopen_page_ms"] = elapsed_ms(mark)
    assert len(page) == PAGE_SIZE and preview == page
    before = reads.size
    mark = perf_counter()
    path = page[0][0]
    st = (root / path).lstat()
    assert api._fingerprint(st) == api._fingerprint(stamps[path]), "selected file changed"
    selected = bound_record(path, reads.full(root / path, st, st.st_size))
    assert selected is not None
    stats.update(selected_ms=elapsed_ms(mark), selected_opens=1, selected_bytes=reads.size - before)
    with closing(sqlite3.connect(database)) as reader:
        rows = reader.execute("SELECT * FROM rows ORDER BY path").fetchall()
    return summarize(stats, rows, page, selected)


def generate(root: Path, count: int, body_bytes: int) -> None:
    root.mkdir()
    schema = {
        "type": "object",
        "x-softschema": {"contract": "Example"},
        "properties": {key: {"type": "string"} for key in ("id", "name")},
    }
    (root / "example.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    line = "body text\n"
    body = (line * (body_bytes // len(line) + 1))[:body_bytes]
    for n in range(count):
        values = {"id": f"item{n:05}", "name": f"Item {n:05}"}
        path = root / f"row{n:05}"
        if n % 2:
            path.with_suffix(".json").write_text(
                json.dumps({"softschema": "Example", **values}), encoding="utf-8"
            )
        else:
            header = "---\nsoftschema: {contract: Example, envelope: item}\nitem: "
            path.with_suffix(".md").write_text(
                header + json.dumps(values) + "\n---\n" + body, encoding="utf-8"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scratch", required=True, type=Path, help="existing directory for temporary trial data"
    )
    parser.add_argument(
        "--root", type=Path, help="read this corpus; otherwise generate a flat tree"
    )
    parser.add_argument("--table", default="Example")
    parser.add_argument(
        "--prefix", default="", help="folder path relative to root, with trailing slash"
    )
    parser.add_argument("--synthetic-rows", type=int, default=1024)
    parser.add_argument("--body-bytes", type=int, default=96 * 1024)
    parser.add_argument("--engine", choices=("eager", "projection"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if sys.platform not in ("darwin", "linux"):
        parser.error("RSS measurement supports macOS and Linux")
    if args.engine:
        run = eager if args.engine == "eager" else projection
        result = run(
            args.root.resolve(), args.scratch / f"{args.engine}.sqlite", args.table, args.prefix
        )
        print(json.dumps({"engine": args.engine, **result}))
        return
    if args.root and args.scratch.resolve().is_relative_to(args.root.resolve()):
        parser.error("use a scratch directory outside the corpus")
    with TemporaryDirectory(dir=args.scratch) as directory:
        work = Path(directory).resolve()
        root = args.root
        if root is None:
            root = work / "flat"
            generate(root, args.synthetic_rows, args.body_bytes)
        results: list[Stats] = []
        for engine in ("eager", "projection"):
            command = [
                sys.executable,
                __file__,
                "--engine",
                engine,
                "--scratch",
                str(work),
                "--root",
                str(root),
                "--table",
                args.table,
                "--prefix",
                args.prefix,
            ]
            results.append(json.loads(subprocess.check_output(command, text=True)))
        for key in ("records", "tables", "row_digest", "page_digest", "selected_digest"):
            assert results[0][key] == results[1][key], f"strategies disagree on {key}"
        print(
            json.dumps(
                {
                    "python": platform.python_version(),
                    "platform": platform.system(),
                    "architecture": platform.machine(),
                    "parser": yaml_parser_mode(),
                    "results": results,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
