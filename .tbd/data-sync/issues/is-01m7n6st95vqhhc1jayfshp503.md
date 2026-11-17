---
type: is
id: is-01m7n6st95vqhhc1jayfshp503
title: "test_files_totals_stable_chrome: 'none unknown slow 180px dark' layout shift 2e-05 on 3.14t (run 44052069066, #509)"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
created_at: 2026-11-17T16:52:48.547Z
updated_at: 2026-11-17T16:52:48.547Z
---
Recurred after mb-onuj closed: AssertionError layout shift 2e-05, '81 held' -> '155 no ignored files' rows at tests/test_files_totals_stable_chrome.py:166 on test (3.14t), PR #509 run 44052069066 job 133932082441. Passed on rerun. Find whether it is a real sub-pixel shift or a threshold/timing flake.
