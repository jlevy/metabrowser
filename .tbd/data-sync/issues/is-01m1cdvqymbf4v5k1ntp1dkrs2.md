---
type: is
id: is-01m1cdvqymbf4v5k1ntp1dkrs2
title: "PR #90 CODE-02: --api on an SSE route printed an arbitrary prefix as success"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m1cdvq5dqpv1t2svby05zhx5
created_at: 2026-08-31T17:28:50.899Z
updated_at: 2026-08-31T17:29:11.106Z
closed_at: 2026-08-31T17:29:11.106Z
close_reason: "Fixed in 501b31b; see the disposition map on PR #90."
resolution: null
duplicate_of: null
---
The client's second receive() returns http.disconnect, so the stream terminated and exited 0, contradicting the docs, the parity exemption, and the timeout design.
