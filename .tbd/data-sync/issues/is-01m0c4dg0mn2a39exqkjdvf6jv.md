---
type: is
id: is-01m0c4dg0mn2a39exqkjdvf6jv
title: Watcher-driven stale for uncommitted comparisons
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T04:28:05.011Z
updated_at: 2026-08-19T04:28:05.011Z
---
A historical comparison is immutable; an uncommitted one goes stale with a refresh offer rather than repainting under the reader. Wire generation_token from the service to the existing watcher so the shell can offer the refresh without moving the reader mid-review.
