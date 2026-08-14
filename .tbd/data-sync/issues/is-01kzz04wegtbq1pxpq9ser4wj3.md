---
type: is
id: is-01kzz04wegtbq1pxpq9ser4wj3
title: Render the complete registry-driven Files Overview
kind: feature
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - ui
  - overview
dependencies:
  - type: blocks
    target: is-01kzz0681weprsdjnd151fxkhj
parent_id: is-01kzyxvf9qfc627wszts904wx3
created_at: 2026-08-14T02:03:20.911Z
updated_at: 2026-08-14T02:04:05.564Z
---
Refactor folder/file_type_summary_model.js and distribution_view.js to consume Breakdown v1 directly. Render registry group order; make every nonempty family disclosable with one or more extension children; add No extension basename children, Remaining types raw children, and exact neutral Others rows; resolve child icons through the shared identity helper; and preserve family colors, percentages, size emphasis, ignored scope, expansion keys, responsive alignment, accessibility, and disposal. Tests: singleton and multi-child disclosure, keyboard/ARIA, caps/Others, generic fallbacks, empty and pending folders, ignored toggling, live replacement, responsive light/dark layouts, and parent/child conservation. Acceptance: the view model adds only presentation values and performs no taxonomy or aggregation logic.
