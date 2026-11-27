---
type: is
id: is-01m8f5e6kyyapa5v5whqgz8j8y
title: Keep native setup checks aligned with the plugin list
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8amwjx1z7rpzb8emdknjxk1
hold: null
hold_until: null
created_at: 2026-11-27T18:49:14.616Z
updated_at: 2026-11-27T18:58:31.490Z
started_at: 2026-11-27T18:51:10.542Z
closed_at: 2026-11-27T18:58:31.480Z
close_reason: Hosted macOS app run 46052501000 passed at ed624db2037ffa03a0ecb713658776acd8326bde with the native summary checked against its pinned CLI transcript.
resolution: null
duplicate_of: null
---
The native DoctorReport test read the real CLI golden but repeated a 17-plugin count in its expectation. The SoftSchema rollout adds an 18th plugin, so compare the native summary with the CLI transcript field instead. Hosted macOS run 46051402102 located the one failing assertion.

## Notes

Hosted macOS test DoctorReportTests.readsTheReportMetabPrints captured the 18-plugin CLI summary but expected a hard-coded 17. It now compares the underlying transcript summary with the displayed row. Swift syntax parsing passed locally; exact hosted native tests are the full behavioral gate.
