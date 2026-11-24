---
type: is
id: is-01m87bz38jc6dg5pk0wh0ppc4v
title: "PR #771 A7: pin CHECKBOX_ATTRIBUTES in the shared-allowlist parity test"
kind: task
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m87bxfh1ymbm8c10h6rzs8gx
hold: null
hold_until: null
created_at: 2026-11-24T18:09:24.234Z
updated_at: 2026-11-24T18:30:21.042Z
started_at: 2026-11-24T18:16:19.111Z
closed_at: 2026-11-24T18:30:21.038Z
close_reason: "Fixed in d08c91f8e: the shared-allowlist test compares the page's CHECKBOX_ATTRIBUTES with the server's; a drifted JS value fails it."
resolution: null
duplicate_of: null
---
Low, suggestion. tests/test_inert_html.py:66-76 and :163-178. Add CHECKBOX_ATTRIBUTES to the compared dump. PR #771, review https://github.com/jlevy/metabrowser/pull/771#pullrequestreview-6044731578
