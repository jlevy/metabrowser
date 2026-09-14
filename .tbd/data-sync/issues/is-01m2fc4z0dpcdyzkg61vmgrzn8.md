---
type: is
id: is-01m2fc4z0dpcdyzkg61vmgrzn8
title: "PR #116 review R1: plan puts the mtime rule in the wrong phase and names the wrong bead"
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m2fc4y836btjbcn5xa0skzp3
created_at: 2026-09-14T07:12:20.995Z
updated_at: 2026-09-14T07:29:19.288Z
closed_at: 2026-09-14T07:29:19.287Z
close_reason: "Fixed in 85fc77d1 (PR #116): plan labels <HOME> Cache 1A and opt-in <MTIME> Cache 1B-a, points at mb-dg00; mb-dg00 notes record the rules arrive with those goldens."
resolution: null
duplicate_of: null
---
docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md:134-139. Home rule is Cache 1A, opt-in mtime rule is Cache 1B-a (clones); the owning bead for cache goldens is mb-dg00, not mb-4gnu. Relabel, point at mb-dg00, and add a note to mb-dg00.
