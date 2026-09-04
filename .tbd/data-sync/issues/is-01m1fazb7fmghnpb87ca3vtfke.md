---
type: is
id: is-01m1fazb7fmghnpb87ca3vtfke
title: Fix lazy plugin views after staged preview handoff
kind: bug
status: closed
priority: 0
version: 3
labels: []
dependencies: []
created_at: 2026-09-01T20:36:06.510Z
updated_at: 2026-09-01T20:45:04.598Z
closed_at: 2026-09-01T20:45:04.597Z
close_reason: Fixed on branch codex/lazy-plugin-view-mount and fully verified.
resolution: null
duplicate_of: null
---
Metabrowser 0.9.0 and current main render only the initial file view. Clicking any inactive plugin tab changes the active tab but leaves its panel empty because the staged preview handoff loses or strands the one-shot lazy mount. Trading's SDK 0.5 Web Research Bundle reproduces this on both a data-only Queries view and its URLs view. Add an actual DOM regression test, preserve lazy mounting through the handoff, run make verify, and release or otherwise provide a consumable fixed version for the Trading downstream.

## Notes

Reproduced against released 0.9.0 with the Trading SDK 0.5 Web Research Bundle: clicking Queries selected an empty panel, and clicking URLs did the same while Source had rendered. Root cause: the function-scoped mount binding in the plugin-view loop made every lazy callback invoke the final Source renderer. Changed the binding to block scope, added a regression assertion, and verified in the in-app browser that Queries and URLs mount independently. make verify passes: 1,680 pytest tests, 99 tryscript cases, lint, types, audits, build, distribution, wheel smoke, doctor, and API check.
