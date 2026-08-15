---
type: is
id: is-01m03qv53915238ktd5prxgkpy
title: Implement the reserved mb. query namespace in the URL codec
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-navigation-extensions.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz4ejm8kxev59qawa3a9yqd
created_at: 2026-08-15T22:14:25.639Z
updated_at: 2026-08-15T22:14:33.152Z
---
The browser URL grammar (docs/architecture.md#browser-url-grammar) reserves query keys beginning with mb. for Metabrowser presentation parameters, leaving every other key to the document. The grammar is documented and the seam is pinned by codec tests, but nothing is implemented: query is still carried verbatim and uninterpreted.

Implement the split in the URL codec rather than at call sites, so no consumer has to remember to filter:

- parse reserved keys from passthrough keys once;
- sort reserved keys for one canonical spelling;
- keep a pinned key that matches the current default, because defaults are viewer-dependent and an omitted key means 'viewer's choice';
- report an unrecognized mb. key as a visible diagnostic, never passing it through as document metadata;
- preserve the invariant that removing every mb. key yields that content's canonical URL.

mb-281d (source-view line locations) is the first consumer and should land the codec split with it. Classification rule for future entries: a key is reserved only when the sender should decide it for the recipient; viewer-owned settings such as theme and font stay in host-only cookies.
