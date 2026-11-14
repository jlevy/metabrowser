---
type: is
id: is-01m7bj988bdg3crc888wrertd4
title: "Raw resources: a replaced image stays stale in Chrome (path-only /raw URLs, no revalidation)"
kind: bug
status: in_progress
priority: 2
version: 4
labels: []
dependencies: []
created_at: 2026-11-13T23:01:04.393Z
updated_at: 2026-11-14T00:49:45.619Z
---
Found while fixing #408 (mb-wzly), present on main: in Chrome, a Markdown image replaced on disk at the same path keeps showing the old image, both on returning to the document and after a reload (0 requests). Measured with a 240x120 red image replaced by a 360x90 magenta one. WebKit reloads it correctly.

Cause (from the experiment): `/raw` URLs are path-only and lack a revalidating header. With `Cache-Control: no-cache` added by a proxy, Chrome's reload got the new image, but the in-page return stayed stale.

Done when: a replaced image shows its new content on return and on reload in Chrome and WebKit (for example a version token in the `/raw` URL from the inventory, plus a revalidating header), measured, with a test.
