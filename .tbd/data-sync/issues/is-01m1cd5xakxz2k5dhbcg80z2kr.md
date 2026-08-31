---
type: is
id: is-01m1cd5xakxz2k5dhbcg80z2kr
title: "PR #90 PLAN-05: The OpenAPI refusal does not discriminate from the adopted design"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m1cd5vdf1q8c3mj15at60znc
created_at: 2026-08-31T17:16:55.506Z
updated_at: 2026-08-31T17:29:10.675Z
closed_at: 2026-08-31T17:29:10.675Z
close_reason: "Fixed in 501b31b; see the disposition map on PR #90."
resolution: null
duplicate_of: null
---
The adopted design also commits a schema, serves it, and offers it to plugin authors. The reasoning must name what actually differs -- versioning, deprecation policy, request-side scope -- or the refusal is unmotivated.
