---
type: is
id: is-01m1cd5wxsqksa7tfvhqrs0gz6
title: 'PR #90 PLAN-04: "file:// honours --filter" does not reproduce, undermining the local-origin decision'
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m1cd5vdf1q8c3mj15at60znc
created_at: 2026-08-31T17:16:55.096Z
updated_at: 2026-08-31T17:29:10.669Z
closed_at: 2026-08-31T17:29:10.669Z
close_reason: "Fixed in 501b31b; see the disposition map on PR #90."
resolution: null
duplicate_of: null
---
Verified stronger than reported: with a default origin git warns "filtering not recognized by server, ignoring", and WITH uploadpack.allowFilter=true the blob is still present -- no partial clone in either case. The closed local-origin decision and bead mb-dxmb both rest on this. The hardlink and packs arguments hold; the --filter one does not.
