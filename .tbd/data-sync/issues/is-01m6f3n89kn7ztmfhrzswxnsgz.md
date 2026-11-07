---
type: is
id: is-01m6f3n89kn7ztmfhrzswxnsgz
title: "Review pull requests well on large repositories: fresh mirror and existing checkout"
kind: epic
status: open
priority: 1
version: 65
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
created_at: 2026-11-02T21:46:44.914Z
updated_at: 2026-11-07T02:27:19.107Z
---
The owner's goal, 2026-11-02: review PRs seamlessly both fresh from the cached mirror and from an existing checkout without duplicating its storage, responsive on large PRs faster than GitHub itself, following the design system rigorously, with all workflows documented cleanly. Found by testing on a real 1.2 GB private repository with a shallow checkout and 211 linked worktrees. All work lands on branch claude/v012-pr-review-workflows, above release stack 278. The Pulls tab itself is a separate stack in the linked session: mb-q3jt, mb-x174, mb-zx9q, mb-cbak, mb-r50o, mb-lnkl, mb-iw1v.

## Notes

Current checkpoint: first9featurePRs are actually merged to main8aae81d0. Remaining12forwardcascade to f9e8c524 has exact whole-tree equality to reviewed a4; normalatomicpublication succeeded, freshheadCI/nativegroup/artifactchecks still pending. GlobalinstalledCLI/previews remain verifieda4 (samecode) pending finalmain replacement. Mandatorypostlanding integratedreview/docs/skills/plans/beads remains mb-ao35. Preserve draft247/WIPs and audit .tbd/config.yml; clean independent landingcheckout is /Users/levy/wrk/github/metabrowser-landing-01a1a051.

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
