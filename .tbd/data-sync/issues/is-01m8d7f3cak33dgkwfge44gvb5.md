---
type: is
id: is-01m8d7f3cak33dgkwfge44gvb5
title: Measure startup preparation of the current commit comparison
kind: task
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-26-post-load-performance.md
labels: []
dependencies: []
parent_id: is-01m8cs8jdw8yh0hvdy6449jm9j
created_at: 2026-11-27T00:46:12.361Z
updated_at: 2026-11-27T00:46:13.895Z
closed_at: 2026-11-27T00:46:13.894Z
close_reason: Exp-122 retained as a diagnostic. First API comparison ranges overlap and preparation carries its own startup cost.
resolution: null
duplicate_of: null
---
H138, exp-122. Loopback ABBA against exact 065e464f on pinned Metabrowser 7a02fed4b131, external origin acquisition off. First comparison 113–152 ms unprepared and 100–122 ms after 100–142 ms preparation. Resolved commit, comparison and commit-details hashes matched. Two samples per condition on a busy host. No automatic prefetch change.
