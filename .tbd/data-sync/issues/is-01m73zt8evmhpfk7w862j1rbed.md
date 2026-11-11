---
type: is
id: is-01m73zt8evmhpfk7w862j1rbed
title: Avoid duplicate PR ages and align conversation commit hashes
kind: bug
status: in_progress
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m7327d4wd92r1n5bnmr1b0zb
hold: null
hold_until: null
created_at: 2026-11-11T00:23:37.690Z
updated_at: 2026-11-11T00:33:58.162Z
started_at: 2026-11-11T00:23:59.367Z
---
Omit duplicate displayed opened/updated ages in PR metadata. Make conversation commit hashes match committed text size, with a leading muted GitHub icon. Show Rendered | Source only for supported formats and hide the chooser for permanent Source fallback, preserving focus on the file disclosure. Style View on GitHub text and icon like View file and View at base. Render checks as a status badge, plain check name, then a leading muted GitHub icon and View action on GitHub link. Keep shared design guidance current and verify end to end.

## Notes

Implemented on codex/pr-metadata-polish above #349. Independent review found chooser CSS visibility and hidden-focus bugs, both fixed and re-reviewed with no remaining findings. Built-in browser checks on real PRs #346 and #349 verified duplicate age omission, 12px check/hash metadata, muted leading GitHub icons, separate action links, source files without a chooser, and display:none for unsupported Markdown controls. Full local make verify is in progress.
