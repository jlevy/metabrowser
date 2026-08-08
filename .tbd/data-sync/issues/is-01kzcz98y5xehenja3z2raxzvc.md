---
type: is
id: is-01kzcz98y5xehenja3z2raxzvc
title: Metabrowser must not bridge KPress size-ramp tokens
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-07T02:01:56.420Z
updated_at: 2026-08-07T02:02:07.867Z
closed_at: 2026-08-07T02:02:07.866Z
close_reason: Fixed
---
Metabrowser's KPress bridge mapped whole graded size families onto single host values: --kpress-font-size-mono/-mono-small/-mono-tiny all to one 0.9x token, and --kpress-font-size-small/-smaller/-tiny all to one 0.85x token. A second rule, .metabrowser-kpress-host .kpress code { font-size: var(--kpress-font-size-mono) }, then out-specified KPress's own context rules (.kpress-table code and friends), flattening the ramp everywhere.

Measured in Chromium at a 1300px pane before the fix:
- inline code in a table cell: 13.5px inside a 12.75px cell (code LARGER than its own text)
- table text: 12.75px against 15px prose (KPress intends 14.25px)
- prose code: 13.5px (KPress intends 12.3px)

Fix: delete every size bridge except --kpress-caps-label-size (a real design divergence), scope the legacy .md-body code/pre rules away from the KPress host with :not(.metabrowser-kpress-host) instead of restating a size in a counter-rule, and soften the inline-code border to a new --inline-code-border token. Anchoring --kpress-host-font-size-base is the whole sizing bridge.
