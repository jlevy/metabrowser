---
type: is
id: is-01m6kb77qv63n187kgkkgxgkgk
title: Describe no-serve acquisition reuse and borrowing accurately
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T13:15:51.930Z
updated_at: 2026-11-04T17:21:01.595Z
closed_at: 2026-11-04T17:21:01.595Z
close_reason: "All 17 accepted documentation findings corrected in reviewed/merged PR #298 and independently verified on its exact final-main tree. Completed against actual final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9; final independent integration review and all nine main CI jobs passed. Original evidence retains its execution pins; genuine future and release scope remains separate."
resolution: null
duplicate_of: null
---
Documentation review D9: command-line reference says --no-serve always fetches all objects into a complete clone. Acquisition first reuses a healthy published store, including remembered borrowing, and --checkout can select a lender on a new acquisition. Qualify full-clone behavior to the applicable cache miss without a lender. Apply the same correction to the repository-source Overlay stores list, consistently with D1; never infer a lender from cwd. Documentation only.
