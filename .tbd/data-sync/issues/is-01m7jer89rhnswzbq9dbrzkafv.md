---
type: is
id: is-01m7jer89rhnswzbq9dbrzkafv
title: README's centered icon block costs its own rendered diff and shows two sanitizer warnings
kind: bug
status: in_progress
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
delegate: claude-code@macbookpro
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-16T15:14:02.679Z
updated_at: 2026-11-16T17:32:19.356Z
started_at: 2026-11-16T17:32:19.355Z
---
README.md:1-3 uses <p align="center"> and <h1 align="center">. `metab . --api '/api/kpress/render?path=README.md'` returns two html_sanitized_attribute warnings, so the README page shows a Diagnostics disclosure, and the rendered-Markdown diff projects any README change as unsupported (a Markdown '# Metabrowser' title projects as ready; see tests/test_markdown_diff_projection.py:647-654). Options: let the inert renderer and the projection keep presentational align on p and h1, or accept the trade. Recorded in the documentation plan's Rendering bullet. From PR #452 review A5: https://github.com/jlevy/metabrowser/pull/452#pullrequestreview-5922214786
