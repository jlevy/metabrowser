---
type: is
id: is-01m2h9jhhdn774nzxs9j94h726
title: "v0.11 start gate: v0.10.0 released from main"
kind: task
status: closed
priority: 1
version: 38
spec_path: docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01kxry30twkcz9sg4ecahcg63j
  - type: blocks
    target: is-01kxry31k2e62styhj8t59jj12
  - type: blocks
    target: is-01kxry31tw40txkbzctzv1mtsd
  - type: blocks
    target: is-01kzsb4jnyd56wy89xmztkmz2m
  - type: blocks
    target: is-01kzsb4jzq5a37evdz4bk0dqg4
  - type: blocks
    target: is-01kzsb4k9hwrt25jj9j6svkvaf
  - type: blocks
    target: is-01m0b71xwkrf39qnq9ccgxmfp4
  - type: blocks
    target: is-01m0dkj0gqvpzpxm7t1tpshf30
  - type: blocks
    target: is-01m10vgc38hk6pm0rkgzw2hsk0
  - type: blocks
    target: is-01m10vgw6vhq82cd495kvhh9gf
  - type: blocks
    target: is-01m10vgwqwn8gjdv8fm183vztr
  - type: blocks
    target: is-01m10xd666fefs5z7ft5m58zj0
  - type: blocks
    target: is-01m1389aetecehg10qdf7zb9rz
  - type: blocks
    target: is-01m1389bszmmkqj7d90sq8p3bj
  - type: blocks
    target: is-01m1389rewn2mkj8emj3wxwpr7
  - type: blocks
    target: is-01m2h3vkgbkeq82ch4mzkrch1g
  - type: blocks
    target: is-01m2h3vtmk6apasv27t6ygrrxf
  - type: blocks
    target: is-01m2h5an32kbkp6zfkhkjzq55f
  - type: blocks
    target: is-01m2h7gjbhrb9fdsbjjbcsf2n1
  - type: blocks
    target: is-01m2h7gjc36fqv8cv38qd9zynr
  - type: blocks
    target: is-01m2h7h50h2y8hhhq7x7f1zcmd
  - type: blocks
    target: is-01m2h7hrjfx06hzpr7ptz7k9wn
  - type: blocks
    target: is-01m2h7hrjt6yzb16neh8g2zvsd
  - type: blocks
    target: is-01m2h7jjga1ge5dzvs913n5fgs
  - type: blocks
    target: is-01m2h7jjgpzyfbf10238j32z6q
  - type: blocks
    target: is-01m2h9jjh45d8db9rbd0qtscf7
  - type: blocks
    target: is-01m2h9jka5t3kw909ae7xefx8d
  - type: blocks
    target: is-01m2h9jm62mjccx6x3bx0nct2a
  - type: blocks
    target: is-01m2h9jn8eq1896pa2567wcw9s
  - type: blocks
    target: is-01m132tzn4pek5ew15mreke534
  - type: blocks
    target: is-01m10z5s3nhwmdyp1dcbwfwc33
  - type: blocks
    target: is-01m10z5zm6bknq2q57dsfjfv31
  - type: blocks
    target: is-01m1389tccq35y5z8ya6dpycwn
  - type: blocks
    target: is-01kzcvmq7ry46jxy4gcde7x4cq
  - type: blocks
    target: is-01kzcvmqfy6gw5h36vs1hx3bms
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-09-15T01:05:49.099Z
updated_at: 2026-09-15T16:22:48.909Z
closed_at: 2026-09-15T16:22:48.909Z
close_reason: v0.10.0 is released from main; the tag v0.10.0 points at c97de624 and PyPI carries 0.10.0.
resolution: null
duplicate_of: null
---
Hard gate for the v0.11 implementation graph. Close only after mb-i57d creates the v0.10.0 tag and release from the intended main commit, origin/main is fetched and verified at that commit, and the first v0.11 implementation branch is created from it. All repository, status, trust, provider, view, and parity implementation roots in the v0.11 delivery map depend on this bead; design/review work may proceed before it.
