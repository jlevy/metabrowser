---
type: is
id: is-01m6jrdfayb71zm3ck9p929cys
title: Keep delayed PR Markdown rendering bound to its current record
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m6jhbnan8czw6c97gr5511mr
created_at: 2026-11-04T07:47:13.373Z
updated_at: 2026-11-04T07:47:13.373Z
---
The dedicated correctness review at a7b964c4 reproduced stale Markdown publication: a record A HTML response passes the controller check, waits for inert/style assets, then renderMarkdown looks up the current texts map after record B replaces it and inserts old A HTML into B. This structure already exists on main c934; the newer CSS await also exposes the boundary. Add a focused new stacked PR with a post-await record, element and disposal ownership guard, meaningful delayed-asset negative/positive controls, independent review, normal gates/CI and affected whole-shell acceptance. Preserve plain current text when obsolete work finishes. No source mutation while the existing normal push hook runs.
