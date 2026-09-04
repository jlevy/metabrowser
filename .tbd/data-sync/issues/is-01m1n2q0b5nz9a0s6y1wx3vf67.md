---
type: is
id: is-01m1n2q0b5nz9a0s6y1wx3vf67
title: The browser shows escaped names for files holding a literal %
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-04T02:07:11.204Z
updated_at: 2026-09-04T02:07:11.204Z
---
The inventory publishes the canonical identity as InventoryEntry.name, so a file named 'report%20final.txt' displays in the browser as 'report%2520final.txt'. Lookups now work end to end (the API accepts the identity and _safe_path_from_identity decodes it), so this is display only -- but it is a visible regression against main, which shows the real name.

Decision taken 2026-09-03: show the real name. The wire keeps carrying only the canonical form, per the review's position that a stated inverse makes a second path field unnecessary, so the SPA needs the inverse in JS: port native_inventory_name from contract.py, apply it when rendering names and when building /view/ links (navigation.js ROUTE_PREFIX), and keep sending the canonical identity to /api/*.

Note the asymmetry that makes this more than cosmetic: /view/<path> is a human-facing URL and takes the PLATFORM name -- tests/test_markdown_github_fixture.py pins /view/docs/100%25.md for a file named 100%.md -- while /api/* takes the identity. The SPA has to know which is which.
