---
type: is
id: is-01m7nz91me6818xtzmqzt9zrhs
title: "Front matter: YAML aliases expanded on the event loop freeze the server (alias bomb in an untrusted file)"
kind: bug
status: closed
priority: 1
version: 6
labels:
  - security
  - alpha
dependencies: []
child_order_hints:
  - is-01m7p7s75fpxmkw7z647aaqap2
  - is-01m7pbmj503na98d3a3a4jqc3b
  - is-01m7pbmjraba81fxxr4j11wa7r
  - is-01m7pbmk965r11qkqa2af36b25
created_at: 2026-11-18T00:00:33.419Z
updated_at: 2026-11-18T17:04:22.066Z
closed_at: 2026-11-18T17:04:22.065Z
close_reason: "Fixed by #542 (merged 3af860113): bounded YAML loader; deferrals tracked in their own beads."
resolution: null
duplicate_of: null
---
From PR #527 review B (B1, High): _json_safe_frontmatter (server.py:3056, called at :3876, :3599) and /api/file expand YAML aliases on the event loop; a 354-byte file with seven alias levels returned 33.6 MB and stalled the loop ~1.6 s (x9 per level). Reachable from any served mirror (untrusted) or --untrusted folder; the pin path shares the helper (git/content_routes.py:317-331). Pre-existing on main; fix independently of #527.
