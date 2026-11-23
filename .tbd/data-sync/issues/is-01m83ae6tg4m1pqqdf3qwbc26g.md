---
type: is
id: is-01m83ae6tg4m1pqqdf3qwbc26g
title: A reader's request that joins a background pull-request job already told to stop is answered joined and then dropped
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
hold: null
hold_until: null
created_at: 2026-11-23T04:25:44.086Z
updated_at: 2026-11-23T04:50:50.255Z
started_at: 2026-11-23T04:38:39.759Z
closed_at: 2026-11-23T04:50:50.248Z
close_reason: "Fixed in a91a1b8c9 on #721"
resolution: null
duplicate_of: null
---
Found by #721 review B (B3), reproduced; the code is on main (mirror_refresh request_pull_refresh / the pull job's preemption). The same race #721 fixed for the idle mirror fetch (MirrorSession._join_running restarts the fetch for a request that joined a stopped one): a reader's request joining a background pull job in the tick it is preempted is answered 'joined' and then dropped. #721 adds foreground arrivals that open the window more often. Fix: restart the pull job for a joining reader once the stopped one unwinds, with a test that fails first; reproduction in the store-freshness worktree's attic/review-721/B/test_repro_b.py.
