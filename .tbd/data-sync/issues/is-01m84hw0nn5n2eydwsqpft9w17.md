---
type: is
id: is-01m84hw0nn5n2eydwsqpft9w17
title: A reader joining a checkout's background pull job that is being stopped is answered joined and then dropped
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-23T15:54:51.444Z
updated_at: 2026-11-23T17:29:16.295Z
started_at: 2026-11-23T16:10:30.078Z
closed_at: 2026-11-23T17:29:16.293Z
close_reason: "Fixed in #762 (6fd2b2092): RefreshCoordinator.start_again_when_stopped, shared by MirrorSession and checkout.start_pull_refresh, restarts a pull job a reader joins while it is being stopped, including the eager-revision promotion and the optional comparison. test_a_readers_start_that_joins_a_job_being_stopped_gets_its_job fails 4/4 with origin/main's checkout.py and mirror_refresh.py and passes with the fix. Review C of #721, C1."
resolution: null
duplicate_of: null
---
Found by #721 review C (C1), post-merge follow-up of a91a1b8c9 (mb-iz5l). mb-iz5l fixed the race only for a mirror (MirrorSession.request_pull_refresh, mirror_refresh.py). A folder that serves a checkout starts its pull jobs through checkout.start_pull_refresh (builtin_plugins/github/checkout.py), which has the same shape: a reader's start for a pull request whose background (prefetch) job is running promotes it and answers "joined" (checkout.py:470-476 on origin/main 889f47752; the eager-revision branch at :432-437 likewise), but when a reader's job has just arrived at the checkout's store turn the background holder was already told to stop (preempt=partial(coordinator.cancel, key), :857-862), so the promoted job ends cancelled and nothing refreshes the pull request.

Reproduced on origin/main 889f47752 with the production start_pull_refresh and a ServedPull.refresh stand-in (reproduction in the review-pm-probe worktree's attic/pmreview/test_checkout_race.py, run with `pytest -p tests.conftest`): start(12, background=True) runs; a reader's start(11) arrives at the turn; start(12) before 12's job unwinds is answered "joined"; events are ["refresh 12", "refresh 12 cancelled", "refresh 11", "refresh 11 ends"], with no refresh of 12 after the join. The changelog fragment changelog.d/mb-iz5l.md says the case is fixed without naming the host.

Fix: give start_pull_refresh what MirrorSession._start_again_when_stopped gives the mirror: when coordinator.job(key) is cancelling() and the start is a reader's, count it in _PULL_JOBS, keep _COMPARISON_WANTED for a comparison start, and start _pull_job again from a done callback once the stopped job has unwound (once per key; nothing at shutdown). Consider moving the restart onto RefreshCoordinator so both hosts share one implementation. Test: the reproduction above, failing first; also the eager-revision branch.
