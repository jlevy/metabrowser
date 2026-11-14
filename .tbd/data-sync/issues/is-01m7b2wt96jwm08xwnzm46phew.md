---
type: is
id: is-01m7b2wt96jwm08xwnzm46phew
title: "Markdown view: images may blank on re-entry in the macOS app (lazy images in WebKit)"
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
created_at: 2026-11-13T18:32:08.228Z
updated_at: 2026-11-14T00:06:40.050Z
closed_at: 2026-11-14T00:06:40.049Z
close_reason: "Merged in #408: re-entered Markdown images inside the tree reuse their loaded copy in WebKit (0 requests, 0 blank frames when nothing changed); any inventory change or reconnect forgets them; hidden paths never held; late loads ignored. Follow-ups: mb-ndtm, mb-k3au."
resolution: null
duplicate_of: null
---
Found by the avatar-flicker sweep (#399), not measured. KPress adds `loading="lazy"` to Markdown images (`kpress/format/markdown.py`, around lines 324 and 690). #399 measured that WebKit, the macOS app's engine, re-requests a lazy image that is rebuilt, and paints frames without it: 1 to 3 frames per rebuild in the app, none in Chrome.

Re-entering a Markdown file rebuilds its document, so images visible at first paint may blank in the app the same way.

Done when:
- this is measured in the app's WKWebView;
- if it reproduces, the images visible at first paint are eager, through the Markdown view or KPress;
- the "A Repaint Keeps Its Images" rule in `docs/design-system.md` covers it.
