---
type: is
id: is-01m6mp811vf52jmazawykb3bw6
title: Make PR and Git navigation feel immediate with measured prefetching
kind: feature
status: in_progress
priority: 1
version: 30
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex-prefetch
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
child_order_hints:
  - is-01m6mph0qe489751nr9gb2hfq3
  - is-01m6mpjbb70kg8tdwgznd5tdvx
  - is-01m6mpjbqxs81cdgeg8fgjgjat
  - is-01m6mr68zq45xz8wz6das0q2x6
  - is-01m6msqxnfdpdgj9d3bykq9knv
  - is-01m6mt130svbg10hxkvkt62bhx
  - is-01m6mv2e96yj34gqsra4f0prmz
  - is-01m6mwaa51n75m8kxnprppnr6n
  - is-01m6mwzwzd4jmbe0jbpxqpep3j
  - is-01m6mzhaqwfp2frzwkpyjh7p62
  - is-01m6n17whe9tnqh95c7j5560rr
  - is-01m6n43mfv1y88nsemyc2y3tqq
  - is-01m6n43xgpc5a5py8rt60gjma8
  - is-01m6n5xwntvy5fmqtrewb5kp9z
  - is-01m6n96gp3d4kaba25mk0nrbbq
  - is-01m6ng3rk55p8sm1970bqkvqmv
  - is-01m6pgx59g8t2jp6t48c8y95bz
hold: null
hold_until: null
created_at: 2026-11-05T01:47:46.617Z
updated_at: 2026-11-08T11:44:51.303Z
started_at: 2026-11-05T01:47:47.197Z
---
Improve perceived navigation latency for pull-request selection and Git history on a new branch from verified main. Follow the existing performance-loop framework: register a few falsifiable hypotheses before implementation; test their mechanisms on the unchanged build; use frozen subjects and explicit cold, warm, prepared and unprepared cache states; measure trusted input to exact useful painted content, including server, decode, asset and mount phases. Confirm accepted changes with interleaved repeated controls and candidate runs, preserve correctness/cancellation/account/source ownership and bounded background work, and record rejected hypotheses as well. Reuse existing harnesses and concise session/golden tests rather than adding a parallel framework. Preserve the default installed verified build and the two user preview servers while experimenting; install a successor only after verification. Track actual timings, ranges, bytes, request counts/concurrency, long tasks, CPU/RSS and cache provenance. Branch: codex/perf-prefetch-20261104. No speculative product changes before diagnostic evidence.

## Notes

November 8: scoped prefetch fixes delivered

PR #334 merged at fe04a4b1cfb25cc16e1e8399252f4b664633a6c6, whose tree exactly equals gated 1ede1e220. Independent A–D reviews, full verification, all nine PR and all nine main CI jobs passed. Both aliases and all three previews now run 0.11.1.dev1283+1ede1e220. Functional sessions pass for checkout/managed PR334 Conversation, six-file Changes and nine Checks, independent Commit/PR restoration, #/title/number Quick Search and Markdown gutter/padding. Scoped correctness beads mb-b0aq and mb-ygiq are closed and synced.

Retain a real current-build observation for the measurement round: managed8863 emitted a slow-fetch warning at 11:24:45Z for POST /api/plugin/github/pull-refresh, 2014 ms total / 2010 ms server / 4 ms transit, response1598 bytes. Concurrent functional make verify was running. No cache classification, first-useful-paint measurement, causal attribution or regression conclusion is established. This is recorded in b0aq-mechanism-20261108/installed-browser-verification.json; do not hide it as clean console output or treat it as a quiet comparison. H74 cold assets, H75 natural intent/request joining, quiet large-PR comparisons and the 100 ms prepared-paint target remain open.

November 8: navigation stabilization on new branch

Verified main through PR #333 is merged and installed as a2bb0d29a. Same-identity catalog replacement was confirmed to cancel unfinished PR core preparation; mb-b0aq owns the focused correction on codex/v012-navigation-performance-20261108. Initial commit ea1c5ace passed focused checks and received independent senior, correctness and resource-lifetime passes. Review B1 found a real late-receipt cursor race at 600 rows (599 current cores, then no timers); mb-ygiq is claimed for correction before full verification. No paint/latency speedup is claimed. Backend attempt leases remain intact. The future branch/worktree chooser mb-itzy remains paused.

Cold-asset attribution mb-5rm1, natural intent/request joining mb-97ex, quiet large-PR comparisons mb-jwfx and render-window qualification mb-mwuz remain open. Regular-folder exp-057 collected zero pairs after quiet preflight deferred for unrelated host activity. Final source-frozen measurements follow the reviewed/gated correction; they are not replaced by virtual scheduler tests.

November8 current scope reconciliation: deliveredprefetch/UIstacks302and331 plusdocumentation332 mergedthroughmain240da85cbb45b72defed0084aadc99ee0be234ed anddefaultinstallede204. Do not treat oldawaitingmerge notes below ascurrent. ThisP1navigationperformanceparent remainsopen for H74coldassetattribution(mb-5rm1), H75naturalintent/requestjoining(mb-97ex), andinitialcorecohortfairness(mb-b0aq). Private3hypothesisprotocolprepared in navigation-performance-preparation/protocol.json usingexistingexp055playbook/recorder; currentprepared/cachedpainttarget100ms, historicalexp052150ms isdifferentcriterion. Existinggit-revisionsscenario warmsassets andcannotmeasurefirst-tabdelay; genericcomparecorrectlyrefusessamebuild. No newmeasurementsorproductionprefetchchanges made. Finishreviewedloadingownershipfix mb-4mfc, merge/installverifiedsuccessor, thenmeasureonnewbranchfromverifiedmain withfrozen cache/build/subjects, >=3admissiblerunspercondition and>=5interleavedpairsforeffects<2x perexistingrules. Regularfolderexp057 isseparatemb-cf6y anddoesnotclearPRnavigation. QuietlargePRqualifications mb-jwfx/mb-mwuz remainexplicit. FutureFileslive/cachedbranchworkflow mb-itzy stayspaused, noimplementation. No release/tag/publicationapproval.

First performance layer: PR #299, 0d1b132d on main base db52ec09. Independent review clean, full local verification and normal push gate passed. GitHub CI is running. The bounded visible-PR preparation remains a separate measured experiment (mb-oywk).

PR #299 is mergeable and all nine GitHub CI jobs passed, including admitted Git 2.43 and 2.50. First-layer beads closed. H74/H75 broader diagnostics and the visible preparation experiment remain open.

Confirmed two more layers using the existing hypothesis, paired measurement, and unchanged gate workflow: selected settlement (mb-dmby, exp-051), then bounded visible descriptions (mb-oywk, exp-052). H81 depends on H82. Both manually verified in existing checkout and URL-managed mode, with repository verification running. Default CLI remains verified main.

Exact full gate passed for 1a39e43b stacked above 034d1491 and PR #299. The two additional layers are in the ordinary atomic pre-push gate; native stack linking and exact CI remain.

Native stack #302 fully verified and ready for owner merge: #299 0d1b132d, #300 034d1491, #301 3c8acd21. All three clean, non-draft, and 9/9 green. First-layer Qodo dispositions published, and all four top-layer findings fixed/resolved with review evidence. H81/H82/H83 scoped beads closed. Default installed CLI remains verified main. Broader H74/H75 diagnostic beads remain open.

Installation and review follow-up: both default CLI entry points now run the verified stack-tip wheel 0.11.1.dev1162+3c8acd21. The installed doctor passed all 11 plugin checks and the older preview processes were stopped. GitHub still shows the same three heads in native stack #302, each mergeable with all nine checks green. The remaining #299 thread has a recorded rebuttal and awaits reviewer closure. The stack awaits owner merge. The H74 and H75 measurements are open follow-ups outside this delivery.

Pulls UI status follow-up mb-bn0z is complete in PR #303, the fourth layer of native stack #302 above #301. Exact head 5c8cb75b passed all nine GitHub CI jobs. Both installed CLI entry points now run verified 0.11.1.dev1165+5c8cb75b.

2026-11-07 stack readiness update. Native #302 now has 21 clean, green and reviewed PR layers through #320 ab905365. The accepted prefetch experiments and later UI/caching work are integrated forward with current main included. Final full gate, three opt-in real-gh sessions and checkout/managed browser checks pass. Both default commands run 0.11.1.dev1214+ab905365. Owner merge is the next landing step. Existing quiet-host and tagged-head performance qualifications continue in the separately scoped beads.
