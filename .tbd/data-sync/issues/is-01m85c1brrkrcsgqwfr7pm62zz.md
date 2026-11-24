---
type: is
id: is-01m85c1brrkrcsgqwfr7pm62zz
title: "PR #765 A2: the diff toolbar overflows at 380 px once a File type is chosen"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m8577bzvw6qnfffw9g5f56x2
hold: null
hold_until: null
created_at: 2026-11-23T23:32:09.622Z
updated_at: 2026-11-24T01:05:52.316Z
started_at: 2026-11-23T23:34:59.108Z
closed_at: 2026-11-24T01:05:52.315Z
close_reason: "Fixed in 462859300: the toolbar wraps with the choosers as one group; Chrome check with the production File type control in five states at 1,063 to 320 px."
resolution: null
duplicate_of: null
---
Medium. src/metabrowser/builtin_plugins/diff/styles.css:39-46 (non-wrapping flex row), :187-206 (flex: none), diff-view.js:2214-2244. With File type narrowed or failed, Split | Unified runs 31 to 200 px past the toolbar at 380 px. The Chrome check tests/dom/diff-current-chrome.mjs:219-229 mounts no File type control, so the parity row diff.toolbar-choosers-paint (arch-parity-registry.md:382) overstates it. Decision: wrap, choosers together and right-aligned on their own line; nothing scrolls sideways from 1,063 to 320 px.

Review A on PR #765: https://github.com/jlevy/metabrowser/pull/765#pullrequestreview-6031120972
