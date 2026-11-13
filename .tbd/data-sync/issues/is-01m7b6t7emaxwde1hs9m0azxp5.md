---
type: is
id: is-01m7b6t7emaxwde1hs9m0azxp5
title: /raw gzips already-compressed media
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-13T19:40:37.715Z
updated_at: 2026-11-13T19:40:37.715Z
---
`/raw` compresses already-compressed media, on main and on #372 alike. The transition
diagnostic for exp-083 (diag083, 2026-11-13) saw `/raw?path=images%2Fmetabrowser-overview.jpg`
served with `Content-Encoding: gzip` at 109,282 bytes (control) and 109,324–109,368 bytes
(#372 builds): gzip saves nothing on a 109 KB JPEG. The body still took 3.6–4.2 ms after the
headers on localhost, on the cold image view's critical path, in every run of every build.

Fix: skip gzip for content types that are already compressed. That covers `image/*` except
SVG, `video/*`, `audio/*`, and archive types (`application/zip`, `application/gzip`,
`application/x-xz`, and the like). One way is a content-type check in front of the gzip
responder. Another is setting `Content-Encoding: identity`, which Starlette's responder
honors, on `/raw` answers of those types.

Measure first: a cold image view's `/raw` body time and painted ready, interleaved against
main.
