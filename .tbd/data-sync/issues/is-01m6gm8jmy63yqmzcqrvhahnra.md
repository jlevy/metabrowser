---
type: is
id: is-01m6gm8jmy63yqmzcqrvhahnra
title: "PR #283 G1: bypass persisted manifests when their bank cannot invalidate corruption"
kind: bug
status: in_progress
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
created_at: 2026-11-03T11:56:09.750Z
updated_at: 2026-11-03T11:58:28.726Z
---
Independent real-route probe at58270d69: a forged blob creates persisted wrong exact totals; actual owner-readable/non-writable0500 bank makes corruption-time invalidation fail safely409. Restore genuine blob and reset process state while bank remains0500: GET200 returns genuine patches but stale exact+24/-1 rather than+2/-0. Refuse adoption of a persisted manifest when its bank cannot support invalidation; recompute disposable metadata without network or checkout writes. Preserve normal writable-bank hit performance, private-path checks, and owner permissions. Add actual-permission regression and negative control. This is a newly reproduced lifecycle gap beyond Review F fixes, not a reverted prior finding. Root stopped push before source publication and stopped dependent final acceptance; all exact-head gates and CI must rerun after forward propagation.

## Notes

Investigating confirmed G1 at owning #283 3cb49015. A read-only manifest bank can retain statistics derived from corrupt bytes after object repair and process restart. Pure writability gating is insufficient when permissions later return; design must preserve normal disk-hit performance and private storage guarantees. No implementation change yet.
