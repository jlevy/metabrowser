---
type: is
id: is-01m84dwn33we44mg2sat73pyqz
title: "main red at b68cc9571: checkout store retry backoff test sees a try at once (0.0003 s) after the first"
kind: bug
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10
labels:
  - ci
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-23T14:45:18.050Z
updated_at: 2026-11-23T15:03:21.313Z
started_at: 2026-11-23T15:03:21.299Z
---
main's CI run 45187239621 (push of b68cc9571, the #747 merge) failed unit (3.13, 1/2): tests/test_checkout_store.py:550 test_a_failing_acquisition_is_tried_again_less_often_each_time. The intervals between tries were [0.2005, 0.0003, 0.8008, 0.8011] s: the second try followed the first at once, so the gaps did not grow. This is the shape mb-0tw5 (closed) fixed, a page's own try ending as the timer falls due, and #747 carried 770e74038 (judge only the first five tries). Find the mechanism that starts a try at once here, then fix it or revert; see AGENTS.md on a red main.
