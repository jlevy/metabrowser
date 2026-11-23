---
type: is
id: is-01m83ce87ftr08zgrmtaazgbpw
title: "RollupRest docstring: rest also comes from the node budget"
kind: chore
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m836qya23kghgk2m3t9em8nc
created_at: 2026-11-23T05:00:43.114Z
updated_at: 2026-11-23T05:00:43.114Z
---
wire_models.py RollupRest says a rest bucket holds children past the per-directory `top` cap, but the node budget also folds children into rest (found while addressing review A on #722).
