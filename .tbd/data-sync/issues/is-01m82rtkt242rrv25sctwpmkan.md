---
type: is
id: is-01m82rtkt242rrv25sctwpmkan
title: Use muted design-system text for embedded progress status
kind: bug
status: in_progress
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/713
    at: 2026-11-22T23:46:24.722Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-22T23:17:56.613Z
updated_at: 2026-11-23T00:02:36.827Z
started_at: 2026-11-22T23:27:41.999Z
---
The Agents overview Indexing session details message uses normal text ink. Use the existing muted progress styling for embedded status, document the rule in the design system, and verify both appearances while preserving count announcements and layout.

## Notes

The Agents overview uses the shared muted token, with the existing neutral spinner and count. Chrome verified light and dark themes with 4.62:1 and 7.81:1 contrast. The design-system guide documents this presentation for embedded progress. Verified development preview at 9c6e73b47. PR #713 pending the hosted main gate.
