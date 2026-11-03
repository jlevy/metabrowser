---
type: is
id: is-01m6f3abb5ys26ghefzy1d3kcs
title: Identity and a source with no store
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3abz4cv8g936k4ry94ygb
parent_id: is-01m2nz9gwd4wyxmrpx49cp9yck
hold: null
hold_until: null
created_at: 2026-11-02T21:40:47.588Z
updated_at: 2026-11-03T07:15:47.101Z
started_at: 2026-11-03T07:01:12.887Z
---
The repository resolved per request from the served root's context, validated by the plugin's grammar. The first write publishes an unattached source, reads create nothing, and records carry no_store.

## Notes

2026-11-03 HANDOFF: done and tested on wip/pulls-5-checkout (24a95778), not on #288's branch. The repository comes from builtin_plugins/github/checkout.py: discover_repository_context reduced through GithubUrlReducer and parse_repository_url, resolved off the loop once per (root, home). An HTTPS and an SSH remote, and a subdirectory, share one identity; a fork lists its origin; a remote the grammar refuses (under_score), and a non-GitHub one, answer not_github. A read creates nothing (no home, no source). The first write calls claim_source, then publish_unattached_source in cache/acquire.py, which writes source.yml alone. A record without a store carries unavailable.comparison no_store, and a server with a store answers it stale. Evidence: tests/golden/cli-github-checkout.txt and tests/test_github_checkout.py. Missing: the no-gh tryscript over the --checkout fixture home, and the map rows. See mb-cbak.
