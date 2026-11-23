---
type: is
id: is-01m84rxw22jd5dtfbcpky2c9cx
title: A checkout's promotion of a waiting background pull job never calls StoreTurn.promoted, so the reader waits for the background holder to finish
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
created_at: 2026-11-23T17:58:12.286Z
updated_at: 2026-11-23T17:58:12.286Z
---
Found by review A of #762 (A1, Medium), at head 6fd2b2092. The concern was raised, unverified, by the PR's author.

A folder's checkout promotes a background (prefetch) pull job to a reader's by removing its key from `state.background` (`src/metabrowser/builtin_plugins/github/checkout.py:438-441`, the eager-revision branch, and `:507-509`, `_readers_start`), but never calls `StoreTurn.promoted()`. The mirror does (`src/metabrowser/mirror_refresh.py:1981-1983` for a pull job, `:1297-1298` for the idle fetch), and `StoreTurn`'s docstring (`mirror_refresh.py:821-845`) makes it the promoter's duty: a job that queued as background stopped nothing when it arrived. So when a reader opens a pull request whose prefetch is waiting at the checkout's store turn behind other background work (another prefetch, the prefetch's lists through `checkout_store_turn`, or the folder store's idle fetch, which share the turn through `store_turn(home, source)`), the reader's job waits for that work to finish, not to unwind. This is the gap #721 review A3 (Medium) fixed for the mirror only. Present since v0.13.0.

Reproduced with the production `start_pull_refresh` and `_idle_job_stand` (scratch test in the review worktree, `attic/mut/tests/test_review762_repros.py::test_a_promoted_prefetch_waiting_at_the_turn_stops_a_background_holder`, parametrized metadata / comparison / eager_revision): `start(13, background=True)` holds the turn; `start(12, background=True)` waits; a reader's `start(12, ...)` answers `joined`. 0.5 s later the events are `["refresh 13"]` in all three cases: 13 was not stopped and 12 had not run. Only after 13 ends on its own does 12 run.

Fix: call `state.turn.promoted()` after `state.background.discard(key)` in both places. With that applied to a scratch copy, the reproduction passes (events `["refresh 13", "refresh 13 cancelled", ...12's work]`) and all of `tests/test_github_checkout.py` passes. Add the reproduction as a test.
