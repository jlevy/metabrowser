---
type: is
id: is-01kzsrnranhah719z6ngrbmeqe
title: "PR #30 review R7: surface subscriber backlog loss"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kzsrn1678d07r42wx26b1kwh
created_at: 2026-08-12T01:16:32.980Z
updated_at: 2026-08-12T01:33:15.032Z
closed_at: 2026-08-12T01:33:15.031Z
close_reason: Added first-occurrence and 30-second rate-limited warning logs for subscriber backlog overflow and resync recovery.
---
PR #30 senior review R7, inventory.py:1071. Replacing a full subscriber delta backlog with a resync marker is logged only at DEBUG, hiding capacity trouble at normal log levels.
