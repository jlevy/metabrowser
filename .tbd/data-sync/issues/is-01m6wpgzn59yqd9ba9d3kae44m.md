---
type: is
id: is-01m6wpgzn59yqd9ba9d3kae44m
title: Fix a reproduced PR-to-Commits loading placeholder race
kind: bug
status: in_progress
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m5wdbsy6z6d95sgg03kwmm76
parent_id: is-01m5wdbsy6z6d95sgg03kwmm76
hold: null
hold_until: null
created_at: 2026-11-08T04:26:35.547Z
updated_at: 2026-11-08T07:33:55.910Z
started_at: 2026-11-08T07:10:33.064Z
---
During source-preview UI acceptance at24f3721c9, one fresh /pull/327 -> Commits -> first history row changed URL to /commit/afaf38b85a83443e25002765203c216bd11f8dfa but left Loading commit with zero connected stages; tooltip independently had correct detail, direct local commit GET returned200 in78ms, and no console errors were captured. Direct reload then rendered correctly. A repeat of the same fresh PR-to-Commits sequence also rendered correctly. Cause and introduction are unestablished; do not claim a reproducible regression or add speculative compatibility/fallback code. Read-only independent audit found no confirmed delayed-landing claimant. During final installed-wheel QA, repeat cold and retained-preview handoffs; if it recurs capture preview-owner/pending-claim attrs, selected request settlement and source identity to distinguish pending detail, asset/comparison or stale navigation. Preserve failed observation separately from passing repetitions.

## Notes

Independent review final: no open findings across4files after timer removal and pendingPreviewClaim ownership guard. Both red proofs preserved:5loadingoverwrite assertions and2crossclaim busy assertions failed beforefix. Final35focusedpytest+2goldenblocks+types/Biomepass. Live sourcepreview at productionJS SHAeeffe28523094c6496d0bd6dcd2254d3ddd1990fc840391f6ca54d1208d4e8b9: managed PR332->Commits main240 mounts16diff sections; existingcheckout PR332->Commits afaf38 mounts4; both1connectedstage, no spinner/busyresidue and zero currentconsolewarnings/errors. Exactservedbytesmatchbothports. Temporaryservers8890/8891 stopped normallySIGINT130, defaultinstalledpreviewsunchanged. Fullmakeverify running beforecommit; no timingclaim. 

November 8 stabilization checkpoint: reproduced on installed e204ce9b5/main240, with a connected delayed-loading placeholder but no staged diff after PR332 -> Commits -> first row. Focused production-JavaScript session now reproduces both timer boundaries: slow assets and deferred paint. Unchanged base fails five assertions; fix removes the redundant JS loading timer and installs the shared CSS-delayed spinner before staging. 35 focused pytest tests and 2 golden blocks passed; independent review and actual patched browser verification pending. Preserve the original one-off observations above as history. This remains a release blocker until reviewed, gated, merged and installed. Evidence is retained privately in the commit-stall-20261108 evidence directory; no release authorization given.
