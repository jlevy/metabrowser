---
type: is
id: is-01m7raea4zb9dg4bjt8xw1r5ka
title: Present a pull-request URL only after the GitHub status check passes
kind: feature
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
labels: []
dependencies: []
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
created_at: 2026-11-18T21:54:09.182Z
updated_at: 2026-11-18T21:54:09.182Z
---
Follow-up to mb-si2g, which left this part of the plan's Sign-In 'Before the work' item out of scope. The plan says that metab URL and --present URL both check sign-in before a first clone or a pull request read. mb-si2g covered metab URL: GithubProvider.check_first_clone runs gh_status.github_status(version=False), and a pull-request URL in SIGN_IN_STATES stops with GithubSignInRequiredError ('...: <message> (<state>); nothing was cloned'). A pull request with no usable cached record also stops when its read fails in one of those states (PullRequestUnavailableError.blocking -> CLIError in cli/selection.py open_pull_for_cli). --present (cli/present.py) only resolves the target and hands it to the app or a browser, so a signed-out pull-request URL fails later, inside the app's start. To do: for a GitHub pull-request target, have --present run the same check before delivery and stop with present's exit code for a refused target and the fix step; --dry-run --json reports the status object. Add goldens using tests/fixtures/github-status/gh (FAKE_GH_STATUS variants) and update docs/command-line.md's --present section.
