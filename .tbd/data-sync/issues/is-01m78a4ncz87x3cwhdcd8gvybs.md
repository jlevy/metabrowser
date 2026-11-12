---
type: is
id: is-01m78a4ncz87x3cwhdcd8gvybs
title: "Commits main tab: avoid drawing a tab Git then refuses, using the cached repo info"
kind: task
status: open
priority: 4
version: 1
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T16:41:02.108Z
updated_at: 2026-11-12T16:41:02.108Z
---
Deferred from review A (A13, remainder) on jlevy/metabrowser#370. A press on Commits before registration is now remembered; the remaining part is to use the TTL-cached repo_info to avoid drawing the Commits tab when Git will refuse the folder, so the tab bar does not change after discovery.
