---
type: is
id: is-01kzmqed5sgcx3nj3kfzqrjwga
title: "Address review: PR #26 — projection-free catalog notification"
kind: task
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels: []
dependencies: []
child_order_hints:
  - is-01kzmqezf2ybdt7rsyzgp5t1y3
  - is-01kzmqezx2bsks2axpcxpykd55
  - is-01kzmqf0bxehdqmkgnyrystg59
  - is-01kzmqf0v4xs8pkzpc81vd919e
created_at: 2026-08-10T02:18:51.448Z
updated_at: 2026-08-10T02:30:24.436Z
closed_at: 2026-08-10T02:30:24.435Z
close_reason: All four findings fixed in 6f4e676.
---
Senior review of PR #26 at 70b6f80, verdict request-changes. Findings R1-R4 in https://github.com/jlevy/metabrowser/pull/26#issuecomment-5235177339

Core defect: the subscription this PR introduces makes bumpRevision() build the complete sorted snapshot on every mutation whenever any listener is installed — and the palette installs one for the application lifetime, so it runs while the palette is closed. That reintroduces main-thread work on the very hot path this PR set out to flatten.

Do-not-fix list from the reviewer: keep the ancestor-lookup removal (no trie); the leading-edge timer anchoring is correct as written; no dependency, wire-format, XSS, path-containment, or SDK-boundary issues found.
