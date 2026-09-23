---
type: is
id: is-01kxry30twkcz9sg4ecahcg63j
title: "Plugin SDK: mounted sub-routers with path parameters and honest responses"
kind: feature
status: closed
priority: 1
version: 11
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01kxse0vfwwkcq1a6mfdx6v9ad
  - type: blocks
    target: is-01m2h7hrjt6yzb16neh8g2zvsd
  - type: blocks
    target: is-01m2ktkve5n2fztx8smd6n9vja
  - type: blocks
    target: is-01m2kw2cra83fyszkrptvhfead
parent_id: is-01m10vgwqwn8gjdv8fm183vztr
created_at: 2026-07-17T21:00:32.476Z
updated_at: 2026-09-23T07:37:17.352Z
closed_at: 2026-09-23T07:37:17.350Z
close_reason: "Superseded 2026-09-23 by the thin-mirror plan (docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md, PR #227; epic mb-hall), per the user's decisions. Replacement: mb-vrl7 (PR view), built as an internal page without the public router, address-space and resource-kind SDKs."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: 8abea237-409f-4114-b118-4efa20f438b3
    linked_at: 2026-08-16T08:06:11.913Z
---
Add optional installed-plugin RouterSpec declarations and Starlette mounts for path parameters, full methods, streaming/conditional responses, and honest statuses. Validate trusted callables plus reserved/duplicate prefixes, preserve exact data hooks, and add route/CLI parity/distribution coverage. Treat this as additive SDK 0.6 only if existing manifests and window.metabrowser behavior remain unchanged, with plugin docs and CHANGELOG; otherwise bump PLUGIN_SDK_VERSION and every built-in manifest in one commit, with no dual contract. Hosted-review resource routes are the first consumer; browser navigation is separately owned by mb-6mle.
