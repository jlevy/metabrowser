---
type: is
id: is-01m3wgefqnj91f8avyyv4x8t5w
title: "Landing gate: regular-folder behavior is unchanged from v0.11.0 except documented fixes"
kind: task
status: in_progress
priority: 1
version: 7
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
  - is-01m3zcr18c7gmtctd4g8d8sfc1
hold: null
hold_until: null
created_at: 2026-10-01T19:53:16.765Z
updated_at: 2026-10-02T22:46:18.635Z
started_at: 2026-10-01T19:53:20.458Z
---
The user's requirement (2026-10-01): 'carefully review to make sure the entire PR stack can land safely without destabilizing any existing features for regular pages (bugfixes excepted) ... thoroughly tested/reviewed. then the new features are purely additive.' Earlier evidence (byte-identical CLI output on 14 routes, a landing-risk review, a browser smoke) was taken at #244 and is stale: later PRs changed code every page uses (#246 capability SDK removal and --doctor; #248 pin guard and pageshow handling; #249 ROOT rule and the Git panel's commit loading; #254 plugin SDK split into an on-demand views file, plugin loading order, lazy imports; #261 run_git reading stderr; the page-connection and mirror-name fixes). Gate: on the final stack tip, three independent differentials against v0.11.0 on regular trusted folders, each re-runnable with one command: (1) evidence audit: every test, golden and fixture that exists on main and was modified or deleted in the stack, classified hunk by hunk; main's own black-box goldens run against the tip's build; (2) data and modes: every route main registers, every CLI mode and flag, response headers, plugin loading and environment handling, over several corpora, byte-compared; (3) browser: a scripted matrix of views and interactions in stock Chrome on both builds, comparing normalized DOM, console, requests and screenshots. Every difference is classified: identical; intended change with its CHANGELOG entry; bugfix; or unexplained. Accept rule: zero unexplained differences, and a written list of every intended non-additive change to an existing feature for the user to sign off (known so far: Plugin SDK 0.6 -> 0.7 is breaking; --untrusted and --no-active-content now render Markdown inert and apply a strict CSP; --doctor output; metab '' is refused; a scheme:// argument is always a source; source views gained a line gutter). Cross-browser paint (Safari, Firefox) remains a manual check for the user.

## Notes

2026-10-02: the fixes are in #264 and #267. The data differential and evidence audit were restarted on 14fcdb85 as a detached job at 13:46 (first attempt killed by a 30-minute background limit); results not read yet. The browser differential has not been re-run on the final head. All three must pass on the final head with zero unexplained differences. Harness sources and the f62c16b1 reports are preserved in metabrowser-landing-gate-evidence/ beside the main checkout; see HANDOFF.md there for the re-run commands.

2026-10-01: state of the three checks. (1) Evidence audit: complete; its three regular-folder regressions are restored in #264. (2) Data and modes: 20,234 comparisons at f62c16b1, zero unexplained, report at scratchpad landing-gate/data/REPORT.md; two regressions (STRUCTURED_CACHE_SIZE=0; diff document hook answers 404 for a name that is not .patch or .diff) and one already fixed in #264 (structured size); deliberate changes with no CHANGELOG entry: --end-of-options on rev-parse, typed 404 for an unreadable file on the diff hook, dotenv warning printed 15 times instead of 9. (3) Browser: 1,320 steps at f62c16b1, report at landing-gate/browser/REPORT.md; accept rule NOT met: F1 stray attribute on folder rows (1,108 steps), F2 hover prefetch (fixed in #264 after the capture), F4 a lazy image fetched earlier (no mechanism; 5 of 6 captures); F3 line pitch 21 px to 18 px on large plain files; two new module requests; log rows lose their clickable accessibility node. Fixes for the regressions, F1 and F3 are mb-55tr. make verify passed on 8879c4de (3,952 Python and 266 browser tests). Owed: re-run all three checks on the final tip after mb-55tr; decisions on F4, the module requests, the log-row accessibility node, and CHANGELOG entries for the deliberate changes.
