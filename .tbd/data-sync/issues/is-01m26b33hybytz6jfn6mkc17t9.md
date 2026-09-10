---
type: is
id: is-01m26b33hybytz6jfn6mkc17t9
title: Restore large-document TOC scrollspy parity
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-09-10T19:00:41.660Z
updated_at: 2026-09-10T19:31:46.925Z
closed_at: 2026-09-10T19:31:46.923Z
close_reason: Restored fragment-only same-document TOC links, added a scoped passive/rAF IntersectionObserver fallback that drives KPress's production active-section model, and pinned long-document behavior, bounded lookup, native preservation, and disposal in a dedicated browserless golden.
resolution: null
duplicate_of: null
---
The Markdown viewer TOC no longer highlights the section currently in view on large documents, including plan-2026-03-30-predict-qa.md at #implementation-plan. Reproduce, fix production interaction logic, and add browserless production-JS golden evidence so the behavior is CLI-testable.
