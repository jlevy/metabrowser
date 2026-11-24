---
type: is
id: is-01m87zs9sbky91edkksae1vbdt
title: "Folded rendered runs: send small ones inline, fetch only large ones on expand"
kind: task
status: open
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-11-24T23:55:45.834Z
updated_at: 2026-11-24T23:55:56.540Z
---
User request 2026-11-24, refining mb-qn7e lazy folds: a folded run below a measured size is included in the route answer so opening it is instant; only runs past the bound are left as placeholders fetched when opened. Threshold measured, recorded beside its constant.

## Notes

User guidance 2026-11-24: a folded run under about 100 source lines is sent inline in the answer from the start; only longer runs are placeholders fetched on open. Confirm by measurement and record it beside the constant.
