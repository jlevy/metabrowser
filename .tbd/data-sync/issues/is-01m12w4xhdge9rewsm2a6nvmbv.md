---
type: is
id: is-01m12w4xhdge9rewsm2a6nvmbv
title: "R5: split the Git-status measurement gate out of the backend bead"
kind: chore
status: closed
priority: 2
version: 2
spec_path: docs/project/reviews/review-2026-08-27-delivery-order-for-status-cache-and-providers.md
labels: []
dependencies: []
parent_id: is-01m12w4tz60cps1t8d6z1v4zet
created_at: 2026-08-28T00:26:07.275Z
updated_at: 2026-08-28T02:23:03.194Z
---
mb-u4mf contains three evidence gates whose outcomes become implementation constants: submodule policy, the entry/byte/timeout/debounce/row budgets, and whether copy detection earns its cost. Measurement sharing a bead with the code it constrains gets done to justify the code rather than to choose it, and its result is never separately reviewed. The plan also allows the phase to return to design review if --untracked-files=all cannot be bounded, which cannot surface while the gate is invisible. Split the corpus and measurement run into their own bead ahead of mb-u4mf.
