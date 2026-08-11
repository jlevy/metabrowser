---
type: is
id: is-01kzshb9awcyhz2k534v8r3b89
title: "PR #30 review R3: restore hover fill for wrapped chips"
kind: bug
status: closed
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01kzshazdfnw7wz3h768kgbfmg
created_at: 2026-08-11T23:08:29.916Z
updated_at: 2026-08-11T23:20:30.610Z
closed_at: 2026-08-11T23:20:30.609Z
close_reason: Fixed with regression coverage; make verify passes (891 pytest tests and 28 golden CLI scenarios).
---
PR #30 Cursor review thread PRRT_kwDOTX174c6YYzsB. src/metabrowser/static/styles.css:1956-1960 and 1995-2017. Wrapped chip background specificity suppresses the shared hover fill.

## Notes

Fixed: wrapped chips now use a specificity-matched hover rule backed by the shared hover token. Added a design-system CSS contract regression.
