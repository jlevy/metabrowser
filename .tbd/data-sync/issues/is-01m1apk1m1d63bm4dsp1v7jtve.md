---
type: is
id: is-01m1apk1m1d63bm4dsp1v7jtve
title: "PR #90 P90-03: The normalizer rewrites user data at any payload depth"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m1apk016z6h7ms919ekta9z0
created_at: 2026-08-31T01:22:54.209Z
updated_at: 2026-08-31T01:22:54.209Z
---
page_cursor and elapsed_ms are matched by key name anywhere in the tree, including inside user content. Reviewer reproduced an envelope where parsed shows placeholders while pretty_yaml shows the real values in the same response.
