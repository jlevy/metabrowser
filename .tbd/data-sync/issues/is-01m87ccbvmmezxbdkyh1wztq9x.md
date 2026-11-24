---
type: is
id: is-01m87ccbvmmezxbdkyh1wztq9x
title: "PR #766 B2: module docstring line in markdown_projection.py is 149 characters"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m8577az40f83ecdxrw97hmth
hold: null
hold_until: null
created_at: 2026-11-24T18:16:39.022Z
updated_at: 2026-11-24T18:20:27.440Z
started_at: 2026-11-24T18:16:46.633Z
closed_at: 2026-11-24T18:20:27.439Z
close_reason: "Fixed on PR #766 in 8ce2c385d: the module docstring paragraph is rewrapped to 100 characters. Reply: https://github.com/jlevy/metabrowser/pull/766#issuecomment-7140501833"
resolution: null
duplicate_of: null
---
Low finding B2 of review B (round 2) on PR #766 (https://github.com/jlevy/metabrowser/pull/766#pullrequestreview-6044735853). At src/metabrowser/diff/markdown_projection.py:29, against the 100-character limit in pyproject.toml:153; from 1a3325b9c (A16's reflow).
