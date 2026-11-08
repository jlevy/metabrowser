---
type: is
id: is-01m6xa4ytymbe41wm6ta709yt9
title: Check multi-file browser formatting in the pre-commit hook
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m5wdbsy6z6d95sgg03kwmm76
created_at: 2026-11-08T10:09:33.021Z
updated_at: 2026-11-08T10:09:33.021Z
---
During the normal ea1c5ace2 commit, two staged JavaScript paths were selected. The Lefthook output ran Biome on pulls-panel.js only and printed make: Nothing to be done for tests/dom/github-pr-prefetch-behavior.js. Inspect how STAGED_FILES and {staged_files} are quoted and passed through Lefthook/Make; reproduce with two fixture paths, including spaces, without mutating real staged source. If confirmed, correct argument transport and add a focused negative check. Full lint-check/verify still checks all browser files, and both changed files were explicitly formatted/type-checked in the focused run, so this observation does not waive or block the current full gate. Keep this tooling follow-up separate from the PR-prefetch ownership fix.
