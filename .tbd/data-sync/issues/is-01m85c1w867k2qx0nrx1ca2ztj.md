---
type: is
id: is-01m85c1w867k2qx0nrx1ca2ztj
title: "PR #765 A6: a hunk's heading in Current can be a line the change removed"
kind: bug
status: in_progress
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m8577bzvw6qnfffw9g5f56x2
hold: null
hold_until: null
created_at: 2026-11-23T23:32:26.500Z
updated_at: 2026-11-23T23:35:14.485Z
started_at: 2026-11-23T23:35:14.483Z
---
Low. diff-view.js:712-715: Current's header is '@@ +start,count @@ heading', and Git takes the heading from the old file (diff/adapters/patch_file.py:420-422). Decision: drop the heading in Current, keep it in Diff.

Review A on PR #765: https://github.com/jlevy/metabrowser/pull/765#pullrequestreview-6031120972
