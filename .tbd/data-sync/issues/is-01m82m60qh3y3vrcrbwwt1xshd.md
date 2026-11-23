---
type: is
id: is-01m82m60qh3y3vrcrbwwt1xshd
title: Use clean GitHub repository and branch links for repository browsing
kind: bug
status: closed
priority: 1
version: 5
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/708
    at: 2026-11-22T22:37:05.110Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-22T21:56:47.471Z
updated_at: 2026-11-23T00:16:21.074Z
started_at: 2026-11-22T21:57:25.095Z
closed_at: 2026-11-23T00:16:21.074Z
close_reason: "Independently reviewed and merged in Metabrowser #708 at 5c4afed47 after its exact hosted run and current main CI passed. Confirmed in the active Mac development preview."
resolution: null
duplicate_of: null
---
At the default repository root, View on GitHub and its menu should target the clean repository URL. Use a readable named ref for known branches and reserve immutable commit hashes for specific historical items, such as a commit. Preserve correct source repository/fork identity and existing PR destinations. Track the server counterpart change with direct route and browser coverage.

## Notes

Independent senior review reproduced an unproven same-name origin branch mapping and Unicode Git ref delimiter failures. Both fixed and independently rechecked at candidate 032d89bac. Verified with real repository/branch/commit CLI destinations and installed the current development preview.
