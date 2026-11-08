---
type: is
id: is-01m6f3nm5xr0xc912vqyky74hz
title: Re-run the folder comparison after this branch merges
kind: task
status: in_progress
priority: 1
version: 11
delegate: codex@spud10
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m5wdbsy6z6d95sgg03kwmm76
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-02T21:46:57.084Z
updated_at: 2026-11-08T17:21:17.831Z
started_at: 2026-11-03T09:32:28.834Z
---
This branch changes plain-folder narrow diffs, and possibly toggles. Extends mb-2g6f's re-run on the head to be tagged; the sign-off record must then name this branch's changes too.

## Notes

November 8, 17:20 UTC: all four exact426 browser cells pass

After the owner unlocked the Mac, root used the built-in ChatGPT browser to compare published0.11.0 and exact gated426 on the unchanged 55-file fixture. Split and Unified on each build reached src/file-54.py and showed the actual VALUE_12=12 to120 diff fully inside the viewport. Per-cell console warning/error logs are empty from the recorded cutoffs. No routine partial counter appeared in the observed states on either build. Candidate commit description is a neutral white page-card, normal text color, Source Sans3 at15px/22.5px with preserved newlines. Screenshots, full AX and DOM/console receipts are saved for all four cells. This is functional evidence, not a painted-latency or quiet performance verdict. Prior locked-Mac/not-run receipts remain intact. Temporary browser tabs69/70 are closed; only the three retained previews remain. Owned test servers8981/8982 are being cleaned by the server agent, with exact PID/argv/cwd checks.

Evidence: folder55-final426-20261108/manual-followup-20261108T171350Z and the matching durable visualization artifacts. The original CLI55-file/55-patch equality and clean apply-oracle proof remain unchanged. Keep the bead open for the eventual tag-head and separate owner acceptance; no release publication is authorized.

November 8, 2026: exact gated 426ce7b62dccdd6ce4aefdba5b6744d7a510259b (0.11.1.dev1287+426ce7b62; wheel SHA256 476aba4d52c3d3d0f24edf77efae3f3286e4065f231fbad596b4ccd3663c79ab) was compared with the preserved published 0.11.0 wheel (SHA256 b099786f84408968df10296fdf7226218dd8853faf1cdb02a25787c5ab396e7f), using the exact read-only fd426 wheel profiles. The original 55-file fixture was reused unchanged: base 7d475f4a3fb584542ea9632131ef4d7da669485d, head 8070d037181c545f1743e56918d21dff29fcd852. Complete CLI --diff HEAD --format json payloads match, with 55 manifest files and 55 patches. Both --diff-check apply oracles are clean and reproduce target a4f6e55d71f87e75db3d653dae36f65ad0495984418b9cebe64282ed1c206408.

The four current-head browser cells (published/candidate, Split/Unified) are blocked and NOT RUN. CUA could not create an iab tab; its inventory reported no browser and a locked Mac. No unlock or alternate control technology was attempted, no tabs were created, and prior 519c browser proof remains historical. No warning/error counts or timing acceptance are claimed for these unrun cells. Owned servers on 8871/8872 were verified and cleaned; both PIDs/listeners are absent, default previews remain, fixture and source checkout remain clean/unchanged. Used origins are recorded for later cold-origin exclusions. Durable evidence: folder55-final426-20261108/{comparison.json,cli-comparison.json,fixture-before.json,browser-blocker.json,cleanup.json,used-ports.json}. Keep this bead open for current-head browser completion and separate owner acceptance.

November7 exactinstalled519c33239 follow-up completed:0.11.1.dev1275+519c33239 CLI --diff HEAD --format json equals preserved0.11.0controlfullpayload,55manifestfiles/55patches, cleaninmemoryapplytargeta4f6e55d71f87e75db3d653dae36f65ad0495984418b9cebe64282ed1c206408,fixtureunchanged. Rootbuilt-inbrowser freshUnifiedandfreshSplit reach/hydratefile54withVALUE_12=120 (barpositions679/698of900viewport),55sectionbars,noNofMcounter,0warnings/errors. Switchinglayoutretainslastfilehydration; viewportresets,sofreshSplitwascheckedseparately. Evidencefolder55-installed-519c-comparison.json preservesprecisescope. Tempserver8892andbothagenttabsclosed. Currentproductfixtureacceptancecomplete; finalreleasehead/ownersignoffstillseparate. BehaviorchangerecordnowhasdatedNov7addendumunderfinaldocsPRpreparation.

November 7 release-preparation checkpoint: Installed main68534af93 candidate now passes an explicit55-file plain-folder session: complete CLI document55patches, clean apply with identical produced/target tree SHA256 a4f6e55d71f87e75db3d653dae36f65ad0495984418b9cebe64282ed1c206408, final deferred file hydrates after End scrolling in both Split and Unified, no routine partial counter, neutral15px/22.5px commit description. Evidence recorded in the release-preparation directory. This is the candidate half only; baseline comparison and eventual release-head/owner sign-off remain open.

Review A of PR #284 (A6): include a commit of more than 50 files in the plain-folder re-run. On a folder nothing is kept, so each deferred file costs the manifest run again (about 0.7 s at 1,183 files), one after the other; the scheduler's one-at-a-time hydration is a folder-visible change beside the narrow diffs and toggles.

2026-11-03 owner clarification: this is a new feature stack whose frontend and backend ship together on one local server; there are no old-client backward-compatibility constraints. Earlier interpretation of additive as preserving omitted-number PR calls was too broad. Compatibility-only API aliases and the extra dotenv expansion resolver have been forward-reverted, without rewriting history. #280 ed400452 is tree-identical to reviewed64fa; #281 a30750dc restores required numbers with focused current-contract tests. Final clean composition de87065ded8a606f21fb85093474c8ca0cc50cbe has its entire src tree exactly equal measured/reviewed68db82b5 (treeca658425530ac05b2202ba7f9d223ade08fbd9f4), preserving all G1/cache/recovery/navigation/rendering fixes. All live frontend and CLI calls/current runnable examples supply explicit numbers. Root focused148tests passed147.07seconds; full exact-head verification, independent composition audit, Chrome smoke and public live checks are in progress. R6 ed0 full makeverify passed before this policy clarification and is retained as superseded evidence. The complete945 diagnostic run (20527data/1320browser/120file/three connectionpairs) is preserved NONFINAL, not a backward-compatibility gate or owner-signoff requirement for new PR API shapes. No source branches pushed yet beyond earlier font64fa; no PR merged; all merges forward; original WIP and8863 untouched.

2026-11-04 final landing update: all 23 PRs in this delivery (21 feature PRs plus #297 and #298) are merged on main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9. Postlanding Review E: https://github.com/jlevy/metabrowser/pull/298#pullrequestreview-5772391263. Final-main CI passed all nine jobs: https://github.com/jlevy/metabrowser/actions/runs/41868009781. The verified global CLI is 0.11.1.dev1154+db52ec09; final installed-wheel, browser, coordinator manual and production-cache acceptance are complete. Current feature landing is fully accepted. Earlier pending-gate or no-merge statements are historical; preserve each original build, test and measurement provenance. This does not claim a v0.12.0 release, a quiet-host performance result or completion of separate future work.

PR #284 and its reviewed follow-ups are merged. This feature-landing acceptance does not discharge the explicit greater-than-50-file plain-folder comparison or the comparison/sign-off on the eventual head to be tagged. Preserve the prior diagnostic as NONFINAL and keep this release-comparison task open.
