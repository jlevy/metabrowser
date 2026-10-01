---
type: is
id: is-01m36k3w9vgwy97c9hcj2sqrs5
title: "v0.12 thin mirror: GitHub-web-like browsing from a local git/gh mirror"
kind: epic
status: open
priority: 1
version: 34
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
child_order_hints:
  - is-01m36k3wrx24ha3x4p1fyj7d6h
  - is-01m36k3x6wgk2y66yn2f757gq5
  - is-01m36k3xm77y33seww2jbwwb69
  - is-01m36k3y0t6fvtqhskx3cqxx95
  - is-01m36k3ydz3tgxmycjj8wknzq5
  - is-01m36ma4er7sj7gqsqpz6jms30
  - is-01m36ma4wj1mvqw8rhgw3mqh6s
  - is-01m37h2x8k6p4th9qnxnbznb5e
  - is-01m37r4r2gttbwczyvatymwewx
  - is-01m396mp15n7r99k2v45d59egp
  - is-01m39amsczwb0ehaa4mgajhdw1
  - is-01m39kypk8gc88f4zdc5m0b86f
  - is-01m39kypz26xxnehmrbk8bmj74
  - is-01m3ab89a0vv5ghc93ss2fpph1
  - is-01m3abtp09dg24eyarfw89fe1a
  - is-01m3abtppe5zk35mdh5yjjf85x
  - is-01m3aghkeb2jnz3q6dqpjnefbe
  - is-01m3am6na1enwz3c75e6p7pn0h
  - is-01m3am6nwyanzc2t01c2mcrqf0
  - is-01m3am6pfnqs97wb8pzk5kwzn5
  - is-01m3am6q1xpe54dwyw95jvt95f
  - is-01m3awj2tre3j0swwzvyvb9rzv
  - is-01m3awjb0pgvy42f8k9435jwe1
  - is-01m3tcz49ctsbrgmab6vxpw1k9
  - is-01m3tcz4v3nwkwh8peed9s8q00
  - is-01m3tcz5d5nqxzjd3mfycysqdx
  - is-01m3tcz5y19g5w5evdqs170h4n
  - is-01m3tcz6h4v10dq3nxt8p6a1pm
  - is-01m3te95dfdnc80j5xywqje9ke
  - is-01m3thxkbk1e6e2yf8z4wrysy0
  - is-01m3tjd3zk6s2xbfvqee6h0t2m
  - is-01m3tmpfvab4wsd8v1dyz1fg3f
created_at: 2026-09-23T07:36:37.434Z
updated_at: 2026-10-01T02:29:04.473Z
---
Epic for the 2026-09-23 thin-mirror plan (PR #227). Metabrowser is a thin wrapper: full bare mirrors updated with git fetch, no invented refs, gc off, views pinned by commit ID, gh as credential helper and API client, PR data as validated JSON records, seamless background refresh. Delivery: Design, Simplify, URL open, PR data, PR view; each a stacked PR with independent review and green CI.
