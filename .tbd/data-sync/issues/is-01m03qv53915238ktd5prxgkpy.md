---
type: is
id: is-01m03qv53915238ktd5prxgkpy
title: Implement the reserved _mb_ query namespace in the URL codec
kind: feature
status: open
priority: 3
version: 9
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-navigation-extensions.md
labels: []
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-08-15T22:14:25.639Z
updated_at: 2026-11-20T17:27:15.140Z
extensions:
  linear:
    id: 04c8ca32-f221-440d-b4cc-8b2ca23ea4be
    linked_at: 2026-08-16T08:05:43.510Z
---
The browser URL grammar (docs/architecture.md#browser-url-grammar) reserves query keys beginning with _mb_ for Metabrowser presentation parameters, leaving every other key to the document. Reserved keys are snake_case, matching this server's existing query parameters such as include_ignored and every key on the JSON wire. The grammar is documented and the seam is pinned by codec tests (tests/dom/navigation-route-behavior.js, cli-ui-navigation.tryscript.md), but query is still carried verbatim and uninterpreted.

When the first feature needs a sender-decided parameter, implement the split in the URL codec rather than at call sites: parse reserved keys from passthrough keys once; sort reserved keys for one canonical spelling; keep a pinned key that matches the current default, because defaults are viewer-dependent and an omitted key means 'viewer's choice'; report an unrecognized _mb_ key as a visible diagnostic, never passing it through as document metadata; preserve the invariant that removing every _mb_ key yields that content's canonical URL.

Source-view line locations shipped as GitHub-style #L fragments (#235/#239) and do not use this namespace, so no consumer is scheduled. A key is reserved only when the sender should decide it for the recipient; viewer-owned settings such as theme and font stay in host-only cookies.
