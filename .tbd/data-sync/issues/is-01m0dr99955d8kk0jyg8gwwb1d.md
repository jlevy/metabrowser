---
type: is
id: is-01m0dr99955d8kk0jyg8gwwb1d
title: "Diff view: fold long contiguous runs behind an expander"
kind: feature
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-19T19:34:32.996Z
updated_at: 2026-08-19T19:34:32.996Z
---
GitHub-style folding inside a file section: a contiguous run of diff lines longer than a settable threshold (default ~40; user-settable, off switchable) breaks after the first stretch with a fold bar — an expand/contract control in the section-disclosure vocabulary (chevron, muted bar, keyboard reachable) showing 'N more lines'. Applies to whole added/deleted files and to long runs inside hunks alike. Expansion must not remount the section (the collapse rule); folding composes with mark-as-viewed (mb-i5i4) and later context expansion (mb-hhmb). Mimic GitHub's affordance but keep our tokens/primitives. Measure before bounding: pick the default threshold from the 13k-line PR-58 diff.
