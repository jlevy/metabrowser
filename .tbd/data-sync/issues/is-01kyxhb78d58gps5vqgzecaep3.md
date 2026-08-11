---
type: is
id: is-01kyxhb78d58gps5vqgzecaep3
title: Review Finterm TOC treatment for Metabrowser and KPress
kind: task
status: closed
priority: 1
version: 4
labels: []
dependencies: []
created_at: 2026-08-01T02:09:43.688Z
updated_at: 2026-08-01T02:57:24.931Z
closed_at: 2026-08-01T02:57:24.930Z
close_reason: Applied and verified Finterm-style TOC policy in Metabrowser; documented the KPress upstream token follow-up. Full local verification and PR CI passed.
---

## Notes

Reviewed Finterm's published-document TOC against KPress v0.3.0 and Metabrowser. Metabrowser now passes typed toc_collapse_depth=1, keeps KPress scroll-follow, and uses the same borderless/hidden-scrollbar wide rail while preserving the bordered narrow drawer. Headless Chrome against the same Figma report confirmed pane width 1428px, border 0px/none, scrollbar-width none, overflow-y auto, 35/46 deep entries collapsed, and the expand control present. Full make verify passed (741 pytest tests and 28 CLI goldens). Upstream assessment: KPress behavior is complete; repeated host CSS overrides justify public wide-TOC rail chrome tokens, not another behavior change.
