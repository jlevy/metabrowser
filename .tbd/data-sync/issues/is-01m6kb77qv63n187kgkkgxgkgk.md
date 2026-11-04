---
type: is
id: is-01m6kb77qv63n187kgkkgxgkgk
title: Describe no-serve acquisition reuse and borrowing accurately
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T13:15:51.930Z
updated_at: 2026-11-04T13:15:51.930Z
---
Documentation review D9: command-line reference says --no-serve always fetches all objects into a complete clone. Acquisition first reuses a healthy published store, including remembered borrowing, and --checkout can select a lender on a new acquisition. Qualify full-clone behavior to the applicable cache miss without a lender. Apply the same correction to the repository-source Overlay stores list, consistently with D1; never infer a lender from cwd. Documentation only.
