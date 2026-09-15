---
type: is
id: is-01kxry31tw40txkbzctzv1mtsd
title: "Plugin SDK: repository-scoped nav panels and virtual collections"
kind: feature
status: open
priority: 1
version: 6
spec_path: docs/project/architecture/arch-hosted-review-model.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01kxse0vt4cyng7mvtr3hk2rct
  - type: blocks
    target: is-01m2h7jjgpzyfbf10238j32z6q
parent_id: is-01m10vgwqwn8gjdv8fm183vztr
created_at: 2026-07-17T21:00:33.500Z
updated_at: 2026-09-15T00:30:52.949Z
extensions:
  linear:
    id: 28ee38a5-1006-44dd-a6a0-814e434a8190
    linked_at: 2026-08-16T08:06:17.779Z
---
Expose the repository-scoped plugin surface needed by the hosted-review Pull Requests panel. A plugin can register a nav panel backed by a bounded virtual collection and reuse shell focus, selection, paging, virtualization, restoration, loading/error/disposal, and item-like/folder-like container mechanics without reaching into app.js globals. The hosted-review plugin is the first named consumer; the surface stays provider-neutral and receives parity and lifecycle coverage.
