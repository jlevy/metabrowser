"""In-process navigation API checks for the ``metab`` CLI.

The check drives the same HTTP route handlers as the browser without binding a
port or opening a browser. Its concise transcript is stable enough for golden
testing and useful when diagnosing a large real directory from an installed
command.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
from starlette.types import ASGIApp

from metabrowser.cli.asgi_client import (
    INDEX_READY_TIMEOUT_S,
    ApiResponse,
    IndexResult,
    InProcessClient,
    wait_for_index,
)
from metabrowser.cli.common import apply_log_level
from metabrowser.cli.plugin_paths import resolve_extra_plugin_dirs
from metabrowser.dotenv import load_dotenv_chain
from metabrowser.errors import CLIError

LOG = logging.getLogger(__name__)

# Markdown: present in every directory this check is pointed at (a repository,
# a run directory), and narrow enough that a tree still carrying folders with
# no match is visibly wrong rather than plausibly complete.
_FILTER_PROBE_TYPE = ".md"


@dataclass(frozen=True, slots=True)
class _CheckStep:
    """One normalized request result in the navigation scenario."""

    label: str
    status_code: int
    fields: str
    valid: bool


def _tree_step(label: str, status_code: int, payload: Any) -> _CheckStep:
    if not isinstance(payload, dict):
        return _CheckStep(label, status_code, "invalid JSON envelope", False)
    tree = payload.get("tree")
    summary = payload.get("summary")
    index_status = payload.get("tally_cache_status")
    if (
        not isinstance(tree, list)
        or not isinstance(summary, dict)
        or not isinstance(index_status, str)
    ):
        return _CheckStep(label, status_code, "invalid tree envelope", False)
    tracked_files = summary.get("files")
    ignored_files = summary.get("ignored_files")
    tracked_size = summary.get("size")
    ignored_size = summary.get("ignored_size")
    if not (
        isinstance(tracked_files, int)
        and isinstance(ignored_files, int)
        and isinstance(tracked_size, int)
        and isinstance(ignored_size, int)
    ):
        return _CheckStep(label, status_code, "invalid tree summary", False)
    files = tracked_files + ignored_files
    size = tracked_size + ignored_size
    fields = f"rows={len(tree)}; files={files}; size={size}; index={index_status}"
    return _CheckStep(label, status_code, fields, status_code == 200)


def _tree_probe_step(label: str, status_code: int, payload: Any) -> _CheckStep:
    valid = (
        status_code == 200 and isinstance(payload, dict) and isinstance(payload.get("tree"), list)
    )
    return _CheckStep(label, status_code, "response=tree", valid)


def _filtered_step(label: str, status_code: int, payload: Any) -> _CheckStep:
    """Check the filtered tree projection the navigation panel asks for.

    The filter decides which folders are listed and what each one rolls up to,
    over the whole index rather than over the rows a response carries. Only the
    envelope can report that, so the step reads the totals rather than counting
    what came back.
    """

    if not isinstance(payload, dict):
        return _CheckStep(label, status_code, "invalid JSON envelope", False)
    tree = payload.get("tree")
    filtered = payload.get("filtered")
    if not isinstance(tree, list) or not isinstance(filtered, dict):
        return _CheckStep(label, status_code, "missing filtered projection", False)
    files = filtered.get("files")
    size = filtered.get("size")
    if not (isinstance(files, int) and isinstance(size, int)):
        return _CheckStep(label, status_code, "invalid filtered totals", False)
    # Every listed row has to be earning its place: a folder with a zero
    # rollup is the defect this projection replaced.
    empty_dirs = sum(1 for row in tree if row.get("type") == "dir" and not row.get("total_files"))
    fields = f"rows={len(tree)}; files={files}; size={size}; empty_dirs={empty_dirs}"
    return _CheckStep(label, status_code, fields, status_code == 200 and empty_dirs == 0)


def _recent_step(status_code: int, payload: Any) -> _CheckStep:
    if not isinstance(payload, dict):
        return _CheckStep("live filter", status_code, "invalid JSON envelope", False)
    files = payload.get("total_matching")
    index_status = payload.get("tally_cache_status")
    if not isinstance(files, int) or not isinstance(index_status, str):
        return _CheckStep("live filter", status_code, "invalid recent envelope", False)
    return _CheckStep("live filter", status_code, f"files={files}", status_code == 200)


def _read_json(response: Any) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


async def _run_navigation_scenario(
    app: ASGIApp,
    *,
    index_timeout_s: float = INDEX_READY_TIMEOUT_S,
) -> tuple[
    ApiResponse, ApiResponse, ApiResponse, IndexResult, ApiResponse, ApiResponse, ApiResponse
]:
    """Exercise the navigation routes while the background index is active."""

    async with InProcessClient(app, label="navigation API", logger=LOG) as client:
        initial = await client.get("/api/tree", params={"depth": "2"})
        live = await client.get("/api/recent", params={"window": "live"})
        cleared = await client.get("/api/tree", params={"depth": "2"})
        index_result = await wait_for_index(client, timeout_s=index_timeout_s)
        final = await client.get("/api/tree", params={"depth": "2"})
        # Rows and tallies travel separately now: a request carrying rows never
        # waits for the pass over every index entry that produces the summary.
        # The check wants both, so it asks both channels -- which is also what
        # the browser does. See explorations/performance-loop/experiments/exp-007.
        final_tallies = await client.get("/api/tree", params={"depth": "0"})
        # After the index is complete, so the projection is answering from the
        # whole tree rather than from whatever the walk had reached.
        filtered = await client.get("/api/tree", params={"depth": "2", "types": _FILTER_PROBE_TYPE})
    return initial, live, cleared, index_result, final, final_tallies, filtered


def run_api_check(
    root: Path,
    *,
    plugins_dir: list[Path] | None = None,
    log_level: str = "",
    index_timeout_s: float = INDEX_READY_TIMEOUT_S,
) -> None:
    """Run the browser's navigation request sequence without a browser."""

    load_dotenv_chain()
    apply_log_level(log_level)
    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise CLIError(f"{resolved} is not a directory")

    extra_plugin_dirs = resolve_extra_plugin_dirs(plugins_dir)
    os.environ["METABROWSER_PLUGINS_DIRS"] = os.pathsep.join(
        str(plugin_dir) for plugin_dir in extra_plugin_dirs
    )

    from metabrowser import server

    server._set_root_dir(resolved)
    initial, live, cleared, index_result, final, final_tallies, filtered = asyncio.run(
        _run_navigation_scenario(server.app, index_timeout_s=index_timeout_s)
    )

    steps_before_index = (
        _tree_probe_step("initial tree", initial.status_code, _read_json(initial)),
        _recent_step(live.status_code, _read_json(live)),
        _tree_probe_step("cleared filter", cleared.status_code, _read_json(cleared)),
    )
    final_payload = _read_json(final)
    tallies_payload = _read_json(final_tallies)
    if isinstance(final_payload, dict) and isinstance(tallies_payload, dict):
        final_payload = {
            **final_payload,
            "summary": tallies_payload.get("summary"),
        }
    final_step = _tree_step("final nav", final.status_code, final_payload)
    filtered_step = _filtered_step("filtered nav", filtered.status_code, _read_json(filtered))
    typer.echo(f"api check: {root}")
    typer.echo("scenario: nav-live-clear-filter")
    for step in steps_before_index:
        typer.echo(f"{step.label}: {step.status_code}; {step.fields}")
    typer.echo(f"index: {index_result.detail}")
    typer.echo(f"{final_step.label}: {final_step.status_code}; {final_step.fields}")
    typer.echo(f"{filtered_step.label}: {filtered_step.status_code}; {filtered_step.fields}")
    passed = index_result.completed and all(
        step.valid for step in (*steps_before_index, final_step, filtered_step)
    )
    typer.echo(f"result: {'pass' if passed else 'fail'}")
    if not passed:
        raise CLIError("navigation API check failed")
