---
type: is
id: is-01m84rxx9w226sz3h6zeb0aqbb
title: Another reader's start cancels an optional comparison job a reader already promoted, dropping a joined request
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
created_at: 2026-11-23T17:58:13.562Z
updated_at: 2026-11-23T20:48:58.960Z
closed_at: 2026-11-23T19:05:59.291Z
close_reason: "Fixed in #762, commit f51c58108: _readers_start cancels the checkout's optional comparison job for another pull request's start only while eager.mode is idle, and clears state.eager either way. test_an_optional_job_a_reader_promoted_is_not_ended_by_another_readers_start (metadata, comparison) fails 2/2 with origin/main's checkout.py and passes with the fix; in a scratch copy, an unconditional cancel, a state.eager kept for a promoted job, and never cancelling an idle one each fail a test. Changelog fragment changelog.d/mb-qi6a.md. Review A of #762, A2."
resolution: null
duplicate_of: null
---
Found by review A of #762 (A2, Medium), at head 6fd2b2092.

`_readers_start` (`src/metabrowser/builtin_plugins/github/checkout.py:493-503`) ends the checkout's optional comparison job whenever a reader's start names another pull request: `coordinator.cancel(checkout_job_key(repository, eager.number))`, whatever `eager.mode` is. A reader's own start for the same pull request promotes that job (`eager.mode = "foreground"`) and is answered `joined`, but `state.eager` still names it, so the next reader's start for any other pull request cancels the promoted job. Nothing starts it again: no request joined it while it was stopping, so `RefreshCoordinator.start_again_when_stopped` never fires, and the stopped job's `finally` discards a comparison wish (`checkout.py:930-933`). The reader who was told `joined` gets no refresh, or no comparison, until the page's next stale ask or a press of Refresh. The PR's new docstring (`checkout.py:424-427`) says `joined` is never an answer for work that is then dropped; `start_pull_refresh`'s docstring calls only the optional job one another reader's start ends. Present since v0.13.0 (`checkout.py:456-463` there).

Reproduced with the production `start_pull_refresh` and `_idle_job_stand` (scratch test in the review worktree, `attic/mut/tests/test_review762_repros.py::test_a_readers_promoted_optional_job_is_not_ended_by_another_readers_start`): `start(12, comparison=True, eager_revision=...)` starts the idle phase; the reader's `start(12)` answers `joined`; while 12's refresh runs, `start(11)` answers `started`. Events: `["idle 12 starts", "idle 12 cancelled", "refresh 12", "refresh 12 cancelled", "refresh 11", "refresh 11 ends"]`. With `start(12, comparison=True)` instead: `["idle 12 starts", "idle 12 ends", "comparison 12", "comparison 12 cancelled", "refresh 11", "refresh 11 ends"]`.

Fix: cancel the job only while `eager.mode == "idle"`, and clear `state.eager` either way (the promoted job counts in `_PULL_JOBS` and keeps its own `eager` in `_pull_job`). With that applied to a scratch copy, both cases pass, and so does all of `tests/test_github_checkout.py`, the four-way `test_a_readers_start_that_joins_a_job_being_stopped_gets_its_job` included. Add the reproduction as a test.
