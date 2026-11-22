"""Untrusted Markdown renders in the Markdown child, under a deadline, and never in a thread.

Every document rendered under the untrusted profile -- a pinned mirror's, a folder served
with ``--untrusted``, and a pull request's texts (``tests/test_github_pulls.py``) -- goes
to the child that ``diff/markdown_projection_worker.py`` runs. A render past the deadline
stops the child and is refused with a code, kept by the document's blob ID or a hash of
its text, so a reload is refused without rendering again; the next document starts a new
child. These tests pin the refusal, the kept verdict, the identity it is kept by, the
renders it does not stack, and what the child renders: plain code and the inert
allowlist. Timings are asserted only against costs minutes apart.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import kpress_adapter, server
from metabrowser.capabilities import DEFAULT_CAPABILITIES, Capabilities, set_capabilities
from metabrowser.diff import markdown_projection_worker as worker_module
from metabrowser.diff.markdown_projection_worker import (
    InertRender,
    InertRenderRefused,
    ProjectionWorker,
)
from metabrowser.git.tree_source import GitPath
from tests.git_pin_harness import fast_import_store, pinned_client
from tests.github_pull_fixture import allowlist_violations
from tests.required_tools import needs_git
from tests.test_inert_html import HOSTILE_README

# The review of mb-273l timed 1,000 unpaired `[` before 239 KB of `%` at 23.1 s, and the
# cost is linear in the run of `%` (about 90 µs a byte at load average 11, 2026-11-17):
# this one would hold a thread for minutes, far past the deadline and its margin below.
PATHOLOGICAL = "[" * 1000 + "%" * (2 * 1024 * 1024)
# The same shape at the pull request text's bound takes seconds: past a shortened deadline.
SLOW = "[" * 100 + "%" * (60 * 1024)
SLOW_WIRE = GitPath.from_segments(b"slow.md").to_wire()
README_WIRE = GitPath.from_segments(b"README.md").to_wire()
# What the refused render may take beyond the deadline and the start it waits for: the
# frame's encoding, the kill, and a loaded machine. The render itself would take minutes.
MARGIN_S = 20.0


@pytest.fixture
def untrusted() -> Iterator[None]:
    set_capabilities(Capabilities(active_content=False, mutations=False))
    try:
        yield
    finally:
        set_capabilities(DEFAULT_CAPABILITIES)


def _request(text: str, identity: str, **fields: Any) -> InertRender:
    return InertRender(
        source_text=text,
        source_path=fields.pop("source_path", "doc.md"),
        identity=identity,
        kind="markdown",
        view="document",
        ext=".md",
        mtime_hash=fields.pop("mtime_hash", identity),
        size=len(text.encode()),
        **fields,
    )


def _count_exchanges(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """How many render exchanges reach a child: a kept refusal makes none."""

    exchanges: list[int] = []
    exchange = ProjectionWorker._exchange_render  # pyright: ignore[reportPrivateUsage]

    async def counted(
        self: ProjectionWorker, process: asyncio.subprocess.Process, frame: bytes
    ) -> object:
        exchanges.append(process.pid)
        return await exchange(self, process, frame)

    monkeypatch.setattr(ProjectionWorker, "_exchange_render", counted)
    return exchanges


@needs_git
def test_a_pathological_pinned_document_is_refused_at_the_deadline_while_the_server_answers(
    tmp_path: Path, untrusted: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    exchanges = _count_exchanges(monkeypatch)
    store, commit = fast_import_store(
        tmp_path,
        {b"README.md": b"# Fine\n\nA *short* readme.\n", b"slow.md": PATHOLOGICAL.encode()},
    )

    async def run() -> dict[str, Any]:
        async with pinned_client(store, commit) as (client, _subject):
            loop = asyncio.get_running_loop()
            began = loop.time()
            render = asyncio.create_task(
                client.get("/api/kpress/render", params={"path": SLOW_WIRE, "view": "document"})
            )
            # Other requests while the child renders: each answers before the render does.
            answered: list[tuple[int, bool]] = []
            while not render.done():
                status = await client.get("/api/source/status")
                answered.append((status.status_code, render.done()))
                await asyncio.sleep(0.05)
            refused = await render
            elapsed = loop.time() - began
            rendered_before_reload = len(exchanges)
            # A reload is refused by the kept verdict, and renders nothing.
            again = await client.get(
                "/api/kpress/render", params={"path": SLOW_WIRE, "view": "document", "toc": "off"}
            )
            rendered_after_reload = len(exchanges)
            fine = await client.get(
                "/api/kpress/render", params={"path": README_WIRE, "view": "document"}
            )
            return {
                "answered": answered,
                "refused": (refused.status_code, refused.json()),
                "elapsed": elapsed,
                "again": (again.status_code, again.json()),
                "rendered_by_reload": rendered_after_reload - rendered_before_reload,
                "fine": (fine.status_code, fine.json()),
            }

    result = asyncio.run(run())
    status, body = result["refused"]
    assert status == 422
    assert body == {
        "type": "kpress_render_refused",
        "code": "render_deadline",
        "error": "Rendering took longer than 5 seconds, so it was stopped",
        "deadline_ms": worker_module.INERT_RENDER_DEADLINE_MS,
        "remembered": False,
        "path": SLOW_WIRE,
    }
    limit = worker_module._RENDER_DEADLINE_S + worker_module._START_WAIT_S + MARGIN_S  # pyright: ignore[reportPrivateUsage]
    assert result["elapsed"] < limit
    answered = result["answered"]
    assert all(code == 200 for code, _done in answered)
    # The last may have answered just after the render did; the rest answered while it ran.
    assert sum(1 for _code, done in answered if not done) >= 3, answered
    assert result["again"] == (422, {**body, "remembered": True})
    assert result["rendered_by_reload"] == 0, "the reload rendered nothing"
    status, fine = result["fine"]
    assert status == 200 and fine["inert"] is True
    assert '<h1 id="user-content-fine">Fine</h1>' in fine["html"]


def test_an_untrusted_folder_keeps_the_refusal_by_the_documents_text(
    tmp_path: Path, untrusted: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker_module, "_RENDER_DEADLINE_S", 0.2)
    exchanges = _count_exchanges(monkeypatch)
    (tmp_path / "slow.md").write_text(SLOW, encoding="utf-8")
    (tmp_path / "copy.md").write_text(SLOW, encoding="utf-8")
    server._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]
    with TestClient(server.app) as client:
        first = client.get("/api/kpress/render", params={"path": "slow.md", "view": "document"})
        # Another file with the same text is the same document: refused without a render.
        copy = client.get("/api/kpress/render", params={"path": "copy.md", "view": "document"})
        rendered_before_sent = len(exchanges)
        # A page's own text in its place is another document, and renders.
        sent = client.post(
            "/api/kpress/render",
            json={"path": "slow.md", "view": "document", "source_text": "# Sent\n"},
        )
    assert first.status_code == 422
    assert first.json()["code"] == "render_deadline"
    assert first.json()["deadline_ms"] == 200
    assert first.json()["error"] == "Rendering took longer than 0.2 seconds, so it was stopped"
    assert copy.status_code == 422
    assert first.json()["remembered"] is False
    assert copy.json() == {**first.json(), "path": "copy.md", "remembered": True}
    assert rendered_before_sent == 1, "the copy rendered nothing"
    assert sent.status_code == 200
    assert '<h1 id="user-content-sent">Sent</h1>' in sent.json()["html"]


def test_identical_requests_in_flight_share_one_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker_module, "_RENDER_DEADLINE_S", 0.3)
    kills: list[int] = []
    kill = ProjectionWorker._kill  # pyright: ignore[reportPrivateUsage]

    def counted(self: ProjectionWorker, process: asyncio.subprocess.Process) -> None:
        if process.returncode is None:
            kills.append(process.pid)
        kill(self, process)

    monkeypatch.setattr(ProjectionWorker, "_kill", counted)

    async def run() -> list[BaseException | dict[str, Any]]:
        worker = ProjectionWorker()
        try:
            request = _request(SLOW, "sha256:slow")
            return await asyncio.gather(
                *(worker.render_inert(request) for _ in range(3)), return_exceptions=True
            )
        finally:
            await worker.aclose()

    answers = asyncio.run(run())
    assert [type(answer) for answer in answers] == [InertRenderRefused] * 3
    assert {getattr(answer, "code", None) for answer in answers} == {"render_deadline"}
    assert len(kills) == 1, "three reloads of one document cost one render and one kill"


def test_a_render_waits_for_a_child_still_starting_rather_than_replacing_it() -> None:
    # A served pin starts the child as it attaches, so its first document can arrive
    # while that child is spawned but not yet ready; the render waits for that child.
    def spawned(worker: ProjectionWorker) -> asyncio.subprocess.Process | None:
        return worker._process  # pyright: ignore[reportPrivateUsage]

    async def run() -> tuple[int, int | None, dict[str, Any]]:
        worker = ProjectionWorker()
        try:
            worker.start(renders=True)
            # Polled, at most 30 s: the spawn sets the process before its ready frame.
            for _ in range(6000):
                if spawned(worker) is not None:
                    break
                await asyncio.sleep(0.005)
            starting = spawned(worker)
            assert starting is not None and not worker.ready, "spawned, not yet ready"
            rendered = await worker.render_inert(_request("# Waited\n", "sha256:waited"))
            serving = spawned(worker)
            return starting.pid, None if serving is None else serving.pid, rendered
        finally:
            await worker.aclose()

    starting, serving, rendered = asyncio.run(run())
    assert serving == starting
    assert '<h1 id="user-content-waited">Waited</h1>' in rendered["html"]


def test_closing_waits_for_every_child_it_stopped_to_exit() -> None:
    # A child reaped after its event loop closed makes asyncio log on standard error,
    # which a one-shot command printed; closing waits for the exits on the loop instead.
    def spawned(worker: ProjectionWorker) -> asyncio.subprocess.Process | None:
        return worker._process  # pyright: ignore[reportPrivateUsage]

    async def run() -> list[asyncio.subprocess.Process]:
        worker = ProjectionWorker()
        children: list[asyncio.subprocess.Process] = []
        try:
            for text in ("# One\n", "# Two\n"):
                await worker.render_inert(_request(text, f"sha256:{text}"))
                child = spawned(worker)
                assert child is not None and child not in children
                children.append(child)
                if len(children) == 1:
                    # Stopped as a deadline stops it; the next render starts another.
                    worker._kill(child)  # pyright: ignore[reportPrivateUsage]
        finally:
            await worker.aclose()
        return children

    children = asyncio.run(run())
    assert len(children) == 2
    assert [child.returncode is not None for child in children] == [True, True]


def test_closing_waits_for_a_replacement_spawn_to_finish_cancelling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run() -> None:
        spawn_began = asyncio.Event()
        spawn_cleaned_up = asyncio.Event()

        async def spawn(*_args: str, **_kwargs: Any) -> asyncio.subprocess.Process:
            # Pause before asyncio returns the Process to the worker.
            spawn_began.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                await asyncio.sleep(0)
                spawn_cleaned_up.set()
                raise
            raise AssertionError("expected the replacement spawn to be cancelled")

        worker = ProjectionWorker()
        try:
            worker.start(renders=True)
            assert await worker.started()
            child = worker._process  # pyright: ignore[reportPrivateUsage]
            assert child is not None
            worker._kill(child)  # pyright: ignore[reportPrivateUsage]
            await child.wait()
            monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
            worker._replace()  # pyright: ignore[reportPrivateUsage]
            await asyncio.wait_for(spawn_began.wait(), timeout=5)
            assert worker._process is None  # pyright: ignore[reportPrivateUsage]
        finally:
            await worker.aclose()
        assert spawn_cleaned_up.is_set()

    asyncio.run(run())


def test_the_child_renders_what_the_in_process_inert_render_would() -> None:
    async def run() -> dict[str, Any]:
        worker = ProjectionWorker()
        try:
            return await worker.render_inert(_request(HOSTILE_README, "sha256:hostile"))
        finally:
            await worker.aclose()

    rendered = asyncio.run(run())
    expected = kpress_adapter.inert_render(
        kpress_adapter.render_kpress_view(
            source_text=HOSTILE_README,
            source_path="doc.md",
            kind="markdown",
            view="document",
            ext=".md",
            mtime_hash="in-process",
            size=len(HOSTILE_README.encode()),
            plain_code=True,
        )
    )
    assert rendered["inert"] is True
    assert rendered["html"] == expected["html"]
    assert rendered["assets"] == expected["assets"]
    # What the sanitizer removed stays in the child (review C of #527, C3).
    assert set(expected) - set(rendered) == {"sanitizer_diagnostics"}
    assert allowlist_violations(rendered["html"], images=True) == []


def test_inert_renders_never_run_in_the_server(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(**_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("an untrusted document rendered in the server's interpreter")

    monkeypatch.setattr(kpress_adapter, "render_kpress_view", refuse)
    monkeypatch.setattr(kpress_adapter, "inert_render", refuse)
    # A cold child: the render waits for it rather than running in a thread meanwhile.
    fence = "# Code\n\n```console\n$ ls -la\n```\n"

    async def run() -> tuple[dict[str, Any], dict[str, Any]]:
        worker = ProjectionWorker()
        try:
            document = await worker.render_inert(_request(fence, "sha256:fence"))
            text = await worker.render_inert(
                _request(fence, "sha256:fence", link_base="https://github.com/octo/demo/pull/7")
            )
            return document, text
        finally:
            await worker.aclose()

    document, text = asyncio.run(run())
    # Plain code: escaped, with none of the spans highlighting would add for the allowlist
    # to drop.
    assert "<pre><code>$ ls -la\n</code></pre>" in document["html"]
    assert "<span" not in document["html"]
    assert set(text) == {"html"}
    assert "<pre><code>$ ls -la\n</code></pre>" in text["html"]


def test_kpress_errors_cross_the_child_as_they_were_raised() -> None:
    async def run() -> None:
        worker = ProjectionWorker()
        try:
            await worker.render_inert(_request("# x\n", "sha256:x", profile="no-such-profile"))
        finally:
            await worker.aclose()

    with pytest.raises(kpress_adapter.KPressInvalidRequestError):
        asyncio.run(run())


# Says it is ready, then exits at the first request without answering.
_EXITS = (
    "import sys, json\n"
    "body = json.dumps({'ready': True}).encode()\n"
    "sys.stdout.buffer.write(len(body).to_bytes(4, 'big') + body)\n"
    "sys.stdout.buffer.flush()\n"
    "sys.stdin.buffer.read(4)\n"
)


def test_a_child_that_exits_mid_render_refuses_that_document_and_keeps_it() -> None:
    async def run() -> tuple[str, InertRenderRefused | None]:
        worker = ProjectionWorker(command=(sys.executable, "-c", _EXITS))
        request = _request("# x\n", "sha256:exits")
        try:
            with pytest.raises(InertRenderRefused) as refused:
                await worker.render_inert(request)
            return refused.value.code, worker.refusal(request)
        finally:
            await worker.aclose()

    code, kept = asyncio.run(run())
    assert code == "renderer_exited"
    assert kept is not None and kept.code == "renderer_exited"
    assert kept.http_status == 422


def test_a_child_that_cannot_start_is_refused_as_unavailable_and_not_kept(
    tmp_path: Path,
) -> None:
    async def run() -> tuple[InertRenderRefused, InertRenderRefused | None]:
        worker = ProjectionWorker(command=(str(tmp_path / "absent-python"),))
        request = _request("# x\n", "sha256:absent")
        with pytest.raises(InertRenderRefused) as refused:
            await worker.render_inert(request)
        return refused.value, worker.refusal(request)

    refused, kept = asyncio.run(run())
    assert refused.code == "renderer_unavailable"
    assert refused.http_status == 503
    assert refused.payload()["remembered"] is False
    assert kept is None, "a reload tries again"


def test_the_server_imports_no_renderer_for_the_child_it_manages() -> None:
    # The worker module is imported by the server; the projection module it runs in the
    # child imports KPress and Pygments, which the server's start must not pay for.
    code = (
        "import json, sys\n"
        "import metabrowser.server\n"
        "names = ('kpress', 'pygments', 'metabrowser.diff.markdown_projection',"
        " 'metabrowser.inert_html')\n"
        "print(json.dumps({name: name in sys.modules for name in names}))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code], check=True, capture_output=True, text=True
    )
    assert json.loads(completed.stdout.strip().splitlines()[-1]) == {
        "kpress": False,
        "pygments": False,
        "metabrowser.diff.markdown_projection": False,
        "metabrowser.inert_html": False,
    }
