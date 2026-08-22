---
type: is
id: is-01m0nst4bcy6dffddp5xxqv7pe
title: "File header: bold the served-root prefix"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-22T22:35:09.035Z
updated_at: 2026-08-22T22:35:09.035Z
---
The served-root prefix in the file header renders at `--weight-normal` while every crumb after it is bold. Requested: make the prefix bold too, keeping it grey.

Grey already carries the "this is context, not content" signal on its own, so the weight does not need to carry it as well, and the two halves of one address reading at two weights is the odd part.

Touches `.file-header-root` in styles.css, which currently sets `font-weight: var(--weight-normal)` against the `.file-header-path` container's `--weight-bold`.
