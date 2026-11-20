---
type: is
id: is-01m7rab2z29yvkj8nhj8sht7y0
title: The browser page names no favicon, so the tab shows the browser's default instead of the app's mark
kind: feature
status: open
priority: 3
version: 5
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/580
    at: 2026-11-20T17:02:48.986Z
labels:
  - linear
dependencies: []
parent_id: is-01m7wysf407hkpj5n35r533gzc
created_at: 2026-11-18T21:52:23.521Z
updated_at: 2026-11-20T18:01:11.724Z
extensions:
  linear:
    id: bdc6cf2a-0f88-426a-9fd9-887414001ac5
    linked_at: 2026-11-20T18:01:11.722Z
---
Found by the icon catalog (mb-k1k7, docs/design-system-icons.md, Known Departures). The shell page (server.py's index template) declares no <link rel=icon>, so every browser asks for /favicon.ico, gets a 404 (recorded in docs/project/qa/qa-2026-11-07-v012-release-preparation.md and earlier QA notes), and draws its default. The app's mark exists (apps/macos/AppIcon/, AppIconMark for the title bar's mark alone). An owner decision: which mark and form (the full icon, or the mark alone, light and dark), served from where, and at what startup cost; a data: URI or a static asset with a long cache life costs no startup script bytes.
