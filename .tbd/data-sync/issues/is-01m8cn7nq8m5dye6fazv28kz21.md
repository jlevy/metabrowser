---
type: is
id: is-01m8cn7nq8m5dye6fazv28kz21
title: Build a staged disk-backed SoftSchema table projection
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
labels: []
dependencies:
  - type: blocks
    target: is-01m8cn7pfer7dn5f1em8t8xhv8
  - type: blocks
    target: is-01m8cn7q1vmcb79egjcc9bqp7f
parent_id: is-01m8amwjx1z7rpzb8emdknjxk1
created_at: 2026-11-26T19:27:34.631Z
updated_at: 2026-11-26T19:27:35.991Z
---
Project source revision, selected cells and stable row keys into an indexed generation. Support paged sort/filter through normal table routes with fixed memory and parity. Coordinate upstream ss-p0wt.
