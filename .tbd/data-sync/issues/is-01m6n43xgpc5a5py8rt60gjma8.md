---
type: is
id: is-01m6n43xgpc5a5py8rt60gjma8
title: Stop obsolete PR Files mounts after releasing the page
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
assignee: jlevy
delegate: jlevy
labels: []
dependencies: []
parent_id: is-01m6mp811vf52jmazawykb3bw6
hold: null
hold_until: null
created_at: 2026-11-05T05:50:11.989Z
updated_at: 2026-11-05T07:18:59.353Z
started_at: 2026-11-05T05:50:12.473Z
closed_at: 2026-11-05T07:18:59.353Z
close_reason: "Implemented or diagnosed in Metabrowser PR #299 at 0d1b132d. Independent review, paired evidence, local make verify and all nine GitHub CI jobs passed; PR is mergeable. Merge remains with the owner."
resolution: null
duplicate_of: null
---
A full PR Files page becomes ready before its nested diff finishes loading. Releasing the page cancels its work while keeping the old DOM, so the old diff host identity can survive. The Files mount currently checks that identity alone after awaiting assets, the prefetched payload, and renderer completion. A released page can therefore start a renderer, claim a late handle, or publish retry/readiness work. A direct selected comparison GET also starts without the page cancellation signal. Check both page and diff ownership at the existing await boundaries, release late handles, and wire the existing abortable comparison transport without losing normal typed failures. Pin held assets, held selected comparison, and late renderer controls through the existing exact production DOM session. Keep the product worktree frozen through its running verification.
