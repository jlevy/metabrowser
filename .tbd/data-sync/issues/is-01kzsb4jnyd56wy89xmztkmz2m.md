---
type: is
id: is-01kzsb4jnyd56wy89xmztkmz2m
title: "Repository library Phase 1B-a: hardened generic Git acquisition (no serving)"
kind: task
status: open
priority: 1
version: 15
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
  - type: blocks
    target: is-01m2kwk6h6pzxanejy6c339r08
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-11T21:19:58.653Z
updated_at: 2026-09-16T01:16:42.405Z
extensions:
  linear:
    id: 0ffb0ef8-e09f-4e96-8736-01e0592ab450
    linked_at: 2026-08-16T08:05:43.419Z
---
Extend the existing Git runner with version detection, stdin isolation, non-interactive environment, and bounded acquisition/background policies. Clone to owner-only staging, validate pinned HEAD plus strict records, and publish a generic entry atomically with no replacement. Acquisition does not depend on Git-status is_clean because Metabrowser created and validates the staged checkout; serving, replacement, repair, and purge remain gated on mb-u4mf. Keep one Git runner, no GitHub dependency, and no serving in this bead.
