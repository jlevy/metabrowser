---
type: is
id: is-01m8d6341yzhweagpbaq2gjf8k
title: Retain the origin warm-up deadline after a single poll timeout
kind: bug
status: in_progress
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-26-post-load-performance.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/908
    at: 2026-11-27T00:24:06.112Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/908#pullrequestreview-6081929648
    at: 2026-11-27T00:24:06.149Z
labels: []
dependencies: []
parent_id: is-01m8d3zanve7vz9fwprcdcjt8g
created_at: 2026-11-27T00:22:11.254Z
updated_at: 2026-11-27T00:24:08.885Z
---
PR 908 review A1. A transient source status TimeoutError should allow another poll within the fixed first-visit origin warm-up deadline.

## Notes

Fixed in 91037baf5 and verified by the recorder logic test. The disposition is published; the PR remains draft.
