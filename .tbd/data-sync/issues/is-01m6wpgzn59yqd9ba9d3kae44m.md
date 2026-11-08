---
type: is
id: is-01m6wpgzn59yqd9ba9d3kae44m
title: Fix a reproduced PR-to-Commits loading placeholder race
kind: bug
status: closed
priority: 1
version: 9
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
updated_at: 2026-11-08T09:27:08.131Z
started_at: 2026-11-08T07:10:33.064Z
closed_at: 2026-11-08T09:27:08.130Z
close_reason: Reviewed fixes merged in PR333; exact-head full gate and all PR/main CI jobs passed. Gated build installed, both source modes and original Markdown preview verified; separate release/performance gates remain open.
resolution: null
duplicate_of: null
---
A PR-to-Commits transition can remain on its loading placeholder because a delayed JS callback replaces the connected staged diff or ready commit. A superseded selection can also clear the newer selection's busy indicator after deferred paint or missing-commit source-freshness acquisition. These are now deterministically reproduced against production GitPanel JavaScript. Fix by installing the standard CSS-delayed spinner before staging and keeping asynchronous cleanup owned by its preview claim. Cover timers, frames, delayed assets and missing-commit freshness independently in the existing concise session/golden. Completion requires independent review, normal full gate and CI, forward merge, and installed-artifact verification in managed-cache and existing-checkout modes. Keep release differentials/performance approval separate. The original one-off report is retained as historical notes.

## Notes

November 8: stabilization completed

PR #333 merged forward at main 9416b78b8dc2657a3e1745f5d6b7152c9dfc6e98. Its full tree e933e676afc54d99521986f709c6c8ecd2e7717f equals reviewed head a2bb0d29ab6165dacf95705bf189b2208b96c534, retained as an ancestor. Independent Review A has no open findings. All nine PR CI jobs and all nine merged-main jobs passed.

The exact gated wheel 0.11.1.dev1280+a2bb0d29a (SHA-256 81524fde0549e9111a76c94305fb578fef544e93cf9e08d340a4ea4389479bb0) is installed for both CLI aliases. Doctor reports 11 healthy plugins, all 33 served assets match, all 45 applicable runtime pins are unchanged, and the portable skill content is verified with its source pin advanced. Only the three verified old preview servers were replaced; cache, config, targets and checkout edits were preserved.

Installed browser checks pass PR-to-Commits in managed and checkout modes: correct commit, one connected diff, no remaining loading state. Managed preview selects main 9416b78. The original CHANGELOG route retains aligned card padding and right-hand contents. No current console warning/error appears after installation; old logs remain historical. Source checks also cover rapid replacement and independent tab restoration.

Complete exact-head make verify passed 4,917 tests, nine expected skips, 386 golden checks, lint/types, audits and artifact checks with zero filesystem errors. Red/green evidence covers loading-timer overwrite, superseded paint cleanup and superseded missing-commit freshness cleanup. All asynchronous cleanup paths were audited. The earlier interrupted push and partial e204 differential remain preserved, not relabeled as passes.

PR status and post-merge evidence are current. Release differentials, quiet performance/navigation work, final installed QA/owner acceptance and release approval remain separate and open. mb-itzy stays paused; no branch/worktree chooser implementation. No tag or release was created.

November8 final follow-up: first fix committed as d0edd4c962e3269978be92a61d035dd139d255ad after precommit makeverify4917passed/9expectedskips,386goldenchecks, audits/build/smoke/zeroFSerrors and normalcommit hooks. Root follow-up review reproduced missing-commit crossclaim cleanup after awaiting sourceFreshness; two independent red assertions. Ordinarypush gate was interrupted130 before branchpublication, verified no remote branch and no ownedprocesses remain. Adding minimal same-claim guard/test in forwardcommit; no historyrewrite. Fixer audited all selectCommit clearPendingState boundaries; no additional unguarded await cleanup found. No finalcodegate/install/release acceptance claimed yet.

Independent review final: no open findings across4files after timer removal and pendingPreviewClaim ownership guard. Both red proofs preserved:5loadingoverwrite assertions and2crossclaim busy assertions failed beforefix. Final35focusedpytest+2goldenblocks+types/Biomepass. Live sourcepreview at productionJS SHAeeffe28523094c6496d0bd6dcd2254d3ddd1990fc840391f6ca54d1208d4e8b9: managed PR332->Commits main240 mounts16diff sections; existingcheckout PR332->Commits afaf38 mounts4; both1connectedstage, no spinner/busyresidue and zero currentconsolewarnings/errors. Exactservedbytesmatchbothports. Temporaryservers8890/8891 stopped normallySIGINT130, defaultinstalledpreviewsunchanged. Fullmakeverify running beforecommit; no timingclaim. 

November 8 stabilization checkpoint: reproduced on installed e204ce9b5/main240, with a connected delayed-loading placeholder but no staged diff after PR332 -> Commits -> first row. Focused production-JavaScript session now reproduces both timer boundaries: slow assets and deferred paint. Unchanged base fails five assertions; fix removes the redundant JS loading timer and installs the shared CSS-delayed spinner before staging. 35 focused pytest tests and 2 golden blocks passed; independent review and actual patched browser verification pending. Preserve the original one-off observations above as history. This remains a release blocker until reviewed, gated, merged and installed. Evidence is retained privately in the commit-stall-20261108 evidence directory; no release authorization given.

Original report (historical; later reproductions resolve its uncertainty):
During source-preview UI acceptance at24f3721c9, one fresh /pull/327 -> Commits -> first history row changed URL to /commit/afaf38b85a83443e25002765203c216bd11f8dfa but left Loading commit with zero connected stages; tooltip independently had correct detail, direct local commit GET returned200 in78ms, and no console errors were captured. Direct reload then rendered correctly. A repeat of the same fresh PR-to-Commits sequence also rendered correctly. Cause and introduction are unestablished; do not claim a reproducible regression or add speculative compatibility/fallback code. Read-only independent audit found no confirmed delayed-landing claimant. During final installed-wheel QA, repeat cold and retained-preview handoffs; if it recurs capture preview-owner/pending-claim attrs, selected request settlement and source identity to distinguish pending detail, asset/comparison or stale navigation. Preserve failed observation separately from passing repetitions.
