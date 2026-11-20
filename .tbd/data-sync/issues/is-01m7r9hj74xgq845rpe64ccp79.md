---
type: is
id: is-01m7r9hj74xgq845rpe64ccp79
title: Pin switches from source-freshness.js and the diff plugin's View on branch have the same refused-request window as the chooser had (mb-bio7)
kind: bug
status: open
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m7wys615s2mfvbc93c9g2pac
created_at: 2026-11-18T21:38:27.126Z
updated_at: 2026-11-20T17:09:42.783Z
---
Found while fixing mb-bio7 (jlevy/metabrowser#567): static/source-freshness.js and builtin_plugins/diff/index.js (View on branch, ~line 237) also POST /api/source/pin and then navigate, so the leaving page's guarded pollers can be refused with 409 pin_changed and flash the stale/Reload offer. #567 adds MetabrowserSourcePinGuard.hold (createSwitchHold) for the chooser; these two callers should hold the same way. Also: the '3,354 compressed bytes' comment at server.py:2040 is stale after #567 (now ~4,300).

## Notes

Review A of #567, A7: the diff plugin is a built-in plugin, so per AGENTS.md (Browser and Plugin Boundary) its fix must go through the window.metabrowser SDK (add a hold to the SDK), not call window.MetabrowserSourcePinGuard.hold directly.
