---
type: is
id: is-01kzrybqyaxahny0231fzfx1ng
title: Clarify and normalize user-facing application messages
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-08-11T17:36:41.929Z
updated_at: 2026-08-11T18:02:00.400Z
closed_at: 2026-08-11T18:02:00.399Z
close_reason: Audited and normalized browser-facing status, loading, empty, truncation, search, plugin, and recovery copy; fixed valid root null rendering and exposed the Live filter's 90-second cutoff; added regression coverage and completed live-browser and make verify validation.
---
Audit Metabrowser's browser-facing banners, empty states, errors, loading text, tooltips, and plugin diagnostics from first principles. Each message should state what happened, make the user impact explicit, and give a useful next action when one exists. Remove print-centric framing from the source truncation warning and align related terminology. Exclude developer logs and CLI diagnostics unless they are directly presented as product guidance.
