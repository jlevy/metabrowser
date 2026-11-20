---
type: is
id: is-01m7nnxnedw2fvq6ef6p0ka73z
title: "GitHub status check: gh path, version, account, scopes; --doctor section, route, and preflight"
kind: feature
status: closed
priority: 2
version: 10
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/581
    at: 2026-11-20T17:05:57.514Z
delegate: claude-code@spud10
labels:
  - linear
dependencies:
  - type: blocks
    target: is-01m7nnxsky2r2jf9d5n3ac3vty
  - type: blocks
    target: is-01m7r8wednnec21h8ac7xbmed6
  - type: blocks
    target: is-01m7raea4zb9dg4bjt8xw1r5ka
  - type: blocks
    target: is-01m7raej2pvscj726pn3nsh2cy
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
hold: null
hold_until: null
created_at: 2026-11-17T21:17:03.309Z
updated_at: 2026-11-20T17:05:57.521Z
started_at: 2026-11-18T21:02:21.507Z
closed_at: 2026-11-19T01:12:00.549Z
close_reason: "Landed in #581"
resolution: null
duplicate_of: null
---
Phase 1. gh auth status --active --hostname github.com --json hosts; report GhFailureState; registered route plus --doctor --json; check before a first clone or pull request read and stop with the fixing command instead of a silent fallback; read token scopes where gh reports them.

## Notes

2026-11-18, built in jlevy/metabrowser#581 (branch claude/github-status-check). builtin_plugins/github/gh_status.py runs gh auth status --active --hostname github.com --json hosts (and gh --version for the doctor and the route). States: ok, gh_missing, gh_too_old, not_logged_in, missing_scope, network_error, gh_failed. SIGN_IN_STATES = gh_missing, gh_too_old, not_logged_in. The answer is kept GH_STATUS_TTL_S=10 s per gh path and configuration, single-flight per event loop, and bounded by GH_STATUS_TIMEOUT_S. Readers: metab --doctor (a github section; --json key github; never changes the exit status), POST /api/plugin/github/status (body {} or {"fresh": true}), and GithubProvider.check_first_clone. A pull-request URL in a sign-in state stops before cloning: Error line '...cannot be read: <message> (<state>); nothing was cloned'. An uncached pull request whose read fails in a sign-in state stops with exit 1 ('Error: pull request N of URL: <message> (<state>)') instead of falling back (PullRequestUnavailableError.blocking). missing_scope keeps the reason not_found_or_private and adds the gh auth refresh --scopes repo hint to the clone hint and to the pull-request message. For mb-1rl3: both Error lines end a clause with (<state>), so GitHubFailure.state(in:) reads them as is; there is no new PullDataState for the scope. Follow-ups: mb-1mw0 (--present URL check), mb-29nb (page surface).
