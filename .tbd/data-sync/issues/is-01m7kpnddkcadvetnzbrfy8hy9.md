---
type: is
id: is-01m7kpnddkcadvetnzbrfy8hy9
title: "Chrome flake: 'Chrome wrote no DevTools port' from launchChrome in tests/dom/chrome-session.mjs failed tests/test_changed_file_rows_chrome.py twice and passed on a rerun of the same commit"
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
created_at: 2026-11-17T02:51:32.658Z
updated_at: 2026-11-17T02:51:32.658Z
---
Found by the CI speed assessment (research-2026-11-16-ci-speed.md). Runs 43915467225 attempt 1, test (3.14), and 43917125328 attempt 3, test (3.13): test_both_trees_of_changed_files_draw_one_row_in_chrome, 'Error: Chrome wrote no DevTools port at launchChrome (tests/dom/chrome-session.mjs:51)'. Both runs went green on a rerun with no change. The helper is shared by every Chrome-tier module, so the cause is not that test's. Find whether Chrome exited or the 30 s deadline passed, reproduce under load with the loop mb-alff and mb-nvo0 used, and fix the cause.
