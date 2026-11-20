---
type: is
id: is-01m7jer89rhnswzbq9dbrzkafv
title: README's centered icon block costs its own rendered diff
kind: bug
status: open
priority: 3
version: 6
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
delegate: claude-code@macbookpro
labels: []
dependencies: []
parent_id: is-01m7wysdnvzch4gb5zvqwvn04e
hold: null
hold_until: null
created_at: 2026-11-16T15:14:02.679Z
updated_at: 2026-11-20T17:14:50.558Z
started_at: 2026-11-16T17:32:19.355Z
---
README.md:1-3 uses <p align="center"> and <h1 align="center">. `metab . --api '/api/kpress/render?path=README.md'` returns two html_sanitized_attribute warnings, so the README page shows a Diagnostics disclosure, and the rendered-Markdown diff projects any README change as unsupported (a Markdown '# Metabrowser' title projects as ready; see tests/test_markdown_diff_projection.py:647-654). Options: let the inert renderer and the projection keep presentational align on p and h1, or accept the trade. Recorded in the documentation plan's Rendering bullet. From PR #452 review A5: https://github.com/jlevy/metabrowser/pull/452#pullrequestreview-5922214786

## Notes

2026-11-16: the two sanitizer warnings no longer reach the reader (jlevy/metabrowser#480 keeps html_sanitized* in sanitizer_diagnostics). jlevy/kpress#75 admits align on p, div, h1-h6, so once released and the kpress floor is raised the README icon renders centered. Remaining here: diff/markdown_projection.py still refuses raw HTML, so any README change projects as unsupported; and the inert allowlist (inert_html.py) drops align under the untrusted profile. Both are separate decisions.

2026-11-20 audit: moved from in_progress back to open. No open PR and no active session since 2026-11-16. Since then PR #626 keeps align, width and height in the inert allowlist (untrusted renders too), and PR #452 measured the trusted README as centered with no Diagnostics disclosure. Still open: the rendered-diff projection refuses raw HTML (diff/markdown_projection.py, 'raw HTML has no reliable Markdown projection'), so a README change shows as Source in a pull request's Changes.
