---
type: is
id: is-01m7kpnddkcadvetnzbrfy8hy9
title: "Chrome flake: 'Chrome wrote no DevTools port' from launchChrome in tests/dom/chrome-session.mjs failed tests/test_changed_file_rows_chrome.py twice and passed on a rerun of the same commit"
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
hold: null
hold_until: null
created_at: 2026-11-17T02:51:32.658Z
updated_at: 2026-11-18T03:46:45.922Z
started_at: 2026-11-18T03:46:45.922Z
---
Found by the CI speed assessment (research-2026-11-16-ci-speed.md). Runs 43915467225 attempt 1, test (3.14), and 43917125328 attempt 3, test (3.13): test_both_trees_of_changed_files_draw_one_row_in_chrome, 'Error: Chrome wrote no DevTools port at launchChrome (tests/dom/chrome-session.mjs:51)'. Both runs went green on a rerun with no change. The helper is shared by every Chrome-tier module, so the cause is not that test's. Find whether Chrome exited or the 30 s deadline passed, reproduce under load with the loop mb-alff and mb-nvo0 used, and fix the cause.

## Notes

2026-11-18 coordinator: now the most frequent CI flake under the split CI: seen today on #525 (test 3.12), #516 attempt 2 (test 3.14), #506 (3.14t, 6 tests), and #544 at 181cffaed (chrome (3.14, 4/4), diff-markdown-fold-chrome.mjs:312). Each run of the new CI starts 4+ Chrome shards on cold runners, so a launch flake now fails ci-ok often. Raise to P1: make launchChrome retry a launch that writes no DevTools port (bounded, with the stderr tail in the error), and record the failure rate.
