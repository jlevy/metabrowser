---
type: is
id: is-01m7p8ffq7tfjem1x88tt6rqe5
title: "pr-view.mjs: replay after the reload, skip POST-only paths, take t0 before navigating"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7n6v8n050erzeb13c5tasar
created_at: 2026-11-18T02:41:21.638Z
updated_at: 2026-11-18T02:41:21.638Z
---
From review A on jlevy/metabrowser#524 (finding A10). In explorations/performance-loop/pr-view.mjs the replay of every GET /api/plugin/ URL runs before --reload, so the pr-warm-reload step follows an extra request of each GET (pull-markdown included); it also asks POST-only paths as GET and gets 405s, though the header says it asks each GET. t0 is taken after Page.navigate, so a document slower than 1 s never gets a timeOrigin and shows as timed out. Fix before the next round that reads pr-warm-reload: run the replay after the reload (or record it separately), replay only GET paths, take t0 before Page.navigate. A new protocol registers the changed sha256; exp-099 to exp-101 stay as recorded (their reload step is reported, not deciding).
