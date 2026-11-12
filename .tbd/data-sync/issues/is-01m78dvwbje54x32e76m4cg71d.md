---
type: is
id: is-01m78dvwbje54x32e76m4cg71d
title: "Warm pull request landing: avoid the placeholder title frame"
kind: task
status: open
priority: 4
version: 1
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T17:46:08.625Z
updated_at: 2026-11-12T17:46:08.625Z
---
Deferred from review C (C7) on jlevy/metabrowser#370. A warm /pull/N reload shows the placeholder title 'Pull request #N' for a frame or two (138 to 166 ms in one load) before the record's title; nothing moves. Serve the cached title in the placeholder, or hold the header until the cached record paints.
