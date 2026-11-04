---
type: is
id: is-01m6kb7a7528d1apcy8p2s87wf
title: Keep the local PR shortcut consistent about explicit stack requests
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T13:15:54.468Z
updated_at: 2026-11-04T17:21:01.628Z
closed_at: 2026-11-04T17:21:01.628Z
close_reason: "All 17 accepted documentation findings corrected in reviewed/merged PR #298 and independently verified on its exact final-main tree. Completed against actual final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9; final independent integration review and all nine main CI jobs passed. Original evidence retains its execution pins; genuine future and release scope remains separate."
resolution: null
duplicate_of: null
---
Documentation review D17: human-maintained local create-or-update-pr-simple fork says an explicit stack request may use flat paths because no standing stack grant exists, contradicting its own authorization step and the validation-plan sibling. Match the sibling's condition for when nobody requested a stack. Preserve generated baselines, .tbd/doc-forks/base, .tbd/config and all recorded grants; this is a narrow contradictory-prose correction, not a policy or tool setup change.
