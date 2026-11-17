---
type: is
id: is-01m7kgg36dvwj9r6tnbcx0t4mp
title: "PR #490 B2: the Chrome check's descriptions claim loads it does not make"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k4tntv9my4ynk41w81g0sj
hold: null
hold_until: null
created_at: 2026-11-17T01:03:46.892Z
updated_at: 2026-11-17T02:33:16.151Z
started_at: 2026-11-17T01:04:00.767Z
closed_at: 2026-11-17T02:33:16.150Z
close_reason: "fixed in 0855877 on PR #490 (CI run 43992596826 green); disposition: https://github.com/jlevy/metabrowser/pull/490#issuecomment-6936212343"
resolution: null
duplicate_of: null
---
Low, PR #490 review B (https://github.com/jlevy/metabrowser/pull/490#pullrequestreview-5930582691). The docs and test headers said the clean folder was measured at 180 px, which it was not, and 'Seven loads' took the stripped shell where eight did.
