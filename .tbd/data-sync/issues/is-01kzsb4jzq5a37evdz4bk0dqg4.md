---
type: is
id: is-01kzsb4jzq5a37evdz4bk0dqg4
title: "Repository library Phase 1: f01 home, cache identity, and atomic store"
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
created_at: 2026-08-11T21:19:58.966Z
updated_at: 2026-08-27T05:40:22.781Z
extensions:
  linear:
    id: 72de9d89-2da1-484f-b3bf-1a9e3204a9bb
    linked_at: 2026-08-16T08:05:43.426Z
---
Implement METABROWSER_HOME, user-owned config.yml, cache/layout.yml, fail-closed f01 format handling, ordered idempotent migrations, and atomic publication. Derive identity from the SHA-256 digest of the normalized credential-free source; combine a readable slug with a digest suffix, verify the full digest in repo.yml, extend the suffix on collision, and use no-replace path claim and publication semantics. Add home and entry locks, same-filesystem staging, quarantine, catalog scanning, and recoverable purge primitives.
