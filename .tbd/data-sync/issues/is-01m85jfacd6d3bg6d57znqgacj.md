---
type: is
id: is-01m85jfacd6d3bg6d57znqgacj
title: Menu titles miss 4.5:1 on the raised surface in the light theme
kind: bug
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7wysf407hkpj5n35r533gzc
created_at: 2026-11-24T01:24:38.387Z
updated_at: 2026-11-25T02:18:38.525Z
---
.menu-title uses --label-color (--muted) on --viz-surface-raised: 4.43:1 measured in Chrome 2026-11-23 for the same pairing in File Overview's tooltip, which #779 fixed for tooltips only. Lift light --muted or give raised surfaces a label ink, and pin it in test_design_vocabulary.py.
