---
type: is
id: is-01m26b33hybytz6jfn6mkc17t9
title: Restore large-document TOC scrollspy parity
kind: bug
status: closed
priority: 1
version: 5
labels: []
dependencies: []
created_at: 2026-09-10T19:00:41.660Z
updated_at: 2026-09-10T22:20:07.467Z
closed_at: 2026-09-10T22:20:07.467Z
close_reason: "Implemented and verified the release-hardening slice: Recent now filters and clusters the complete server-selected model with bounded convergence repair; functional UI parity is enforced through CLI/golden evidence over exact production JavaScript; Markdown TOC composition restores same-document scrollspy and KPress disclosure; image preview is manifest-owned. make verify passes, including 1,968 tests, 104 golden scenarios, audits, and isolated wheel smoke."
resolution: null
duplicate_of: null
---
The Markdown viewer TOC no longer highlights the section currently in view on large documents, including plan-2026-03-30-predict-qa.md at #implementation-plan. Reproduce, fix production interaction logic, and add browserless production-JS golden evidence so the behavior is CLI-testable.

## Notes

Interim review found the new Markdown golden still ran link enhancement and KPress scrollspy in separate processes, leaving the original composition seam untested. Reopened until one production-module session runs enhancer -> KPress init/fallback -> scroll/dispose.
