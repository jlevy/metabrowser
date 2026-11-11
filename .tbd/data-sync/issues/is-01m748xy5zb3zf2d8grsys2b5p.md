---
type: is
id: is-01m748xy5zb3zf2d8grsys2b5p
title: Persist recent and added roots in metab, served by a roots route
kind: feature
status: open
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m748xsest94amc9cyx26j1zk
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:02:55.422Z
updated_at: 2026-11-11T22:28:38.601Z
---
Phase 4. Recent and added roots move from the app's defaults into metab state with provenance; a route serves them so a browser tab gets the same switcher; list, add, and remove commands with goldens; the security policy for adding roots applies (see the security models in the 2026-11-08 brief).

## Notes

2026-11-11, from review A on jlevy/metabrowser#352 (fixed in 083af6f8): the chosen root-admission security model decides which persisted roots skip Phase 3's in-app confirmation; this bead now blocks the switcher (mb-9lf4).
