---
type: is
id: is-01m7kchv2nan1dcd9ad4mhwfw8
title: "PR #453 A2: mb.objects has no write or registration calls for types, sources, normalizers, put"
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
created_at: 2026-11-16T23:54:49.812Z
updated_at: 2026-11-17T00:36:59.342Z
started_at: 2026-11-16T23:55:04.239Z
closed_at: 2026-11-17T00:36:59.340Z
close_reason: "fixed in a832c30 (PR #453); disposition reply https://github.com/jlevy/metabrowser/pull/453#issuecomment-6933923484"
resolution: null
duplicate_of: null
---
Review A (round 1) of PR #453, finding A2, severity Medium. Review: https://github.com/jlevy/metabrowser/pull/453#pullrequestreview-5916025215. Anchors: docs/project/specs/active/plan-2026-11-14-object-data-model-and-views.md:745-756, :788-789, :591. Fix: name registerType/registerSource/put, say which are SDK and which host-private, and whether a plugin type ships its own normalizer
