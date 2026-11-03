---
type: is
id: is-01m6fpn47xyw9vw25rehmw2kgr
title: "PR #281 D8: test_a_job_cancelled_while_it_waits_gives_up_its_place fails only by the 60 s timeout"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6fpn0yb9yn4kakx1qp787e4
hold: null
hold_until: null
created_at: 2026-11-03T03:18:43.708Z
updated_at: 2026-11-03T04:10:46.184Z
started_at: 2026-11-03T03:50:31.342Z
closed_at: 2026-11-03T04:10:46.183Z
close_reason: "Fixed in 7061ecc1: waits 5 s for the last job and asserts it ran; with M6 applied it fails by AssertionError, not the 60 s timeout."
resolution: null
duplicate_of: null
---
Suggestion. Wrap await last in asyncio.wait_for(last, 5). Review: https://github.com/jlevy/metabrowser/pull/281#pullrequestreview-5746822976 (PR #281, head 7bef1356).
