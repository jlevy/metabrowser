---
type: is
id: is-01m1cdvs3fwmnxgwbnp2nmx047
title: "PR #90 CODE-05: cursor and previous_cursor were not normalized"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m1cdvq5dqpv1t2svby05zhx5
created_at: 2026-08-31T17:28:52.078Z
updated_at: 2026-08-31T17:28:52.078Z
---
They carry the same per-request random token as page_cursor. Today's golden dodges it only because cursor is null; the first paging golden would churn.
