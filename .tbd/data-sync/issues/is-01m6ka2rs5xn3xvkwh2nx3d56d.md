---
type: is
id: is-01m6ka2rs5xn3xvkwh2nx3d56d
title: Remove the retired Markdown graph SDK claim from current architecture
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T12:55:56.961Z
updated_at: 2026-11-04T12:55:56.961Z
---
Expanded documentation review D3: docs/architecture.md advertises bounded Markdown graph analysis through the SDK, while current exports and docs/plugins.md correctly say graph analysis is not exposed. Update the current architecture to the implemented navigation contract and the future KPress-owned bounded server-route boundary already tracked in mb-614c. Preserve historical plan evidence and do not add an API as part of this documentation correction. Independently verify the exact successor against current exports and actual landed main.
