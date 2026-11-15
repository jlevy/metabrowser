---
type: is
id: is-01m7g5yrcvd999dht2q31j64xs
title: Pull request numbers are bold wherever they identify a pull request
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T18:01:49.721Z
updated_at: 2026-11-15T18:48:44.745Z
started_at: 2026-11-15T18:48:44.743Z
---
The user's request (2026-11-15), verbatim:

"and the PR numbers should be bold as well.

Let's make all of these consistent design system changes too, so everything is following standard conventions."

Read as: every place a pull request's number ("#455") is shown as its identifier is bold, at the same weight the stack position ("1/6") already uses, through one convention stated once in docs/design-system.md. Known places: the Pulls nav rows (`.github-pulls-number` in pulls-panel.js), the stack menu's members (`.github-pull-stack-member-number` in pull-page.js), and the PR page title's number (`.github-pull-number`). Search for others (Commits tab, Diff summary, plugin docs).

Done when each of those is bold through one shared rule or token, not per-surface weights; the design system has one convention for a pull request's number; Chrome checks pin the computed weight on each surface; and the CHANGELOG says so. Stack numbers ("Stack #N") keep the stack label design the user specified earlier (gray, all caps) unless the convention says otherwise for a stated reason.
