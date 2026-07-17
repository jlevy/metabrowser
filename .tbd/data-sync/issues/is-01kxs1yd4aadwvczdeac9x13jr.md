---
type: is
id: is-01kxs1yd4aadwvczdeac9x13jr
title: "R2: centralize data-path selector escaping; fix removal/insert sites; behavioral DOM test"
kind: bug
status: closed
priority: 1
version: 4
labels: []
dependencies:
  - type: blocks
    target: is-01kxs2bd3cgdpv7tka15ts9j99
parent_id: is-01kxs2b441234qwdrbz6zekv70
created_at: 2026-07-17T22:07:55.530Z
updated_at: 2026-07-17T22:15:28.584Z
closed_at: 2026-07-17T22:15:28.584Z
close_reason: Fixed and pushed; make verify green (723 tests incl. new host-validation CLI, selector round-trip, and copy-delegate behavioral suites).
---
_findChildContainerFor/_insertRowSorted/_removeRenderedRows escape quotes only; backslash filenames break live remove/insert. One helper for every data-path selector + DOM test with backslash+quote paths.
