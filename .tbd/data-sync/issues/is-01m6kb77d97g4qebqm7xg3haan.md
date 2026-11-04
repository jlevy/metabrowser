---
type: is
id: is-01m6kb77d97g4qebqm7xg3haan
title: Reconcile current architecture routes, summaries and extension rules
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T13:15:51.588Z
updated_at: 2026-11-04T13:15:51.588Z
---
Documentation review D8: current architecture incorrectly says /pulls defaults to All, every launched URL is /view/, folder composition has two rows, and all dotfiles are extensionless. Current routes default Open with explicit state=all; selection_view_href can launch a PR; Files/Ignored/Total are three rows; dotfiles with a later suffix retain that logical extension. Correct matching design-system row-count wording too. Verify against route, serve, folder-totals and fs_paths source without changing behavior.
