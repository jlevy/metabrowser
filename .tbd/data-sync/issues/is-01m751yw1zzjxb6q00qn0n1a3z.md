---
type: is
id: is-01m751yw1zzjxb6q00qn0n1a3z
title: "PR #346 C3: every walk key runs describePull for an unchanged tab"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m751ytvafc561t05kr196g8y
hold: null
hold_until: null
created_at: 2026-11-11T10:20:20.414Z
updated_at: 2026-11-11T10:34:27.933Z
started_at: 2026-11-11T10:20:28.478Z
closed_at: 2026-11-11T10:34:27.932Z
close_reason: "Fixed in 6d924fd3: the page handle's showFile skips a repeated settling claim (controller.snapshot().settling), not controller.setTab. Probe attic/perf-showfile.js on the real handle: 3.5 ms -> 0.0003 ms per key at 500+500 comments, 0.36 -> 0.0003 at 50+50. A non-settling showFile still ends the claim (pending-file 'unclaimed' variant; mutation skip-ignores-claim killed)."
resolution: null
duplicate_of: null
---
Low. showFile now calls controller.setTab on every key (pull-page.js:4165), up to 1.76 ms per call with 500+500 comments. Fix: skip a repeated settling call in showFile (tab files, already settling, settling again), not inside controller.setTab. Review: https://github.com/jlevy/metabrowser/pull/346#pullrequestreview-5857164511 (PR #346, review C, follow-up round 3, head 4318e80).
