---
type: is
id: is-01m87zs9sbky91edkksae1vbdt
title: "Folded rendered runs: send small ones inline, fetch only large ones on expand"
kind: task
status: in_progress
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
hold: null
hold_until: null
created_at: 2026-11-24T23:55:45.834Z
updated_at: 2026-11-25T03:54:27.817Z
started_at: 2026-11-24T23:57:44.076Z
---
User request 2026-11-24, refining mb-qn7e lazy folds: a folded run below a measured size is included in the route answer so opening it is instant; only runs past the bound are left as placeholders fetched when opened. Threshold measured, recorded beside its constant.

## Notes

PR #811. A fold spanning INLINE_FOLD_MAX_LINES (100) source lines or more is withheld from a Concise answer and fetched with blocks=I-J when opened or linked into; shorter folds come inline. Measured 2026-11-24 on investment-research #22 (load average ~430): inline folds opened in 1-2 ms; the withheld 49-block, 272-line fold of .agents/skills/tbd/SKILL.md opened in 20-135 ms (request 8-118 ms, 25.6 KB, 6.6 KB compressed); HTML is 94 bytes a line, so an inline fold adds at most ~9 KB. Route golden: tests/golden/cli-github-pull-rendered-views.txt.
