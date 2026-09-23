---
type: is
id: is-01m2h9jka5t3kw909ae7xefx8d
title: "Provider SDK: capability registry, injection, and async lifecycle"
kind: feature
status: open
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: null
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2h9jm62mjccx6x3bx0nct2a
  - type: blocks
    target: is-01m2h7gjbhrb9fdsbjjbcsf2n1
  - type: blocks
    target: is-01m2kw2bvjj5kcsczkz40cmhqx
parent_id: is-01m10xd666fefs5z7ft5m58zj0
hold: null
hold_until: null
created_at: 2026-09-15T01:05:50.914Z
updated_at: 2026-09-23T00:21:41.301Z
started_at: 2026-09-16T22:38:02.389Z
---
Add a closed ProviderAdapterSpec/capability registry for trusted installed provider plugins. Validate provider and instance claims plus callable imports, reject duplicate claims, construct adapters in application lifespan, inject only provider-neutral ports, and await cancellation/close on shutdown and root replacement. RepositoryObjectJobPort accepts a non-secret authorization context plus an opaque process-local GitFetchCredentialLease; a plugin may pass that capability but cannot inspect, serialize, log, or persist it. Hosted-review services discover adapters through this registry; server, cache, routes, and renderers never import GitHub.
