---
type: is
id: is-01m2f00j0t5r01h85mm1fpcwtm
title: "PR #111 review R3: CHANGELOG J/K entry overclaims coverage and Help listing"
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m2f006s6gd550e7knf1qw3m6
created_at: 2026-09-14T03:40:13.721Z
updated_at: 2026-09-14T04:22:37.395Z
closed_at: 2026-09-14T04:22:37.394Z
close_reason: "Fixed in e277e7a9 (PR #111): CHANGELOG names the file tree (Files and Recent) and Git history and limits the Help claim to the file tree; README and design-system already accurate."
resolution: null
duplicate_of: null
---
PR #111 review R3 (Low). CHANGELOG.md:24-29 says 'wherever the arrow keys step through a list' and 'Help lists them beside the arrows'; Quick File and filter menus are excluded, and Help lists them only for the file tree. Fix: name the surfaces (file tree in Files and Recent, Git history). Also check README and docs/design-system.md.
