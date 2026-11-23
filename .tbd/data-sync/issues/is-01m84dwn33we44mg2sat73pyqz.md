---
type: is
id: is-01m84dwn33we44mg2sat73pyqz
title: "main red at b68cc9571: checkout store retry backoff test sees a try at once (0.0003 s) after the first"
kind: bug
status: closed
priority: 1
version: 4
delegate: claude-code@spud10
labels:
  - ci
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-23T14:45:18.050Z
updated_at: 2026-11-23T15:33:36.633Z
started_at: 2026-11-23T15:03:21.299Z
closed_at: 2026-11-23T15:33:36.598Z
close_reason: Fixed by PR 755 (cherry-pick of mb-0tw5's 65e49d5bc)
resolution: null
duplicate_of: null
---
main's CI run 45187239621 (push of b68cc9571, the #747 merge) failed unit (3.13, 1/2): tests/test_checkout_store.py:550 test_a_failing_acquisition_is_tried_again_less_often_each_time. The intervals between tries were [0.2005, 0.0003, 0.8008, 0.8011] s: the second try followed the first at once, so the gaps did not grow. This is the shape mb-0tw5 (closed) fixed, a page's own try ending as the timer falls due, and #747 carried 770e74038 (judge only the first five tries). Find the mechanism that starts a try at once here, then fix it or revert; see AGENTS.md on a red main.

## Notes

Mechanism is mb-0tw5's: asyncio.wait_for raises TimeoutError when _settled is set in the same loop iteration as the timeout, so the timer started a try right after a page's own try ended. The fix 65e49d5bc was on the still-open PR 677, not main; cherry-picked onto PR 755. Main's 889f47752 run 45197627733 failed the same way (admitted-git 2.56.1).
