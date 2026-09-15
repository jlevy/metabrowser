---
type: is
id: is-01kzs5m38dz1egphfwf30c8h7n
title: Repository library and hosted-review roadmap
kind: epic
status: open
priority: 1
version: 37
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
  - is-01m1389aetecehg10qdf7zb9rz
  - is-01m1389bszmmkqj7d90sq8p3bj
  - is-01m1389rewn2mkj8emj3wxwpr7
  - is-01m2h3qzqep911zn6jwx7dmb9t
  - is-01m2h3vkgbkeq82ch4mzkrch1g
  - is-01m2h3wteafc7mt3x0efnv4xex
  - is-01m2h5ar8jct8wbp94xj39gkq4
  - is-01m0dkj0gqvpzpxm7t1tpshf30
  - is-01kxry31k2e62styhj8t59jj12
  - is-01m2h7gjc36fqv8cv38qd9zynr
  - is-01m2h7jjga1ge5dzvs913n5fgs
created_at: 2026-08-11T19:43:35.692Z
updated_at: 2026-09-15T00:31:44.493Z
extensions:
  linear:
    id: 06ad4ed9-e57c-43ff-a0bd-72bc542de8f5
    linked_at: 2026-08-16T08:05:43.412Z
---
Deliver the repository-library roadmap with a GitHub-first v0.11 vertical slice: freeze the v0.10 contracts; add the versioned application home and generic Git cache; open and reuse any authorized GitHub repository and any exposed branch through detached materializations under the untrusted profile; define provider-neutral Hosted Review Format contracts with a frontmatter change-request document; implement a bounded gh api adapter and auth states; cache directly addressed PR bundles before the bounded PR index; and render plugin-owned PR documents, diffs, revision content, and a virtual Pull Requests nav collection. Full cache management, the chooser, GitHub issues, future GitLab adapters, stacked changes, and measured very-large-repository support remain tracked later.
