---
type: is
id: is-01kxry61y6js3d742m8r32hzca
title: Reduce top whitespace above rendered README content
kind: bug
status: closed
priority: 2
version: 3
labels:
  - ui
dependencies: []
created_at: 2026-07-17T21:02:11.909Z
updated_at: 2026-07-17T21:29:08.410Z
closed_at: 2026-07-17T21:29:08.410Z
close_reason: Implemented and verified the compact tab spacing, reduced embedded-document top spacing, shared toggle/tab label typography, larger Markdown prose, and viewport-bounded default tree expansion; refreshed the README screenshot and passed make verify with 709 tests.
---
The main Markdown README preview leaves too much space above its first rendered content, particularly above the expanded diagnostics section. Reduce the redundant top spacing without disturbing ordinary Markdown flow.
