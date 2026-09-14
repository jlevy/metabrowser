---
type: is
id: is-01m2fczav4hbd9vd4c44g233xd
title: "PR #118 review R4: record that row height and name line height change together"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m2fcz83jz15cmfj6yfdvm1sq
created_at: 2026-09-14T07:26:45.087Z
updated_at: 2026-09-14T07:26:45.087Z
---
PR #118 review R4 (Low). styles.css:2345-2352 and docs/design-system.md:647-652: baseline alignment places the text group at the top of the content box; it reads centered only because --ui-row-height is the name line box plus 2px pads. Add one sentence to the CSS comment and the doc.
