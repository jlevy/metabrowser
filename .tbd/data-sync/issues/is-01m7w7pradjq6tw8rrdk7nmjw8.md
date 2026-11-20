---
type: is
id: is-01m7w7pradjq6tw8rrdk7nmjw8
title: Branch chooser loses its scroll and focus when the Files toolbar redraws between a scroll and its scroll event
kind: bug
status: closed
priority: 3
version: 6
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-20T10:23:17.835Z
updated_at: 2026-11-20T17:25:28.403Z
closed_at: 2026-11-20T17:25:28.401Z
close_reason: "Mechanism (toolbar refill between a scroll and its scroll event restored the stale drawnAt) fixed on main by #658 (7877276e8, holdScroll); duplicate fix #661 closed."
resolution: null
duplicate_of: null
---
PR 648 run 44715405301 job 136218068873: tests/test_ref_selector_pulls_chrome.py::test_rows_with_a_pull_request_are_placed_by_their_own_height_in_chrome failed at line 213 (the session ran past SESSION_TIMEOUT_S). The same code passed on PR 654, which contains PR 648. Unrelated to the change under test; rerun once.

## Notes

Second failure on PR 655 run 44771960710 job 136411797385 (chrome 3.13, 1/4): line 207, middle centerIndex 5 != expectedIndex 301 (the long list's center row). Two different assertions in one module across two runs; the module is flaky under CI load.
