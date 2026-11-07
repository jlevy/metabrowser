---
type: is
id: is-01m6sqgkmrvgmdx0htfvr7xnv3
title: Load diff patches ahead of scrolling without a routine counter
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-07T00:46:08.529Z
updated_at: 2026-11-07T00:46:08.529Z
---
Keep all known changed file names available from the manifest, keep the first patch batch fast, and start a small cancellable lookahead for later patches. Remove the normal loaded-of-total message. Preserve useful per-file spinner, failures, actual truncation guidance, explicit jumps and bounded work on large diffs.
