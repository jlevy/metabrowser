---
type: is
id: is-01m82wvn1ka0r5r0pafr2683hv
title: Balance vertical spacing around the PR overview size and diff summary
kind: bug
status: closed
priority: 2
version: 4
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
updated_at: 2026-11-23T01:42:40.739Z
started_at: 2026-11-23T00:33:34.651Z
closed_at: 2026-11-23T01:42:40.686Z
close_reason: "Independently reviewed and merged in #718 at 44c475dd5 after exact PR and current main checks passed. Real Chrome verified state, author, and branches order, the shared 21-point size row and the measured vertical spacing while preserving Commit geometry."
resolution: null
duplicate_of: null
---
Give the PR Overview size line equal breathing room above and below. Separate the size and diff-summary group from PR metadata, and reduce the space beneath the diff summary by reusing existing spacing tokens. Preserve the shared byte styles and diff summary contents.
