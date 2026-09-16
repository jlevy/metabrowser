---
type: is
id: is-01m2h7hrjt6yzb16neh8g2zvsd
title: "Hosted review Phase 4A: direct PR document and diff route"
kind: feature
status: open
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
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
created_at: 2026-09-15T00:30:26.393Z
updated_at: 2026-09-16T01:08:56.545Z
---
Add plugin-owned direct hosted-resource API routes and the canonical /hosted/<provider-kind>/<instance-key>/<repository-key>/<resource-kind>/<resource-key>[/<inner>] browser address, depending on RouterSpec mb-xzj3, AddressSpaceSpec and codec mb-6mle, and ResourceKindSpec mb-83w0. Register change-request as the first kind and render one cached ChangeRequest without an index: validate all common records, compose text-safe metadata, HTTPS-only links, untrusted Markdown, reviews/checks/freshness, and base/head comparison through Git, revision content, File Diff Format, and diff plugin. Prove direct and index acquisition converge on the same stable provider object address and cover offline, partial, unavailable refs, hostile metadata, startup/popstate/replacement/disposal, hosted-review-session, and cli-ui-hosted-review.
