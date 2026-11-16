---
type: is
id: is-01m7kbqvvr4qsp7bzpxf4dqqg9
title: "PR #485 B3: Ten relative links in the plan to publishing.md, the app README and SUPPLY-CHAIN-SECURITY.md are broken"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T23:40:38.647Z
updated_at: 2026-11-16T23:48:26.975Z
started_at: 2026-11-16T23:40:39.382Z
closed_at: 2026-11-16T23:48:26.974Z
close_reason: "Fixed in 9e7d362be: all ten links use ../../../publishing.md, ../../../../apps/macos/README.md and ../../../../SUPPLY-CHAIN-SECURITY.md; a link checker over the four changed docs resolves all 53 relative links and anchors, and flags the six broken targets at d2d4c51."
resolution: null
duplicate_of: null
---
Low. PLAN:39, :374, :391, :552, :778, :807, :826, :834, :836, :837. The plan is in docs/project/specs/active/, so ../../publishing.md resolves under docs/project. Fix: ../../../publishing.md, ../../../../apps/macos/README.md, ../../../../SUPPLY-CHAIN-SECURITY.md, and verify each resolves. Review B (follow-up, round 2) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5929906549
