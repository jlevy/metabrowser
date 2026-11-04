---
type: is
id: is-01m6kb79wn3mpeqsfm82gp93hb
title: Remove the unsupported inventory-construction validation multiplier
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T13:15:54.132Z
updated_at: 2026-11-04T17:21:01.619Z
closed_at: 2026-11-04T17:21:01.619Z
close_reason: "All 17 accepted documentation findings corrected in reviewed/merged PR #298 and independently verified on its exact final-main tree. Completed against actual final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9; final independent integration review and all nine main CI jobs passed. Original evidence retains its execution pins; genuine future and release scope remains separate."
resolution: null
duplicate_of: null
---
Documentation review D16: current Python inventory-cost guide says construction costs roughly thirty canonical validations, inconsistent with the measured table immediately above. Remove the unsupported multiplier and state only that extra construction adds per-entry work. Preserve the dated measured values, provenance and future batching scope. No rerun, replacement measurement or new performance claim.
