---
type: is
id: is-01kzsb4jnyd56wy89xmztkmz2m
title: "Repository library Phase 1B-a: hardened generic Git acquisition (no serving)"
kind: task
status: open
priority: 1
version: 13
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01kzsb4k9hwrt25jj9j6svkvaf
  - type: blocks
    target: is-01m1389rewn2mkj8emj3wxwpr7
  - type: blocks
    target: is-01m2h3vkgbkeq82ch4mzkrch1g
  - type: blocks
    target: is-01m2h7gjc36fqv8cv38qd9zynr
  - type: blocks
    target: is-01m0dkj0gqvpzpxm7t1tpshf30
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-11T21:19:58.653Z
updated_at: 2026-09-15T00:39:21.343Z
extensions:
  linear:
    id: 0ffb0ef8-e09f-4e96-8736-01e0592ab450
    linked_at: 2026-08-16T08:05:43.419Z
---
Extend the single existing Git process boundary with version detection, stdin isolation, the full non-interactive environment, and explicit request, acquisition, and background policies. Add provider-neutral clone to staging, pinned HEAD validation, immutable repository identity plus atomic state, no-replace publication, honest object state, and measured background backfill. An acquired gitroot must enter serving through the v0.10 inventory coordinator and its joinable handle lifecycle; this phase itself does not serve. Keep one Git runner and no GitHub dependency.
