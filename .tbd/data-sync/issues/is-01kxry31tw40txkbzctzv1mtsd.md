---
type: is
id: is-01kxry31tw40txkbzctzv1mtsd
title: "Plugin SDK: repository-scoped nav panels and virtual collections"
kind: feature
status: deferred
priority: 1
version: 10
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
updated_at: 2026-09-23T07:37:21.554Z
extensions:
  linear:
    id: 28ee38a5-1006-44dd-a6a0-814e434a8190
    linked_at: 2026-08-16T08:06:17.779Z
---
Expose additive SDK 0.6 repository-scoped nav panels and bounded virtual collections only if existing calls retain behavior; otherwise bump the SDK and all manifests in one commit. Provide focus, selection, paging, virtualization, restoration, loading/error, root-replacement, and disposal without private app.js access. Update plugin-author docs and CHANGELOG. The hosted-review panel is the first consumer, with exact panel-window, selection, restoration, root-replacement, and disposal functions executed by tests/dom/hosted-review-session.js and cli-ui-hosted-review.
