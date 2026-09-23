---
type: is
id: is-01kzsb4k9hwrt25jj9j6svkvaf
title: "Repository Phase 2A: URL reduction, HTTPS opening and immutable serving"
kind: task
status: closed
priority: 1
version: 20
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: null
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01kzt6hdasbhx6maqzvtxntxj7
  - type: blocks
    target: is-01m10vgv018nef5svd0kb54gv9
  - type: blocks
    target: is-01m10vgwqwn8gjdv8fm183vztr
  - type: blocks
    target: is-01m2h7gjc36fqv8cv38qd9zynr
  - type: blocks
    target: is-01m2kw2b66x74xxjjtdp3wrsr4
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-08-11T21:19:59.280Z
updated_at: 2026-09-23T07:37:09.585Z
started_at: 2026-09-16T21:10:44.828Z
closed_at: 2026-09-23T07:37:09.584Z
close_reason: "Superseded 2026-09-23 by the thin-mirror plan (docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md, PR #227; epic mb-hall), per the user's decisions. Replacement: mb-bgs7 (URL open: HTTPS mirror, internal GitHub resolver, ref/path split, serving), with no public reducer SDK."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: 04c1dc4d-0602-449f-95a5-09481c36a843
    linked_at: 2026-08-16T08:05:43.432Z
---
Preserve the existing str-or-None CLI root classification and connect installed URL reducers from mb-12cz, retaining ref/path, provider target and line/query intent. Integrate HTTPS acquisition from mb-s1lt, acquire or reuse the shared store, resolve the default full OID, and serve one leased GitRevisionSubject through browser and inspection lifecycles. Prove cold public HTTPS open, warm/read-only/offline reuse without network or provider credential lookup, forced untrusted policy with a populated cache, and cleanup. Non-default branch integration remains mb-2xq7. Publish this work and its tests together in one new Phase 2A PR above the reviewed foundation stabilization head.
