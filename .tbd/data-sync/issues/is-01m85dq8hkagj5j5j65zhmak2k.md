---
type: is
id: is-01m85dq8hkagj5j5j65zhmak2k
title: "Pull timeline session: 'the page waits as long as the server said' fails when the page has not yet armed its retry timer"
kind: bug
status: closed
priority: 1
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/773
    at: 2026-11-24T00:28:21.224Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-24T00:01:35.794Z
updated_at: 2026-11-24T00:28:24.665Z
started_at: 2026-11-24T00:03:15.763Z
closed_at: 2026-11-24T00:28:24.632Z
close_reason: "Mechanism: the timeline session's waits block left Date.now on the wall clock while asserting an exact 60,000 ms held wait. pull-page.js sets heldUntil = Date.now() + heldMs and, in the same synchronous run, arms heldUntil - Date.now(); a millisecond turning between the two reads armed 59,999 ms (59,986 when descheduled). settle() was not the cause: the timer was always armed, only its delay moved. Reproduced: 25/1500 full runs failed at :589 at load ~350; a clock ticking 1 ms per read failed it every run. Fix (PR #773): the session pins its clock for the whole run and the B3/D4 blocks move that clock; 0/1500 failures after. No production change."
resolution: null
duplicate_of: null
---
