---
type: is
id: is-01m882cmhfztwz3sd46nhjvf99
title: One vocabulary for refresh and reload controls
kind: task
status: closed
priority: 2
version: 5
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/814
    at: 2026-11-25T03:54:56.443Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7wysf407hkpj5n35r533gzc
hold: null
hold_until: null
created_at: 2026-11-25T00:41:16.585Z
updated_at: 2026-11-25T03:55:12.901Z
started_at: 2026-11-25T01:04:50.401Z
closed_at: 2026-11-25T03:55:12.844Z
close_reason: "Merged in #814 (4b84d4a93): one word per meaning for asking again, Refresh (in place), Fetch (first ask), Retry (after a failure), Reload page (location.reload); the Pulls tab's Reload is Refresh, and reader copy says 'Reload the page to try again.' tests/test_browser_copy.py enforces it. The macOS labels follow in the Settings follow-up PR."
resolution: null
duplicate_of: null
---
The owner asked (2026-11-24): the nav column has a Reload button and pull request pages have a Refresh link. Inventory every refresh/reload control and use one consistent vocabulary everywhere.
