---
type: is
id: is-01m8hnrxardat89vt0c369h08s
title: Make local Git fixture checks independent of the production free-space reserve
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
created_at: 2026-11-28T18:13:11.639Z
updated_at: 2026-11-28T18:13:11.639Z
---
The full local gate aborts ordinary tiny test clones when the external test volume has less than the production 1 GB reserve. Keep reserve-specific tests on the production threshold, and make unrelated local clone fixtures provide deterministic free-space evidence. Reproduce on the unchanged base as well as a candidate.
