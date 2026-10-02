---
type: is
id: is-01m3wgefqnj91f8avyyv4x8t5w
title: "Landing gate: regular-folder behavior is unchanged from v0.11.0 except documented fixes"
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
child_order_hints:
  - is-01m3xdkv8pgb8q69mvem8svn27
hold: null
hold_until: null
created_at: 2026-10-01T19:53:16.765Z
updated_at: 2026-10-02T04:23:01.128Z
started_at: 2026-10-01T19:53:20.458Z
---
The user's requirement (2026-10-01): 'carefully review to make sure the entire PR stack can land safely without destabilizing any existing features for regular pages (bugfixes excepted) ... thoroughly tested/reviewed. then the new features are purely additive.' Earlier evidence (byte-identical CLI output on 14 routes, a landing-risk review, a browser smoke) was taken at #244 and is stale: later PRs changed code every page uses (#246 capability SDK removal and --doctor; #248 pin guard and pageshow handling; #249 ROOT rule and the Git panel's commit loading; #254 plugin SDK split into an on-demand views file, plugin loading order, lazy imports; #261 run_git reading stderr; the page-connection and mirror-name fixes). Gate: on the final stack tip, three independent differentials against v0.11.0 on regular trusted folders, each re-runnable with one command: (1) evidence audit: every test, golden and fixture that exists on main and was modified or deleted in the stack, classified hunk by hunk; main's own black-box goldens run against the tip's build; (2) data and modes: every route main registers, every CLI mode and flag, response headers, plugin loading and environment handling, over several corpora, byte-compared; (3) browser: a scripted matrix of views and interactions in stock Chrome on both builds, comparing normalized DOM, console, requests and screenshots. Every difference is classified: identical; intended change with its CHANGELOG entry; bugfix; or unexplained. Accept rule: zero unexplained differences, and a written list of every intended non-additive change to an existing feature for the user to sign off (known so far: Plugin SDK 0.6 -> 0.7 is breaking; --untrusted and --no-active-content now render Markdown inert and apply a strict CSP; --doctor output; metab '' is refused; a scheme:// argument is always a source; source views gained a line gutter). Cross-browser paint (Safari, Firefox) remains a manual check for the user.
