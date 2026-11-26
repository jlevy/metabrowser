---
type: is
id: is-01m8aemtkexd5q10ctj04e7vyq
title: asyncio.run in guided-review route tests cancels the Markdown child's replacement mid-spawn, which hangs CPython 3.12 and 3.13
kind: bug
status: closed
priority: 1
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/856
    at: 2026-11-25T23:15:24.262Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-25T22:53:56.715Z
updated_at: 2026-11-25T23:51:52.560Z
started_at: 2026-11-25T22:54:01.450Z
closed_at: 2026-11-25T23:51:52.559Z
close_reason: "Fixed in #856 (merge fc20ff03f): guided-review route tests end their loops with shared_worker().aclose(); fresh_markdown_child fails a test whose loop ended mid-start of the Markdown child."
resolution: null
duplicate_of: null
---
Main red at 49975eab4 (run 45714404855, unit (3.12, 1/2)): pytest-xdist worker gw3 'crashed' in tests/test_guided_review_route.py::test_a_note_past_the_render_deadline_shows_as_typed. Mechanism: the test drives the route through bare asyncio.run (_ask), which skips the server lifespan's shared_worker().aclose(). The render past the deadline kills the child and _refuse() -> _replace() starts a replacement child in a detached task (_launch). When the route returns within a few loop turns, asyncio.run's _cancel_all_tasks cancels _launch inside create_subprocess_exec together with base_subprocess's _connect_pipes task. On CPython 3.12 and 3.13, _make_subprocess_transport then awaits transp._wait(), which only _call_connection_lost wakes, and that needs every pipe connected and disconnected; the pipes stay None, so the wait never ends. CPython 3.14 wakes wait() on process exit (gh-119710). The main thread sits in select under _cancel_all_tasks until pytest-timeout's thread method (60 s) os._exit()s the worker: 'node down: Not properly terminated'. Fix: run every route call that can use the real Markdown child inside a loop that ends with shared_worker().aclose(), as the server's lifespan does, and make the suite refuse a test that leaves the shared worker's child or start alive past its loop.
