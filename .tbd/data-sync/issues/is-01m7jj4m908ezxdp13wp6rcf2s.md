---
type: is
id: is-01m7jj4m908ezxdp13wp6rcf2s
title: "PR #476 A1: Diff summary row shows no placeholder while a core preview waits for the record and its comparison"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7jgg4b9taqwxcfevgd9c6gc
hold: null
hold_until: null
created_at: 2026-11-16T16:13:13.887Z
updated_at: 2026-11-16T17:10:04.792Z
started_at: 2026-11-16T16:13:20.568Z
closed_at: 2026-11-16T17:10:04.791Z
close_reason: "Fixed in de4118672: describePull sets comparisonComing for a refreshing core preview with comparison_state pending and for a no_store record the page asked to prepare (preparing_comparison, or Changes fetching it); paintSummaryWait holds the same summaryPending node from core to record to read. Confirmed by headerSummary (tests/dom/github-pull-page-mount-behavior.js, cli-ui-github-pull-page.tryscript.md): the core-preview and asked-to-prepare cases read 'nothing' at eafcfab and 'the pending placeholder' after."
resolution: null
duplicate_of: null
---
Severity: Medium. PR #476 Review A (round 1), finding A1: https://github.com/jlevy/metabrowser/pull/476#pullrequestreview-5923174293. References: pull-page.js:1257-1281, :4856, :5443-5453; docs/design-system.md:1377-1383.
