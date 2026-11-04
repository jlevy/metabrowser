---
type: is
id: is-01m6ka2rs5xn3xvkwh2nx3d56d
title: Remove the retired Markdown graph SDK claim from current architecture
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T12:55:56.961Z
updated_at: 2026-11-04T17:21:01.565Z
closed_at: 2026-11-04T17:21:01.565Z
close_reason: "All 17 accepted documentation findings corrected in reviewed/merged PR #298 and independently verified on its exact final-main tree. Completed against actual final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9; final independent integration review and all nine main CI jobs passed. Original evidence retains its execution pins; genuine future and release scope remains separate."
resolution: null
duplicate_of: null
---
Expanded documentation review D3: docs/architecture.md advertises bounded Markdown graph analysis through the SDK, while current exports and docs/plugins.md correctly say graph analysis is not exposed. Update the current architecture to the implemented navigation contract and the future KPress-owned bounded server-route boundary already tracked in mb-614c. Preserve historical plan evidence and do not add an API as part of this documentation correction. Independently verify the exact successor against current exports and actual landed main.
