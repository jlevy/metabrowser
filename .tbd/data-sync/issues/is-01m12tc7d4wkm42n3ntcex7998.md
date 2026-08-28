---
type: is
id: is-01m12tc7d4wkm42n3ntcex7998
title: Replace visible loading text outside the Git panel
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m12tc1tacfnggr44ecjnb17d
created_at: 2026-08-27T23:55:09.602Z
updated_at: 2026-08-28T00:11:19.743Z
closed_at: 2026-08-28T00:11:19.742Z
close_reason: "Fixed in 101b4ad: size and file-count tooltips use tally-pending blocks, recent-files uses .recent-loading, byte preview uses .bytes-loading. distribution-view.js was already compliant (skeleton plus sr-only) and was a false positive in the initial sweep."
resolution: null
duplicate_of: null
---
Remaining visible strings found in the sweep: app.js:2326 '<span class="tip-loading">Loading size…</span>' and :2333 'Loading file count…' in hover tooltips; app.js:3751 '<div class="recent-empty">Loading recent files…</div>'; builtin_plugins/folder/distribution-view.js:97 loading.textContent = 'Loading file types…'; builtin_plugins/binary/bytes-view.js:34 LOADING_TEXT = 'Loading bytes…'. Each needs a skeleton block or a spinner per the documented rule; sr-only names stay.
