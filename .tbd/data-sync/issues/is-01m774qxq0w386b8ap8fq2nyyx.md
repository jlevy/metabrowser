---
type: is
id: is-01m774qxq0w386b8ap8fq2nyyx
title: Transition scenario for the performance loop, and a baseline round
kind: task
status: in_progress
priority: 1
version: 22
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m774qzdxvfrwsyzmx5dgtce1
  - type: blocks
    target: is-01m774r1q8f0z91jm14wd3m2h6
  - type: blocks
    target: is-01m774r3cs24qrntm810jeqndz
  - type: blocks
    target: is-01m774r4psqf6bqd00a8pae0dw
  - type: blocks
    target: is-01m774r5n7h5t75ydr0b6m5z00
  - type: blocks
    target: is-01m774r6nmb6sxnp5gbpy1sfaz
  - type: blocks
    target: is-01m774r7k4mqvs813sjppzvceh
  - type: blocks
    target: is-01m774r833ppra9j905zvb5z6a
  - type: blocks
    target: is-01m774r8p6ht39jjcf8sj2fejk
  - type: blocks
    target: is-01m774r967jvcvcx4btkpyfzeg
  - type: blocks
    target: is-01m774r9n7z8bymhs94yjq67sw
  - type: blocks
    target: is-01m774ra6cpn1h8jnk2mkzq0nh
  - type: blocks
    target: is-01m774ramhp4w2e08j3t30aw9g
  - type: blocks
    target: is-01m774rb30k3bd8ehwy6exbwq4
  - type: blocks
    target: is-01m774rbhb56bd9d69fq1y3f0c
  - type: blocks
    target: is-01m774rbz6q8kxewh1pxe06xv4
  - type: blocks
    target: is-01m774rcdp9y54xga8fmgy2912
  - type: blocks
    target: is-01m774rcw2wb289avpff6qvm1e
  - type: blocks
    target: is-01m774rdb8j84szr2bamkxphvm
  - type: blocks
    target: is-01m774rdstn0r4rtfnn10sdbp9
parent_id: is-01m774q0ep0jq6vhb790rart0v
hold: null
hold_until: null
created_at: 2026-11-12T05:47:27.327Z
updated_at: 2026-11-12T05:48:42.064Z
started_at: 2026-11-12T05:48:42.063Z
---
Commit a scenario in explorations/performance-loop that records per transition: painted-ready, blank frames, region movement (works in WebKit), layout-shift entries (Chrome), requests by class, duplicate subject requests. Baseline round exp-058 on main.
