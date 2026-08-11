---
type: is
id: is-01kxry6262x317wne1svwfxy74
title: Align toggle-label typography with unselected tabs
kind: bug
status: closed
priority: 2
version: 3
labels:
  - ui
dependencies: []
created_at: 2026-07-17T21:02:12.161Z
updated_at: 2026-07-17T21:29:08.422Z
closed_at: 2026-07-17T21:29:08.422Z
close_reason: Implemented and verified the compact tab spacing, reduced embedded-document top spacing, shared toggle/tab label typography, larger Markdown prose, and viewport-bounded default tree expansion; refreshed the README screenshot and passed make verify with 709 tests.
---
Toggle labels currently appear lighter, darker, and without the tracking used by tab labels. Reuse the unselected-tab label typography: medium weight, subtle letter spacing, and muted gray.
