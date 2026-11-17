---
type: is
id: is-01m7kchvk4fztkxw0wfjrdahvr
title: "PR #453 A3: Stated loading tier of store and list host contradicts Phase 1 data flow"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-14-object-data-model-and-views.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7f2vek3t6sca32adhd4gq33
hold: null
hold_until: null
created_at: 2026-11-16T23:54:50.339Z
updated_at: 2026-11-17T00:36:59.763Z
started_at: 2026-11-16T23:55:04.672Z
closed_at: 2026-11-17T00:36:59.763Z
close_reason: "fixed in a832c30 (PR #453); disposition reply https://github.com/jlevy/metabrowser/pull/453#issuecomment-6933923484"
resolution: null
duplicate_of: null
---
Review A (round 1) of PR #453, finding A3, severity Medium. Review: https://github.com/jlevy/metabrowser/pull/453#pullrequestreview-5916025215. Anchors: docs/project/specs/active/plan-2026-11-14-object-data-model-and-views.md:649-651, :892-895, :1260-1261; static/pulls-nav.js idle mount. Fix: state each module's tier; store with the Pulls panel or in sdk-views; count the bundle fetch in the /pulls first-paint round
