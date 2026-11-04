---
type: is
id: is-01m6ka8t6b2sa3d64qvqv7kcea
title: Reconcile large-content limits and Pulls navigation windowing documentation
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T12:59:15.018Z
updated_at: 2026-11-04T17:21:01.586Z
closed_at: 2026-11-04T17:21:01.586Z
close_reason: "All 17 accepted documentation findings corrected in reviewed/merged PR #298 and independently verified on its exact final-main tree. Completed against actual final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9; final independent integration review and all nine main CI jobs passed. Original evidence retains its execution pins; genuine future and release scope remains separate."
resolution: null
duplicate_of: null
---
Expanded documentation review D7: large-content-rendering.md incorrectly makes nonvirtualized rendering universal, treats the historical 1,000-file fixture as the current manifest cap, and describes obsolete unwindowed Pulls limits. Scope file-content rendering separately from windowed Git/Pulls navigation; preserve historical measurements while deriving the actual manifest cap and current cached-page/display/overscan/window distinctions from source. Make no new timing claim or runtime change. Independently verify all constants and final wording before closure.
