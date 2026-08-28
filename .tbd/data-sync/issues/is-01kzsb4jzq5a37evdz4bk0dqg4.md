---
type: is
id: is-01kzsb4jzq5a37evdz4bk0dqg4
title: "Repository library Phase 1A: f01 and SoftSchema format foundation"
kind: task
status: open
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzsb4k9hwrt25jj9j6svkvaf
  - type: blocks
    target: is-01m10vgw6vhq82cd495kvhh9gf
  - type: blocks
    target: is-01kzsb4jnyd56wy89xmztkmz2m
  - type: blocks
    target: is-01m1389aetecehg10qdf7zb9rz
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-11T21:19:58.966Z
updated_at: 2026-08-28T03:58:14.488Z
extensions:
  linear:
    id: 72de9d89-2da1-484f-b3bf-1a9e3204a9bb
    linked_at: 2026-08-16T08:05:43.426Z
---
Implement METABROWSER_HOME, user-owned config.yml, enforced cache/layout.yml, fail-closed f01 handling, ordered migrations, and atomic YAML infrastructure. Adopt released SoftSchema after dependency review; register ApplicationConfig/v1, CacheLayout/v1, RepositoryIdentity/v1, and RepositoryState/v1 with host-bound packaged compiled schemas, strict machine records, permissive unknown-preserving config, drift and artifact corpus checks, same-filesystem staging, locks, quarantine, and recoverable trash. Do not clone or serve a URL in this phase.
