---
type: is
id: is-01m0txjqbssxdr626a9dcwemv6
title: "PR #74 review MB74-C3: settle watcher-gap freshness and coverage semantics"
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0txhaybmj82ym2wcm85zz0b
created_at: 2026-08-24T22:17:12.824Z
updated_at: 2026-08-24T22:22:55.044Z
---
Source: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5401198953. docs/project/architecture/arch-inventory-provider.md:181 currently lists watcher_gap as partial coverage while FDU treats an observation gap as stale freshness until reconciliation. Choose one cross-provider semantic digest: watcher gap makes freshness stale with a typed issue; coverage degrades only if reconciliation discovers or cannot resolve an enumeration hole.
