---
type: is
id: is-01m76mgz189rm1bxcz0y9svcym
title: "PR #341 D3: an unexpectedly accepted reject fixture leaves its watchdog running"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m76mgk23q075j4w3wjjg27a0
created_at: 2026-11-12T01:04:02.086Z
updated_at: 2026-11-12T01:31:25.686Z
closed_at: 2026-11-12T01:31:25.685Z
close_reason: "fixed in 8a8b2ef3 (pushed, head 358cebd5): render-svg --time-limit replaces the watchdog; test-scripts.sh checks the accepted-fixture path and that no process outlives the check. Disposition: https://github.com/jlevy/metabrowser/pull/341#issuecomment-6811709019"
resolution: null
duplicate_of: null
---
Severity Low. PR #341, review D (https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5867388071). apps/macos/scripts/build-icon.sh:44 exits when a rejection fixture renders, before cancelling the watchdog started at :42; the EXIT trap only removes the temp dir, so the watchdog later sends SIGKILL to a reaped (possibly reused) pid. Fix: cancel and join the watchdog on both outcomes and from exit cleanup; check that no watchdog remains.
