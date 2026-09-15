---
type: is
id: is-01m2h7hrjt6yzb16neh8g2zvsd
title: "Hosted review Phase 4A: direct PR document and diff route"
kind: feature
status: open
priority: 1
version: 3
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
updated_at: 2026-09-15T00:31:16.632Z
---
Add the plugin-owned direct hosted-review route and render one cached ChangeRequest document without a PR index or nav panel. Compose validated metadata, the untrusted Markdown description, reviews/checks/freshness summaries, and the selected base/head comparison through the existing Git adapter, revision-content paths, File Diff Format, and diff plugin. Direct /pull/<n> GitHub URL reduction opens this same provider-neutral record identity. Cover offline, partial, unavailable ref, disposal, and exact CLI/API parity paths.
