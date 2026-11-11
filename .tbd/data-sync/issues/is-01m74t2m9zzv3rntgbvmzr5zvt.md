---
type: is
id: is-01m74t2m9zzv3rntgbvmzr5zvt
title: "PR #346 A1: Changes shows progress when no attempt is running or scheduled"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74t21pvwps4wh189z73rspr
hold: null
hold_until: null
created_at: 2026-11-11T08:02:34.931Z
updated_at: 2026-11-11T08:21:19.334Z
started_at: 2026-11-11T08:02:46.499Z
closed_at: 2026-11-11T08:21:19.333Z
close_reason: "Fixed in 9c625f4e: comparisonQueued is the one predicate that sends the automatic comparison and makes describePull show progress; the core preview is pending only while the selected fetch is on its way or queued (fetchQueued); Changes without its address offers Fetch changes. Confirmed by tests/dom/github-checkout-comparison-session.js (cold direct visit, refused variant, unowned Changes; golden cli-ui-github-checkout-comparison.tryscript.md), github-pull-core-preview-behavior.js, and github-pull-page-mount-behavior.js; each failed on 63d5d7f."
resolution: null
duplicate_of: null
---
Medium. src/metabrowser/builtin_plugins/github/pull-page.js:863-868 (core preview after a refused or failed selected fetch shows 'Changes are still being prepared.' indefinitely) and :939-941 (record without a store on Changes without route ownership shows 'Fetching changes…' while fetchSelectedChanges never sends, :1402-1426). Fix: derive pending from the predicate that sends the request; accurate not-yet-fetched text with an action otherwise. Review: https://github.com/jlevy/metabrowser/pull/346#pullrequestreview-5855482052 (PR #346, review A, round 1).
