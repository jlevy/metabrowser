---
type: is
id: is-01m6g59qm4ewjgek4vjmndcxrj
title: "Stabilize PR review stacks: rendering, checkout workflows, review gaps, performance"
kind: epic
status: closed
priority: 1
version: 37
delegate: claude-code@spud10.local
labels: []
dependencies: []
child_order_hints:
  - is-01m6g5eq1rdb9f15dx2kecf1p0
  - is-01m6g5eqdtdmc5pj1eb9ryy6s1
  - is-01m6g5eqspq97btjbwk0nhwcjw
  - is-01m6g5f41jkfzt0ywcsgxms6j4
  - is-01m6g6cagcckfs78k2ddzs1zz9
  - is-01m6ghtfstncw2xgewnwzvjr6y
  - is-01m6gm8jmy63yqmzcqrvhahnra
  - is-01m6gpx262g6vfcn9s8dchjq2r
  - is-01m6gqtjg4ebm3h0w7hz9gyd46
  - is-01m6gvbnpx1qywge9tfh33h8s1
  - is-01m6h3s8en6hje5zrdtjbja9pk
  - is-01m6h3va3ry0j6ct473xy5wqn2
  - is-01m6h4nw538w9tme59sgg8917h
  - is-01m6h5a8c671spvr36mtqjpf62
  - is-01m6h5a8rbfbgfvrv9q3g3jj62
  - is-01m6h5a94yzpd0bmy8edq4z824
  - is-01m6h5a9g5ddg45d493gd41g2g
  - is-01m6h5a9vdhrjr479p67xy5wxr
  - is-01m6h5aa6zjcc6y9xgfjhs2ay0
  - is-01m6h5aaj3kfc3t71kra95axh9
  - is-01m6h9761vr0ay7nfd0fcta7zg
  - is-01m6h976dzh2bc0jzd7qhdrz69
  - is-01m6h976s1n784zvdzv30ny11j
  - is-01m6h9774ejbxc15dh0d3h4njk
  - is-01m6h9cdfbssfhw070vzh342qy
  - is-01m6h9cdtr5yhgk4wpjhg5kdpw
  - is-01m6h9ce663frjs7y677k6xf8w
hold: null
hold_until: null
created_at: 2026-11-03T07:34:38.973Z
updated_at: 2026-11-03T20:17:10.834Z
started_at: 2026-11-03T07:35:09.898Z
closed_at: 2026-11-03T20:17:10.833Z
close_reason: Stack stabilization and review completed at ea771741. Owning PR status sections and published reviews/dispositions record the exact validation. All 171 current-head CI jobs are green; no remaining reviewed blocker. Residual baseline observer follow-up mb-czrw is now under mb-2iok. Merge-only, quiet-machine performance, browser/release acceptance and broader epics remain open. No PR merged.
resolution: null
duplicate_of: null
---
Audit stacks 278 and 286, preserve completed reviews, review uncovered changes, stabilize PR rendering for existing worktrees and managed repository stores, and validate through the established performance loop. User authorized subagents and implementation in this session.

## Notes

2026-11-03 takeover progress: all uncovered product changes now have independent source review and fixed-finding rechecks through integrated 64afc0d9. Final real-Chrome QA passed managed repo URL, readonly main and linked checkout subdirectories, file navigation/history/current-file, explicit repair pending/completed/failed/recovered, and light/dark wide/narrow rendering; 25 checkout/common-Git fingerprints unchanged. Font layer 280 is pushed and all nine CI jobs green. Full local gate at64 passed lint/types/contracts/parity and 4647 Python tests with9 legitimate skips; two stale Python comparison-route goldens need owning-layer corrections, alongside two registry transcript updates. Four-doc workflow correction b6a0074c independently reviewed clean. Final forward-only propagation, exact-head full gate, normal push hooks, per-layer remote CI, formal review publication/dispositions and final additive harness remain in progress. No PR merged or history rewritten. Source behavior is frozen pending those gates; Low baseline-matched observer diagnostic tracked in mb-czrw.

2026-11-03 12:00 UTC: finalization held for newly reproduced Medium G1, mb-4vsk. The complete local gate at 58270d69 passed (4,649 Python tests, 373 tryscript checks, audits, distribution/installed-wheel smokes); eight live public GitHub tests passed. A separate independent real-route probe then reproduced stale exact counts after corruption-time invalidation fails in a read-only manifest bank, backing objects are repaired, and process state restarts. Owning-head reproduction at #283 3cb49015 confirms this is lower-layer code. The normal atomic push was stopped during its quality hook with exit 130, and all seven source remote heads were verified unchanged. The exact-head acceptance driver was stopped cleanly: all 51 owned processes gone and validation ports free. Its full audit and partial raw data/browser evidence are preserved, not claimed as final acceptance. The earlier complete 64afc0d9 diagnostic has zero unexplained product differences. Writer is implementing a bounded private epoch fallback outside the bank plus nonmutating adoption eligibility checks, including permission restoration and stale in-flight writes. After independent recheck, root will merge forward, repeat exact-head gates and acceptance, then push normally and watch CI. No PR has been merged; port 8863 remains untouched.

2026-11-03 R4 freeze at ccb5927e508a1988196c8290754b0bc5356832b3. All seven updated layer heads contain both their current base and original published remote head. New G1 read-only manifest/restart defect fixed by ea891a57 and independently verified, including permission restoration and late stale writes. Current-main omitted-number PR API compatibility restored by 6d956e45 on #281; independent Review F is clean and the fixture-only successor481efd1d passes its recorders. Current-file mount subscription regression C1 fixed by ef297383 on #287 and independently verified: three nonquiet1627-file pairs improve longest load task217 to163ms and first painted text672 to606.1ms; held-row ranges overlap, so no held-speed claim. Final merge and test adaptations independently audited clean at exact R4:15independent Python probes,3696canonical parser cases,18legacy cases, G1 and D1/D2/C1 lifecycle controls. Fresh make verify and complete immutable-wheel v0.11.0 additive harness are now running at R4; eight public read-only live GitHub tests already passed at R4 with no skips in71.53s. Small final Chrome smoke and factual publication audit are active. Earlier completed diagnostic and superseded gates are retained as nonfinal evidence. Seven source branches remain unpushed pending normal final gates; #280 is already reviewed/pushed/green. No PR merged, no rebase/force-push, private repository unnamed publicly, original WIP refs and user8863 server preserved.

2026-11-03 R4 acceptance stopped cleanly for a further strict-additivity fix, mb-3rcp. #28054a9000c removed current-main ${VAR} dotenv expansion to avoid quadratic work. Existing review requested this and documentation acknowledged it, but no explicit owner approval to break a valid logging setting was found. DEBUG/verbose/default examples reproduce the loss. Writer is implementing ordered compatible expansion with efficient prior-binding/shell lookups, bounded materialization and atomic file refusal. A new independent tokenizer check found the pinned variable regex itself quadratic on malformed ${ repetitions (32768characters9.375seconds); the fix must use an equivalent linear scanner, retain the64KiB regular-file input cap, warning deduplication and allowlist, and pass independent semantic/adversarial review. The exact R4 full gate stopped by scoped SIGINT at62percent with no reported product failure; all6ownedPIDs gone and no pass marker. R4 additive audit completed but data/browser partial, all39ownedPIDs gone/ports free/415control fingerprints unchanged. These are diagnostic only. R4 public live8passed and final installed-wheel Chrome17actions/25unchanged fingerprints passed. No source branches pushed or PRs merged. After owning#280 fixreview, mergeforward throughall8changedlayers, repeat all exact-head gates, normal atomicpush/hooks andremoteCI, thenpublish preparedreviews/dispositions.

2026-11-03 R5 frozen at 945012cac10f62c03a5f370e18e0a40099323f41. Owning #280 fix 2945bbfe restores ordered dotenv expansion with bounded work/output, UTF-8 and unchanged allowlist/precedence. Independent Review F is clean: 28 behavior/budget cases, 43 repository tests, 2,497 real-file and 335,923 direct token comparisons, baseline/negative/locale controls. Independent propagation audit confirms all eight changed layers contain their old heads, previous remote heads and new bases; every R4-to-R5 delta is exactly the five reviewed dotenv files. All 256 final JS/CSS blobs are unchanged; upper docs preserved. Fresh R5 installed-wheel Chrome smoke passes 17 actions with 25 unchanged fingerprints and no external requests/application errors. The unchanged installed V2 probe matches current main in all 18 dotenv cases, and legacy PR API/header/default behavior also passes. Full make verify, complete fresh additive audit/data/browser matrices, and public live tier are running at this exact SHA. No source branches pushed yet, no PR merged, original WIP refs and8863 server preserved. Next are normal atomic push with its complete quality hook, every layer CI, formal review/disposition publication, readiness and tracking sync.

2026-11-03 R5 full gate result: 4,696 Python tests passed with9expected skips; tryscript370passed/3failed. The three failures are stale expectations from independently reviewed runtime changes: #281 numberless/no-attended GET now200legacyabsence instead of400, #281 empty-body/no-attended POST409no_pull_request instead of400, and the #288 mount-session transcript lacks the three new true C1 lifecycle result fields. Agents are correcting exactly those recorded blocks and adjacent false number-required prose, with no production change. Child mb-gy9q tracks the two #281 blocks. The C1 block exists only in #288; no new lower #287 block is being added. R5 full additive run continues at its immutable actual wheel; its audit A/B/C is complete with all inherited residuals explicitly explained. We will prove complete product/source/lock equivalence for the transcript-only successor, retain R5 provenance honestly and run complete make verify on the final successor. No final-pass marker or push/merge occurred.

2026-11-03 owner clarification: this is a new feature stack whose frontend and backend ship together on one local server; there are no old-client backward-compatibility constraints. Earlier interpretation of additive as preserving omitted-number PR calls was too broad. Compatibility-only API aliases and the extra dotenv expansion resolver have been forward-reverted, without rewriting history. #280 ed400452 is tree-identical to reviewed64fa; #281 a30750dc restores required numbers with focused current-contract tests. Final clean composition de87065ded8a606f21fb85093474c8ca0cc50cbe has its entire src tree exactly equal measured/reviewed68db82b5 (treeca658425530ac05b2202ba7f9d223ade08fbd9f4), preserving all G1/cache/recovery/navigation/rendering fixes. All live frontend and CLI calls/current runnable examples supply explicit numbers. Root focused148tests passed147.07seconds; full exact-head verification, independent composition audit, Chrome smoke and public live checks are in progress. R6 ed0 full makeverify passed before this policy clarification and is retained as superseded evidence. The complete945 diagnostic run (20527data/1320browser/120file/three connectionpairs) is preserved NONFINAL, not a backward-compatibility gate or owner-signoff requirement for new PR API shapes. No source branches pushed yet beyond earlier font64fa; no PR merged; all merges forward; original WIP and8863 untouched.
