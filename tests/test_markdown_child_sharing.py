"""One hostile text must not stall every other render and projection on the server.

The Markdown child renders one document at a time for every route that renders untrusted
Markdown, and projects Markdown diffs too (``diff/markdown_projection_worker.py``, "One
child for both jobs"). These tests pin what keeps that sharing safe: an abandoned render
is cancelled and never holds the queue, distinct renders in flight are bounded, a
projection never waits behind or fails with an inert render, a refusal is kept only for
what the child did with the document and lapses, failed starts cool off, and the child
leads its own process group yet ends with the server.

Most run against ``tests/markdown_child_standin.py``, a stand-in that speaks the child's
frames and answers in milliseconds as each text says, so a deadline, a cancellation, or a
crash costs about a second. Timings are asserted only against costs seconds apart.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Generator, Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import kpress_adapter, server
from metabrowser.capabilities import DEFAULT_CAPABILITIES, Capabilities, set_capabilities
from metabrowser.diff import markdown_projection_worker as worker_module
from metabrowser.diff.markdown_projection import prepare_markdown_diff
from metabrowser.diff.markdown_projection_worker import (
    InertRender,
    InertRenderRefused,
    ProjectionWorker,
    shared_worker,
)
from metabrowser.frontmatter_yaml import (
    FRONTMATTER_ERROR_MESSAGE,
    FrontmatterError,
    load_frontmatter_yaml,
)
from metabrowser.git.tree_source import GitPath
from tests.git_pin_harness import fast_import_store, pinned_client
from tests.process_group import group_is_live
from tests.required_tools import needs_git
from tests.test_markdown_diff_projection import (
    _patch,  # pyright: ignore[reportPrivateUsage]
)

STANDIN = Path(__file__).with_name("markdown_child_standin.py")
OLD = b"# Guide\n\nSee [the old page](old.md) today.\n"
NEW = b"# Guide\n\nSee [the new page](new.md) now.\n"
# Far past every deadline these tests set: a render of it ends only by a kill.
FOREVER = "sleep 600"


def _standin(*args: str) -> tuple[str, ...]:
    return (sys.executable, "-I", str(STANDIN), *args)


def _request(text: str, identity: str | None = None, **fields: Any) -> InertRender:
    name = identity or f"sha256:{text}"
    return InertRender(
        source_text=text,
        source_path=fields.pop("source_path", "doc.md"),
        identity=name,
        kind="markdown",
        view="document",
        ext=".md",
        mtime_hash=name,
        size=len(text.encode()),
        **fields,
    )


def _child(worker: ProjectionWorker) -> asyncio.subprocess.Process | None:
    return worker._process  # pyright: ignore[reportPrivateUsage]


def _alive(pid: int) -> bool:
    """Whether *pid* is still a process, a zombie included: once the loop that started the
    child has closed, ``not _alive`` says that loop both stopped and reaped it."""

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


async def _ready(worker: ProjectionWorker) -> asyncio.subprocess.Process:
    worker.start(renders=True)
    async with asyncio.timeout(30):
        assert await worker.started()
    child = _child(worker)
    assert child is not None
    return child


async def _rendering(worker: ProjectionWorker, text: str) -> asyncio.Task[dict[str, Any]]:
    """A render of *text* that the child has begun."""

    task = asyncio.create_task(worker.render_inert(_request(text)))
    for _ in range(600):
        lock = worker._lock  # pyright: ignore[reportPrivateUsage]
        if lock is not None and lock.rendering and _child(worker) is not None:
            break
        await asyncio.sleep(0.01)
    await asyncio.sleep(0.1)
    return task


@pytest.fixture
def processes(monkeypatch: pytest.MonkeyPatch) -> None:
    # Projections use the child on every build here, as the worker's own tests do.
    monkeypatch.setattr(worker_module, "_gil_enabled", lambda: True)


def test_a_render_nobody_waits_for_is_cancelled_and_stops_the_child_with_no_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker_module, "_RENDER_DEADLINE_S", 30.0)

    async def run() -> tuple[int, bool, InertRenderRefused | None, float, dict[str, Any]]:
        worker = ProjectionWorker(command=_standin())
        try:
            await _ready(worker)
            abandoned = await _rendering(worker, FOREVER)
            child = _child(worker)
            assert child is not None
            abandoned.cancel()
            with pytest.raises(asyncio.CancelledError):
                await abandoned
            async with asyncio.timeout(10):
                await child.wait()
            began = time.monotonic()
            quick = await worker.render_inert(_request("echo quick"))
            return (
                child.pid,
                bool(worker._flights),  # pyright: ignore[reportPrivateUsage]
                worker.refusal(_request(FOREVER)),
                time.monotonic() - began,
                quick,
            )
        finally:
            await worker.aclose()

    pid, flights, kept, waited, quick = asyncio.run(run())
    assert not _alive(pid), "the child rendering the abandoned document was stopped"
    assert kept is None, "nobody saw a deadline, so nothing is kept"
    assert flights is False
    assert quick["html"] == "<p>echo quick</p>"
    assert waited < 10, "the next document does not wait for the abandoned render"


def test_queued_renders_whose_requests_left_never_reach_the_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Four documents that would each hold the child for its whole deadline; their requests
    # all go away, and an ordinary document asked next waits for none of them.
    monkeypatch.setattr(worker_module, "_RENDER_DEADLINE_S", 20.0)

    async def run() -> tuple[float, dict[str, Any], int]:
        worker = ProjectionWorker(command=_standin())
        try:
            await _ready(worker)
            running = await _rendering(worker, FOREVER)
            queued = [
                asyncio.create_task(worker.render_inert(_request(f"sleep 60\n{n}")))
                for n in range(3)
            ]
            await asyncio.sleep(0.2)
            for task in (*queued, running):
                task.cancel()
            await asyncio.gather(*queued, running, return_exceptions=True)
            left = len(worker._flights)  # pyright: ignore[reportPrivateUsage]
            began = time.monotonic()
            quick = await worker.render_inert(_request("echo next"))
            return time.monotonic() - began, quick, left
        finally:
            await worker.aclose()

    waited, quick, left = asyncio.run(run())
    assert left == 0
    assert quick["html"] == "<p>echo next</p>"
    assert waited < 10, "four abandoned renders would have held it four deadlines"


def test_past_the_bound_a_distinct_render_is_refused_busy_and_not_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker_module, "_RENDER_DEADLINE_S", 30.0)

    async def run() -> tuple[InertRenderRefused, InertRenderRefused | None, bool]:
        worker = ProjectionWorker(command=_standin())
        try:
            await _ready(worker)
            held = [
                asyncio.create_task(worker.render_inert(_request(f"sleep 60\n{n}")))
                for n in range(worker_module._MAX_RENDERS)  # pyright: ignore[reportPrivateUsage]
            ]
            await asyncio.sleep(0.2)
            busy = _request("echo one too many")
            with pytest.raises(InertRenderRefused) as refused:
                await worker.render_inert(busy)
            # A request identical to one in flight joins it rather than counting again.
            joined = asyncio.create_task(worker.render_inert(_request("sleep 60\n0")))
            await asyncio.sleep(0.1)
            joins = not joined.done()
            for task in (*held, joined):
                task.cancel()
            await asyncio.gather(*held, joined, return_exceptions=True)
            return refused.value, worker.refusal(busy), joins
        finally:
            await worker.aclose()

    refused, kept, joins = asyncio.run(run())
    assert refused.code == "renderer_busy"
    assert refused.http_status == 503
    assert refused.payload()["remembered"] is False
    assert refused.payload()["error"] == "The document renderer is busy with other documents"
    assert kept is None, "a busy refusal is not kept: a reload tries again"
    assert joins


@pytest.mark.usefixtures("processes")
def test_a_projection_asked_while_a_render_holds_the_child_projects_at_once_and_correctly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Review A's A2: a projection queued behind a render that hit its deadline was
    # answered `unsupported`, which the rendered-diff route then kept.
    monkeypatch.setattr(worker_module, "_RENDER_DEADLINE_S", 1.0)
    patch = _patch(OLD, NEW)
    expected = prepare_markdown_diff(old=OLD, new=NEW, patch=patch, namespace="n")

    async def run() -> tuple[list[Any], float, BaseException | dict[str, Any]]:
        worker = ProjectionWorker(command=_standin())
        try:
            await _ready(worker)
            slow = await _rendering(worker, FOREVER)
            began = time.monotonic()
            answers = [
                await worker.prepare(old=OLD, new=NEW, patch=patch, namespace="n") for _ in range(3)
            ]
            waited = time.monotonic() - began
            outcome: BaseException | dict[str, Any]
            try:
                outcome = await slow
            except InertRenderRefused as refused:
                outcome = refused
            # And once the render's child is gone, before the next is ready.
            answers.append(await worker.prepare(old=OLD, new=NEW, patch=patch, namespace="n"))
            return answers, waited, outcome
        finally:
            await worker.aclose()

    answers, waited, outcome = asyncio.run(run())
    # The stand-in answers a projection with no blocks: these are the real projection,
    # from the thread, so none of them waited for or met the render's child.
    assert answers == [expected] * 4
    assert waited < 1.0, "no projection waited for the render's deadline"
    assert isinstance(outcome, InertRenderRefused) and outcome.code == "render_deadline"


def test_waiting_projections_take_the_child_before_waiting_renders() -> None:
    lock = worker_module._ChildLock()  # pyright: ignore[reportPrivateUsage]
    order: list[str] = []

    async def take(name: str, kind: Any, hold_s: float = 0.0) -> None:
        async with lock.hold(kind):
            order.append(name)
            await asyncio.sleep(hold_s)

    async def run() -> None:
        first = asyncio.create_task(take("projection 1", "projection", 0.05))
        await asyncio.sleep(0)
        render = asyncio.create_task(take("render", "render"))
        cancelled = asyncio.create_task(take("cancelled render", "render"))
        await asyncio.sleep(0)
        later = asyncio.create_task(take("projection 2", "projection"))
        await asyncio.sleep(0)
        cancelled.cancel()
        await asyncio.gather(first, render, later, cancelled, return_exceptions=True)
        assert lock.holder is None

    asyncio.run(run())
    assert order == ["projection 1", "projection 2", "render"]


def test_a_child_killed_from_outside_is_not_charged_to_the_next_document() -> None:
    # Review D's D3: the write to a child already dead was blamed on the document.
    async def run() -> tuple[dict[str, Any], InertRenderRefused | None]:
        worker = ProjectionWorker(command=_standin())
        try:
            child = await _ready(worker)
            os.kill(child.pid, signal.SIGKILL)
            request = _request("echo after the kill")
            return await worker.render_inert(request), worker.refusal(request)
        finally:
            await worker.aclose()

    rendered, kept = asyncio.run(run())
    assert rendered["html"] == "<p>echo after the kill</p>"
    assert kept is None


@pytest.mark.parametrize("held_s", [0.9, 0.42], ids=["late-400ms", "late-20ms"])
def test_an_answer_in_the_pipe_when_a_late_loop_runs_the_deadline_is_accepted(
    held_s: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Review D's D4: the child answers at 0.2 s, the server's loop is held from 0.1 s to
    # past the 0.5 s deadline, which runs late with the whole answer waiting: about 0.4 s
    # late, and about 20 ms late, inside the margin past which the pipe gets its longer
    # look (review E's E3).
    monkeypatch.setattr(worker_module, "_RENDER_DEADLINE_S", 0.5)

    async def run() -> tuple[dict[str, Any], InertRenderRefused | None]:
        worker = ProjectionWorker(command=_standin())
        try:
            await _ready(worker)
            request = _request("sleep 0.2")
            asyncio.get_running_loop().call_later(0.1, time.sleep, held_s)
            return await worker.render_inert(request), worker.refusal(request)
        finally:
            await worker.aclose()

    rendered, kept = asyncio.run(run())
    assert rendered["html"] == "<p>sleep 0.2</p>"
    assert kept is None


def test_a_refusal_is_kept_for_its_time_and_then_rendered_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker_module, "_RENDER_DEADLINE_S", 0.3)
    monkeypatch.setattr(worker_module, "_VERDICT_TTL_S", 1.0)

    async def run() -> tuple[
        InertRenderRefused, InertRenderRefused | None, InertRenderRefused | None
    ]:
        worker = ProjectionWorker(command=_standin())
        request = _request("sleep 5")
        try:
            await _ready(worker)
            with pytest.raises(InertRenderRefused) as first:
                await worker.render_inert(request)
            kept = worker.refusal(request)
            await asyncio.sleep(1.2)
            return first.value, kept, worker.refusal(request)
        finally:
            await worker.aclose()

    first, kept, lapsed = asyncio.run(run())
    assert first.code == "render_deadline" and first.payload()["remembered"] is False
    assert kept is not None and kept.code == "render_deadline"
    assert kept.payload()["remembered"] is True
    assert lapsed is None, "a kept refusal lapses, so a load spike does not hide a document"


def test_a_killed_render_starts_its_replacement_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker_module, "_RENDER_DEADLINE_S", 0.3)

    async def run() -> tuple[int, bool, int]:
        worker = ProjectionWorker(command=_standin())
        try:
            killed = await _ready(worker)
            with pytest.raises(InertRenderRefused):
                await worker.render_inert(_request("sleep 5"))
            replacing = worker._starting is not None  # pyright: ignore[reportPrivateUsage]
            replacement = await _ready(worker)
            return killed.pid, replacing, replacement.pid
        finally:
            await worker.aclose()

    killed, replacing, replacement = asyncio.run(run())
    assert replacing, "the next document does not wait for a start"
    assert replacement != killed


def test_a_start_slower_than_the_render_deadline_still_renders() -> None:
    # mb-xmte: the start wait was the render deadline's default, so a child that took
    # longer than that to start, as one does at a load average of 300 to 400, had its
    # document refused as unavailable. The stand-in is ready half a second past it.
    slow_start = worker_module.INERT_RENDER_DEADLINE_MS / 1000 + 0.5
    assert slow_start < worker_module._START_WAIT_S  # pyright: ignore[reportPrivateUsage]

    async def run() -> dict[str, Any]:
        worker = ProjectionWorker(command=_standin("--slow-start", str(slow_start)))
        try:
            return await worker.render_inert(_request("echo slow start"))
        finally:
            await worker.aclose()

    assert asyncio.run(run())["html"] == "<p>echo slow start</p>"


def test_a_start_past_its_wait_is_refused_unkept_and_goes_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker_module, "_START_WAIT_S", 0.3)

    async def run() -> tuple[str, bool, dict[str, Any]]:
        worker = ProjectionWorker(command=_standin("--slow-start", "2"))
        try:
            with pytest.raises(InertRenderRefused) as refused:
                await worker.render_inert(_request("echo x"))
            first = _child(worker)
            # The same start goes on, and the same document renders once it is ready.
            child = await _ready(worker)
            return (
                refused.value.code,
                child is first and not refused.value.remembered,
                await worker.render_inert(_request("echo x")),
            )
        finally:
            await worker.aclose()

    code, same_start, rendered = asyncio.run(run())
    assert code == "renderer_unavailable"
    assert same_start, "the refusal neither replaced the start nor was kept"
    assert rendered["html"] == "<p>echo x</p>"


@pytest.mark.parametrize("deadline_ms", ["250", "600000"])
def test_the_render_deadline_does_not_move_the_start_wait(deadline_ms: str) -> None:
    # A start costs the same whatever a document may take, so the setting that bounds a
    # render, shortened or lengthened, leaves the wait for a start where it was measured.
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import metabrowser.diff.markdown_projection_worker as worker;"
            "print(worker._RENDER_DEADLINE_S, worker._START_WAIT_S)",
        ],
        env={**os.environ, "METABROWSER_INERT_RENDER_DEADLINE_MS": deadline_ms},
        capture_output=True,
        text=True,
        check=True,
    )
    deadline, start_wait = (float(each) for each in completed.stdout.split())
    assert deadline == int(deadline_ms) / 1000
    assert start_wait == worker_module._START_WAIT_S  # pyright: ignore[reportPrivateUsage]


def test_three_failed_starts_cool_off_then_try_again_and_say_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Review A's A3: three failed starts used to refuse every document until a restart.
    monkeypatch.setattr(worker_module, "_START_COOL_OFF_S", 1.0)
    monkeypatch.setattr(worker_module, "_START_WAIT_S", 2.0)

    async def run() -> tuple[list[str], int, str, dict[str, Any]]:
        worker = ProjectionWorker(command=(str(tmp_path / "absent-python"),))
        codes: list[str] = []
        try:
            for _ in range(2):
                with pytest.raises(InertRenderRefused) as refused:
                    await worker.render_inert(_request("echo x"))
                codes.append(refused.value.code)
            starts = worker._starts  # pyright: ignore[reportPrivateUsage]
            # The cause passes; within the cool-off the worker does not try yet.
            worker._command = _standin()  # pyright: ignore[reportPrivateUsage]
            with pytest.raises(InertRenderRefused) as cooling:
                await worker.render_inert(_request("echo y"))
            await asyncio.sleep(1.2)
            return codes, starts, cooling.value.code, await worker.render_inert(_request("echo z"))
        finally:
            await worker.aclose()

    with caplog.at_level(logging.WARNING, logger=worker_module.__name__):
        codes, starts, cooling, rendered = asyncio.run(run())
    assert codes == ["renderer_unavailable"] * 2
    assert starts == 3
    assert cooling == "renderer_unavailable"
    assert rendered["html"] == "<p>echo z</p>", "after the cool-off a start is tried again"
    said = [record.getMessage() for record in caplog.records]
    assert sum("did not start: it could not be spawned" in line for line in said) == 1, said
    assert any("failed 3 starts in a row" in line for line in said), said


def test_closing_ends_queued_renders_and_starts_no_child_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Review B's B6 and review D's D2: renders queued at the close ran on a child started
    # after it, beside one another.
    monkeypatch.setattr(worker_module, "_RENDER_DEADLINE_S", 30.0)

    async def run() -> tuple[list[object], int, bool]:
        worker = ProjectionWorker(command=_standin())
        running = await _rendering(worker, FOREVER)
        child = _child(worker)
        assert child is not None
        queued = [
            asyncio.create_task(worker.render_inert(_request(f"sleep 60\n{n}"))) for n in range(2)
        ]
        await asyncio.sleep(0.1)
        await worker.aclose()
        answers = await asyncio.gather(running, *queued, return_exceptions=True)
        await asyncio.sleep(0.3)
        started_after = _child(worker) is not None or worker._starting is not None  # pyright: ignore[reportPrivateUsage]
        return [getattr(answer, "code", answer) for answer in answers], child.pid, started_after

    codes, pid, started_after = asyncio.run(run())
    assert codes == ["renderer_unavailable"] * 3
    assert not _alive(pid)
    assert started_after is False


@pytest.mark.parametrize("stopped", [True, False], ids=["stopped", "running"])
def test_closing_on_a_later_loop_does_not_wait_for_an_earlier_loops_child(stopped: bool) -> None:
    # Review D's D7: the close awaited a child that belonged to another loop, after a stop
    # on that loop and with the child still running alike.
    worker = ProjectionWorker(command=_standin())

    async def first() -> int:
        child = await _ready(worker)
        assert os.getpgid(child.pid) == child.pid, "the child leads its own group"
        if stopped:
            worker._kill(child)  # pyright: ignore[reportPrivateUsage]
            worker.stop()
        return child.pid

    async def second() -> None:
        await worker.aclose()

    pid = asyncio.run(first())
    asyncio.run(second())
    # Only the loop that started the child waits for it, and that loop has closed: under a
    # pidfd child watcher (Linux, Python 3.12 and later) the killed child stays a zombie
    # until CPython collects its Popen. `os.kill(pid, 0)` answers for a zombie as for a
    # live process, so the look is for a member of its group still running.
    deadline = time.monotonic() + 10
    while group_is_live(pid, deadline) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not group_is_live(pid, deadline), "the earlier loop's child was stopped all the same"


def test_an_exchange_past_the_idle_limit_does_not_run_the_idle_stop_every_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Review D's D5: the idle timer re-armed at zero delay while a render held the child.
    monkeypatch.setattr(worker_module, "_IDLE_S", 0.2)
    calls = 0
    idle = ProjectionWorker._idle  # pyright: ignore[reportPrivateUsage]

    def counted(self: ProjectionWorker) -> None:
        nonlocal calls
        calls += 1
        idle(self)

    monkeypatch.setattr(ProjectionWorker, "_idle", counted)

    async def run() -> dict[str, Any]:
        worker = ProjectionWorker(command=_standin())
        try:
            await _ready(worker)
            return await worker.render_inert(_request("sleep 1.5"))
        finally:
            await worker.aclose()

    assert asyncio.run(run())["html"] == "<p>sleep 1.5</p>"
    assert calls <= 4, calls


def test_a_refusal_nobody_waits_for_reports_nothing_to_the_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Review D's D6: on Python 3.14 a refused render with a cancelled waiter was logged
    # as an error through `asyncio.shield`.
    monkeypatch.setattr(worker_module, "_RENDER_DEADLINE_S", 0.4)
    reported: list[dict[str, Any]] = []

    async def run() -> object:
        asyncio.get_running_loop().set_exception_handler(
            lambda _loop, context: reported.append(context)
        )
        worker = ProjectionWorker(command=_standin())
        try:
            await _ready(worker)
            request = _request("sleep 5")
            left = asyncio.create_task(worker.render_inert(request))
            stays = asyncio.create_task(worker.render_inert(request))
            await asyncio.sleep(0.1)
            left.cancel()
            answers = await asyncio.gather(left, stays, return_exceptions=True)
            await asyncio.sleep(0.1)
            return getattr(answers[1], "code", answers[1])
        finally:
            await worker.aclose()

    assert asyncio.run(run()) == "render_deadline"
    assert reported == []


def test_kpress_errors_and_wrong_answers_cross_the_child_as_they_should() -> None:
    # Review D's D9 and review B's B7.
    async def run() -> dict[str, object]:
        worker = ProjectionWorker(command=_standin())
        outcomes: dict[str, object] = {}
        try:
            for text in ("error", "invalid", "shapeless", "garbage"):
                request = _request(text)
                try:
                    await worker.render_inert(request)
                except Exception as exc:  # which one is the point
                    kept = worker.refusal(request)
                    outcomes[text] = (
                        type(exc).__name__,
                        getattr(exc, "code", str(exc)),
                        kept and kept.code,
                    )
            # The child serves on after a KPress error; a wrong answer stopped it.
            outcomes["after"] = (await worker.render_inert(_request("echo after")))["html"]
        finally:
            await worker.aclose()
        return outcomes

    assert asyncio.run(run()) == {
        "error": ("KPressRenderError", "boom", None),
        "invalid": ("KPressInvalidRequestError", "no such profile", None),
        "shapeless": ("InertRenderRefused", "renderer_exited", "renderer_exited"),
        "garbage": ("InertRenderRefused", "renderer_exited", "renderer_exited"),
        "after": "<p>echo after</p>",
    }


@pytest.fixture
def untrusted() -> Iterator[None]:
    set_capabilities(Capabilities(active_content=False, mutations=False))
    try:
        yield
    finally:
        set_capabilities(DEFAULT_CAPABILITIES)


def test_a_kpress_render_error_in_the_child_is_the_routes_502(
    tmp_path: Path, untrusted: None
) -> None:
    (tmp_path / "doc.md").write_text("error\n", encoding="utf-8")
    server._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]
    shared_worker()._command = _standin()  # pyright: ignore[reportPrivateUsage]
    with TestClient(server.app) as client:
        answer = client.get("/api/kpress/render", params={"path": "doc.md", "view": "document"})
    assert answer.status_code == 502
    assert answer.json()["type"] == "kpress_render_error"
    assert answer.json()["detail"] == "boom"


def test_front_matter_json_has_no_type_for_reaches_the_child_in_the_loaders_form(
    tmp_path: Path, untrusted: None
) -> None:
    # Review B's B2: each of these answered 500 under the untrusted profile. Since review
    # E's E1 the bounded loader (frontmatter_yaml.py) owns the form, and the worker sends
    # its mapping as it is: a key by its JSON text, binary as base64, and a set as a list.
    (tmp_path / "doc.md").write_text(
        "---\nblob: !!binary aGVsbG8=\ntags: !!set {a, b}\n2: two\na: letter\n"
        "? [x, y]\n: pair\n~: nothing\ntrue: yes\n---\necho\n",
        encoding="utf-8",
    )
    server._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]
    shared_worker()._command = _standin()  # pyright: ignore[reportPrivateUsage]
    with TestClient(server.app) as client:
        answer = client.get("/api/kpress/render", params={"path": "doc.md", "view": "document"})
        file = client.get("/api/file", params={"path": "doc.md"})
    assert answer.status_code == 200, answer.text
    assert answer.json()["frontmatter"] == {
        "blob": "aGVsbG8=",
        "tags": ["a", "b"],
        "2": "two",
        "a": "letter",
        '["x", "y"]': "pair",
        "null": "nothing",
        "true": "yes",
    }
    assert answer.json()["frontmatter_error"] is None
    # The same value `/api/file` answers, from the same loader.
    assert file.json()["frontmatter"] == answer.json()["frontmatter"]


# Review B's B1 document at six levels, 308 bytes: nine lists of nine aliases to the list
# before them, which is 9**6 strings written out. Before the bounded loader it reached
# the event loop as a mapping that cost 105 to 1,024 ms a walk (review E's E1).
ALIAS_LEVELS_6 = (
    "---\n"
    + "l0: &l0 [" + ",".join(['"lol"'] * 9) + "]\n"
    + "".join(f"l{level}: &l{level} [" + ",".join([f"*l{level - 1}"] * 9) + "]\n" for level in range(1, 6))
    + "---\n# Doc\n"
)  # fmt: skip


def _alias_levels_reason() -> str:
    metadata = ALIAS_LEVELS_6.split("---\n")[1]
    with pytest.raises(FrontmatterError) as refused:
        load_frontmatter_yaml(metadata)
    return str(refused.value)


def test_an_alias_bomb_in_front_matter_reaches_the_child_as_the_loaders_reason_on_a_folder(
    tmp_path: Path, untrusted: None
) -> None:
    assert len(ALIAS_LEVELS_6.encode()) == 308
    (tmp_path / "bomb.md").write_text(ALIAS_LEVELS_6, encoding="utf-8")
    server._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]
    shared_worker()._command = _standin()  # pyright: ignore[reportPrivateUsage]
    with TestClient(server.app) as client:
        answer = client.get("/api/kpress/render", params={"path": "bomb.md", "view": "document"})
    assert answer.status_code == 200, answer.text
    # The text and the reason; written out, the value would be megabytes.
    assert len(answer.content) < 4_096
    assert answer.json()["frontmatter"] is None
    # The child is handed the page's sentence; the loader's reason is the agent's detail.
    assert answer.json()["frontmatter_error"] == FRONTMATTER_ERROR_MESSAGE
    assert answer.json()["frontmatter_error_detail"] == _alias_levels_reason()
    assert "larger than 1,048,576 characters" in answer.json()["frontmatter_error_detail"]


@needs_git
def test_an_alias_bomb_in_front_matter_reaches_the_child_as_the_loaders_reason_on_a_pin(
    tmp_path: Path, untrusted: None
) -> None:
    store, commit = fast_import_store(tmp_path, {b"bomb.md": ALIAS_LEVELS_6.encode()})
    wire = GitPath.from_segments(b"bomb.md").to_wire()

    async def run() -> tuple[int, dict[str, Any], int]:
        shared_worker()._command = _standin()  # pyright: ignore[reportPrivateUsage]
        async with pinned_client(store, commit) as (client, _subject):
            answer = await client.get(
                "/api/kpress/render", params={"path": wire, "view": "document"}
            )
            return answer.status_code, answer.json(), len(answer.content)

    status, body, size = asyncio.run(run())
    assert status == 200, body
    assert size < 4_096
    assert body["frontmatter"] is None
    assert body["frontmatter_error"] == FRONTMATTER_ERROR_MESSAGE
    assert body["frontmatter_error_detail"] == _alias_levels_reason()


class _Watched(dict[str, Any]):
    """Front matter that records the thread of each read of it, and can refuse every read.

    C's JSON encoder reads a ``dict`` subclass through ``items()``, as a walk would.
    """

    def __init__(self, threads: list[int], *, refuse: bool = False, **items: Any) -> None:
        super().__init__(**items)
        self.threads = threads
        self.refuse = refuse

    def items(self) -> Any:
        if self.refuse:
            raise AssertionError("the front matter was read")
        self.threads.append(threading.get_ident())
        return super().items()


def test_the_event_loop_never_reads_the_front_matter_and_its_key_ignores_it() -> None:
    # Review E's E1: the front matter was copied, then encoded for the flight's key, on
    # the event loop. Only the frame, built on a worker thread, reads it now.
    reads: list[int] = []

    async def run() -> tuple[int, dict[str, Any]]:
        worker = ProjectionWorker(command=_standin())
        try:
            request = _request("echo", frontmatter=_Watched(reads, title="One", tags=["a"]))
            return threading.get_ident(), await worker.render_inert(request)
        finally:
            await worker.aclose()

    loop_thread, rendered = asyncio.run(run())
    assert rendered["frontmatter"] == {"title": "One", "tags": ["a"]}
    assert reads and loop_thread not in reads, "only the frame's thread read it"
    # The key reads none of it, so the same bytes are one flight whatever object carries
    # their front matter: the routes parse it from the bytes the key names.
    unread = _Watched([], refuse=True, title="One")
    assert _request("echo", frontmatter=unread).flight_key == _request("echo").flight_key


def test_a_one_shot_command_starts_no_child_and_a_served_session_does(
    tmp_path: Path, untrusted: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Review A's A16 and review C's C2.
    server._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]
    shared_worker()._command = _standin()  # pyright: ignore[reportPrivateUsage]

    def starting() -> bool:
        worker = shared_worker()
        return _child(worker) is not None or worker._starting is not None  # pyright: ignore[reportPrivateUsage]

    with TestClient(server.app):
        one_shot = starting()
    monkeypatch.setattr(worker_module._SERVING, "pages", True)  # pyright: ignore[reportPrivateUsage]
    with TestClient(server.app):
        served = starting()
    assert one_shot is False
    assert served is True


def test_stopping_at_once_kills_the_child_in_its_own_group() -> None:
    async def run() -> int:
        worker = ProjectionWorker(command=_standin())
        child = await _ready(worker)
        worker_module.stop_children()
        async with asyncio.timeout(10):
            await child.wait()
        await worker.aclose()
        return child.pid

    assert not _alive(asyncio.run(run()))


def test_a_deadline_below_one_millisecond_is_refused_when_the_module_loads() -> None:
    # Review B's B4: zero refused every document at once and kept each refusal.
    completed = subprocess.run(
        [sys.executable, "-c", "import metabrowser.diff.markdown_projection_worker"],
        env={**os.environ, "METABROWSER_INERT_RENDER_DEADLINE_MS": "0"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "METABROWSER_INERT_RENDER_DEADLINE_MS must be a positive number" in completed.stderr


# Starts a worker on the child the arguments name, says the child's process ID, then
# renders FOREVER if asked and says so, and ticks every 0.1 s.
_DRIVER = """
import asyncio, sys
from metabrowser.diff.markdown_projection_worker import InertRender, ProjectionWorker

async def main():
    render = sys.argv[1] == "render"
    worker = ProjectionWorker(command=tuple(sys.argv[2:]) or None)
    worker.start(renders=True)
    assert await worker.started()
    print("child", worker._process.pid, flush=True)
    if render:
        text = "[" * 1000 + "%" * (2 * 1024 * 1024)
        asyncio.ensure_future(worker.render_inert(InertRender(
            source_text=text, source_path="slow.md", identity="sha256:slow", kind="markdown",
            view="document", ext=".md", mtime_hash="slow", size=len(text))))
        await asyncio.sleep(1.0)
        print("rendering", flush=True)
    while True:
        print("tick", flush=True)
        await asyncio.sleep(0.1)

asyncio.run(main())
"""


@contextlib.contextmanager
def _driver(
    *args: str, env: dict[str, str] | None = None
) -> Generator[tuple[subprocess.Popen[str], queue.Queue[str]]]:
    process = subprocess.Popen(
        [sys.executable, "-c", _DRIVER, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
        env={**os.environ, **(env or {})},
    )
    lines: queue.Queue[str] = queue.Queue()

    def read() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            lines.put(line.strip())

    threading.Thread(target=read, daemon=True).start()
    try:
        yield process, lines
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)


def _next(lines: queue.Queue[str], prefix: str, timeout_s: float) -> str:
    deadline = time.monotonic() + timeout_s
    while (left := deadline - time.monotonic()) > 0:
        try:
            line = lines.get(timeout=left)
        except queue.Empty:
            break
        if line.startswith(prefix):
            return line
    raise AssertionError(f"no {prefix!r} line within {timeout_s} s")


def test_the_child_leads_its_own_group_so_suspending_the_server_does_not_wedge_its_loop() -> None:
    # Review D's D1: on Python 3.14.7 and later on macOS a child stopped with the server's
    # group was reaped by a blocking wait on the event loop, which then never woke.
    with _driver("idle", *_standin()) as (process, lines):
        child = int(_next(lines, "child", 60).split()[1])
        assert os.getpgid(child) == child, "the child leads its own process group"
        assert os.getpgid(child) != os.getpgid(process.pid)
        _next(lines, "tick", 10)
        os.killpg(process.pid, signal.SIGSTOP)
        time.sleep(0.3)
        os.killpg(process.pid, signal.SIGCONT)
        while not lines.empty():
            lines.get_nowait()
        _next(lines, "tick", 10)
        _next(lines, "tick", 10)


def test_the_child_ends_with_a_server_killed_while_it_renders() -> None:
    with _driver("render", env={"METABROWSER_INERT_RENDER_DEADLINE_MS": "600000"}) as (
        process,
        lines,
    ):
        child = int(_next(lines, "child", 60).split()[1])
        _next(lines, "rendering", 30)
        os.kill(process.pid, signal.SIGKILL)
        process.wait(timeout=10)
        for _ in range(100):
            if not _alive(child):
                break
            time.sleep(0.1)
        assert not _alive(child), "the child ended with the server, mid-render"


def test_an_inert_render_answers_no_sanitizer_diagnostics() -> None:
    # Review C's C3: they were most of a raw-HTML document's answer, and no page reads them.
    async def run() -> dict[str, Any]:
        worker = ProjectionWorker()
        try:
            return await worker.render_inert(_request("# T\n\n<script>alert(1)</script>\n" * 20))
        finally:
            await worker.aclose()

    rendered = asyncio.run(run())
    assert "sanitizer_diagnostics" not in rendered
    assert rendered["inert"] is True and "<script" not in rendered["html"]
    assert kpress_adapter is not None


def test_a_text_is_one_with_a_link_base_however_empty_on_both_sides_of_the_pipe() -> None:
    # Review B's B8: the parent asked whether link_base was truthy, the child whether it
    # was a string, so an empty one was kept as a document and hardened as a text.
    assert _request("x", link_base="").verdict_key[-1] == "text"
    assert _request("x").verdict_key[-1] == "document"


def test_stopping_at_once_never_signals_a_child_already_reaped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Review E's E2: a child that died of something else stayed in the list, and a stop
    # sent SIGKILL to its number, which the system may have given to another process.
    signalled: list[int] = []
    kill = os.kill

    def recorded(pid: int, sig: int) -> None:
        if sig == signal.SIGKILL:
            signalled.append(pid)
        kill(pid, sig)

    async def run() -> tuple[int, int]:
        gone = ProjectionWorker(command=_standin())
        live = ProjectionWorker(command=_standin())
        dead = await _ready(gone)
        alive = await _ready(live)
        kill(dead.pid, signal.SIGKILL)
        async with asyncio.timeout(10):
            await dead.wait()
        monkeypatch.setattr(os, "kill", recorded)
        worker_module.stop_children()
        monkeypatch.setattr(os, "kill", kill)
        async with asyncio.timeout(10):
            await alive.wait()
        await gone.aclose()
        await live.aclose()
        return dead.pid, alive.pid

    dead, alive = asyncio.run(run())
    assert dead not in signalled, "the reaped child's number is not signalled"
    assert signalled == [alive]


def test_a_refusal_is_logged_by_a_name_that_cannot_reach_the_terminal_raw(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Review E's E7: the path a request gave, a pin's display path rather than its wire
    # token, and the end of what the child wrote to its standard error.
    monkeypatch.setattr(worker_module, "_RENDER_DEADLINE_S", 5.0)

    async def run() -> None:
        worker = ProjectionWorker(command=_standin())
        try:
            for request in (
                _request("crash", "sha256:one", source_path="a\n\x1b[31mb.md"),
                _request("crash", "blob:two", source_path="g1-YQ", display_path="docs/pinned.md"),
            ):
                with pytest.raises(InertRenderRefused):
                    await worker.render_inert(request)
        finally:
            await worker.aclose()

    with caplog.at_level(logging.WARNING, logger=worker_module.__name__):
        asyncio.run(run())
    said = [record.getMessage() for record in caplog.records if "Refused" in record.getMessage()]
    assert len(said) == 2, said
    assert all("\n" not in line and "\x1b" not in line for line in said), said
    assert said[0].startswith("Refused rendering 'a\\n\\x1b[31mb.md'"), said
    assert said[1].startswith("Refused rendering 'docs/pinned.md'"), said
    assert all(
        "renderer_exited; its standard error ended 'stand-in crashed'" in line for line in said
    )


def test_a_reload_of_a_refused_document_does_not_walk_its_front_matter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Review E's E1: the walk ran before the kept refusal was checked, so a reload of a
    # refused document with a costly mapping paid for it again on the event loop.
    monkeypatch.setattr(worker_module, "_RENDER_DEADLINE_S", 0.3)

    async def run() -> InertRenderRefused:
        worker = ProjectionWorker(command=_standin())
        try:
            with pytest.raises(InertRenderRefused):
                await worker.render_inert(_request("sleep 5", frontmatter={"title": "Slow"}))
            # The same document again, its front matter refusing any read.
            unread = _Watched([], refuse=True, title="Slow")
            with pytest.raises(InertRenderRefused) as again:
                await worker.render_inert(_request("sleep 5", frontmatter=unread))
            return again.value
        finally:
            await worker.aclose()

    again = asyncio.run(run())
    assert again.code == "render_deadline" and again.remembered is True


def test_memory_exit_refuses_documents_and_projections(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(worker_module, "_gil_enabled", lambda: True)
    caplog.set_level(logging.INFO, logger=worker_module.__name__)

    async def run() -> None:
        worker = ProjectionWorker(command=_standin("--rss-exit", str(worker_module._RSS_EXIT)))  # pyright: ignore[reportPrivateUsage]
        try:
            request = _request("memory")
            with pytest.raises(InertRenderRefused) as first:
                await worker.render_inert(request)
            assert first.value.code == "renderer_exited"
            with pytest.raises(InertRenderRefused) as second:
                await worker.render_inert(request)
            assert second.value.remembered
            await worker.render_inert(_request("echo"))
            result = await worker.prepare(old=OLD, new=NEW, patch=_patch(OLD, NEW), namespace="n")
            assert result.projection.get("reason") == "memory"
            assert "rendering it on a new child" not in caplog.text
            assert (await worker.render_inert(_request("recovered")))["html"] == "<p>recovered</p>"
        finally:
            await worker.aclose()

    asyncio.run(run())


def test_child_checks_peak_before_ready_and_before_sending_its_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import io

    sink = io.BytesIO()
    watching = threading.Event()
    monkeypatch.setattr(worker_module, "_warm", lambda: None)
    monkeypatch.setattr(worker_module, "_answer", lambda request: {"answer": request})
    frame = worker_module._frame  # pyright: ignore[reportPrivateUsage]
    ready = frame({"ready": True})

    def check() -> None:
        assert watching.is_set()
        if sink.getvalue() == ready:
            raise MemoryError("simulated child exit")
        assert not sink.getvalue()

    monkeypatch.setattr(worker_module, "_check_rss", check)
    with pytest.raises(MemoryError, match="simulated child exit"):
        worker_module.serve(io.BytesIO(frame({"op": "example"})), sink, watching=watching)
    assert sink.getvalue() == ready


@pytest.mark.parametrize(("platform", "units"), [("darwin", 1), ("linux", 1024)])
def test_child_memory_budget_uses_platform_rss_units(
    monkeypatch: pytest.MonkeyPatch, platform: str, units: int
) -> None:
    import resource
    from types import SimpleNamespace

    limit = worker_module._RSS_BYTES  # pyright: ignore[reportPrivateUsage]
    report = SimpleNamespace(ru_maxrss=limit // units)
    monkeypatch.setattr(resource, "getrusage", lambda who: report)
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(os, "_exit", sys.exit)
    worker_module._check_rss()  # pyright: ignore[reportPrivateUsage]
    report.ru_maxrss += 1
    with pytest.raises(SystemExit) as stopped:
        worker_module._check_rss()  # pyright: ignore[reportPrivateUsage]
    assert stopped.value.code == worker_module._RSS_EXIT  # pyright: ignore[reportPrivateUsage]
