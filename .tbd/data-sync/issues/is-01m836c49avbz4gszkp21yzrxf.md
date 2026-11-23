---
type: is
id: is-01m836c49avbz4gszkp21yzrxf
title: "Phase 2: built-in collection plugin for YAML collection files (record route, Rows, Table, Source)"
kind: task
status: open
priority: 2
version: 4
spec_path: docs/project/research/research-2026-11-22-annotated-collections-and-guided-pr.md
labels: []
dependencies:
  - type: blocks
    target: is-01m836c4t77h19q6q9wdh833zk
  - type: blocks
    target: is-01m836c59zjyn3p0p4azezrhh3
  - type: blocks
    target: is-01m836c5sjm5382s2wc93p852s
parent_id: is-01m836c38mhwwhmnxwz2ydn61z
created_at: 2026-11-23T03:14:42.090Z
updated_at: 2026-11-23T03:14:43.634Z
---
Move the format module out of the GitHub plugin into a built-in 'collection' plugin (split format from the PR carrier then). A 'collection' kind via yaml_has_key on .yaml/.yml; GET /api/plugin/collection/record?path= with --api goldens (groups, file, folder, missing, path escape, over-bound, invalid YAML, wrong contract); Rows layout, a [[table_source]] Table, Source. Make comparison and overview optional; add items[].group. Test detection of a YAML file past _YAML_PREFIX_BYTES. Parity rows, the map, changelog fragment.
