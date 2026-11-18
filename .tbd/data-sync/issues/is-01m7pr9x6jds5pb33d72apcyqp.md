---
type: is
id: is-01m7pr9x6jds5pb33d72apcyqp
title: "Parity registry: a tier for persisted state that only metab and a golden reach, for app.open-recent-menu and app.present-delivery"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
created_at: 2026-11-18T07:17:56.049Z
updated_at: 2026-11-18T07:17:56.049Z
---
Review A19 on #546 (mb-40k4). app.open-recent-menu is paint-exempt with cli/recent_cli.py as its owner because devtools/check_parity.py accepts only paths under src/metabrowser, so the row cannot name the Swift that draws the menu, and its paint check verifies only the tests/ paths. #540 makes the same workaround for app.present-delivery. Add a tier for persisted state with a metab mode and a golden, which check_parity.py holds to that golden, and move both rows to it. Deferred from #546: it changes what check_parity.py accepts, which is wider than that pull request.
