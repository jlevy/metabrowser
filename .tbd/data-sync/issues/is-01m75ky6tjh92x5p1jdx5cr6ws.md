---
type: is
id: is-01m75ky6tjh92x5p1jdx5cr6ws
title: "PR #348 G2: per-token code charges assume linear lexers; 15 of 594 are quadratic in line length"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m75ky4vdrf0qhqbhy15j46z4
created_at: 2026-11-11T15:34:33.041Z
updated_at: 2026-11-11T15:48:24.265Z
closed_at: 2026-11-11T15:48:24.264Z
close_reason: "Fixed in f959206b: no lexer runs on the revision page; devicetree, systemd, registry, make lines grown to the 64 KiB cap render in 8.4-8.9 ms; all 596 aliases at 4/8 KB at most 5 ms (first cold render 196 ms). Same test."
resolution: null
duplicate_of: null
---
Review G2 (https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5860828559): devicetree 48 KB estimated 400 ms renders in 79 s; systemd 59.8 s; registry 33 s; make 36.9 s.
