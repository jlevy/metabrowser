"""Build deterministic Git histories and measure paging cost shapes.

This is an exploration tool, not a release gate. It records machine-dependent
timings alongside structural facts so the v0.9 Git-history implementation can
choose page, buffer, cache, and rendering budgets from evidence. The streaming
spool is deliberately isolated here until the measurement bead accepts or
rejects the mechanism.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import struct
import subprocess
import tempfile
import time
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

import psutil

from metabrowser.git.log import LOG_FORMAT, parse_log_output, read_log_page
from metabrowser.git.process import GIT_COMMON_ARGS, git_environment, git_executable
from metabrowser.git.wire import GitCommit

HistoryShape = Literal["linear", "branch-heavy", "merge-heavy"]

DEFAULT_DEPTHS = (250, 1_000, 10_000)
DEFAULT_PAGE_SIZE = 250
DEFAULT_SHAPES: tuple[HistoryShape, ...] = ("linear", "branch-heavy", "merge-heavy")
DEFAULT_SKIP_DEPTHS = (0, 250, 1_000, 5_000, 9_000)
FAST_IMPORT_BRANCHES = 4
FRAME_HEADER_BYTES = 8
READ_CHUNK_BYTES = 64 * 1024


class CorpusFacts(TypedDict):
    """Stable identity of one generated history corpus."""

    commit_count: int
    object_format: str
    shape: HistoryShape


@dataclass(frozen=True)
class _Frame:
    offset: int
    length: int


class HistorySpool:
    """Completed framed replay spool produced by one ordered Git walk."""

    def __init__(
        self,
        temporary_directory: tempfile.TemporaryDirectory[str],
        *,
        frames: Sequence[_Frame],
        commit_count: int,
        git_rss_peak_bytes: int,
        page_ready_ms: Sequence[float],
        parent_rss_peak_bytes: int,
        peak_buffer_bytes: int,
        walk_elapsed_ms: float,
    ) -> None:
        self._temporary_directory = temporary_directory
        self.path = Path(temporary_directory.name) / "history.pages"
        self._frames = tuple(frames)
        self.commit_count = commit_count
        self.git_rss_peak_bytes = git_rss_peak_bytes
        self.page_ready_ms = tuple(page_ready_ms)
        self.parent_rss_peak_bytes = parent_rss_peak_bytes
        self.peak_buffer_bytes = peak_buffer_bytes
        self.walk_elapsed_ms = walk_elapsed_ms

    @property
    def page_count(self) -> int:
        return len(self._frames)

    @property
    def spool_bytes(self) -> int:
        return self.path.stat().st_size

    @property
    def max_page_bytes(self) -> int:
        return max((frame.length for frame in self._frames), default=0)

    @property
    def read_chunk_bytes(self) -> int:
        return READ_CHUNK_BYTES

    def replay_page(self, index: int) -> list[GitCommit]:
        """Read and parse one completed page without touching preceding pages."""
        frame = self._frames[index]
        with self.path.open("rb") as source:
            source.seek(frame.offset)
            raw_length = source.read(FRAME_HEADER_BYTES)
            if len(raw_length) != FRAME_HEADER_BYTES:
                raise RuntimeError("history spool frame header is truncated")
            length = struct.unpack(">Q", raw_length)[0]
            if length != frame.length:
                raise RuntimeError("history spool frame index disagrees with its header")
            payload = source.read(length)
        if len(payload) != length:
            raise RuntimeError("history spool frame payload is truncated")
        return parse_log_output(payload)

    def replay_all(self) -> Iterator[list[GitCommit]]:
        """Yield pages in logical order for measurement and differential checks."""
        for index in range(self.page_count):
            yield self.replay_page(index)

    def close(self) -> None:
        self._temporary_directory.cleanup()

    def __enter__(self) -> HistorySpool:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def _run_git(root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    executable = git_executable()
    if executable is None:
        raise RuntimeError("git executable not found on PATH")
    result = subprocess.run(
        [executable, *GIT_COMMON_ARGS, *args],
        cwd=root,
        check=False,
        capture_output=True,
        input=input_bytes,
        env=git_environment(),
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} exited {result.returncode}: {detail}")
    return result.stdout


def _commit_record(
    *,
    branch: str,
    index: int,
    parent: int | None,
    merge: int | None = None,
) -> bytes:
    message = f"history commit {index}"
    content = f"deterministic history payload {index}\n"
    timestamp = 1_700_000_000 + index
    lines = [
        f"commit refs/heads/{branch}",
        f"mark :{index}",
        f"committer History Fixture <history@example.invalid> {timestamp} +0000",
        f"data {len(message.encode('utf-8'))}",
        message,
    ]
    if parent is not None:
        lines.append(f"from :{parent}")
    if merge is not None:
        lines.append(f"merge :{merge}")
    lines.extend(
        [
            "M 100644 inline history/payload.txt",
            f"data {len(content.encode('utf-8'))}",
            content.rstrip("\n"),
            "",
        ]
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _linear_import(commit_count: int) -> Iterable[bytes]:
    for index in range(1, commit_count + 1):
        yield _commit_record(branch="main", index=index, parent=index - 1 or None)


def _branch_heavy_import(commit_count: int) -> Iterable[bytes]:
    yield _commit_record(branch="main", index=1, parent=None)
    tips = dict.fromkeys(range(FAST_IMPORT_BRANCHES), 1)
    for index in range(2, commit_count + 1):
        branch_index = (index - 2) % FAST_IMPORT_BRANCHES
        yield _commit_record(
            branch=f"feature-{branch_index + 1}",
            index=index,
            parent=tips[branch_index],
        )
        tips[branch_index] = index


def _merge_heavy_import(commit_count: int) -> Iterable[bytes]:
    yield _commit_record(branch="main", index=1, parent=None)
    main_tip = 1
    feature_tip = 1
    for index in range(2, commit_count + 1):
        if index % 2 == 0:
            yield _commit_record(branch="feature", index=index, parent=main_tip)
            feature_tip = index
        else:
            yield _commit_record(
                branch="main",
                index=index,
                parent=main_tip,
                merge=feature_tip,
            )
            main_tip = index


def _import_stream(shape: HistoryShape, commit_count: int) -> bytes:
    if shape == "linear":
        records = _linear_import(commit_count)
    elif shape == "branch-heavy":
        records = _branch_heavy_import(commit_count)
    else:
        records = _merge_heavy_import(commit_count)
    return b"".join(records) + b"done\n"


def build_history_corpus(
    root: Path,
    *,
    shape: HistoryShape,
    commit_count: int,
) -> CorpusFacts:
    """Create one deterministic repository through a single fast-import process."""
    if commit_count < 1:
        raise ValueError("commit_count must be positive")
    if shape not in DEFAULT_SHAPES:
        raise ValueError(f"unknown history shape: {shape}")
    if root.exists() and any(root.iterdir()):
        raise ValueError(f"history corpus directory is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    _run_git(root, "init", "-q", "-b", "main", "--object-format=sha1")
    _run_git(root, "fast-import", "--quiet", input_bytes=_import_stream(shape, commit_count))
    _run_git(root, "reset", "--hard", "-q", "main")
    object_format = _run_git(root, "rev-parse", "--show-object-format").decode().strip()
    return CorpusFacts(commit_count=commit_count, object_format=object_format, shape=shape)


def _sample_rss(process: psutil.Process) -> int:
    try:
        return process.memory_info().rss
    except (psutil.Error, ProcessLookupError):
        return 0


def _flush_page(destination: Any, page: bytearray, frames: list[_Frame]) -> None:
    payload = bytes(page)
    header_offset = destination.tell()
    destination.write(struct.pack(">Q", len(payload)))
    destination.write(payload)
    destination.flush()
    frames.append(_Frame(offset=header_offset, length=len(payload)))
    page.clear()


def spool_history(root: Path, *, page_size: int = DEFAULT_PAGE_SIZE) -> HistorySpool:
    """Walk all refs once and publish replayable framed pages as they complete."""
    if page_size < 1:
        raise ValueError("page_size must be positive")
    executable = git_executable()
    if executable is None:
        raise RuntimeError("git executable not found on PATH")

    temporary_directory = tempfile.TemporaryDirectory(prefix="metabrowser-history-")
    spool_path = Path(temporary_directory.name) / "history.pages"
    args = [
        executable,
        *GIT_COMMON_ARGS,
        "log",
        "-z",
        f"--format={LOG_FORMAT}",
        "--decorate=full",
        "--date-order",
        "--all",
    ]
    process = subprocess.Popen(
        args,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=git_environment(),
    )
    git_process = psutil.Process(process.pid)
    parent_process = psutil.Process()
    frames: list[_Frame] = []
    page_ready_ms: list[float] = []
    pending = bytearray()
    page = bytearray()
    page_records = 0
    commit_count = 0
    peak_buffer_bytes = 0
    git_rss_peak_bytes = 0
    parent_rss_peak_bytes = _sample_rss(parent_process)
    started = time.perf_counter()

    try:
        if process.stdout is None:
            raise RuntimeError("git history process did not expose stdout")
        with spool_path.open("wb") as destination:
            while True:
                chunk = process.stdout.read(READ_CHUNK_BYTES)
                if not chunk:
                    break
                pending.extend(chunk)
                git_rss_peak_bytes = max(git_rss_peak_bytes, _sample_rss(git_process))
                parent_rss_peak_bytes = max(parent_rss_peak_bytes, _sample_rss(parent_process))
                while True:
                    boundary = pending.find(0)
                    if boundary < 0:
                        break
                    record = pending[:boundary]
                    del pending[: boundary + 1]
                    if not record:
                        continue
                    page.extend(record)
                    page.append(0)
                    page_records += 1
                    commit_count += 1
                    peak_buffer_bytes = max(peak_buffer_bytes, len(page) + len(pending))
                    if page_records == page_size:
                        _flush_page(destination, page, frames)
                        page_records = 0
                        page_ready_ms.append((time.perf_counter() - started) * 1_000)
            if pending:
                raise RuntimeError("git history stream ended inside a commit record")
            if page:
                _flush_page(destination, page, frames)
                page_ready_ms.append((time.perf_counter() - started) * 1_000)
        returncode = process.wait(timeout=15)
        if returncode != 0:
            stderr = process.stderr.read() if process.stderr is not None else b""
            detail = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"git history walk exited {returncode}: {detail}")
    except BaseException:
        process.kill()
        process.wait()
        temporary_directory.cleanup()
        raise

    return HistorySpool(
        temporary_directory,
        frames=frames,
        commit_count=commit_count,
        git_rss_peak_bytes=git_rss_peak_bytes,
        page_ready_ms=page_ready_ms,
        parent_rss_peak_bytes=parent_rss_peak_bytes,
        peak_buffer_bytes=peak_buffer_bytes,
        walk_elapsed_ms=(time.perf_counter() - started) * 1_000,
    )


def _ordered_revisions(root: Path) -> list[str]:
    raw = _run_git(root, "rev-list", "--date-order", "--all")
    return raw.decode("ascii").splitlines()


def _round_ms(value: float) -> float:
    return round(value, 3)


def _megabytes(value: int) -> float:
    return round(value / (1024 * 1024), 3)


def measure_history_corpus(
    root: Path,
    *,
    shape: HistoryShape,
    commit_count: int,
    page_size: int = DEFAULT_PAGE_SIZE,
    skip_depths: Sequence[int] = DEFAULT_SKIP_DEPTHS,
) -> dict[str, Any]:
    """Measure current offset pages and the one-walk replay prototype."""
    process = psutil.Process()
    offset_pages: list[dict[str, int | float]] = []
    for skip in skip_depths:
        if skip >= commit_count:
            continue
        rss_before = _sample_rss(process)
        started = time.perf_counter()
        page = asyncio.run(read_log_page(root, skip=skip, limit=page_size, refs=None))
        elapsed_ms = (time.perf_counter() - started) * 1_000
        payload_bytes = len(
            json.dumps(dict(page), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
        offset_pages.append(
            {
                "commits": len(page["commits"]),
                "elapsed_ms": _round_ms(elapsed_ms),
                "payload_bytes": payload_bytes,
                "rss_after_mb": _megabytes(_sample_rss(process)),
                "rss_before_mb": _megabytes(rss_before),
                "skip": skip,
            }
        )

    expected = _ordered_revisions(root)
    with spool_history(root, page_size=page_size) as spool:
        observed = [commit["id"] for page in spool.replay_all() for commit in page]
        replay_indexes = sorted({0, max(0, spool.page_count // 2), max(0, spool.page_count - 1)})
        replay_samples: list[dict[str, int | float]] = []
        for page_index in replay_indexes:
            started = time.perf_counter()
            commits = spool.replay_page(page_index)
            replay_samples.append(
                {
                    "commits": len(commits),
                    "elapsed_ms": _round_ms((time.perf_counter() - started) * 1_000),
                    "page": page_index,
                }
            )
        prototype = {
            "commit_count": spool.commit_count,
            "git_rss_peak_mb": _megabytes(spool.git_rss_peak_bytes),
            "max_page_bytes": spool.max_page_bytes,
            "ordered_revision_match": observed == expected,
            "page_count": spool.page_count,
            "page_ready_ms": [_round_ms(value) for value in spool.page_ready_ms],
            "page_size": page_size,
            "parent_rss_peak_mb": _megabytes(spool.parent_rss_peak_bytes),
            "peak_buffer_bytes": spool.peak_buffer_bytes,
            "replay_pages": replay_samples,
            "spool_bytes": spool.spool_bytes,
            "spool_bytes_per_commit": round(spool.spool_bytes / max(1, spool.commit_count), 3),
            "walk_elapsed_ms": _round_ms(spool.walk_elapsed_ms),
        }

    return {
        "corpus": CorpusFacts(
            commit_count=commit_count,
            object_format=_run_git(root, "rev-parse", "--show-object-format").decode().strip(),
            shape=shape,
        ),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "offset_pages": offset_pages,
        "schema": "metabrowser-git-history-measurement/v1",
        "streaming_prototype": prototype,
    }


def measure_matrix(
    root: Path,
    *,
    depths: Sequence[int] = DEFAULT_DEPTHS,
    shapes: Sequence[HistoryShape] = DEFAULT_SHAPES,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """Build and measure every requested shape/depth pair."""
    measurements: list[dict[str, Any]] = []
    for shape in shapes:
        for depth in depths:
            corpus_root = root / f"{shape}-{depth}"
            if not corpus_root.exists():
                build_history_corpus(corpus_root, shape=shape, commit_count=depth)
            measurements.append(
                measure_history_corpus(
                    corpus_root,
                    shape=shape,
                    commit_count=depth,
                    page_size=page_size,
                    skip_depths=tuple(skip for skip in DEFAULT_SKIP_DEPTHS if skip < depth),
                )
            )
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "measurements": measurements,
        "page_size": page_size,
        "schema": "metabrowser-git-history-matrix/v1",
    }


def _parse_csv_ints(raw: str) -> tuple[int, ...]:
    values = tuple(int(value.strip()) for value in raw.split(",") if value.strip())
    if not values or any(value < 1 for value in values):
        raise argparse.ArgumentTypeError("expected comma-separated positive integers")
    return values


def _parse_csv_shapes(raw: str) -> tuple[HistoryShape, ...]:
    values = tuple(value.strip() for value in raw.split(",") if value.strip())
    unknown = set(values) - set(DEFAULT_SHAPES)
    if not values or unknown:
        raise argparse.ArgumentTypeError(f"unknown history shape(s): {', '.join(sorted(unknown))}")
    return cast(tuple[HistoryShape, ...], values)


def _write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
            json.dump(payload, destination, indent=2, sort_keys=True)
            destination.write("\n")
        temporary_path.replace(path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="build one deterministic history corpus")
    build.add_argument("root", type=Path)
    build.add_argument("--shape", choices=DEFAULT_SHAPES, required=True)
    build.add_argument("--commits", type=int, required=True)

    measure = subparsers.add_parser("measure", help="measure one existing corpus")
    measure.add_argument("root", type=Path)
    measure.add_argument("--shape", choices=DEFAULT_SHAPES, required=True)
    measure.add_argument("--commits", type=int, required=True)
    measure.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    measure.add_argument("--skip-depths", type=_parse_csv_ints, default=DEFAULT_SKIP_DEPTHS)
    measure.add_argument("--output", type=Path, required=True)

    matrix = subparsers.add_parser("matrix", help="build and measure a shape/depth matrix")
    matrix.add_argument("root", type=Path)
    matrix.add_argument("--depths", type=_parse_csv_ints, default=DEFAULT_DEPTHS)
    matrix.add_argument("--shapes", type=_parse_csv_shapes, default=DEFAULT_SHAPES)
    matrix.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    matrix.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "build":
        facts = build_history_corpus(args.root, shape=args.shape, commit_count=args.commits)
        print(json.dumps(facts, sort_keys=True))
        return 0
    if args.command == "measure":
        result = measure_history_corpus(
            args.root,
            shape=args.shape,
            commit_count=args.commits,
            page_size=args.page_size,
            skip_depths=args.skip_depths,
        )
        _write_json_atomic(args.output, result)
        print(args.output)
        return 0
    result = measure_matrix(
        args.root,
        depths=args.depths,
        shapes=args.shapes,
        page_size=args.page_size,
    )
    _write_json_atomic(args.output, result)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
