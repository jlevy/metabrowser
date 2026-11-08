---
type: is
id: is-01m6yf7sfcwhqr17xdzy45r7tr
title: Ensure SDK template renderers work on direct plugin-page loads
kind: bug
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex/prefetch_ownership_review
labels: []
dependencies:
  - type: blocks
    target: is-01m5wdbsy6z6d95sgg03kwmm76
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-08T20:57:43.147Z
updated_at: 2026-11-08T21:02:14.095Z
started_at: 2026-11-08T21:02:13.494Z
---
Installed c3 authored SDK 0.7 sample works after navigating from folder Overview, but direct reload of the public long-controls.md plugin page renders Could not display this view. Console records metabrowser.render: Mustache.js is not loaded — bundle is missing at plugin-sdk.js456, sample index.js30, view-composition mount151 and app6035. Both fixture manifest and styles match the existing public sample; it uses the documented synchronous SDK render helper. First establish whether the SDK or plugin asset-declaration contract owns template readiness, reproduce a focused regression and use existing asset loading/lifetime mechanisms. Do not add speculative compatibility or an unconditional large eager dependency. Preserve original console and failed reload. Independently review the smallest correct fix, normal complete gate and current installed direct-entry/browser replay. This is separate from measured large-source continuation and actual downstream owner migration.

## Notes

Cold-entry diagnosis confirms a host readiness gap: the public synchronous render helper requires Mustache, but plugin loading awaits sdk-views while Mustache is left to a best-effort idle chain. Prepare the smallest explicit readiness repair with a real red regression; current source remains unchanged while the earlier QA gate completes. Direct-reload console/DOM/image evidence is preserved under authored-sdk07-controls-20261108/manual-c3-20261108. All copy/paste and both continuation paths pass independently; full SDK acceptance remains blocked by the direct-entry failure.
