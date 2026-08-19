---
type: is
id: is-01m09s6rn8gpznqbygaqyqf3kq
title: "Diff P1: comparison model, patch-file source, and unified renderer"
kind: feature
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-18T06:33:41.287Z
updated_at: 2026-08-19T04:28:50.998Z
closed_at: 2026-08-19T04:28:50.997Z
close_reason: "Superseded by the file-level decomposition: mb-t2ub (format.py), mb-eaci (adapters/base.py), mb-rre2 (adapters/patch_file.py), mb-uawv (service.py), mb-27dr (wire.py + routes.py), mb-snkb (diff_model.js), mb-ao1d (diff_view.js), mb-yv0g (file kind + view descriptors). Same scope, now at implementable granularity with a wired dependency graph."
---
Phase 1 of the general diff spec: diff/model.py, diff/adapters/patch_file.py, diff/service.py, diff/routes.py, the diff file kind, and static/diff_view.js unified rendering. Ends with a .patch file rendering as a real diff with no Git involvement — the cheapest proof the model and renderer are source-agnostic, and independently useful.
