---
type: is
id: is-01m0g3js87dh157sze76be5cdy
title: Deferred diffs load themselves behind the standard progress box
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-08-20T17:30:27.462Z
updated_at: 2026-08-20T17:41:04.192Z
closed_at: 2026-08-20T17:41:04.191Z
close_reason: "Landed in 88ceab8: deferred sections show the standard delayed progress box and hydrate themselves via the comparison hook's ?file= narrowing; no loading prose anywhere in the view."
---
Deferred file sections read 'This file's changes have not been loaded yet' — verbose prose and a dead end. Replace with the app's standard delayed spinner (mb-delayed-loading, honoring --loading-state-delay so a fast load never flashes) and load on demand; the section states a failure only when loading actually fails. Applies to every progress state in the diff view; no 'Loading…' prose anywhere.
