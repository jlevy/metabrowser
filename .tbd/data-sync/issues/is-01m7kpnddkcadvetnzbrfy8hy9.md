---
type: is
id: is-01m7kpnddkcadvetnzbrfy8hy9
title: "Chrome flake: 'Chrome wrote no DevTools port' from launchChrome in tests/dom/chrome-session.mjs failed tests/test_changed_file_rows_chrome.py twice and passed on a rerun of the same commit"
kind: bug
status: closed
priority: 1
version: 13
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/554
    at: 2026-11-20T17:01:20.579Z
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
hold: null
hold_until: null
created_at: 2026-11-17T02:51:32.658Z
updated_at: 2026-11-20T19:15:59.605Z
started_at: 2026-11-18T03:46:45.922Z
closed_at: 2026-11-18T07:16:11.879Z
close_reason: "Fixed by #554 (merged fb3e4809d): Chrome warm-up before the run; A11 follow-up in mb-bl54."
resolution: null
duplicate_of: null
extensions: {}
---
Found by the CI speed assessment (research-2026-11-16-ci-speed.md). Runs 43915467225 attempt 1, test (3.14), and 43917125328 attempt 3, test (3.13): test_both_trees_of_changed_files_draw_one_row_in_chrome, 'Error: Chrome wrote no DevTools port at launchChrome (tests/dom/chrome-session.mjs:51)'. Both runs went green on a rerun with no change. The helper is shared by every Chrome-tier module, so the cause is not that test's. Find whether Chrome exited or the 30 s deadline passed, reproduce under load with the loop mb-alff and mb-nvo0 used, and fix the cause.

## Notes

2026-11-18 coordinator: now the most frequent CI flake under the split CI: seen today on #525 (test 3.12), #516 attempt 2 (test 3.14), #506 (3.14t, 6 tests), and #544 at 181cffaed (chrome (3.14, 4/4), diff-markdown-fold-chrome.mjs:312). Each run of the new CI starts 4+ Chrome shards on cold runners, so a launch flake now fails ci-ok often. Raise to P1: make launchChrome retry a launch that writes no DevTools port (bounded, with the stderr tail in the error), and record the failure rate.

2026-11-18 claude/chrome-launch-retry, PR #554 at 6fc79d6a5: newest 200 ci.yml runs (44041121764 to 44232615626, all attempts; 153 failed-job logs plus every Chrome-tier job log). 8 jobs failed "Chrome wrote no DevTools port" (1 split chrome (3.14, 4/4) on #544, 7 whole-suite test jobs); all at the 30 s bound with Chrome still running (calls 30.1-33.3 s), all the job's first Chrome test; Chrome's stderr was discarded, so no log holds it; no profile or port collision (mkdtemp profile and port 0 already, tier runs serially). Cold first start: in 150 chrome jobs opening with a Chrome-only test, 102 were cold, 4.6-28.8 s over warm (median 9.3); the next test is warm after a finished slow start. A cut-off start leaves the next start cold (13.7-67 s over warm, or cut off again; five in a row in run 44175708209 3.14t), so a 30 s kill-and-retry would have saved at most 1 of 8. Fix: a pytest_runtestloop warm-up start (WARM_UP_BOUND_S) before the first Chrome test; launchChrome bounds the whole start, keeps the stderr tail, says exit vs deadline, kills and sweeps a failed start, retries once (START_ATTEMPTS); every start goes to METABROWSER_CHROME_STARTS and the terminal summary prints a "chrome starts:" line (the failure rate per run). Not reproduced locally (warm Mac, 30/30 before and after). Not closed: CI on #554 and later runs' "chrome starts:" lines are the evidence.

2026-11-18 review A on #554 addressed in c0318d239 (dispositions https://github.com/jlevy/metabrowser/pull/554#issuecomment-6970328746): a start is made again only when its Chrome exited, never after a hang at START_BOUND_MS (bead mb-sicb holds the unblock condition); the warm-up's outcome is written to the terminal at once; nested-session tests hold the hook; signal, silent-port and silent-socket cases added; counts de-duplicated (824 of 866 logs; 132 jobs, 90 cold, 4.7-28.8 s over warm, median 9.1); CHROME_TESTS made complete with a check. Follow-up bead mb-bl54 retires per-test cold-start allowances.
