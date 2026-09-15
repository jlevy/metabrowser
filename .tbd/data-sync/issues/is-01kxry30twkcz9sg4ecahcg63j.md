---
type: is
id: is-01kxry30twkcz9sg4ecahcg63j
title: "Plugin SDK: mounted sub-routers with path parameters and honest responses"
kind: feature
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01kxse0vfwwkcq1a6mfdx6v9ad
  - type: blocks
    target: is-01m2h7hrjt6yzb16neh8g2zvsd
parent_id: is-01m10vgwqwn8gjdv8fm183vztr
created_at: 2026-07-17T21:00:32.476Z
updated_at: 2026-09-15T00:30:26.393Z
extensions:
  linear:
    id: 8abea237-409f-4114-b118-4efa20f438b3
    linked_at: 2026-08-16T08:06:11.913Z
---
Add an optional installed-plugin router declaration and build one Starlette Mount per declared router so provider-neutral domain plugins can own browser and API routes with path parameters, full HTTP methods, streaming/conditional responses, and honest status codes. Keep operator-directory plugins JavaScript-only, validate mount prefixes and callable imports, preserve exact data hooks for simple models, update all built-in manifests if PLUGIN_SDK_VERSION must change, and add route/parity/distribution tests. The hosted-review plugin direct PR document route is the first v0.11 consumer.
