---
type: is
id: is-01m6f3n89kn7ztmfhrzswxnsgz
title: "Review pull requests well on large repositories: fresh mirror and existing checkout"
kind: epic
status: in_progress
priority: 1
version: 104
delegate: codex@spud10
labels:
  - release:v0.12.0
dependencies: []
child_order_hints:
  - is-01m6f3n8s7enn9mcye32ks6jrd
  - is-01m6f3n9efn9sj7gkavbthag1c
  - is-01m6f3na4z8cvkyyrn5ge794es
  - is-01m6f3nakaknkwvc7j976xxqcg
  - is-01m6f3nb10jmwg0ej1tbf3vdnz
  - is-01m6f3nbfcsnzgmn95f1gr0dsj
  - is-01m6f3nbz5f5rbwbjcs64vj4g2
  - is-01m6f3ncftw4g837wvn9ygqbbx
  - is-01m6f3ncz8hk3e49ernay4yv8x
  - is-01m6f3nddgbv150407xewcjwds
  - is-01m6f3ndv0s9tpwhvbjwdmtkev
  - is-01m6f3ne8f25m4n06r3d09zw9d
  - is-01m6f3neny40jwz0qeanc3avfh
  - is-01m6f3nf55rm1sjpaagqaph6nr
  - is-01m6f3nj5vpvkbw0m300dcy3jr
  - is-01m6f3njzx91ssw9yq9x2smtv5
  - is-01m6f3nkg482640stjteqx3fvw
  - is-01m6f3nm5xr0xc912vqyky74hz
  - is-01m6f3nmnmmceb1c0rgwvdg8as
  - is-01m6f55s2rxqn1fc5gntccjv9g
  - is-01m6f55tgdfq5q1a28hvqzsbrh
  - is-01m6f55vkpt8e119z7c1wdzxat
  - is-01m6f55wr4c9e7h3q7dt8dtex3
  - is-01m6f60ncbgnmwgg9g07wcsj4t
  - is-01m6f60pqc21gnqnct2pdq16zb
  - is-01m6fa9eepyhrcwa35bmbdmjde
  - is-01m6fczffs8pdsdktnahd1ked2
  - is-01m6fvg6hjg91hmegfq5m3sg4b
  - is-01m6g4n54pv6gbm7yzjxbskegg
  - is-01m6g4q0q0dvzhxj3yesx7qayg
  - is-01m6ghtfstncw2xgewnwzvjr6y
  - is-01m6j4m8h98qy2w5w5wj5d46gj
  - is-01m6j5mzwzjd6xx8bpwxvcpfbb
  - is-01m6jhbnan8czw6c97gr5511mr
  - is-01m6jhcsrvevhaa1kg3fh6g8zg
  - is-01m6k4bp5bmh38vg43syytha0v
  - is-01m6mp811vf52jmazawykb3bw6
  - is-01m6pt19mvgpx4waqfbqdg85yx
  - is-01m6pt1a1kgdp4myh1scekn2wz
  - is-01m6pt1adhsrmxz0hv57c1v5f5
  - is-01m6pt1asfx9rhvfnr7ah2t031
  - is-01m6pt46vbmx4qwd81mnvvfh4p
  - is-01m6q24e0zp42g259j5cgz1zsy
  - is-01m6qd2d538c6k0psmpr1sh0d7
  - is-01m6sbma21wasa5vwdatgatrz6
  - is-01m6sbmaj90en19z2m596h35fk
  - is-01m6sfrk25n3d44qpvbfyhakkc
  - is-01m6shhkwxasd5rpv91y17qc4w
  - is-01m6sppcghnnagtzr2gs9ev631
  - is-01m6sq0zex3pr3hngsdmwfayy6
  - is-01m6sqgkmrvgmdx0htfvr7xnv3
  - is-01m6sx3tjqbthwcgkd91tt9tkt
  - is-01m6sx9vy43qz7syctdkmhf455
  - is-01m6sxexzgyvnye3bw5dy7c4jf
  - is-01m6sxeyax9gqajg1b3csc9gmq
  - is-01m6sxjyqf3b1z01p3gzzjpwty
  - is-01m6sxmwx9fjjnft6mvavs5c7h
  - is-01m6t02b08jdzpvf7sr2qyeb31
  - is-01m6t2y2ngvnp6r2417kmp3aka
  - is-01m6t6db612aj6w19qbxhcrp9a
  - is-01m6th4q8ppch1rc8h9varn3pt
  - is-01m6th4qn5b1s27zkw8rw3736h
  - is-01m6thd4vjfenzzqnxmbehgph4
  - is-01m6thd591bhgt6vp9v5ve0326
  - is-01m6thmx3973vnsw532ya5nk4h
  - is-01m6tkc0b7m61frpp1wv9cesms
  - is-01m6tkevv05t0gr8fc59ehyt9b
  - is-01m6trzcwb5qx8pgpxwwv3thkq
  - is-01m6wkyht4d76t40kybbpah0fj
  - is-01m6wkyj7h8z2qxz5amsvrfd1w
  - is-01m6wkzscv76q4b3w6resytamt
  - is-01m6wnd5z7n48xe1q7j3xxtj7j
  - is-01m6wpacpj9wtx02rt1g8kx49m
  - is-01m6yf7sfcwhqr17xdzy45r7tr
  - is-01m6yvdd0vjh112keerpr3gpc7
hold: null
hold_until: null
created_at: 2026-11-02T21:46:44.914Z
updated_at: 2026-11-09T00:30:29.914Z
started_at: 2026-11-07T05:39:51.585Z
---
The owner's goal, 2026-11-02: review PRs seamlessly both fresh from the cached mirror and from an existing checkout without duplicating its storage, responsive on large PRs faster than GitHub itself, following the design system rigorously, with all workflows documented cleanly. Found by testing on a real 1.2 GB private repository with a shallow checkout and 211 linked worktrees. All work lands on branch claude/v012-pr-review-workflows, above release stack 278. The Pulls tab itself is a separate stack in the linked session: mb-q3jt, mb-x174, mb-zx9q, mb-cbak, mb-r50o, mb-lnkl, mb-iw1v.

## Notes

November 7, 2026: all 28 product PRs in native stack #302 merged with merge commits at main 68534af933f0fcb38a5d81d62691bb42732d58ab. The landed tree exactly matches reviewed/gated 6cf001cdf, which remains an ancestor. Integration Review A: https://github.com/jlevy/metabrowser/pull/327#pullrequestreview-5816169303 . All 16 new findings have dispositions; every thread resolved and all published-head CI green. The 12 current feature/review/validation beads are closed. Post-landing make verify runs in mb-5k2w. Release preparation uses mb-4bd2 and mb-gew9; standard comparison/QA/sign-off gates remain open. Corpus materialization mb-lsm5 must be fixed before measurement; warmup investigation mb-b0aq remains separate. No release tag or publication; user approval required to cut the release.

New user authorization, November 7, 2026: finish verification and review, merge the entire ready PR stack, then prepare a release under the standard process. Do not cut or publish the release without the user's approval. This supersedes earlier owner-only merge checkpoints; the publication approval gate remains explicit. Ownership fix c84d25f8 is integrated through all affected layers. Production regressions fail the prior code and pass the fix; 13 focused tests, eight goldens and both TypeScript checks pass. Frozen full gate is running at6cf001cdf. No PR has yet merged in this round. The latest browser smoke has mixed initial cache readiness and is retained as diagnostic, with a separate investigation below.

Current checkpoint, 2026-11-07: frozen 11dbb8ba3 passed full make verify (4,916 tests, nine expected skips, 385 goldens, both audits, distribution and installed-package smoke checks; 1,255.49 seconds) and its five forward-updated branches were atomically pushed. The original 14 review findings and the PR #327 status finding are resolved, with reviewer acceptance preserved for the three rebuttals. Merge readiness is held for newly confirmed P1 mb-jhgj under mb-1e2y, owned by PR #324: both ready and partial coverage receipts can retain server window W1 while the client records W2, so hide/dispose releases the wrong token. A frontend-only ownership correction needs retained-owner production regressions for both receipts, independent review, forward integration and fresh verification/CI. This is the 16th finding in the current review cycle; preserve the successful 11db gate and all earlier checkpoints as historical evidence. No feature PR has been merged or history rewritten.

Current checkpoint, 2026-11-07: six follow-up PRs322–327 are published and linked above321 in native stack302 (28productlayers total). The first frozen9522 full make verify passed4907tests/9expectedskips and385goldens, audits/distribution/installedsmokes; all six layers published normally. Automated review then found real recovery defects; independently approved fixes0fd1feb5/da501f79/3097cb7b are now forward-merged through all layers into72200d198. Documentation-only successorb8c7e34a records the separate three-pair regressionguard: candidate67–78ms (median76), installed9522 75–194ms (median77), overlap/no new speedupclaim. All six targets were18thOpen with durablecore/no fullrecordbeforeclick;137focusedtests,15goldens,bothTSchecks pass. Originalexp055 six-pair improvement retains its historical1b17 sourcepin. Latestinstallation is underway before a fresh full gate/atomicpush/freshCI. All14newreviewthreads have dispositions being prepared; none merged/historyrewritten. Owneracceptance/release/quiet-host scopes remain open.

Current checkpoint, 2026-11-07: frozen top is0248a32b; its product and test tree exactly matches measured1b17c680. Six forward-stacked follow-up layers above321 implement the seven current beads. The first pre-push gate stopped on public-reference wording in the experiment note; that documentation-only issue is corrected and public hygiene passes. The complete normal make verify gate is running again before atomic publication. All independent reviews and123 focused integrated tests pass. Real browser checks cover checkout and managed sources, shared15px sans message typography, neutral cards, tab/card/source gutters, native KPress padding, wide tables, narrow TOC, real stack titles, and Checks-preserving stack shortcuts. Six paired description observations improved from median1320.5ms to73ms; added metadata cost and diagnostic limits are recorded in exp055. A new managed process reused an unselected143.5-second-old core with zero gh calls. Existing22 remote PRs remain unchanged, green, correctly stacked, and without unresolved review threads. Final publication, CI, installation, and bead closure remain pending. No owner merge or history rewrite.

Current checkpoint (2026-11-07 shared-design acceptance): seven follow-ups are in progress: mb-3vvt Markdown/Source gutter; mb-eicc durable PR cores; mb-1e2y progressive idle/viewport/catalog prefetch (depends on mb-eicc); mb-82fa compact stack menu; mb-2vf2 Shift-J/K stack keys (depends on mb-82fa); mb-ba73 author/action/age baseline; mb-s9bb shared commit/PR description surface. All seven have implementation commits integrated by forward merges in the freshness checkout. Corrected gutter7c is installed as0.11.1.dev1218+7c0188f4 and8411 confirms card-border/tab-box alignment with original KPress padding. Core251, frontend2fc, menu c248, keys8065, baseline6b, surface1d passed focused and independent review. Real-browser integration caught native GitHub stacks omit titles; a source/reader-matching catalog-title projection and menu styling correction are in progress. Integrated focused gate currently102passed/1 stale trusted-icon-parser assertion to update with the menu correction. PR/commit typography and ShiftJ/K were checked in the built-in browser. Design, e2e playbook and changelog updated on local top. Existing22-layer published stack still ends at321; six follow-up layers remain local pending final combined gate, real performance evidence, publication/CI and final installation. No merge or history rewrite. Preserve owner/release/quiet-host follow-ups below.

Current checkpoint (2026-11-07 acceptance follow-up): PR #321 remains the last published/installed head. All 22 existing layers passed review/CI, but new owner testing found follow-up work that must be completed before final acceptance: mb-3vvt shared visible Markdown/Source gutters; mb-eicc durable lightweight PR cores; mb-1e2y startup and scroll-adaptive progressive metadata prefetch (depends on mb-eicc, no eight-PR coverage cutoff); mb-82fa compact stack position menu; mb-2vf2 Shift-J/K stack navigation with shift glyph Help (depends on mb-82fa). Root owns gutter implementation, design/e2e docs, stacking, final integration, real-browser checks and installation. Three sub-agents own persistence, progressive prefetch, and stack menu/handle/glyphs in separate existing checkouts. Planned forward-only layers after #321: gutter, durable cores, progressive prefetch, stack menu/hotkeys. No owner merge has been performed. Existing release/acceptance/performance follow-ups remain tracked; preserve all prior checkpoints below.

Prior checkpoint (2026-11-07): Native stack #302 now has 22 reviewed layers, ending at PR #321 / a7d3c0139a12204fc556da463dbc2c8e40f3bc1a. All actual bases match the preceding heads and all 22 exact-base ancestry checks pass. Every layer has green CI and CLEAN/MERGEABLE status; 24 review threads have zero unresolved items. The new layer renames Git to Commits in navigation, shortcut Help, and current docs. The inherited #320 Markdown/README layout is verified left-aligned under the first view tab, with the desktop TOC to the right and the narrow-pane icon/drawer preserved. Full make verify passed 4892 tests with nine expected default-tier skips, 384 golden scenarios, both audits, and distribution/installed-package checks. Both CLI names and previews now run 0.11.1.dev1216+a7d3c013 with default user cache/settings and wheel-matching assets. Ready for owner merge; nothing merged in this follow-up. Owner acceptance mb-i9ll, post-landing/release reconciliation mb-5k2w, quiet-host/tagged-release comparisons, and clock-provenance follow-up mb-irrw remain tracked in their existing scopes.

Prior checkpoint: first9featurePRs are actually merged to main8aae81d0. Remaining12forwardcascade to f9e8c524 has exact whole-tree equality to reviewed a4; normalatomicpublication succeeded, freshheadCI/nativegroup/artifactchecks still pending. GlobalinstalledCLI/previews remain verifieda4 (samecode) pending finalmain replacement. Mandatorypostlanding integratedreview/docs/skills/plans/beads remains mb-ao35. Preserve draft247/WIPs and audit .tbd/config.yml; clean independent landingcheckout is /Users/levy/wrk/github/metabrowser-landing-01a1a051.

Earlier checkpoints:

2026-11-03 FINAL READINESS at ea771741211193a387c1771e04df29b5a9698100. The full 14-PR stack is independently reviewed and ready for the owner's merge decision. All actual bases contain their lower layer, both native stacks match, every PR is open/non-draft and mergeable/clean, and all 171 CI jobs across 19 current-head workflow runs passed. Final make verify: 4712 Python passed, 9 expected skips, 373 transcript checks; dependency audits, distribution and isolated installed-wheel checks passed. Exact-head public live: 8 passed; fresh installed-wheel Chrome: 22 actions with 25 unchanged checkout/common-Git fingerprints. Managed repository URLs and existing main/linked checkouts pass. Final Review G: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . All findings have published dispositions; fixed threads are resolved, while rebutted/declined threads remain reviewer-visible. Completed stabilization/review beads are closed and residual baseline observer mb-czrw is under mb-2iok. Both WIP branches and the original local server remain unchanged. Frontend/backend ship together on one local server with explicit-number requests; compatibility-only work remains canceled. Historical timing evidence keeps its original source pins; no quiet-machine or universal 500ms claim. Quiet timings, remaining performance/browser/release follow-ups and explicit owner-merge beads remain open. No PR merged or history rewritten. After the owner merges stack278, unstack286, retarget279 to main and relink279/281/285/287/288 as documented on279.

Earlier chronological notes (superseded where they describe pending final gates):

2026-11-03 status. Stack 278 is 272-277, 280, 284, 283, with the Pulls tab as stack 286 (279, 281, 285, 287, 288) on top of 283. PR 280 (design system, docs, workflows): reviewed, addressed, CI green at 996ea90d. PR 284 (large-PR performance): three review rounds; E1 (the mount's single long task, slower than github.com at 1,031 files) in progress, mb-ivvw. PR 283 (checkout overlay step 1): two review rounds addressed, CI green at e8b7ff3d, verified on the 1.2 GB private repository; a follow-up review of its last fixes is pending (mb-3kju). Open after that: mb-l351 (overlay step 2), mb-jwfx (quiet timings), mb-i9ll (the owner's own pass), mb-8pyc and mb-2g6f (folder differentials on the tagged head).


2026-11-03 handoff pause. Heads: PR 280 996ea90d, PR 284 9b624b3a, PR 283 b29dc787 (top of stack 278). Reviews: 280 round 1; 284 rounds 1 to 3, with the E1 fix unreviewed; 283 rounds 1 to 3, with f987d033 reverted at 483e3a83. Open, in order: review the E1 fix and mb-ph3m (cold manifest, the gap to github.com at 1,031 files); mb-hjez (review E follow-ups on 283); the follow-up review of 996ea90d (mb-f15a); mb-6453 (file at top, for the Pulls nav); mb-l351 (overlay step 2); mb-jwfx (quiet timings); mb-i9ll (owner's pass); mb-8pyc and mb-2g6f (folder differentials on the tagged head). The Pulls tab is stack 286 on 283's branch, handed off on its own beads (mb-cbak, mb-zx9q). Merging waits for the owner.


2026-11-03: the Pulls tab's stack 286 is paused too, with all heads green and containing b29dc787; its epic is mb-8rpp, its unfinished work is on wip/pulls-4-files (fff7d6a3) and wip/pulls-5-checkout (24a95778), and #279 carries the unstack-and-relink note for when 278 merges.

2026-11-03 R4 freeze at ccb5927e508a1988196c8290754b0bc5356832b3. All seven updated layer heads contain both their current base and original published remote head. New G1 read-only manifest/restart defect fixed by ea891a57 and independently verified, including permission restoration and late stale writes. Current-main omitted-number PR API compatibility restored by 6d956e45 on #281; independent Review F is clean and the fixture-only successor481efd1d passes its recorders. Current-file mount subscription regression C1 fixed by ef297383 on #287 and independently verified: three nonquiet1627-file pairs improve longest load task217 to163ms and first painted text672 to606.1ms; held-row ranges overlap, so no held-speed claim. Final merge and test adaptations independently audited clean at exact R4:15independent Python probes,3696canonical parser cases,18legacy cases, G1 and D1/D2/C1 lifecycle controls. Fresh make verify and complete immutable-wheel v0.11.0 additive harness are now running at R4; eight public read-only live GitHub tests already passed at R4 with no skips in71.53s. Small final Chrome smoke and factual publication audit are active. Earlier completed diagnostic and superseded gates are retained as nonfinal evidence. Seven source branches remain unpushed pending normal final gates; #280 is already reviewed/pushed/green. No PR merged, no rebase/force-push, private repository unnamed publicly, original WIP refs and user8863 server preserved.

2026-11-03 R4 acceptance stopped cleanly for a further strict-additivity fix, mb-3rcp. #28054a9000c removed current-main ${VAR} dotenv expansion to avoid quadratic work. Existing review requested this and documentation acknowledged it, but no explicit owner approval to break a valid logging setting was found. DEBUG/verbose/default examples reproduce the loss. Writer is implementing ordered compatible expansion with efficient prior-binding/shell lookups, bounded materialization and atomic file refusal. A new independent tokenizer check found the pinned variable regex itself quadratic on malformed ${ repetitions (32768characters9.375seconds); the fix must use an equivalent linear scanner, retain the64KiB regular-file input cap, warning deduplication and allowlist, and pass independent semantic/adversarial review. The exact R4 full gate stopped by scoped SIGINT at62percent with no reported product failure; all6ownedPIDs gone and no pass marker. R4 additive audit completed but data/browser partial, all39ownedPIDs gone/ports free/415control fingerprints unchanged. These are diagnostic only. R4 public live8passed and final installed-wheel Chrome17actions/25unchanged fingerprints passed. No source branches pushed or PRs merged. After owning#280 fixreview, mergeforward throughall8changedlayers, repeat all exact-head gates, normal atomicpush/hooks andremoteCI, thenpublish preparedreviews/dispositions.

2026-11-03 R5 frozen at 945012cac10f62c03a5f370e18e0a40099323f41. Owning #280 fix 2945bbfe restores ordered dotenv expansion with bounded work/output, UTF-8 and unchanged allowlist/precedence. Independent Review F is clean: 28 behavior/budget cases, 43 repository tests, 2,497 real-file and 335,923 direct token comparisons, baseline/negative/locale controls. Independent propagation audit confirms all eight changed layers contain their old heads, previous remote heads and new bases; every R4-to-R5 delta is exactly the five reviewed dotenv files. All 256 final JS/CSS blobs are unchanged; upper docs preserved. Fresh R5 installed-wheel Chrome smoke passes 17 actions with 25 unchanged fingerprints and no external requests/application errors. The unchanged installed V2 probe matches current main in all 18 dotenv cases, and legacy PR API/header/default behavior also passes. Full make verify, complete fresh additive audit/data/browser matrices, and public live tier are running at this exact SHA. No source branches pushed yet, no PR merged, original WIP refs and8863 server preserved. Next are normal atomic push with its complete quality hook, every layer CI, formal review/disposition publication, readiness and tracking sync.

2026-11-03 R5 full gate result: 4,696 Python tests passed with9expected skips; tryscript370passed/3failed. The three failures are stale expectations from independently reviewed runtime changes: #281 numberless/no-attended GET now200legacyabsence instead of400, #281 empty-body/no-attended POST409no_pull_request instead of400, and the #288 mount-session transcript lacks the three new true C1 lifecycle result fields. Agents are correcting exactly those recorded blocks and adjacent false number-required prose, with no production change. Child mb-gy9q tracks the two #281 blocks. The C1 block exists only in #288; no new lower #287 block is being added. R5 full additive run continues at its immutable actual wheel; its audit A/B/C is complete with all inherited residuals explicitly explained. We will prove complete product/source/lock equivalence for the transcript-only successor, retain R5 provenance honestly and run complete make verify on the final successor. No final-pass marker or push/merge occurred.

2026-11-03 owner clarification: this is a new feature stack whose frontend and backend ship together on one local server; there are no old-client backward-compatibility constraints. Earlier interpretation of additive as preserving omitted-number PR calls was too broad. Compatibility-only API aliases and the extra dotenv expansion resolver have been forward-reverted, without rewriting history. #280 ed400452 is tree-identical to reviewed64fa; #281 a30750dc restores required numbers with focused current-contract tests. Final clean composition de87065ded8a606f21fb85093474c8ca0cc50cbe has its entire src tree exactly equal measured/reviewed68db82b5 (treeca658425530ac05b2202ba7f9d223ade08fbd9f4), preserving all G1/cache/recovery/navigation/rendering fixes. All live frontend and CLI calls/current runnable examples supply explicit numbers. Root focused148tests passed147.07seconds; full exact-head verification, independent composition audit, Chrome smoke and public live checks are in progress. R6 ed0 full makeverify passed before this policy clarification and is retained as superseded evidence. The complete945 diagnostic run (20527data/1320browser/120file/three connectionpairs) is preserved NONFINAL, not a backward-compatibility gate or owner-signoff requirement for new PR API shapes. No source branches pushed yet beyond earlier font64fa; no PR merged; all merges forward; original WIP and8863 untouched.

2026-11-04 final landing update: all 23 PRs in this delivery (21 feature PRs plus #297 and #298) are merged on main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9. Postlanding Review E: https://github.com/jlevy/metabrowser/pull/298#pullrequestreview-5772391263. Final-main CI passed all nine jobs: https://github.com/jlevy/metabrowser/actions/runs/41868009781. The verified global CLI is 0.11.1.dev1154+db52ec09; final installed-wheel, browser, coordinator manual and production-cache acceptance are complete. Current feature landing is fully accepted. Earlier pending-gate or no-merge statements are historical; preserve each original build, test and measurement provenance. This does not claim a v0.12.0 release, a quiet-host performance result or completion of separate future work.

The reviewed PR-support stack is landed and fully accepted for managed repository sources and existing checkouts. The earlier merge and final feature-acceptance prerequisites are satisfied. Keep this broad parent open for genuine remaining rendering/windowing, quiet-host performance and release follow-ups. Loaded-host measurements do not prove that all performance goals pass.

2026-11-07 final review and installation update. Native stack #302 has 21 non-draft layers, #299 through #320 excluding stack number #302. Every PR contains its exact declared base and current main db52ec09, is mergeable/CLEAN, has green exact-head CI and zero unresolved review threads. Final tip ab905365. Local make verify passed 4,892 tests with nine expected default-tier skips, 384 golden scenarios, both audits and distribution checks. Three opt-in real-gh PR sessions passed separately. Independent review and built-in browser sessions cover checkout and managed modes, loading/reconnect/cache behavior, keyboard disclosure and shared Markdown/PR layout. Both default CLI names and user previews run 0.11.1.dev1214+ab905365; the installed skill matches source. Ready for owner merge. Owner acceptance mb-i9ll, landed/release reconciliation mb-5k2w, quiet-host/tagged-head comparisons and clock-provenance follow-up mb-irrw remain tracked in their existing scopes.

November 8, current forward checkpoint (supersedes older current-install/awaiting-landing notes): native stack #339 is registered remotely as PR #337 at c3d093d2d222ddce74568e7c74111e2cc0c57d3f, then QA PR #336 at 0a0319daf2d99105aed2ec4c1528f2da4b1d7187. Both heads passed their complete normal gates and all nine PR CI jobs; latest #336 run is 42523716622. The installed application remains exact c3 for both default aliases and the three retained previews. The managed browsed snapshot remains e1cf; that data pin is distinct from the application source.

Local SDK-template readiness commit d69e3e71f876904bbbc116d87e5e14b5f9da1e8d adds the focused mb-vnm1 fix and two minimal plan-status corrections above QA0a. All thirteen unchanged blobs have independent review; integrated checks passed 44 focused pytest cases, one golden, both browser type projects, parity and hygiene. Startup remains twenty requests and 178592 bytes, with 1119 bytes below the unchanged ceiling. Eight live GitHub checks passed in 53.25 seconds. The normal complete gate/push is running in root session 22632; no gate completion or new SDK PR publication is claimed. The new vnm1 P1 release-blocker fix still needs its qualified artifact, CI, installation and cold direct-view replay before closure.

Selected DATA, Parts A/B/C, the corrected full396 browser run and Quick Search supplement, and the 55-file CLI/apply plus four manual browser cells are accepted at their exact historical 426 scope with raw exceptions retained. They do not qualify all later source or quiet performance. mb-06p9 and mb-4ifm retain the 18.7-second Source warning, native-stack poller diagnostics and the current slow managed refresh; causal phase attribution and quiet qualification remain open, with no c3 regression-origin or latency acceptance.

Final publication still requires the owner's approval of the exact final commit and complete notes. The full installed QA/owner matrix, quiet release/navigation/large-PR/Step9 gates remain separate. mb-itzy's future live-worktree workflow remains explicitly paused; reference draft #247 is excluded. No PR merge, release tag or publication is inferred from this checkpoint.

November 8, SDK readiness R2 checkpoint: clean forward commit a17752dd9695b3cdd4ed17926b6c0289cfd60fc0 contains the unchanged thirteen implementation blobs approved in Review A plus three fixture-only blobs approved in Review B. The original d69 normal full gate R1 failed two existing preview No Plugin assertions, with 4929 passes and nine skips; it stopped before goldens, audits, artifact build or push. R1 remains failed and supplied no qualified artifact.

The preview fixture omitted the real Mustache bundle that the production server publishes. The three-file correction uses the actual library and asset loader, retains both original No Plugin assertions and every existing displayed state, adds four expected request-list entries and one real template failure/retry scenario. It changes no production code. Integrated preflight passes 52 focused tests in 2.72 seconds, all 388 goldens in 230.78 seconds, both type projects and parity. The second normal full gate/push is running in root session 30931; no completion, new SDK PR, installer GO, qualified wheel, installation or cold direct-view replay is claimed.

Remote native stack #339 still has exactly two members: PR #337 at c3 then QA PR #336 at 0a. Both are reviewed and all nine CI jobs are green. The SDK successor will be published only after its normal push gate completes. The vnm1 release blocker remains open pending the actual qualified artifact, CI, installation, cold replay and merge reconciliation.

All global server preparation includes four ports: 8411, 8864, 8863 and concurrent 8412, whose effective target matches 8411. All remain on installed c3 now. The user authorized updating all; root will preserve each URL, target, configuration and working directory, including 8412, through controlled restart only after a qualified-wheel GO. No server or installation change has occurred in this checkpoint. The earlier 45 asset comparisons cover the three audited previews, not a new four-server validation.

Historical 426 differential acceptance and raw exceptions remain separate. Quiet performance, source warning attribution under mb-06p9/mb-4ifm, Step9, the full installed owner matrix and exact final release approval remain open. No latency pass, c3 regression origin, release tag or publication is inferred. The mb-itzy workflow remains paused and reference draft #247 excluded.

November 8, qualified SDK R2 delivery (no closure before actual merge): exact a17752dd9695b3cdd4ed17926b6c0289cfd60fc0 passed normal full make verify/push in 1493.61 seconds, with 4931 Python passes, nine expected skips, 388 goldens, clean types/locked audits/distribution/smokes and zero-byte filesystem observer. Original d69 R1 remains failed with two fixture assertions and no qualified artifact or push. Review A is published at https://github.com/jlevy/metabrowser/pull/340#pullrequestreview-5819928655 and Review B at https://github.com/jlevy/metabrowser/pull/340#pullrequestreview-5819928920, covering unchanged reviewed blobs.

SDK PR #340 is now the third member of native stack #339 above #336 and #337, exact a177 on QA0a. Its current CI workflow 42529805379 is running; prior #337/#336 exact heads retain nine green jobs and reviews. All three are drafts in the current metadata snapshot. No merge readiness is inferred from a successful local gate alone.

Both global CLI aliases and all four known servers (8411,8864,8863,8412) now run exact qualified wheel 0.11.1.dev1296+a17752dd9, SHA-256 e6971cfca83f37b84761ef847ed9a358a7723c5301a339b19f153a6f44d42df0. Doctor eleven, 45 unchanged runtime pins, 349 payload files, 355 installed RECORD hashes and 68 served-asset matches pass. Existing targets/configuration/working directories and port8412 URL were preserved. Managed data remains snapshot e1cf, distinct from application source.

The first literal cold entry on reserved fresh origin8986/long-controls.md passes the expected heading, Card, copy control and paste field without the prior Mustache error; root is continuing the full authored SDK replay. That initial result does not complete cold Reload/continuation checks, actual downstream SDK migration, the owner matrix or performance acceptance. Keep vnm1 open until completed replay, exact current CI and actual merge reconciliation.

Fresh remote facts supersede the prior unmerged-research plan: #338 merged unchanged48fec at21:51:06Z into main196ee3c5458b39bcc616f414cc1d1db0f5083f06. Review A findings A1/A2/A3 have no published disposition in the fresh sweep. The standing grant is now effective on main, so the earlier still-ineffective-proposal revert rationale is not an operation already performed. Main196 is not an ancestor of lower c3, even though GitHub reports337/336 CLEAN; root owns the forward-base incorporation and propagation decision, with actual resulting qualification/CI. No refs or source are changed by these notes.

Historical426 differential acceptance/raw exceptions, c3 manual evidence, slow-fetch/Source/poller diagnostics, quiet release/navigation/large-PR/Step9, full installed QA and owner release approval remain separate. No latency pass, new regression-origin claim, release tag or publication. The mb-itzy workflow remains paused and reference247 excluded.

November 8 forward-integration checkpoint: all nine SDK a177 CI jobs pass in workflow 42529805379 and its watch exited zero. The selected installed authored SDK replay is complete: cold long Card, long/small direct Reload, exact 38-character short and 2,960,074-character long copy/paste through final row 040000, initial Source 524,288 characters and two continuation controls. Full Source continuation retains its earlier unchanged-renderer c3 proof and was not rerun at a177; inspection deadlines remain preserved with no timing claim. Product stack menu and Checks-preserving selection pass. Fixture tab 74 is closed; identity-verified PID 79738 received SIGINT, and process/listener 8986 are absent. The four global servers and installed 0.11.1.dev1296+a17752dd9 remain unchanged. Authored integration coverage does not complete actual downstream/owner acceptance.

Main196 forward merges are complete locally: PR #337 head308d72c460ce7d3494c3e169e719759bda5f7388, #336 head5784d8031e5f07fdb68051d2e80b050c013cd399, #340 head8a6c80c66b84e8c7abf17998f1094f2ec08fddef. Each merge increment equals the exact five documentation/policy paths from main and preserves 974 runtime/test entries and the original layer delta. Independently approved fourth local layer b2fb62099f9c8a3a628edc2a1a76d31505c63c6a on codex/research-acceptance-corrections-20261108 contains only four A1/A2 research correction hunks in one document, fourteen added and six removed lines. All four local heads are independently approved.

The normal full gate and atomic, non-force four-ref push at b2fb are running; no completion, new integrated-head qualification/CI, published heads or new fourth-layer PR number is claimed. Installation remains a177. Actual merges and exact-head reconciliation are still pending, so this bead is not closed. Research #338 is already merged; A3 remains open for owner disposition of the effective standing grant, and this step contains no policy revert or native-app architecture adoption. Quiet performance, Step9, complete installed QA, owner acceptance and exact final release approval remain open; mb-itzy stays paused and reference draft #247 excluded.

November 8 published integration/delivery checkpoint: native stack #339 now has four remote layers, #337 at 308d72c460ce7d3494c3e169e719759bda5f7388, #336 at 5784d8031e5f07fdb68051d2e80b050c013cd399, #340 at 8a6c80c66b84e8c7abf17998f1094f2ec08fddef and #342 at b2fb62099f9c8a3a628edc2a1a76d31505c63c6a. Independent follow-up reviews are published and verified: #337 E 5820091134, #336 C 5820092952, #340 C 5820094242, #342 A 5820097396. Exact b2fb normal full gate passed in 1,317.35 seconds: 4,931 Python passes, 9 skips, 388 goldens in 204.14 seconds, clean audits/distribution/smokes and zero-byte observer; atomic four-ref push exited zero. Fresh #337/#336/#340 CI each has all nine passes; #342 has eight passes and Python 3.14 running at this checkpoint. Actual merges remain pending.

Qualified b2fb tree 8d69ce06a4054c4a394248c36ba05e12ddd38fcc wheel 0.11.1.dev1304+b2fb62099 SHA-256 7c6c304373329ecc35ff01dd0a05e9c4a9d68ae6d087292e9f681b6ba697f50f is installed for both aliases and all four global servers. Doctor eleven, 45 unchanged pins and 68 served assets match, preserving targets/configuration. Selected SDK manual replay completed at prior a177; its owned fixture process/listener are cleaned up. No new performance or full downstream/owner acceptance is inferred.

New release blocker mb-9e1t is under mb-4bd2, which depends on it: simplify canonical metabrowser.config/cache identifiers and graceful malformed-config guidance, no permanent old aliases/f02 compatibility, retain f01/v1 payloads. A successor from b2fb is being implemented. User explicitly authorized the private one-account alpha upgrade; read-only inventory found one config root, one cache root, 17 headers and valid config. No account writes occurred. Automatic review rejected raw YAML backup duplication; a safer reversible delta-header journal is planned and the user was informed. No migration success or delivered fix is claimed.

The user explicitly separated macOS spike #341: another agent owns its reviews/fixes, our partial read-only review stopped unpublished, and open mb-ndeh under mb-rvcj is not a release blocker. Research #338 is merged; A1/A2 corrections are in published #342, A3 effective-grant owner disposition remains separate/open with no policy revert. Quiet performance, complete installed QA and exact owner release approval remain open; no tag/publication authorization. mb-itzy stays paused. No bead closure before actual merges.

November 8 actual delivery. Native stack #339 atomically merged PRs #337, #336, #340 and #342 into main a2677882a2281a1e5b622acf4788ded9e5516331 from 23:27:15 to 23:27:18 UTC. Its tree 8d69ce06a4054c4a394248c36ba05e12ddd38fcc matches qualified installed b2fb exactly. All four PRs and merged main passed nine CI contexts. https://github.com/jlevy/metabrowser/actions/runs/42535251691

The installed b2fb browser showed Open 2, Closed 325 and All 327 without Reload, fresh foreground #336 Merged with 18 successful checks from two nine-context CI runs, then restored Files. The prior a177 593 ms background prepare-receipt warning remains under mb-4ifm and supplies no CPU attribution or timing qualification.

Scoped Unicode, reconnect, Treemap, QA document and SDK fixes delivered. PR/Git performance and broader release work remain on their respective beads. The user keeps mb-itzy paused and #341 separate. Draft #247 is reference only.
