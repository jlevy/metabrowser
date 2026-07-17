---
type: is
id: is-01kxry61nvtrdne93wayrt2t23
title: Reduce vertical padding in main preview tabs
kind: bug
status: closed
priority: 2
version: 3
labels:
  - ui
dependencies: []
created_at: 2026-07-17T21:02:11.642Z
updated_at: 2026-07-17T21:29:08.397Z
closed_at: 2026-07-17T21:29:08.396Z
close_reason: Implemented and verified the compact tab spacing, reduced embedded-document top spacing, shared toggle/tab label typography, larger Markdown prose, and viewport-bounded default tree expansion; refreshed the README screenshot and passed make verify with 709 tests.
---
The VIEW and SOURCE tabs in the main preview have excess padding above and below their labels compared with earlier Metabrowser versions. Restore a compact tab height while preserving the existing selected-state styling and usable click target.
