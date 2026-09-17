---
type: is
id: is-01m2nz98xx1f0js249srp1j39g
title: "Hosted review Phase 0D review: publish source-binding correction PR"
kind: task
status: in_progress
priority: 1
version: 12
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: claude-code@spud10.local
labels:
  - release:v0.11.0
  - stack:publication
dependencies:
  - type: blocks
    target: is-01m2kwk6h6pzxanejy6c339r08
  - type: blocks
    target: is-01m2kvemzp183vrykz849c0s5a
  - type: blocks
    target: is-01m10vgw6vhq82cd495kvhh9gf
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
  - type: blocks
    target: is-01kzsb4jzq5a37evdz4bk0dqg4
  - type: blocks
    target: is-01m2p1ps48qjh1qt3wmk8s63ra
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
hold: null
hold_until: null
created_at: 2026-09-16T20:42:11.772Z
updated_at: 2026-09-17T04:06:27.307Z
started_at: 2026-09-16T21:12:28.706Z
---
Independently review the source-binding and local Git object-availability contract correction, resolve every finding through the review shortcut, run make verify, and publish one formal GitHub PR with gh stacked on the exact green shared-repository-mirror design head. Record the PR URL, base and head branch names, immutable OIDs, review evidence, formal stack view, and final green CI. Do not merge; mb-n2ro remains the sole landing coordinator.
