---
type: is
id: is-01m1fcjw9he43zd4kmtmhkbkf6
title: Accept the shipped file-type registry identity in folder rollups
kind: bug
status: closed
priority: 0
version: 4
labels: []
dependencies:
  - type: blocks
    target: is-01m1fbqx7dhbw3c7ybcpfjqda4
created_at: 2026-09-01T21:04:15.152Z
updated_at: 2026-09-01T21:23:01.926Z
closed_at: 2026-09-01T21:23:01.925Z
close_reason: "Fixed in f1d36447: preserve and compare the full live schema-4 registry identity; focused, full, distribution, and live-browser checks pass."
resolution: null
duplicate_of: null
---
MetaBrowser 0.9.0 and current main serialize file_type_breakdown.registry.schema_version=4, but folder/file-type-summary-model.js rejects every live response unless schema_version===3. This makes the file-type rollup fail visibly in the browser. Add a regression at the wire/browser boundary, use the authoritative runtime identity instead of a stale literal where practical, and include the fix in 0.9.1.
