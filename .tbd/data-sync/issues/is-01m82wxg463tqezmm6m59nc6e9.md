---
type: is
id: is-01m82wxg463tqezmm6m59nc6e9
title: Put PR state and ages immediately below the Overview title
kind: bug
status: closed
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/718
    at: 2026-11-23T00:46:40.397Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-23T00:29:25.509Z
updated_at: 2026-11-23T01:42:40.841Z
started_at: 2026-11-23T00:33:35.523Z
closed_at: 2026-11-23T01:42:40.841Z
close_reason: "Independently reviewed and merged in #718 at 44c475dd5 after exact PR and current main checks passed. Real Chrome verified state, author, and branches order, the shared 21-point size row and the measured vertical spacing while preserving Commit geometry."
resolution: null
duplicate_of: null
---
Order the rendered PR Overview header as title, current state and age, author, then head/base branches. Preserve labels, status, loading behavior, and the diff summary.
