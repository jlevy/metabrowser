---
type: is
id: is-01m2h7hrjt6yzb16neh8g2zvsd
title: "Hosted review Phase 4A: direct PR document and diff route"
kind: feature
status: closed
priority: 1
version: 13
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: null
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2h7jjgpzyfbf10238j32z6q
  - type: blocks
    target: is-01m0b71xwkrf39qnq9ccgxmfp4
  - type: blocks
    target: is-01m2ktsfdmrdehcpvg9kqsg6yb
  - type: blocks
    target: is-01m2kw2cra83fyszkrptvhfead
parent_id: is-01m10vgwqwn8gjdv8fm183vztr
hold: null
hold_until: null
created_at: 2026-09-15T00:30:26.393Z
updated_at: 2026-09-23T07:37:18.898Z
started_at: 2026-09-16T21:10:44.912Z
closed_at: 2026-09-23T07:37:18.896Z
close_reason: "Superseded 2026-09-23 by the thin-mirror plan (docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md, PR #227; epic mb-hall), per the user's decisions. Replacement: mb-vrl7 (PR view), built as an internal page without the public router, address-space and resource-kind SDKs."
resolution: null
duplicate_of: null
---
Add plugin-owned direct hosted-resource routes and canonical /hosted address after router, address-space, and resource-kind foundations. Render one cached ChangeRequest without an index and compose metadata, untrusted Markdown, reviews, checks, freshness, File Diff Format, and base/head revision content. Pin one provider manifest plus repository store and exact OIDs; use GitRevisionSubjects even when the Files view is an attached dirty checkout. Prove stable address convergence, offline, partial, and unavailable states, startup, popstate, replacement, disposal, parity, and no checkout mutation.
