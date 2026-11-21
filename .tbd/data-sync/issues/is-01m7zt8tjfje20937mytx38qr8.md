---
type: is
id: is-01m7zt8tjfje20937mytx38qr8
title: Share external and copy action icons across menus
kind: task
status: closed
priority: 2
version: 5
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/685
    at: 2026-11-21T19:56:48.810Z
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m7zt8s6hyeah3vfpm02rb6zf
parent_id: is-01m7wyrvxk2xx44pqtqmy5cq5g
hold: null
hold_until: null
created_at: 2026-11-21T19:45:27.630Z
updated_at: 2026-11-21T20:21:49.854Z
started_at: 2026-11-21T19:45:29.810Z
closed_at: 2026-11-21T20:21:49.852Z
close_reason: "Independently reviewed and merged in Metabrowser #685. Exact PR CI, modified-key checks, Chrome root and counterpart coverage, and parity checks passed."
resolution: null
duplicate_of: null
---
Reuse consistent external-open and copy glyphs for matching menu actions, including Open Repository and Copy Repository URL in the root disclosure. Preserve action labels and accessible names and register the glyphs in the design system. Review existing menu actions for shared replacements within this change.
