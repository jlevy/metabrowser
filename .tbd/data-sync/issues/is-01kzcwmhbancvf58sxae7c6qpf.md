---
type: is
id: is-01kzcwmhbancvf58sxae7c6qpf
title: Watcher can silently miss kernel event-queue overflow (watchfiles drops notify's Rescan flag)
kind: bug
status: open
priority: 2
version: 4
labels: []
dependencies: []
created_at: 2026-08-07T01:15:39.743Z
updated_at: 2026-08-16T08:05:43.375Z
extensions:
  linear:
    id: 3bbdd03f-269a-484a-bdf2-784a5d7a9290
    linked_at: 2026-08-16T08:05:43.375Z
---
Source review of watchfiles' Rust layer (attic/watchfiles/src/lib.rs) shows notify's EventKind::Other + Flag::Rescan — emitted on inotify Q_OVERFLOW, FSEvents MustScanSubDirs, and Windows buffer overruns — is silently discarded in the event-mapping else branch. Metabrowser therefore has no way to learn its inventory is incomplete after large event bursts (git checkout, npm install); it diverges until restart. Not fixable through the watchfiles API. Mitigations: periodic reconciliation sweep in watch_backends.py, or the fdu-watch layer (research-2026-08-06-file-rollup-engine.md) which handles Rescan as InvalidateSubtree. Found during fdu watch-layer research.

## Notes

Reviewed for v0.3.0. This is a pre-existing watchfiles API limitation requiring a broader reconciliation design, not a regression in the release delta. The inventory already has a periodic refresh TTL, the full filesystem/SSE suite and real-browser update checks pass, and a rushed watcher rewrite would add more release risk. Defer to the tracked reconciliation or fdu-watch work.
