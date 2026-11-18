---
type: is
id: is-01m7nnxsky2r2jf9d5n3ac3vty
title: "App: clone progress, GitHub failure states with Copy and Retry, recheck on activation"
kind: feature
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
hold: null
hold_until: null
created_at: 2026-11-17T21:17:07.581Z
updated_at: 2026-11-18T21:30:41.154Z
started_at: 2026-11-18T21:02:10.893Z
---
Phase 1, apps/macos. Status view shows the clone report from stderr; failure states show the reason and command (SetupGuide pattern); re-read GitHub status when the app becomes active.

## Notes

2026-11-18, checked against main a1100bca6. Not built. Related pieces from jlevy/metabrowser#539: a repository start is given up only after StartupDeadline sees no output growth for startupTimeout or repositoryStartupLimit passes, so a long clone is not abandoned; StartingView says when a start waits behind another repository's; the clone confirmation names the gh sign-in. Remaining as scoped: StatusView shows no clone progress line while starting, FailureView shows generic recent output with Retry but no GitHub failure state or copyable command, and nothing rechecks GitHub status on activation (needs mb-si2g).

2026-11-18, built in jlevy/metabrowser#571 (branch claude/app-clone-progress), without depending on mb-si2g. ShellCore StartProgress parses metab's existing clone report (cloning/status/cloned/cached lines and "reading pull request N"); ServerSupervisor.startProgress publishes it while a repository starts and StartingView shows it. ShellCore GitHubFailure diagnoses metab's last "Error:" line by its state (not_logged_in, gh_missing, not_found_or_private with or without the gh install hint, and the network states plus rate_limited) into four kinds with headline, explanation, and gh steps; FailureView shows them with per-command Copy, Copy Message, and Retry. AppDelegate.applicationDidBecomeActive restarts only repositories whose failure is GitHub's (FolderSession.recheckAfterActivation). No metab change, golden, or minimumRelease bump: tests/test_macos_app_pins.py holds the Swift samples to metab's own CloneReport, saying_while_waiting, describe_remote_failure, and gh messages. Hand checks: qa-macos-app-hand-checks.md GitHub Links 19-24. Limits: a clone cannot tell signed out, missing scope, and no access apart (all not_found_or_private), so those fold into the not-found state's steps; not_logged_in is mapped but no start produces it today; the recheck restarts the start. Follow-up mb-1rl3 records what to change once mb-si2g lands.
