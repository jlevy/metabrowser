---
type: is
id: is-01m12w4ys8cxhvkz2jqd44dyem
title: "R7: disambiguate the two Phase 1B beads"
kind: chore
status: open
priority: 3
version: 1
spec_path: docs/project/reviews/review-2026-08-27-delivery-order-for-status-cache-and-providers.md
labels: []
dependencies: []
parent_id: is-01m12w4tz60cps1t8d6z1v4zet
created_at: 2026-08-28T00:26:08.551Z
updated_at: 2026-08-28T00:26:08.551Z
---
mb-h51g 'Phase 1B: hardened generic Git acquisition' and mb-ew38 'Phase 1B: generic URL open and offline reuse' share a phase label; only mb-ew38 carries the trust and status dependencies, so scheduling Phase 1B requires reading both. Rename to separate acquisition from serving, or merge and let one bead carry both dependencies.
