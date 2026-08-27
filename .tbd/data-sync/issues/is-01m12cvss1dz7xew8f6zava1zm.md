---
type: is
id: is-01m12cvss1dz7xew8f6zava1zm
title: "PR #86 review R2: each page request spawns 12 git subprocesses (duplicate scope resolution)"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m12cv7mskztpn9mrxcrdfm75
created_at: 2026-08-27T19:58:59.872Z
updated_at: 2026-08-27T19:58:59.872Z
---
src/metabrowser/git/history.py:821. resolve_default_scope runs rev-parse --verify per candidate, then resolve_history_scope re-resolves the same list. Reuse resolved revisions. PR #86 comment 3873346367
