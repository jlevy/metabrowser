---
type: is
id: is-01m8b560x5nwnggj9n7whes704
title: Overview legend hover Chrome test reads resting labels mid color transition after the theme flips
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-26T05:27:48.897Z
updated_at: 2026-11-26T05:27:48.897Z
---
tests/test_overview_legend_hover_chrome.py failed once in PR #869's CI (chrome 3.13 shard 2/6, run 45760854674) at _entry_marked(dark, 'the dark page'): otherEntriesAtRest was false. It passed 3 of 3 locally at the same head, and main's runs before and after were green. PR #869 changes only ref-chip CSS and does not touch the overview.

Suspected mechanism, read from the code and not yet reproduced: .file-type-summary-legend-label has 'transition: color var(--viz-hover-grow-duration)' (builtin_plugins/folder/file_type_summary.css) and its item has none. tests/dom/overview-legend-hover-chrome.mjs sets documentElement.dataset.theme = 'dark', moves the pointer to the Python entry, and reads at once. restingEntries compares each resting label's computed color with its item's; the item's flips with the theme at once while the label's is still in its transition, so they differ until it ends. On a slow runner the read can land inside it.

To confirm: read the labels' getAnimations() or sample the colors right after the flip. Likely fix: have the reading wait for the labels' transitions to finish after the theme flip, as it would for any other transition, before it compares.
