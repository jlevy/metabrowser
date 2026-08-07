---
type: is
id: is-01kzctt14e1nb4k36bc6jy2qe1
title: "git: browser tests for layout, panel, and end-to-end flow"
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-06-git-graph-view.md
labels: []
dependencies: []
parent_id: is-01kzctqt5s7te6w75jm5pvg6g7
created_at: 2026-08-07T00:43:42.605Z
updated_at: 2026-08-07T00:43:42.605Z
---
Node vm unit tests for computeSwimlanes against hand-written parent lists (linear, simple merge, octopus merge, branch ending mid-page, and a history split across two pages proving continuity), asserting lane assignment rather than pixels. SVG structure tests for renderCommitGraph. DOM tests for tab gating, paging, selection, and hover. One integration test driving the real lifespan and route stack against a fixture repository from /api/git/repo through commit detail.
