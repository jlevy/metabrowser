---
type: is
id: is-01m7f2arby2ydmb874cgx8cg0t
title: The --walk mode calls the Python walker directly, bypassing the inventory provider contract
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7ey9fq9v53mp3c974mg2d89
created_at: 2026-11-15T07:39:14.174Z
updated_at: 2026-11-20T17:01:49.128Z
closed_at: 2026-11-20T17:01:49.127Z
close_reason: Same defect as mb-iyu7 (metab --walk bypasses the inventory provider); its detail is merged into mb-iyu7's notes
resolution: duplicate
duplicate_of: is-01m1mva0attgkp1h6b4h0d8ymd
---
src/metabrowser/walk.py (about :61-65, :135, :571) calls walker.walk_tree instead of going through the inventory provider, so swapping the engine (the planned fdu provider) would leave metab --walk on the Python walker. Route --walk through the provider, or keep it on the walker deliberately and say so in arch-inventory-provider.md. Found by the docs review (plan-2026-11-14).
