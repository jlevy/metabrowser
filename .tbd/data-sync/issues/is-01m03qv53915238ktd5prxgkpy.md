---
type: is
id: is-01m03qv53915238ktd5prxgkpy
title: Implement the reserved _mb_ query namespace in the URL codec
kind: feature
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-navigation-extensions.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz4ejm8kxev59qawa3a9yqd
created_at: 2026-08-15T22:14:25.639Z
updated_at: 2026-08-15T22:54:15.899Z
---
The browser URL grammar (docs/architecture.md#browser-url-grammar) reserves query keys beginning with _mb_ for Metabrowser presentation parameters, leaving every other key to the document. Reserved keys are snake_case, matching this server's existing query parameters such as include_ignored and every key on the JSON wire. The grammar is documented and the seam is pinned by codec tests, but nothing is implemented: query is still carried verbatim and uninterpreted.

Implement the split in the URL codec rather than at call sites, so no consumer has to remember to filter:

- parse reserved keys from passthrough keys once;
- sort reserved keys for one canonical spelling;
- keep a pinned key that matches the current default, because defaults are viewer-dependent and an omitted key means 'viewer's choice';
- report an unrecognized _mb_ key as a visible diagnostic, never passing it through as document metadata;
- preserve the invariant that removing every _mb_ key yields that content's canonical URL.

mb-281d (source-view line locations) is the first consumer and should land the codec split with it, using _mb_view and _mb_lines. Classification rule for future entries: a key is reserved only when the sender should decide it for the recipient; viewer-owned settings such as theme and font stay in host-only cookies.
