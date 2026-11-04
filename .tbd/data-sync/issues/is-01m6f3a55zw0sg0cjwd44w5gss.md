---
type: is
id: is-01m6f3a55zw0sg0cjwd44w5gss
title: Routes that name a number
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3a5ksq0g3qa148nz5q4f0
parent_id: is-01m6f39wqb7nqd20w7z5vpw9vh
hold: null
hold_until: null
created_at: 2026-11-02T21:40:41.278Z
updated_at: 2026-11-04T17:14:29.541Z
started_at: 2026-11-02T22:56:09.915Z
closed_at: 2026-11-04T17:14:29.541Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
pull, pull-refresh, and pull-markdown take a required number, with no fallback. no_pull_request and other_number go away, not_cached is added, _require_served_pull is removed, and every transcript is regenerated in one commit.

## Notes

Done on claude/pulls-2-open-any, PR https://github.com/jlevy/metabrowser/pull/281, commit 863df71b. pull, pull-refresh, and pull-markdown take a required number. no_pull_request and other_number are gone; not_cached for a valid number with no record, not_github for a server with no GitHub repository. _require_served_pull removed. pin_ref added. Transcripts regenerated in that commit; a pull-request URL's commands differ by the number in the route, pin_ref, and status_route.
