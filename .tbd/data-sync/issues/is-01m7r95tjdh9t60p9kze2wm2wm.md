---
type: is
id: is-01m7r95tjdh9t60p9kze2wm2wm
title: Structured file view fails on YAML dates, binary, sets and non-finite numbers
kind: bug
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7wysdnvzch4gb5zvqwvn04e
created_at: 2026-11-18T21:32:02.497Z
updated_at: 2026-11-20T17:13:12.327Z
---
Found by review D6 of PR #557. GET /api/plugin/structured/parsed answers plugin_error (TypeError: Object of type date is not JSON serializable) for a YAML file holding a date, and JSONResponse fails likewise on .inf, !!binary and !!set. The rendered diff (diff/structured_projection.py) reads YAML through the bounded loader (frontmatter_yaml.py) and coerces such values with json_safe_scalar, so Rendered draws a tree the file view cannot. Fix: read the file view's YAML through the same bounded loader and coercion, so the two views agree; this also covers the alias expansion of mb-7th1.
