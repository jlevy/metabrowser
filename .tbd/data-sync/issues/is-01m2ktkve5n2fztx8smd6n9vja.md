---
type: is
id: is-01m2ktkve5n2fztx8smd6n9vja
title: "Plugin SDK: register route-backed resource kinds and model/view capabilities"
kind: feature
status: open
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h7hrjt6yzb16neh8g2zvsd
  - type: blocks
    target: is-01m2ktsfdmrdehcpvg9kqsg6yb
  - type: blocks
    target: is-01m2kw2cra83fyszkrptvhfead
parent_id: is-01m10vgwqwn8gjdv8fm183vztr
created_at: 2026-09-16T00:42:06.660Z
updated_at: 2026-09-16T01:08:56.288Z
---
Add a trusted ResourceKindSpec and installed registry for route-backed semantic resources without fabricating filesystem matchers. Bind each kind to its primary contract/model factory, item/container capabilities, canonical AddressSpaceSpec owner, default/additional views, and parity evidence; keep the existing file-kind matcher unchanged. Reject duplicate kind and (kind, view) claims deterministically, make server and browser consume the same registry, extend architecture/parity checks, and prove one change-request selection uses the mb-6mle canonical provider-instance and opaque-object address codec through metab --show plus browserless production JavaScript.
