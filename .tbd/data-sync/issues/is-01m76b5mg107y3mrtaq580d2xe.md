---
type: is
id: is-01m76b5mg107y3mrtaq580d2xe
title: "PR #352 A2: Root-admission policy is scheduled after the Phase 3 front door that needs it"
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
created_at: 2026-11-11T22:20:33.664Z
updated_at: 2026-11-11T22:26:25.191Z
started_at: 2026-11-11T22:20:41.062Z
closed_at: 2026-11-11T22:26:25.190Z
close_reason: "fixed in 083af6f8 (reviewer option: restrict Phase 3): no root is admitted on an agent request alone; a root with a live server is presented, any other root needs in-app confirmation before the app starts a server; carried into Show X step 3, the brief's phasing, and plan Phase 3; the security model is still decided before Phase 4. Confirmed by the doc checks and a re-read."
resolution: null
duplicate_of: null
---
Medium. PR #352 review A (https://github.com/jlevy/metabrowser/pull/352#pullrequestreview-5865944630). docs/project/specs/active/plan-2026-11-10-native-macos-app.md:52 decides the agent-added-root security model before Phase 4, but Phase 3 (mb-idri, mb-rtgh) lets an agent make the app start a server for a new root under the app's privacy grants (research-2026-11-10-native-app-server-topology.md:566). Fix: make the decision a Phase 3 prerequisite or restrict Phase 3 to approved roots; state when a new root needs confirmation and carry it into the end-to-end flow.
