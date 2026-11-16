---
type: is
id: is-01m7k5qdzhbdxxt023ahctppvd
title: "PR #486 A3: Diff Summary lost Layout's one-step replacement and next-paint re-read"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7jz6wz5wjnb9thcvxybaek0
hold: null
hold_until: null
created_at: 2026-11-16T21:55:32.976Z
updated_at: 2026-11-16T22:03:50.297Z
started_at: 2026-11-16T21:55:39.516Z
closed_at: 2026-11-16T22:03:50.296Z
close_reason: "Fixed in e0720e07c on PR #486: Diff Summary says the next paint or a Retry starts the read again, and a newer summary replaces the drawn one in one step."
resolution: null
duplicate_of: null
---
Low. docs/design-system.md:1491-1494, base :1809-1811. Say what starts a failed comparison's read again (the page's next paint, a Retry), and that a newer comparison's summary replaces the drawn one in one step. Review A on PR #486: https://github.com/jlevy/metabrowser/pull/486#pullrequestreview-5928430110
