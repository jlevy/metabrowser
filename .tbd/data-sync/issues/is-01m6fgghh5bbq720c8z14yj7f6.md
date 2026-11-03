---
type: is
id: is-01m6fgghh5bbq720c8z14yj7f6
title: "PR #284 C7: setTab(files) through the page handle does not move the address"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:22.021Z
updated_at: 2026-11-03T02:31:10.283Z
closed_at: 2026-11-03T02:31:10.282Z
close_reason: "C7 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in 0aa8f047: setTab through the handle goes through the route; verified in visible Chrome (pair-after-*.json)."
resolution: null
duplicate_of: null
---
Low. Review C https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745841338. github/pull-page.js:2104-2111. Move the address through the route so Back behaves as by click.
