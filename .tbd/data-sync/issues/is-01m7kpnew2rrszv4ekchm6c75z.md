---
type: is
id: is-01m7kpnew2rrszv4ekchm6c75z
title: "CI speed 3.1: cut the serial tier's fixed waits, starting with the three pull-header cases at 10.2 s each and the 124 s of test_transitions_instrument.py"
kind: task
status: open
priority: 3
version: 7
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/496
    at: 2026-11-20T17:02:11.172Z
labels: []
dependencies: []
parent_id: is-01m7wysgm9rg3fdch55nst1wrn
created_at: 2026-11-17T02:51:34.145Z
updated_at: 2026-11-20T19:15:59.575Z
extensions: {}
---
Phase 3 of plan-2026-11-16-fast-ci.md. Medians over 18 runs of test (3.13): test_transitions_instrument.py 123.9 s, test_process_group.py 57.2 s, test_github_pull_header_chrome.py 39.5 s, test_files_tab_chrome.py 38.0 s, test_raw_profile_cache_chrome.py 28.0 s, test_changed_file_rows_chrome.py 25.4 s. The three cases of test_the_pull_header_keeps_its_box_in_chrome take 10.24, 10.25, and 10.26 s, which suggests a fixed wait; mb-zv5s (a Chrome session that outlives its result) may be the same cause. Measure where each test's time goes before changing it, and keep every assertion.
