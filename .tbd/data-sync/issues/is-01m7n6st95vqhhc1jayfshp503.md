---
type: is
id: is-01m7n6st95vqhhc1jayfshp503
title: "test_files_totals_stable_chrome: 'none unknown slow 180px dark' layout shift 2e-05 on 3.14t (run 44052069066, #509)"
kind: bug
status: closed
priority: 1
version: 4
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
hold: null
hold_until: null
created_at: 2026-11-17T16:52:48.547Z
updated_at: 2026-11-17T18:08:13.363Z
started_at: 2026-11-17T17:12:37.108Z
closed_at: 2026-11-17T18:08:13.362Z
close_reason: "PR #521 at 638cda7a9: the shift was the main view's folder header (span.folder-header-summary), not the Files panel. Its refresh a debounce after the stream snapshot redrew the fixture folder's age 'just now' as '1m ago' when the folder's first minute ended inside the load, moving the right-aligned summary 7.9 px (1.77e-5). The test now dates the served trees three days back and prints each shift's source. Before: harness 20/20 shifted under CI's order, real test 2/5 failed locally; after: harness 0/20, real test 0/10."
resolution: null
duplicate_of: null
---
Recurring Chrome flake: tests/test_files_totals_stable_chrome.py:166 'none unknown slow 180px dark: layout shift 2e-05', rows '... held' -> '... no ignored files'. Seen on PR #509 run 44052069066 (3.14t) and on main after #514 at 4eb299fd1, run 44128402569 (3.12). Both passed on rerun. It reds main, so it blocks merges.
