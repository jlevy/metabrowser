---
type: is
id: is-01m7kpnebx9r14tv5m3e3wrfwj
title: "Flakes seen once in the CI sample: the metadata line in test_nav_metadata_chrome.py, the gh stop in test_github_pulls.py, and PrivateStorageError in test_github_pull_files.py; reproduce each and fix or split out"
kind: bug
status: open
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-17T02:51:33.629Z
updated_at: 2026-11-20T17:19:10.390Z
---
Found by the CI speed assessment (research-2026-11-16-ci-speed.md). (1) Run 43699500311 attempt 1, test (3.13): test_every_tabs_metadata_line_is_one_component_in_chrome; green on rerun. (2) Run 43631624693 attempt 1, test (3.12): test_gh_runs_in_a_group_the_stop_path_can_kill expected 'gh exited -9' and got 'gh did not answer within 15 s'; green on rerun; not a Chrome test. (3) Run 43582321399, test (3.13), on main, not rerun, so not proven a flake: tests/test_github_pull_files.py:318 raised PrivateStorageError, 'it was replaced while it was being checked', which may be a race in the product. Split a bead out for any that reproduces.

## Notes

2026-11-17: item (2) is traced and fixed in de96415af on claude/ci-parallel-tests (jlevy/metabrowser#499): gh can start before its spawn returns and registers its group, and kill_live_process_groups leaves an unregistered group to stop_process_groups by design, so the test stopped too early and gh ran to its 15 s deadline. The test now waits for the registration; it reproduced on 3.14t in CI run 44032890807 after d5a05e20 removed the stand-in's mv. Items (1) and (3) remain.
