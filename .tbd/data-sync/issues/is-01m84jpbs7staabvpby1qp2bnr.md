---
type: is
id: is-01m84jpbs7staabvpby1qp2bnr
title: "PR #745 merge with #751: a move between Changes and Docs must draw an earlier diff the reader chose, else the record's comparison as read now"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
created_at: 2026-11-23T16:09:14.790Z
updated_at: 2026-11-23T16:16:59.737Z
closed_at: 2026-11-23T16:16:59.734Z
close_reason: "Fixed in the merge 6bd0e5031 and 2e85948ed; fbd4f03ed tests the offer branch, and 85001ce25 (#758) the keep branch (C2 of review C), which fails with mountDiff(diffFor, model.tab). pull-page.js cites this bead from 85001ce25 (C3). Dispositions: https://github.com/jlevy/metabrowser/pull/745#issuecomment-7106888179"
resolution: null
duplicate_of: null
---
Found while merging main's Docs tab (#751) into #745 (merge 6bd0e5031). Changes and Docs are two drawings of one comparison, and main redraws it on a move between them. Taken as main's plain mount of the record's comparison, a move to Docs after the reader took Show the earlier changes drew the newer diff over the reader's choice; taken as a redraw of the mounted diff, a move where nothing was chosen drew the comparison as Changes mounted it, not the record's as read now (its View on branch, image, rendered and size routes).

Fixed in the merge's resolution and 2e85948ed: a move draws the earlier diff the reader chose (filesAction "offer"), else the record's comparison. fbd4f03ed tests the offer branch: tests/dom/github-pull-changes-follow-behavior.js fails with a plain mount ("Docs draws the earlier diff the reader chose"). The keep branch had no failing test (C2 of review C on #745); the follow session now reads the record again at the same commits with no View on branch and asserts Docs draws it, which fails with mountDiff(diffFor, model.tab). The commits and the source comment cited mb-n9ra (A4 of review A), a different finding; review C's C3 asked for this bead.

Review C: https://github.com/jlevy/metabrowser/pull/745#pullrequestreview-6024808335
