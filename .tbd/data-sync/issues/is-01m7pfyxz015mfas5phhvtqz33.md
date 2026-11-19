---
type: is
id: is-01m7pfyxz015mfas5phhvtqz33
title: Rendered diffs for YAML, JSON, and Markdown front matter on a pull request's Changes
kind: epic
status: open
priority: 2
version: 14
labels: []
dependencies: []
child_order_hints:
  - is-01m7pfyye7k2nfmvkkpzw4f8dg
  - is-01m7pfyyw8r4pbhcmshnqk8anc
  - is-01m7pfyzbv2jhjeeea4mgps8tq
  - is-01m7pfyzsxgdj585aw358x5pxm
  - is-01m7pfz08mg470x3an6ndfm54j
  - is-01m7pfz0r1ced3wrnmzh5bhem6
  - is-01m7r95tjdh9t60p9kze2wm2wm
  - is-01m7r95zvyws55krqqyrbraetk
  - is-01m7r965b9r95khy0934kr63hs
  - is-01m7r96aynkd71s9ehjw8y4ze7
  - is-01m7r96j1rqavpv1pgx5fh6nwc
created_at: 2026-11-18T04:52:07.776Z
updated_at: 2026-11-19T00:22:58.701Z
closed_at: null
close_reason: null
resolution: null
duplicate_of: null
---
Extend the Rendered | Source chooser on a pull request's Changes from Markdown bodies to every format the file browser renders from data: YAML and JSON as the structured tree, and Markdown's YAML front matter as KPress's Frontmatter disclosure, each with the same change gutter the Markdown blocks use. Rendering matches the file browser's; the diff adds only row-level change marks. Builds on main; #527 (inert Markdown worker) and #542 (bounded front-matter YAML) touch adjacent code and are not yet mergeable.

## Notes

Reopened: PR #557 still open with five open child beads
