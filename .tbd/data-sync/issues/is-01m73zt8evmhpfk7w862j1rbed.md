---
type: is
id: is-01m73zt8evmhpfk7w862j1rbed
title: Avoid duplicate PR ages and align conversation commit hashes
kind: bug
status: in_progress
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m7327d4wd92r1n5bnmr1b0zb
hold: null
hold_until: null
created_at: 2026-11-11T00:23:37.690Z
updated_at: 2026-11-11T00:59:55.378Z
started_at: 2026-11-11T00:23:59.367Z
---
Omit duplicate displayed opened/updated ages in PR metadata. Make conversation commit hashes match committed text size, with a leading muted GitHub icon. Show Rendered | Source only for supported formats and hide the chooser for permanent Source fallback, preserving focus on the file disclosure. Style View on GitHub text and icon like View file and View at base. Render checks as a status badge, plain check name, then a leading muted GitHub icon and View action on GitHub link. Keep shared design guidance current and verify end to end.

## Notes

Published draft PR https://github.com/jlevy/metabrowser/pull/351 at 1db567f779e701d8601f58d242ff2f6c21171b9f, appended to stack #350 above #349. All requested UI fixes are implemented. Independent review findings for chooser visibility and focus were corrected and re-reviewed. Built-in browser checks on real PRs verified age deduplication, matching 12px metadata, muted leading GitHub icons, separate check-action links, and hidden unavailable choosers. Local full Python run had 4972 passes and one type-token failure, fixed and verified by all 36 design vocabulary tests. All 389 CLI golden cases, lint/types, audits, and distribution smoke checks passed. Server on 8863 now runs this commit against the main checkout. GitHub CI is running; leave open until merged.
