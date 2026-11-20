---
type: is
id: is-01m7r8wednnec21h8ac7xbmed6
title: "App: use the GitHub status check to tell sign-in, scope, and access failures apart, and recheck without restarting"
kind: feature
status: open
priority: 3
version: 4
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/571
    at: 2026-11-20T17:05:45.247Z
labels:
  - linear
dependencies: []
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
created_at: 2026-11-18T21:26:55.155Z
updated_at: 2026-11-20T18:01:10.430Z
extensions:
  linear:
    id: 4e45c967-9dcc-4714-8ea9-7e490105f18e
    linked_at: 2026-11-20T18:01:10.427Z
---
Follow-up to mb-m0ry, which built the app's GitHub failure states without depending on mb-si2g.

What mb-m0ry reads today (apps/macos/Sources/ShellCore/Folders/GitHubFailure.swift): the state in the `Error:` line a failed repository start ends with. A clone reports a signed-out gh, an account without access, and a sign-in without the repo scope as `not_found_or_private`, like a missing repository, so the app shows one "Not found, or this account cannot read it" state whose steps start with `gh auth status`. `not_logged_in` and `gh_missing` already map to their own states, but no start fails with `not_logged_in` today.

Once mb-si2g's check before a first clone stops a start with the reason:
- Check what that `Error:` line names. If it ends with `(not_logged_in)` as GhError states do, the app's "GitHub CLI is not signed in" state shows with no change; otherwise map its form. Add its scope state, if it has one, to `GitHubFailure.kinds` with its own steps (`gh auth refresh --hostname github.com --scopes repo`), and narrow `notFound`'s explanation and steps to what the clone can still not tell apart. Extend `tests/test_macos_app_pins.py` to build those lines from mb-si2g's code.
- Recheck on activation (`FolderSession.recheckAfterActivation`) restarts the failed start each time the app becomes active. With mb-si2g's route or `--doctor --json` GitHub section, ask the status first and restart only when it changed, which saves a failed clone's requests to GitHub per switch.

Related, found while building mb-m0ry:
- A pull request link whose pull request could not be read opens the default branch and says so only on the serve banner (`pull_request: N (not opened: ... (not_logged_in); the pin is the default branch)`, see tests/golden/cli-github-pull-refresh.txt). The app says nothing; an alert like LinkSelection's for a missing ref would.
- After installing gh, the app needs Settings > Find Again before a server's PATH has it. The `noGitHubCLI` state says so; a recheck could re-resolve the tools instead.
