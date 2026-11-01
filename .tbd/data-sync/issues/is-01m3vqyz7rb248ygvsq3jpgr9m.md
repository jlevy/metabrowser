---
type: is
id: is-01m3vqyz7rb248ygvsq3jpgr9m
title: "GitHub pull tests: remaining untested behaviors found by mutation (tabs, --no-tags, closed-PR base fetch, running one-shot refresh)"
kind: task
status: in_progress
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m3te95dfdnc80j5xywqje9ke
hold: null
hold_until: null
created_at: 2026-10-01T12:45:22.544Z
updated_at: 2026-11-01T16:05:45.275Z
started_at: 2026-11-01T16:05:45.274Z
---
From the PR #258 review (mb-738k): mutations that pass on both the base and the branch, not closed in #258. Tab validation in the page controller (pull-page.js; mutants J03, J07); --no-tags on the pull fetch (F05); a closed pull request's refresh also fetching its base branch (F22); a one-shot refresh still running not being an error (F16). For each: add the one case that fails under the mutation, or state why the behavior is not a contract. The reviewer's mutation specs were in the session scratchpad (review258/); the PR #258 body lists them. Not labelled v0.12.
