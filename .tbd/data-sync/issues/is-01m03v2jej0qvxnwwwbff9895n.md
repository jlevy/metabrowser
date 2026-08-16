---
type: is
id: is-01m03v2jej0qvxnwwwbff9895n
title: Enforce and document a ~50ms delay before any loading spinner renders
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m03tqjzm7j6qkxjeath5qe0d
created_at: 2026-08-15T23:10:54.417Z
updated_at: 2026-08-16T00:00:51.380Z
closed_at: 2026-08-16T00:00:51.380Z
close_reason: null
---
Nothing should ever render a progress spinner (or progress text) within the first ~50ms of a load; below that threshold the worst case is the usual gray block with gentle animation. The main loading path already behaves this way (mb-delayed-loading). Audit surfaces that violate this (e.g. tree expansion spinner), fix them, and document the rule clearly in the design system / architecture docs.
