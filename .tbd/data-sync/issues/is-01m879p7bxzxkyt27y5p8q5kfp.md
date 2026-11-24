---
type: is
id: is-01m879p7bxzxkyt27y5p8q5kfp
title: Use a right arrow for in-app navigation menu actions
kind: bug
status: in_progress
priority: 2
version: 3
delegate: codex@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-24T17:29:36.379Z
updated_at: 2026-11-24T17:34:11.637Z
started_at: 2026-11-24T17:30:19.998Z
---
Use the shared right arrow in View this branch, View this tag, and equivalent direct navigation actions. Audit shared menu surfaces for any remaining chevron used for navigating to a destination. Keep disclosure and external-link icons distinct and document the design rule.

## Notes

Included in PR 786 at dc391a2f6ef6986e51209b16eab4ea3e7e4b6ae7, exact review 6044262407. The shared ref menu uses the right arrow for branch, tag, and PR-head navigation. Other chevrons were audited as disclosures. Design system and existing Chrome coverage updated. Standard CI 45449762455 and full verify 45449769481 running.
