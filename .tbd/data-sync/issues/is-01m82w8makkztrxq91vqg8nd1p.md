---
type: is
id: is-01m82w8makkztrxq91vqg8nd1p
title: Use the shared commit copy treatment in the folder details menu
kind: bug
status: closed
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/716
    at: 2026-11-23T00:34:28.937Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-23T00:18:01.681Z
updated_at: 2026-11-23T00:59:20.602Z
started_at: 2026-11-23T00:18:56.356Z
closed_at: 2026-11-23T00:59:20.602Z
close_reason: "Independently reviewed and merged in #716 at ca2beb4cb. Real Chrome and exact hosted tests passed for nested folder menus, commit copy, shared caret motion and repeat-click dismissal."
resolution: null
duplicate_of: null
---
Render the Commit row as the design-system monospace revision with the existing copy action shown on hover and keyboard focus. Preserve the clear label and copy the full revision when it is known.
