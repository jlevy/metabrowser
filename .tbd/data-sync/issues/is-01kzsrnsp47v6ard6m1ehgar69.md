---
type: is
id: is-01kzsrnsp47v6ard6m1ehgar69
title: "PR #30 review S4: finish filter-state SDK migration"
kind: chore
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01kzsrn1678d07r42wx26b1kwh
created_at: 2026-08-12T01:16:34.371Z
updated_at: 2026-08-12T01:33:16.013Z
closed_at: 2026-08-12T01:33:16.012Z
close_reason: Moved filter state onto window.metabrowser.filterState and migrated the SDK, shell, types, and behavioral harness off the legacy global.
---
PR #30 senior review suggestion, app.js:2556-2557 and plugin_sdk.js. filterControls uses window.metabrowser while filterState remains on the legacy global instead of the documented SDK.
