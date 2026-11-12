---
type: is
id: is-01m78tvwd225prdsp5q367gzwq
title: "PR #379 D3: layer 3 leaves 114 bytes of eager budget, and phase 2 plans an eager addition"
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78ttv874k855zfx1arvd5vm
hold: null
hold_until: null
created_at: 2026-11-12T21:33:20.150Z
updated_at: 2026-11-12T21:33:45.531Z
started_at: 2026-11-12T21:33:45.514Z
---
Low. PR #379, review D (https://github.com/jlevy/metabrowser/pull/379#pullrequestreview-5881899935). check_startup_scripts at 9129aac: 179,597 bytes, 114 under the 175 KB gate; layer 3 added about 1,005 compressed eager bytes (app.js +880, plugin-sdk.js +125), and f168ccae dropped the @type annotations on app.js's shellKeymap and keyReveal. Phase 2 plans mb.shortcuts.attach() and its queue in the eager plugin-sdk.js (spec:1322-1323).
