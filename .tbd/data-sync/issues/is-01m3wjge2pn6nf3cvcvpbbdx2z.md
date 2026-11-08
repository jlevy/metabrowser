---
type: is
id: is-01m3wjge2pn6nf3cvcvpbbdx2z
title: Run the 0.12 release rehearsal against published 0.11.0
kind: task
status: in_progress
priority: 1
version: 13
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: codex@spud10
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
  - type: blocks
    target: is-01m5wdbsy6z6d95sgg03kwmm76
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
child_order_hints:
  - is-01m6wfbagcaxwx9x9p2f7mnzqn
hold: null
hold_until: null
created_at: 2026-10-01T20:29:17.780Z
updated_at: 2026-11-08T15:46:08.256Z
started_at: 2026-10-01T20:29:25.524Z
---
Run the standard release checklist stability rehearsal against published 0.11.0 on the reviewed current application candidate: complete make verify, previous-release performance comparison with committed experiment/report, exact-head CI and release-note/version review. Version 0.12.0 is already decided. All candidate captures must satisfy committed hard responsiveness/correctness gates; repeatable regressions block until fixed or explicitly accepted. Review backend semantic equivalence before timings. User authorization now includes merging reviewed green work; no tag, release or publication is authorized without approval of the exact final commit and notes. Preserve historical runs and rerun on the final candidate rather than relabeling old evidence. Related final data/browser/test-evidence gate is mb-2g6f; PR-specific navigation diagnostics are separate in mb-4ifm.

## Notes

November 8: exp-057 resumed on the reviewed 426 candidate

PR #335 passed all nine CI jobs and merged as e1cfca1a66277aa86887f031f9b28b250d4a4928; its tree exactly equals gated426, d330f3312d5c21737dd9627e5d5e93cfb7e94d3b. The exact comparison candidate is 0.11.1.dev1287+426ce7b62, wheel SHA-256 476aba4d52c3d3d0f24edf77efae3f3286e4065f231fbad596b4ccd3663c79ab. Main CI is running separately.

The sole quiet_release_comparison agent has GO for the prepared exp-057 protocol, preserving all gates and the frozen project-10 corpus. Three fresh benchmark environments retain exactly 45 nonproject dependency pins; the four historical browser/backend/audit environments remain reserved and unchanged. Existing canonical recorder rows may append normally; no recorder algorithm or RESULTS-path changes. Candidate hard misses stop the run; no hard-miss repeats. Actual captures/results are not yet accepted. Default1ede CLI/previews and unrelated jobs remain intact; root parks browser and local builds/tests during captures. This is not release approval or final qualification of any later source change.

November 8: quiet collection deferred before captures

Exp-057 final host preflight found unrelated Python activity and external disk traffic. Zero browser/backend pairs were collected; no benchmark environment, default CLI, preview or ledger changed. Preserve preflight-deferred-20261108T0937Z.json and host observations. The newly confirmed PR-prefetch ownership bug mb-b0aq is now claimed for a focused correction; another artifact will need gating before final release measurements. Default installation remains verified a2bb0d29a. Missing-gh installed QA passed independently (mb-m20f), and its temporary port8917 is now in the private used-port history. Do not stop unrelated workloads or weaken budgets to obtain a quiet result.

November 8: exp-057 collection authorized

All product changes through PR #333 are merged and verified at main 9416b78b8dc2657a3e1745f5d6b7152c9dfc6e98. Its tree equals gated application head a2bb0d29ab6165dacf95705bf189b2208b96c534. Both CLI aliases and three previews use that exact wheel, 0.11.1.dev1280+a2bb0d29a (SHA-256 81524fde0549e9111a76c94305fb578fef544e93cf9e08d340a4ea4389479bb0). Local full gate and all PR/main CI jobs pass; installed browser checks pass.

The new clean branch is codex/v012-navigation-performance-20261108. The quiet_release_comparison agent is sole exp-057 collector using the prepared existing driver/protocol. Preliminary host observations show 92–93% CPU idle and almost no disk traffic; it must reconfirm before capturing. No other local tests, builds or browser interactions will run during collection. Default servers and unrelated jobs stay running.

Freeze this reviewed application artifact against exact published 0.11.0, using the existing unchanged shape-2 project-10 corpus/fingerprint. Collect five alternating browser pairs, then five backend pairs. Keep all budgets, validity/identity guards, semantic checks and the declared 1.1 paired rule. Stop immediately on a valid candidate hard-gate failure; do not repeat it into a pass. Preserve exp-056's valid 444 ms failure and all historical evidence.

No new timings or acceptance claim yet. The final release-head data/audit/browser checks, PR navigation hypotheses, final QA and owner approval remain separate. No tag or publication.

Original rehearsal request (historical; later owner instructions authorize reviewed merges):
The user, 2026-10-01: 'We have a standard release process to check for stability and no regressions on features or performance. Let's go ahead and run that early before we land this entire stack. Since there are so many changes, there's quite a bit of risk.' Run docs/publishing.md's Release Checklist steps 1-5 as a rehearsal on the stack's candidate, without tagging, releasing or merging: (2) the complete 'make verify'; (3) the previous-release performance loop (explorations/performance-loop/README.md, 'Comparing a candidate with the previous release') against v0.11.0, recorded as a committed experiment with the performance report regenerated; every candidate run must pass the hard responsiveness and correctness gates, and a repeatable wrong-way metric blocks until fixed or explicitly accepted by the user; read the backend comparison's equivalence (differing rows is a regression until shown otherwise; differing tallies must be confined to what the changelog describes); (4) CI green on the exact candidate commit; (5) review the changes since v0.11.0 and propose the version. Steps 6-10 (tag, publish, post-release checks) are not run. Re-run on the final tip before the landing decision. Related gates: mb-2g6f (regular-folder differentials), mb-67s1 (wall-clock pairs on a quiet machine).

November 7 release-preparation checkpoint: Release preparation is now on merged, verified main68534af93. Previous published baseline remains0.11.0; exact control wheel matches published SHA256. The malformed linked-root corpus was reproduced with a tiny failing behavioral test; correction under mb-lsm5 passes26 serving-harness tests. Five headed and five backend pairs have NOT yet run in this round; wait for the explicit admitted-Git tier to finish before creating/fingerprinting the frozen project10 corpus and measuring. Preserve exp038 failures and all old runs as historical evidence.

2026-10-26 (still owed, now against main's tip): exp-039 was NEVER recorded. explorations/performance-loop/experiments/ ends at exp-038, 'v012-rehearsal-under-load-does-not-clear-the-candidate'. So release checklist step 3 remains unsatisfied. The target moved: main is now 0b016e4b, above the 14fcdb85 that exp-038's candidate measured, and #268 changed the storage layout in between, so the step-3 pairs must be taken on main's tip (or the release-prep head), not on the old stack tip. Steps 1, 2, 4 and 5 need re-confirming there too; CI is green on 0b016e4b, and make verify was re-run on the release-prep branch on 2026-10-26. Blocking condition unchanged: a quiet machine. The host was at load 11.5 on 2026-10-26, which is the same condition that invalidated exp-038, so this cannot be run alongside agent work.

2026-10-02: still owed: release checklist step 3 on a quiet machine with no agents running, on the final head (5 headed pairs passing the hard gates, 5 compare_builds pairs read for first_row), recorded as exp-039. Steps 1, 2, 4, 5 passed in exp-038 (#265). make verify passed on 8879c4de.

2026-10-01 rehearsal on c16912f8 (draft PR #265, exp-038, verdict unresolved). Steps 1, 2, 4, 5 pass: make verify exit 0 (3,877 passed, 8 tier skips; 38 goldens; audits clean; distribution checks pass; installed wheel works); CI 9 of 9 on the exact commit; proposed version 0.12.0. Step 3: equivalence passes (four compare_builds runs, 0 row and 0 tally differences; --walk output byte-identical, 46,721,591 bytes); every responsiveness and correctness gate passes in 32 headed captures; load-independent numbers fine (startup scripts 173 vs 171 KB; DOM, repaints, shift, heap equal; instructions within 1.04x except --doctor 1.78x). Wall-clock gates failed for BOTH builds under load (first_row gate 350 ms: control missed 6 of 11 cached captures, candidate 5 of 11; every candidate miss had load above 30; ratios scatter 0.25x-3.5x). Backend first_row leans against the candidate in 5 of 10 pairs under load (1.07x and 1.00x when both answer under 20 ms; 1.03x by instructions): open until a quiet run. Owed before landing: (1) on a quiet host (the machine was at load 12 when no agents ran), on the final tip, with bytecode in both environments: 5 headed pairs with every candidate capture passing the hard gates, and 5 compare_builds pairs read for first_row; rerun with 'EXP=exp-039 <scratchpad>/release-check/rerun.sh <ref> all' (harness worktree metabrowser-v012-release-check; corpus .bench/project-10 there); (2) the user's acceptance of --doctor at 1.78x; (3) fix probe.js frame_missing_px (the stand-in shares the new .preview-frame column: 450 px vs 900 px); (4) CHANGELOG corrections: lines about --allow-edits on a file:// pin (refused in cli/git_pin_cli.py); add --diff refused on a Git source, URL modes need POSIX (home.py) while pyproject says OS Independent, typed 404 for unrelated histories; (5) the 300,000-file flat-stress pass from exp-036 was not run (disk). Not measurable by the loop: a Git source (no control), repeated loads in one tab (mb-tdmd).
