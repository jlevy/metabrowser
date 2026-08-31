---
type: is
id: is-01m1cdvs3fwmnxgwbnp2nmx047
title: "PR #90 CODE-05: cursor and previous_cursor were not normalized"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m1cdvq5dqpv1t2svby05zhx5
created_at: 2026-08-31T17:28:52.078Z
updated_at: 2026-08-31T17:29:11.125Z
closed_at: 2026-08-31T17:29:11.125Z
close_reason: "Fixed in 501b31b; see the disposition map on PR #90."
resolution: null
duplicate_of: null
---
They carry the same per-request random token as page_cursor. Today's golden dodges it only because cursor is null; the first paging golden would churn.
