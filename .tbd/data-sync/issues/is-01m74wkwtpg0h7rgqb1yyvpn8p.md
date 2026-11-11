---
type: is
id: is-01m74wkwtpg0h7rgqb1yyvpn8p
title: "PR #349 A2: a pending projection shows an immediate spinner over Source, then swaps to Rendered"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74wk8dt7weq5cmkt2hmdrjr
hold: null
hold_until: null
created_at: 2026-11-11T08:46:57.877Z
updated_at: 2026-11-11T09:51:48.883Z
started_at: 2026-11-11T08:47:23.270Z
closed_at: 2026-11-11T09:51:48.882Z
close_reason: "A2 fixed in de42f53d: progress mark in the file bar under mb-delayed-loading; files on screen at mount wait the loading delay with Source hidden. DOM test diff-markdown-behavior.js. Server prefetch of the first screen follows with C4 in phase 2."
resolution: null
duplicate_of: null
---
Severity: Medium. PR #349 review: https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5855490584. References: diff-markdown.js:393-400, 258, 223-229. Addressed on PR #349 (branch codex/pr-rendered-markdown-diffs).
