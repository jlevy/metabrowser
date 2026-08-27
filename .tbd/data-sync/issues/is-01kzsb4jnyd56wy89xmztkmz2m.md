---
type: is
id: is-01kzsb4jnyd56wy89xmztkmz2m
title: "Repository library Phase 1: Git execution policies and hardened acquisition"
kind: task
status: open
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzsb4k9hwrt25jj9j6svkvaf
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-11T21:19:58.653Z
updated_at: 2026-08-27T05:36:12.110Z
extensions:
  linear:
    id: 0ffb0ef8-e09f-4e96-8736-01e0592ab450
    linked_at: 2026-08-16T08:05:43.419Z
---
Extend metabrowser.git.process with version detection, stdin isolation, the complete non-interactive environment, and explicit request, acquisition, and background policies. Add the provider-neutral acquisition service for blobless clone to staging, validation, publication, honest object state, and bounded background backfill. Keep one Git runner and preserve its fixed argv, output limits, cancellation, child cleanup, and environment scrubbing.
