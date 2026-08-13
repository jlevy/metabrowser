---
type: is
id: is-01kzy5v3ztmm470nec8b1ae7rn
title: Keep Treemap active when opening folder cells
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - ui
  - treemap
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-13T18:23:37.977Z
updated_at: 2026-08-13T18:32:26.117Z
closed_at: 2026-08-13T18:32:26.117Z
close_reason: Treemap folder and parent navigation now preserves the Treemap view through the public SDK, with default-view fallback, tests, docs, and live validation.
---
Folder cells activated from the Folder Treemap currently open the destination folder's default Overview tab. Preserve the navigation intent by extending the public openPath contract with an optional preferred view ID, selecting that view when the destination exposes it, and falling back to the declared default otherwise. Treemap directory clicks and parent-key navigation request the Treemap view; file clicks retain their ordinary default view. Acceptance: cached and fetched folder paths open Treemap, unsupported preferred views fall back safely, URL/path history remains unchanged, public types and docs describe the option, and focused plus live-browser tests cover the behavior.
