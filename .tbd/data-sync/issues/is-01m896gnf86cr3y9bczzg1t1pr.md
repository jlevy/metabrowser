---
type: is
id: is-01m896gnf86cr3y9bczzg1t1pr
title: "CI plan: run the files-totals fail-open Chrome case on PRs that touch the shell startup path, even while main is green"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-25T11:12:37.350Z
updated_at: 2026-11-25T11:12:37.350Z
---
#835 broke the shell's fail-open load (filter-controls.js failed), but its PR CI ran test-chrome-fast with --skip-slow (devtools/ci_plan.sh:265, SLOW_TEST_S=20 s in tests/suite_tiers.py:80), which drops tests/test_files_totals_stable_chrome.py (~120 s); only main's full run caught it (mb-1t9k, fixed in #839). Consider pulling that test (or its failOpen case) into the plan when a PR changes eager shell scripts (app.js, filter-controls.js, the startup bundle).
