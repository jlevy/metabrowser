---
type: is
id: is-01m82wvn1ka0r5r0pafr2683hv
title: Balance vertical spacing around the PR overview size and diff summary
kind: bug
status: in_progress
priority: 2
version: 3
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/718
    at: 2026-11-23T00:46:36.876Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-23T00:28:25.000Z
updated_at: 2026-11-23T00:46:36.906Z
started_at: 2026-11-23T00:33:34.651Z
---
Give the PR Overview size line equal breathing room above and below. Separate the size and diff-summary group from PR metadata, and reduce the space beneath the diff summary by reusing existing spacing tokens. Preserve the shared byte styles and diff summary contents.
