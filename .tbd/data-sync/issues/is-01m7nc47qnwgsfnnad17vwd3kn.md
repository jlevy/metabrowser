---
type: is
id: is-01m7nc47qnwgsfnnad17vwd3kn
title: "Flaky: test_files_totals_stable_chrome fails on a near-zero layout shift under load"
kind: bug
status: closed
priority: 2
version: 2
labels:
  - tests
  - flaky
dependencies: []
created_at: 2026-11-17T18:25:52.884Z
updated_at: 2026-11-20T17:00:05.682Z
closed_at: 2026-11-20T17:00:05.680Z
close_reason: "Fixed by PR #521 (mb-j4ts): the 2e-05 shift was the folder header's age label redrawing 'just now' as '1m ago'; the test's folders are now dated three days back"
resolution: null
duplicate_of: null
---
tests/test_files_totals_stable_chrome.py:166 fails intermittently with a layout shift of 2e-05 ("none unknown slow 180px dark", the ignored line held then "No ignored files"). Reproduced on origin/main c6aa02085 (1 of 3 local runs at load average about 8) and on PR #506 CI (test 3.14). The shift is sub-pixel: either the measurement needs a tolerance justified by measurement, or the held line and the final line differ by a fraction of a pixel and the layout should be made exact.
