---
type: is
id: is-01m82kz81ynr4kngw20m4g4cm8
title: Document updating an active Metabrowser development preview before handoff
kind: task
status: closed
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/708
    at: 2026-11-22T22:37:07.104Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-22T21:53:05.597Z
updated_at: 2026-11-23T00:16:21.126Z
started_at: 2026-11-22T21:54:36.713Z
closed_at: 2026-11-23T00:16:21.126Z
close_reason: "Independently reviewed and merged in Metabrowser #708 at 5c4afed47 after its exact hosted run and current main CI passed. Confirmed in the active Mac development preview."
resolution: null
duplicate_of: null
---
When a development app or browser preview is already active, refresh the built app and the server it uses so a user testing changes sees the intended code. Preserve and restore existing windows. Leave development app and browser closed when no development preview is active. Document the procedure in developer-facing documentation.
