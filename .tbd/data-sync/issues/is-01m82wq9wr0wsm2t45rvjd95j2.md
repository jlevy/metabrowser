---
type: is
id: is-01m82wq9wr0wsm2t45rvjd95j2
title: Open new macOS windows at 92 percent of the usable screen height
kind: bug
status: closed
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/717
    at: 2026-11-23T00:34:42.249Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-23T00:26:02.511Z
updated_at: 2026-11-23T01:26:40.508Z
started_at: 2026-11-23T00:27:57.004Z
closed_at: 2026-11-23T01:26:40.493Z
close_reason: "Independently reviewed and merged in #717 at f7db33b46. Thirty-six focused Swift tests and exact general and macOS hosted checks passed. The active development build includes the default. Saved window geometry remains authoritative on restore."
resolution: null
duplicate_of: null
---
Set the default initial window height to 92 percent of its display’s visible frame. Preserve previously saved window sizes, window placement and width, and existing screen-bound and minimum-size handling.
