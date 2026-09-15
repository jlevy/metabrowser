---
type: is
id: is-01m2h99gedgp99s4ygzk38yx61
title: "PR #125 review A-R2: define provider capability registration and async lifecycle"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies: []
parent_id: is-01m2h984s9t8fhm2efg67nwmve
created_at: 2026-09-15T01:00:53.068Z
updated_at: 2026-09-15T01:38:04.842Z
closed_at: 2026-09-15T01:38:04.841Z
close_reason: "Fixed A-R2: added ProviderAdapterSpec capability discovery, duplicate-claim failure, provider-neutral dependency injection, application-lifespan construction, and awaited cancellation/close with mb-ji83 ownership."
resolution: null
duplicate_of: null
---
PR #125 architecture A-R2. Connect the GitHub adapter to the common hosted-review service through a closed installed-plugin capability registry with provider claims, factories, dependencies, duplicate rejection, lifespan construction, dependency injection, async close, and ordered root replacement.
