---
type: is
id: is-01m2h9jka5t3kw909ae7xefx8d
title: "Provider SDK: capability registry, injection, and async lifecycle"
kind: feature
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h9jm62mjccx6x3bx0nct2a
  - type: blocks
    target: is-01m2h7gjbhrb9fdsbjjbcsf2n1
parent_id: is-01m10xd666fefs5z7ft5m58zj0
created_at: 2026-09-15T01:05:50.914Z
updated_at: 2026-09-15T01:06:55.790Z
---
Add a closed ProviderAdapterSpec/capability registry for trusted installed provider plugins. Validate provider and instance claims plus callable imports, reject duplicate claims, construct adapters in application lifespan, inject only provider-neutral ports, and await cancellation/close on shutdown and root replacement. Hosted-review services discover adapters through this registry; server, cache, routes, and renderers never import GitHub.
