---
type: is
id: is-01m8amwj75cvr5f00bhwbk1496
title: Upgrade to softschema 0.9.1 with ruamel.yaml.clib and benchmark collection reads
kind: task
status: in_progress
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/881
    at: 2026-11-26T17:34:38.223Z
delegate: claude-code@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m8amwjx1z7rpzb8emdknjxk1
parent_id: is-01m8amwhv15ckjw7prckfmmggr
child_order_hints:
  - is-01m8cfryytexjgxes91bdg6wbs
hold: null
hold_until: null
created_at: 2026-11-26T00:43:01.733Z
updated_at: 2026-11-26T17:52:09.689Z
started_at: 2026-11-26T09:36:57.972Z
---
Phase 1: supply-chain review of ruamel.yaml.clib; upgrade softschema 0.9.1 + frontmatter-format 0.5.1; adapt to 0.9.0 execution reporting and newly refused characters; metab --doctor shows parser mode; devtools/bench_softschema_collection.py sets the plan's bounds.

## Notes

Benchmark and dependency diagnostics are on https://github.com/jlevy/metabrowser/pull/881. The 4,971-record Universe read+bind was 8.047 seconds C-first vs 41.98 seconds pure, with matched results. Existing YAML table behavior and app contract are covered.
