---
type: is
id: is-01m8d76ayt2crenpbxb52x2143
title: Check account binding before overlapping a selected PR core fetch
kind: task
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-26-post-load-performance.md
labels: []
dependencies: []
parent_id: is-01m8cs8jdw8yh0hvdy6449jm9j
created_at: 2026-11-27T00:41:25.203Z
updated_at: 2026-11-27T00:41:52.034Z
closed_at: 2026-11-27T00:41:52.030Z
close_reason: Exp-121 rejected direct overlap. Both overlapped trials dropped the new account rate hold and admitted background GraphQL after a synthetic 429. Keep the serial behavior.
resolution: null
duplicate_of: null
---
H137 and exp-121. In synthetic ABBA replay using actual gh client budget handling, direct overlap admitted background GraphQL twice after a 429 because the newly verified account cleared the fresh hold. Serial control retained the hold in both runs. No production overlap. Any buffered transport experiment must bind the budget only to its verified account before paired loopback or Chrome timing.
