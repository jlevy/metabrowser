---
type: is
id: is-01m76b5mwrkeq7mfd46pex1q4h
title: "PR #352 A3: Quick switcher's parity exemption contradicts AGENTS.md"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76b583awvd5h3adkdkt2gq7
hold: null
hold_until: null
created_at: 2026-11-11T22:20:34.071Z
updated_at: 2026-11-11T22:26:25.505Z
started_at: 2026-11-11T22:20:41.429Z
closed_at: 2026-11-11T22:26:25.504Z
close_reason: "fixed in 083af6f8 (reviewer option: defer the switcher): quick switcher moves to Phase 4 with the roots route, membership and order from metab with goldens; interim shell-only exemption removed; Dock and File menu recents named as a platform exemption. Confirmed by the doc checks and a re-read."
resolution: null
duplicate_of: null
---
Medium. PR #352 review A (https://github.com/jlevy/metabrowser/pull/352#pullrequestreview-5865944630). docs/project/research/research-2026-11-10-native-app-server-topology.md:478 and :556 exempt the switcher's membership and order until a later roots route; AGENTS.md:33 assigns membership, ordering, and persisted state to a metab route or model with a golden. The plan ships the switcher in Phase 2 and the roots route in Phase 4. Fix: move the roots route into the switcher's phase or defer the switcher until it lands.
