---
type: is
id: is-01kzksypg0hxvdzkfgfcwxeddc
title: "PR #22 review R5: sentinel refetch swallowed while fetch in flight (catalog_feed.js)"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01kzksyn1g7gqhyw86ssr1gfvt
created_at: 2026-08-09T17:43:27.999Z
updated_at: 2026-08-09T17:43:27.999Z
---
Bugbot 3742621182, Medium. Real, same root cause as R4: the fetching guard drops the refetch request; dropped catalog.change events stay unrepaired until another reconnect. Same requestRefetch fix.
