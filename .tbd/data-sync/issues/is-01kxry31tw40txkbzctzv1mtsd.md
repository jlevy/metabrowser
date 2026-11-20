---
type: is
id: is-01kxry31tw40txkbzctzv1mtsd
title: "Plugin SDK: repository-scoped nav panels and virtual collections"
kind: feature
status: closed
priority: 1
version: 12
spec_path: docs/project/architecture/arch-hosted-review-model.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01kxse0vt4cyng7mvtr3hk2rct
  - type: blocks
    target: is-01m2h7jjgpzyfbf10238j32z6q
  - type: blocks
    target: is-01m2kw2d2arc9hn25pfsc4me50
parent_id: is-01m10vgwqwn8gjdv8fm183vztr
created_at: 2026-07-17T21:00:33.500Z
updated_at: 2026-11-20T19:15:57.379Z
closed_at: 2026-10-01T00:13:19.717Z
close_reason: "Superseded 2026-09-23 by the thin-mirror plan (docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md, PR #227; epic mb-hall), per the user's decisions. The plan retires new public nav-panel SDKs and keeps GitHub support internal. The deferred PR panel (mb-iw1v) is re-planned without this SDK unless a consumer needs one."
resolution: canceled
duplicate_of: null
extensions: {}
---
Expose additive SDK 0.6 repository-scoped nav panels and bounded virtual collections only if existing calls retain behavior; otherwise bump the SDK and all manifests in one commit. Provide focus, selection, paging, virtualization, restoration, loading/error, root-replacement, and disposal without private app.js access. Update plugin-author docs and CHANGELOG. The hosted-review panel is the first consumer, with exact panel-window, selection, restoration, root-replacement, and disposal functions executed by tests/dom/hosted-review-session.js and cli-ui-hosted-review.
