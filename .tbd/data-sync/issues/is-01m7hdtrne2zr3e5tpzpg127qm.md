---
type: is
id: is-01m7hdtrne2zr3e5tpzpg127qm
title: "PR #460 A1: the shell's repeat rule misses changed-file rows, so a top-level file's tooltip repeats its name"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjgz0543fxmc38m3p8ajk
hold: null
hold_until: null
created_at: 2026-11-16T05:38:41.965Z
updated_at: 2026-11-16T06:14:50.067Z
started_at: 2026-11-16T05:38:54.869Z
closed_at: 2026-11-16T06:14:50.066Z
close_reason: "fixed in bc0e1537a on claude/tooltips-substantive (PR #460 head b6e2e891d); disposition reply https://github.com/jlevy/metabrowser/pull/460#issuecomment-6908929872"
resolution: null
duplicate_of: null
---
Medium. src/metabrowser/static/app.js:3139-3145 (tipAddsInformation compares only the anchor's whole text); builtin_plugins/github/pull-files-view.js:242-244; builtin_plugins/diff/diff-summary.js:363-364. Coordinator decision: option (a), compare with element boxes inside the anchor; add a Chrome check that a top-level changed-file row's tip does not show while its name is whole. Review A (senior, round 1) on PR #460: https://github.com/jlevy/metabrowser/pull/460#pullrequestreview-5915440680
