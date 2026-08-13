---
type: is
id: is-01kzwky52tcet4twn7e4eknkje
title: Share category colors and modularize Treemap
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-12-directory-file-type-summary.md
labels:
  - frontend
dependencies:
  - type: blocks
    target: is-01kzwkyd569xvj3ak0edyfv8pm
parent_id: is-01kzwg302q9172bvjc543whcte
created_at: 2026-08-13T03:51:28.601Z
updated_at: 2026-08-13T03:51:36.869Z
---
Implement category_palette.js and split the WIP Treemap into treemap_layout.js, treemap_model.js, and treemap.js. Share one ref-counted path palette with File types; keep summary categories distinct and Other neutral; retain slot assignments across live rank/scope changes; remove the classic extra_script global and monolithic folder index; adopt mb.viewState rather than visibility heuristics. Port Treemap behavior and geometry tests and add palette collision, retention, cross-view reuse, lease cleanup, lazy activation, and disposer coverage.
