---
type: is
id: is-01m0c4cycfke1sadh3hd8a24wk
title: "diff/wire.py + diff/routes.py: browser contract and the /api/diff/ collection"
kind: feature
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0c4czd01fxz2rv1na9s3b5q
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T04:27:46.958Z
updated_at: 2026-08-19T04:28:17.513Z
---
wire.py mirrors git/wire.py: TypedDicts for every emitted shape plus validate_manifest, validate_file_patch, validate_resolved_comparison, invoked from tests on everything the routes emit. routes.py exposes DIFF_ROUTES registered the way GIT_ROUTES is: POST /api/diff/comparisons, GET the comparison, GET files/{file_id}/patch, GET files/{file_id}/content/{side}. Opaque file IDs, ETags from comparison + content identity + options + producer version, cancellation terminates queued work.
