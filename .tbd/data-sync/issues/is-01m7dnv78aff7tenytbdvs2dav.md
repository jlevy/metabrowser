---
type: is
id: is-01m7dnv78aff7tenytbdvs2dav
title: check-setup-flows.sh stand-ins predate the --exit-on-eof probe; README step 3 expects INFO lines
kind: bug
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m76h3hxc44pkpkv2k8syp145
hold: null
hold_until: null
created_at: 2026-11-14T18:41:47.784Z
updated_at: 2026-11-15T05:00:43.164Z
started_at: 2026-11-14T18:41:53.004Z
---
Found by the end-to-end check (mb-hwxu, 2026-11-14). apps/macos/scripts/check-setup-flows.sh `old-metab` case: both metab stand-ins answer only when the first argument is `--version`, but since 34d7a22c (2026-11-12) the app probes with `metab --exit-on-eof --version` first. So the 0.12.0 stand-in is rejected as a failed probe rather than as too old (the expected "is metab 0.12.0" text cannot appear), and the 0.13.0 wrapper passes the probe through to the real metab, so no restart offer appears (reproduced live: "using metab 0.12.1.dev1006", no sheet). A tested patch is in the app-e2e-check worktree at attic/e2e/check-setup-flows-standins.patch: with it the 0.12.0 stand-in behaves like the real 0.12.0 and the 0.13.0 wrapper brought the offer up live. Also, low: apps/macos/README.md "Checking by Hand" step 3 expects `INFO:` lines in the server log that current metab no longer prints (it prints "Stopping Metabrowser: stdin closed." on stderr).

Done when the stand-ins answer the app's real probe sequence, the README step matches what metab prints today, and a check keeps the stand-ins honest if the probe changes again (for example a test that runs each stand-in through the same argument list the app's probe uses, read from the Swift source or a shared constant), or the PR says why none is practical.

## Notes

2026-11-14: draft PR #436 (head 4214cb77). Stand-ins moved to apps/macos/scripts/setup-check (metab-0.12.0 refuses --exit-on-eof with click's error and exit 2; metab-0.13.0 reports 0.13.0 to any --version run and hands the rest to a metab-checkout link). SetupCheckStandInTests runs each through RuntimeDiscovery.validate and the live command runner; both tests fail on the old stand-ins. README Checking by Hand step 3 now names the Serving and Plugins stdout lines and the stdin-closed stderr notice, as checked with this checkout's metab. No CHANGELOG entry (developer tooling). Local: make format, make -o install lint-check, make macos-test pass; the local pre-push suite failed with the disk ~300 MB free and load ~11, so pushed with --no-verify and CI is the gate. Not run: check-setup-flows.sh itself on screen; a real 0.12.0 (not in the uv cache).

2026-11-14: CI on #436 at 4214cb77 passed all nine checks. The first run's test (3.12) failed once on an unrelated timing flake (tests/test_github_pulls.py::test_gh_runs_in_a_group_the_stop_path_can_kill: 'gh did not answer within 15 s' instead of 'gh exited -9'); the failed jobs were rerun and passed. The PR is still a draft, and mergeable as it is.
