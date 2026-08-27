---
type: is
id: is-01kzs5m38dz1egphfwf30c8h7n
title: "Repository library: generic Git cache, chooser, and provider snapshots"
kind: epic
status: open
priority: 1
version: 23
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
  - is-01m10wbv02twkf4z2t3szd5835
  - is-01m10vgc38hk6pm0rkgzw2hsk0
  - is-01kzsb4jzq5a37evdz4bk0dqg4
  - is-01kzsb4jnyd56wy89xmztkmz2m
  - is-01kzsb4k9hwrt25jj9j6svkvaf
  - is-01m10vgv018nef5svd0kb54gv9
  - is-01m10vgvh4pvre1adnkgm2egp1
  - is-01m10vgw6vhq82cd495kvhh9gf
  - is-01m10xd666fefs5z7ft5m58zj0
  - is-01m10vgwqwn8gjdv8fm183vztr
  - is-01m10xd6s2fy7qthahs3cz25gk
  - is-01kzt6hdasbhx6maqzvtxntxj7
  - is-01m11xe1pr09sc61h58tq0rcwd
created_at: 2026-08-11T19:43:35.692Z
updated_at: 2026-08-27T15:29:20.599Z
extensions:
  linear:
    id: 06ad4ed9-e57c-43ff-a0bd-72bc542de8f5
    linked_at: 2026-08-16T08:05:43.412Z
---
Implement the phased repository-library plan: format foundation; generic URL-open and offline reuse; Git-only catalog, refresh, and purge; an in-app chooser; a separately modeled GitHub browsing domain; immutable provider snapshots and views; stacked-PR projections; and measured large-repository support. URL serving remains gated on mb-vib1 because fetched repositories are third-party content. GitHub is not a dependency of the first usable generic cache.
