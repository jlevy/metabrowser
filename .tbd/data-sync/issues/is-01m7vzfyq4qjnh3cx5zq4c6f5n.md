---
type: is
id: is-01m7vzfyq4qjnh3cx5zq4c6f5n
title: "File-type palette: JSON, Plain text, and Log files dots look nearly identical when named together in the legend"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-20T07:59:46.403Z
updated_at: 2026-11-20T07:59:46.403Z
---
Seen in PR 650's screenshots (mb-6ckq, legend now names up to 9 families): on this repo JSON and Plain text are 0.0164 (light) / 0.0199 (dark) apart in Oklab, and Log files is a similar teal, so three dots in one legend read as one color; names disambiguate. Consider a co-occurrence-aware check (families likely to be named together must be at least X apart) in check_file_type_colors and adjust the closest pairs.
