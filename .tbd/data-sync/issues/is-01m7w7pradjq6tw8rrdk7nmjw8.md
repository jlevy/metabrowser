---
type: is
id: is-01m7w7pradjq6tw8rrdk7nmjw8
title: "Flake: test_ref_selector_pulls_chrome row-height session timed out in CI chrome (3.13, 4/4)"
kind: bug
status: open
priority: 3
version: 2
labels: []
dependencies: []
created_at: 2026-11-20T10:23:17.835Z
updated_at: 2026-11-20T16:25:40.855Z
---
PR 648 run 44715405301 job 136218068873: tests/test_ref_selector_pulls_chrome.py::test_rows_with_a_pull_request_are_placed_by_their_own_height_in_chrome failed at line 213 (the session ran past SESSION_TIMEOUT_S). The same code passed on PR 654, which contains PR 648. Unrelated to the change under test; rerun once.

## Notes

Second failure on PR 655 run 44771960710 job 136411797385 (chrome 3.13, 1/4): line 207, middle centerIndex 5 != expectedIndex 301 (the long list's center row). Two different assertions in one module across two runs; the module is flaky under CI load.
