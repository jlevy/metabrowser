---
type: is
id: is-01m7n6st95vqhhc1jayfshp503
title: "test_files_totals_stable_chrome: 'none unknown slow 180px dark' layout shift 2e-05 on 3.14t (run 44052069066, #509)"
kind: bug
status: open
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
created_at: 2026-11-17T16:52:48.547Z
updated_at: 2026-11-17T17:00:39.596Z
---
Recurring Chrome flake: tests/test_files_totals_stable_chrome.py:166 'none unknown slow 180px dark: layout shift 2e-05', rows '... held' -> '... no ignored files'. Seen on PR #509 run 44052069066 (3.14t) and on main after #514 at 4eb299fd1, run 44128402569 (3.12). Both passed on rerun. It reds main, so it blocks merges.
