---
type: is
id: is-01kxnx9wyz9tb4yttg2rp3nrf3
title: Prove large-directory startup and interaction budgets
kind: task
status: open
priority: 2
version: 3
spec_path: TODO.md
labels:
  - performance
  - scalability
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-07-16T16:49:06.015Z
updated_at: 2026-08-16T08:06:03.239Z
extensions:
  linear:
    id: a8292724-e972-46d8-aee7-80efaa83ebb4
    linked_at: 2026-08-16T08:06:03.239Z
---
Create public synthetic 100K and 1M entry fixtures or generators and record reproducible cold-start, initial-tree, search, memory, and live-update budgets. CI may use a smaller deterministic gate while a documented benchmark captures the full scale claim.
