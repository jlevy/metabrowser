---
type: is
id: is-01kzshb8ssn1sjvx9sbdj9eda8
title: "PR #30 review R1: keep unknown events consistent with kind filters"
kind: bug
status: closed
priority: 1
version: 4
labels: []
dependencies: []
parent_id: is-01kzshazdfnw7wz3h768kgbfmg
created_at: 2026-08-11T23:08:29.369Z
updated_at: 2026-08-11T23:20:29.686Z
closed_at: 2026-08-11T23:20:29.685Z
close_reason: Fixed with regression coverage; make verify passes (891 pytest tests and 28 golden CLI scenarios).
---
PR #30 Cursor review thread PRRT_kwDOTX174c6YZzmO. src/metabrowser/builtin_plugins/agent_log/index.js:200-265. Mixed logs leave unknown events visible after known kinds are unchecked, so filters cannot isolate selected types.

## Notes

Fixed: unknown rows now follow the aggregate filter state—visible when all known kinds are selected, hidden when the user narrows kinds, and restored when all kinds return. Added mixed-known/unknown DOM regression coverage.
