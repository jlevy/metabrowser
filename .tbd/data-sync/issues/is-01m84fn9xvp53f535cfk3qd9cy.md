---
type: is
id: is-01m84fn9xvp53f535cfk3qd9cy
title: "Treemap: measure how headers and frames distort area comparisons across folders"
kind: task
status: closed
priority: 2
version: 8
spec_path: docs/project/specs/active/plan-2026-11-22-treemap-canvas-granularity.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/763
    at: 2026-11-23T17:32:32.606Z
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T15:16:14.394Z
updated_at: 2026-11-25T02:16:20.156Z
started_at: 2026-11-23T16:59:33.226Z
closed_at: 2026-11-23T18:01:51.927Z
close_reason: "Layer 7 PR #763: folders sized for header and frame; measured and verified in Chrome"
resolution: null
duplicate_of: null
---
A folder's header strip and frame come out of its own area before its children are laid out, so a file in a small or deeply nested folder draws smaller than a file of the same size in a large, shallow one. Measure it on a real repository (each file cell's share of the map's area against its share of the total), and decide whether the layout should compensate, for example by sizing each folder for its value plus its header and frame. Asked about in manual testing.

## Notes

Layer 7, PR #763 (claude/treemap-chrome-compensation): folders weighted by value plus subtree chrome (estimateChrome, chromeRounds 4; one corrective layout under chromePassMaxCells 5000). p10 area/value over median 0.55->0.98 bytes, 0.51->0.97 files at 1100x560; dense map (23k cells) estimate only, deep files 0.47-0.71 from 0.27-0.38. Live Treemap verified in Chrome.
