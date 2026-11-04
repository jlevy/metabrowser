---
type: is
id: is-01m6f55s2rxqn1fc5gntccjv9g
title: A pull-request URL ending in /files opens on Conversation
kind: bug
status: closed
priority: 1
version: 4
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-02T22:13:14.964Z
updated_at: 2026-11-04T17:14:29.815Z
closed_at: 2026-11-04T17:14:29.815Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Found 2026-11-02 writing the guide. metab https://github.com/owner/repo/pull/123/files serves /pull/123: builtin_plugins/github/urls.py near line 472 drops the tail and the banner prints the Conversation address. A reader who copies a Files changed URL from GitHub lands on the wrong tab. Make the served address honor /files, as a blob URL keeps its line anchor, and update docs/reviewing-pull-requests.md and the command-line section, which currently document the behavior as it stands.

## Notes

2026-11-03: fixed on PR 280 (b2e56b2b): a /pull/<n>/files URL selects Files changed, as the Serving line and pull_tab say. Reviewed in round 1. Closes when the stack merges.
