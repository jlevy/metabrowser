---
type: is
id: is-01m7bde4pv1rw6kmdyc5cmafte
title: "Pulls: prefetch changed-file lists so a first expansion draws at once"
kind: feature
status: in_progress
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-11-13T21:36:21.721Z
updated_at: 2026-11-14T00:49:44.951Z
---
Found while fixing mb-ld8g (#406), inferred from grep: only the tree requests `pull-files` or `pull-files-refresh`, so an uncached pull request's first expansion always waits on GitHub (1-5 s), against the "prefetch by default" principle.

Done when: the Pulls panel prefetches file lists for likely-to-be-expanded rows (for example, visible rows, or on hover or focus), bounded by measured cost and GitHub rate limits, so a first expansion usually draws at once; measured before and after.
