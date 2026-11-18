---
type: is
id: is-01m7pq9dk5hbfvrq38zv4v53zb
title: CHANGELOG.md conflicts on every merge to main serialize landing
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-18T07:00:11.492Z
updated_at: 2026-11-18T07:00:11.492Z
---
Overnight 2026-11-18 every merge to main made each open PR with an Unreleased entry conflict in CHANGELOG.md (both sides add at the top of Unreleased), forcing a merge-up and a fresh ~35-job CI run per PR per landing. Options: (a) .gitattributes 'CHANGELOG.md merge=union' (built-in driver; verify GitHub's mergeability check and merge honor it, and that union keeps entries separated by a blank line); (b) changelog fragments (one file per change under changelog.d/, assembled at release). Measure which GitHub honors before choosing.
