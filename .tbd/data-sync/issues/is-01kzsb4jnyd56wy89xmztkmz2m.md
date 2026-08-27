---
type: is
id: is-01kzsb4jnyd56wy89xmztkmz2m
title: "Repository library Phase 1B: hardened generic Git acquisition"
kind: task
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzsb4k9hwrt25jj9j6svkvaf
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-11T21:19:58.653Z
updated_at: 2026-08-27T06:09:26.399Z
extensions:
  linear:
    id: 0ffb0ef8-e09f-4e96-8736-01e0592ab450
    linked_at: 2026-08-16T08:05:43.419Z
---
Extend metabrowser.git.process with version detection, stdin isolation, the full non-interactive environment, and explicit request, acquisition, and background policies. Add provider-neutral clone to staging, pinned HEAD validation, immutable repository identity plus atomic state, no-replace publication, honest object state, and measured background backfill. Keep one Git runner and no GitHub dependency.
