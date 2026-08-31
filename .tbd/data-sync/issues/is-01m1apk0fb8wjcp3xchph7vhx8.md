---
type: is
id: is-01m1apk0fb8wjcp3xchph7vhx8
title: "PR #90 P90-01: AGENTS.md still allows gap parity rows the checker rejects"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m1apk016z6h7ms919ekta9z0
created_at: 2026-08-31T01:22:53.034Z
updated_at: 2026-08-31T01:22:53.034Z
---
AGENTS.md:40 says a gap row is allowed and counted and must name the bead that closes it. check_parity.py, its tests, and the arch doc all reject the gap status outright. Verified: the contradiction is in the top instruction file, both sides landed in this PR.
