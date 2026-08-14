---
type: is
id: is-01kzz03fmd769zawq6gf5d1hd7
title: "Phase 1: Replace routing and establish the navigation SDK"
kind: feature
status: closed
priority: 1
version: 12
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz03fwfcvam3ft3zvfwqx7g
parent_id: is-01kzyxv1db2hhw2ncc20kdr8mp
child_order_hints:
  - is-01kzz4cn498dcvvbkxwt573zmw
  - is-01kzz4dsnst5gw52s28a00czx8
  - is-01kzz4dt2aa6059jzk41yszq49
  - is-01kzz4dtbr1k1339614faee95w
created_at: 2026-08-14T02:02:35.021Z
updated_at: 2026-08-14T03:57:12.874Z
closed_at: 2026-08-14T03:57:12.874Z
close_reason: Canonical /view/ routing and the structured public navigation boundary are complete across mb-b6bb, mb-xt9v, mb-ftti, and mb-pi55.
---
Add the safe direct /view/{path} shell route, segment encoding, CLI startup URLs, folder canonicalization, and push/replace/pop/fragment behavior in a focused strict browser module composed by app.js. Delete the hash file-route parser, heuristic, hashchange file navigation, legacy migration, and compatibility tests. Introduce window.metabrowser.navigation.href(target), open(target, {viewId?}), and current() around one NavigationTarget whose identity is path/query/fragment; migrate every bundled caller atomically and remove openPath plus the metabrowser:open-path event rather than shimming them. Add route, containment, history, SDK, direct-load, CLI golden, and explicit no-legacy-route tests; run make verify.
