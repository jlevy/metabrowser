---
type: is
id: is-01m8d5x7wgbnfcwpm5nnfqvf70
title: "A clickable glyph shows it is clickable: the narrow header's readiness glyph link gets a hover ground"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-27T00:18:58.575Z
updated_at: 2026-11-27T00:18:58.575Z
---
Found in mb-i304: when the pull request header row is too narrow, the readiness badge becomes a glyph-only link to the Checks tab that changes nothing under the pointer. A clickable glyph should answer the pointer as an icon button does (the hover surface only while hovered or focused). Do after mb-omc0, which redraws that glyph.
