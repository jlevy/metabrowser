---
type: is
id: is-01kzs5m38dz1egphfwf30c8h7n
title: "Repository library: versioned cache, URL open, refresh, and provider foundation"
kind: epic
status: open
priority: 1
version: 17
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0b71xgqp0jgz007h0wtzr3z
  - type: blocks
    target: is-01m0c1by1cmexbqhx6xeb3b10p
  - type: blocks
    target: is-01m0c4dfbfnqg3q53y7xzbgc0a
child_order_hints:
  - is-01m10vgc38hk6pm0rkgzw2hsk0
  - is-01kzsb4jzq5a37evdz4bk0dqg4
  - is-01kzsb4jnyd56wy89xmztkmz2m
  - is-01kzsb4k9hwrt25jj9j6svkvaf
  - is-01m10vgv018nef5svd0kb54gv9
  - is-01m10vgvh4pvre1adnkgm2egp1
  - is-01m10vgw6vhq82cd495kvhh9gf
  - is-01m10vgwqwn8gjdv8fm183vztr
  - is-01kzt6hdasbhx6maqzvtxntxj7
created_at: 2026-08-11T19:43:35.692Z
updated_at: 2026-08-27T05:37:14.429Z
extensions:
  linear:
    id: 06ad4ed9-e57c-43ff-a0bd-72bc542de8f5
    linked_at: 2026-08-16T08:05:43.412Z
---
Implement the phased repository-library plan: an f01 application home, stable collision-safe source identity, pinned read-only gitroot entries, offline-first reuse, explicit refresh and management, an in-app chooser, and provider-owned metadata. Phase 1 URL serving remains gated on mb-vib1 because fetched repositories are third-party content. The acquisition boundary also supports the general diff and PR-view work that depends on this epic.
