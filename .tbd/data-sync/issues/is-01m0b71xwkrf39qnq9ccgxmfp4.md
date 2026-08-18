---
type: is
id: is-01m0b71xwkrf39qnq9ccgxmfp4
title: "Annotation layer: anchored threads over a comparison, GitHub review threads first"
kind: feature
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-18T19:54:57.298Z
updated_at: 2026-08-18T19:54:57.298Z
---
Layer 6 anchors from the research: comparison + file-change IDs, side, immutable content identity, byte/line range, context fingerprint. Read-only GitHub review threads are the first consumer (provider plugin territory — conversation plane, not diff plane); a document's own saved edits/annotations are the second. Both arrive as data over the same anchors, not as renderer features. Blocked on the comparison model existing.
