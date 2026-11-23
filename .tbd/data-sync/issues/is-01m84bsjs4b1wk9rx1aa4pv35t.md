---
type: is
id: is-01m84bsjs4b1wk9rx1aa4pv35t
title: "Checkout store: the retry timer starts a try at once after a page's own try ends as it falls due"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-23T14:08:40.219Z
updated_at: 2026-11-23T14:10:19.913Z
started_at: 2026-11-23T14:08:51.835Z
closed_at: 2026-11-23T14:10:19.912Z
close_reason: "Fixed in PR 677: _keep_fresh recomputes the due time when a timeout hides a settled try."
resolution: null
duplicate_of: null
---
main run 45187239621 and PR 677 run 45188481748 fail test_a_failing_acquisition_is_tried_again_less_often_each_time with one wait of ~0.3 ms. Mechanism: asyncio.wait_for raises TimeoutError when the awaited event is set in the same loop iteration the timeout fires (reproduced with a 15-line script); _keep_fresh then calls request_acquisition, the page-started try has just finished, so a new try starts at once. Fix: on TimeoutError, recompute the due time when _settled is set.
