---
type: is
id: is-01m6ka8t6b2sa3d64qvqv7kcea
title: Reconcile large-content limits and Pulls navigation windowing documentation
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T12:59:15.018Z
updated_at: 2026-11-04T12:59:15.018Z
---
Expanded documentation review D7: large-content-rendering.md incorrectly makes nonvirtualized rendering universal, treats the historical 1,000-file fixture as the current manifest cap, and describes obsolete unwindowed Pulls limits. Scope file-content rendering separately from windowed Git/Pulls navigation; preserve historical measurements while deriving the actual manifest cap and current cached-page/display/overscan/window distinctions from source. Make no new timing claim or runtime change. Independently verify all constants and final wording before closure.
