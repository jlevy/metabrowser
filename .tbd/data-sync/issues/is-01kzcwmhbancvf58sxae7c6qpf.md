---
type: is
id: is-01kzcwmhbancvf58sxae7c6qpf
title: Watcher can silently miss kernel event-queue overflow (watchfiles drops notify's Rescan flag)
kind: bug
status: open
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-07T01:15:39.743Z
updated_at: 2026-08-07T14:50:36.434Z
---
Source review of watchfiles' Rust layer (attic/watchfiles/src/lib.rs) shows notify's EventKind::Other + Flag::Rescan — emitted on inotify Q_OVERFLOW, FSEvents MustScanSubDirs, and Windows buffer overruns — is silently discarded in the event-mapping else branch. Metabrowser therefore has no way to learn its inventory is incomplete after large event bursts (git checkout, npm install); it diverges until restart. Not fixable through the watchfiles API. Mitigations: periodic reconciliation sweep in watch_backends.py, or the fdu-watch layer (research-2026-08-06-file-rollup-engine.md) which handles Rescan as InvalidateSubtree. Found during fdu watch-layer research.
