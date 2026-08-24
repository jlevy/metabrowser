---
type: is
id: is-01m0tc6jhy1c64c4z6m3z2xxtq
title: Review FDU PRs 44 and 47 against the finalized inventory provider contract
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0r8xt95921dabcddjjm7csf
created_at: 2026-08-24T17:13:28.893Z
updated_at: 2026-08-24T18:10:07.390Z
closed_at: 2026-08-24T18:03:20.205Z
close_reason: "Exact-head design and implementation reviews are published and cross-linked; all newly discovered adoption blockers are tracked in the FDU epic; MetaBrowser PR #74 is rebased and locally verified."
resolution: null
duplicate_of: null
---
Inspect the exact heads, CI, discussions, diffs, and active FDU beads for PRs #44 and #47; compare the design and implementation against Metabrowser PR #74's finalized InventoryBackend/InventoryHandle contract and performance framework; publish durable cross-linked review and alignment notes without duplicating already tracked work.

## Notes

Reviewed FDU PR #44 at 7f18f208dbd3ccb2002228bb52ae00c5d4ffcabb and the moving PR #47 at e658915, e47a535, and 5012069 against MetaBrowser PR #74. Published design review https://github.com/jlevy/fdu/pull/44#pullrequestreview-5010948152, initial implementation review https://github.com/jlevy/fdu/pull/47#pullrequestreview-5010903190, e47 exact-head follow-up https://github.com/jlevy/fdu/pull/47#pullrequestreview-5010930335, and 501 exact-head follow-up https://github.com/jlevy/fdu/pull/47#pullrequestreview-5011088016. Reciprocal MetaBrowser notes: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5399206770 and https://github.com/jlevy/metabrowser/pull/74#issuecomment-5399373173. Added FDU findings fdu-ycyy, fdu-37dv, fdu-325q, fdu-91ru, fdu-vfx7, fdu-kbir, fdu-662n, fdu-hfdw, fdu-bpp9, and fdu-7urj and linked correctness findings into fdu-vfyw and existing lifecycle, cursor, invalidation, and performance work. Rebasing PR #74 onto main resolved the sole performance-loop README conflict by preserving both provider and release validation. make verify, pre-push quality, and hosted CI passed at b4be2d0.
