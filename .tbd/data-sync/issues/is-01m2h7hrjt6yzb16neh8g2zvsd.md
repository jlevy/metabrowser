---
type: is
id: is-01m2h7hrjt6yzb16neh8g2zvsd
title: "Hosted review Phase 4A: direct PR document and diff route"
kind: feature
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h7jjgpzyfbf10238j32z6q
  - type: blocks
    target: is-01m0b71xwkrf39qnq9ccgxmfp4
parent_id: is-01m10vgwqwn8gjdv8fm183vztr
created_at: 2026-09-15T00:30:26.393Z
updated_at: 2026-09-15T01:19:55.674Z
---
Add the plugin-owned direct hosted-review resource and browser address path, depending on RouterSpec mb-xzj3 and AddressSpaceSpec mb-6mle. Render one cached ChangeRequest without an index: validate every consumed common record, compose text-safe metadata, HTTPS-only links, untrusted Markdown description/comments, review/check/freshness summaries, and base/head comparison through Git, revision content, File Diff Format, and diff plugin. Cover offline, partial, unavailable refs, hostile metadata, startup/popstate/replacement/disposal, and exact /review plus API behavior through hosted-review-session and cli-ui-hosted-review.
