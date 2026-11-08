---
type: is
id: is-01m5wdbsy6z6d95sgg03kwmm76
title: "Coordinate the 0.12.0 release: tag and publish from main"
kind: task
status: in_progress
priority: 1
version: 17
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: codex@spud10
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
child_order_hints:
  - is-01m6wdjwawp9g1bvnefz2hxze3
  - is-01m6wpgzn59yqd9ba9d3kae44m
  - is-01m6wq6jdpw2gshn84zxcr8ewd
  - is-01m6xa4ytymbe41wm6ta709yt9
hold: null
hold_until: null
created_at: 2026-10-26T15:30:46.852Z
updated_at: 2026-11-08T21:58:24.657Z
started_at: 2026-11-08T01:58:21.485Z
---
Coordinate tagging and publishing 0.12.0 from main. This replaces mb-n2ro, which coordinated the LANDING and is closed: the stack merged at 0b016e4b (PR #268, 2026-10-04) with CI 9 of 9 green. PyPI is 0.11.0 and there is no v0.12.0 tag.

Decided by the user on 2026-10-26: NO 0.11.1 patch release. main carries three breaking changes (Plugin SDK 0.6 to 0.7, the cache and configuration XDG split, the stronger meaning of --untrusted and --no-active-content), so it cannot ship as a patch, and a cherry-pick of the plain-folder fixes off v0.11.0 would be real work to deliver fixes that 0.12.0 ships anyway. Version is 0.12.0; later QA findings become 0.12.x.

The release is gated on the user's stated bar: everything additive on what exists, with what is missing tracked in the plans and beads.

ORDER OF WORK

1. Security and gate mechanics. DONE on branch claude/v012-release-prep: tryscript 0.3.0 reached the vulnerable zod 3.25.76 and `make audit` failed on GHSA-mrhx-c7xc-m3w5, so `make verify` failed on main even though CI was green three weeks earlier. Bumped to tryscript 0.3.1 (first-party exemption, reviewed in SUPPLY-CHAIN-SECURITY.md); lock delta is exactly two packages and zod 4.6.6 clears the ordinary cool-off on its own. The non-security upgrades were deliberately reverted and are mb-1jq3.

2. Re-run the landing gate on the release head (mb-2g6f). All three differentials were taken at 14fcdb85 and #268 landed above them with a breaking storage change, so none covers what would be tagged. The browser differential was never read even at the old head. Harnesses survive in the sibling folder metabrowser-landing-gate-evidence: data/run.sh (about 90 minutes, run detached), audit/run.sh, browser/run.sh (about 45 minutes, node 24, Chrome, ports 8851-8858). Corpora are gitignored and rebuild from data/build_corpora.py and browser/make_corpus.mjs. Accept rule unchanged: zero unexplained differences.

3. Release rehearsal step 3 on a quiet machine (mb-cf6y). exp-039 was never recorded; the experiments end at exp-038, which did not clear the candidate because wall-clock gates failed for BOTH builds under load. Needs 5 headed pairs and 5 compare_builds pairs with no agents running. The host was at load 11.5 on 2026-10-26, so this cannot share the machine with other work.

4. Full QA runbook on an installed wheel from the release commit, plus the human-only matrix (the two open P1 children of mb-425f): Chrome, Safari and Firefox; a readable and an unreadable private repository; an external Plugin SDK 0.7 plugin; and real-browser bfcache acceptance, which is the only part of mb-tdmd still open.

5. Documents up to date (mb-bdwl) and the owner's sign-off on the behavior-change record, which must first gain the #268 storage split.

6. Then the standard checklist in docs/publishing.md, steps 6 to 10: `gh release create v0.12.0`, watch publish.yml, verify PyPI metadata, uvx smoke, and the public Agent Skill check.

WHAT IS VERIFIED ADDITIVE (hand-checked on main, 2026-10-26)

The GitHub features are inert without GitHub, and degrade rather than fail without credentials. On a plain folder /api/plugin/github/pull answers state absent with reason no_pull_request at 200, and pull-markdown answers 409 no_pull_request. With NEITHER git NOR gh on PATH and an empty environment, --show and --api /api/tree on a plain folder both work and exit 0, and isolated --cache-dir and --config-dir are left uncreated, so a plain folder leaves no footprint. --doctor reports 11 plugins OK and exits 0 with no git and no gh. A GitHub URL with no git refuses with a typed message, exit 1, no traceback and no cache created. A pull-request URL with git but no gh clones, pins the default branch, exits 0 and names gh_missing as the reason.

WHAT IS NOT ADDITIVE, and needs the owner's decision

The GitHub work is additive; these are separate and each is intended and documented:

- Plugin SDK 0.6 to 0.7 is a HARD GATE, confirmed by hand: a third-party manifest declaring 0.6 is refused at load and --doctor exits 1 naming the fix; at 0.7 it passes. Any external plugin must be updated. Hand-written data-mb-copy controls and hand-built Load more buttons also go silently inert without the page's owner mark.
- The cache and configuration XDG split: METABROWSER_HOME and the old home layout are no longer read. Existing files are left untouched, so nothing is destroyed, but a user who set METABROWSER_HOME must move to --cache-dir / --config-dir. This landed in #268, AFTER the behavior-change record was written, so it is not yet on the sign-off list.
- --untrusted and --no-active-content now render Markdown inert and apply a Content-Security-Policy on a folder, where v0.11.0 only dropped allow-scripts from the /raw sandbox.
- Smaller CLI changes: `metab ""` is refused; a scheme:// argument is always a source; a failed server start exits 1 where v0.11.0 exited 0; source views gained a line gutter; --doctor is about 250 ms slower, 1.78x by design.

The full list with how each was checked is docs/project/reviews/review-2026-10-01-v012-changes-to-existing-behavior.md.

PRACTICAL CONSTRAINT: on 2026-10-26 the data volume was 94 percent full, 403 GiB used of 460 GiB with 26 GiB free (read /System/Volumes/Data, not /, which is the sealed system volume and reports misleadingly). Worktrees are NOT the cause: 40 of the 49 worktree records are stale pointers to directories that no longer exist, so `git worktree prune` cleans records and reclaims nothing, and every metabrowser checkout together is under 2 GiB. The differentials need rebuilt corpora plus two installed builds, which 26 GiB should carry; the 300,000-file flat-stress pass from exp-036 is what disk blocked before, so check free space before attempting that one specifically.

## Notes

November 8: stabilization completed

PR #333 merged forward at main 9416b78b8dc2657a3e1745f5d6b7152c9dfc6e98. Its full tree e933e676afc54d99521986f709c6c8ecd2e7717f equals reviewed head a2bb0d29ab6165dacf95705bf189b2208b96c534, retained as an ancestor. Independent Review A has no open findings. All nine PR CI jobs and all nine merged-main jobs passed.

The exact gated wheel 0.11.1.dev1280+a2bb0d29a (SHA-256 81524fde0549e9111a76c94305fb578fef544e93cf9e08d340a4ea4389479bb0) is installed for both CLI aliases. Doctor reports 11 healthy plugins, all 33 served assets match, all 45 applicable runtime pins are unchanged, and the portable skill content is verified with its source pin advanced. Only the three verified old preview servers were replaced; cache, config, targets and checkout edits were preserved.

Installed browser checks pass PR-to-Commits in managed and checkout modes: correct commit, one connected diff, no remaining loading state. Managed preview selects main 9416b78. The original CHANGELOG route retains aligned card padding and right-hand contents. No current console warning/error appears after installation; old logs remain historical. Source checks also cover rapid replacement and independent tab restoration.

Complete exact-head make verify passed 4,917 tests, nine expected skips, 386 golden checks, lint/types, audits and artifact checks with zero filesystem errors. Red/green evidence covers loading-timer overwrite, superseded paint cleanup and superseded missing-commit freshness cleanup. All asynchronous cleanup paths were audited. The earlier interrupted push and partial e204 differential remain preserved, not relabeled as passes.

PR status and post-merge evidence are current. Release differentials, quiet performance/navigation work, final installed QA/owner acceptance and release approval remain separate and open. mb-itzy stays paused; no branch/worktree chooser implementation. No tag or release was created.

November 8 checkpoint: documentation #332 merged at main240da85cbb45b72defed0084aadc99ee0be234ed, tree equal to gated e204ce9b566eaf72f82bf36536fc780edd774a04. All nine PR and main CI jobs pass. Both default CLI aliases and three existing previews are installed from gated 0.11.1.dev1277+e204ce9b5 (wheel fe271138444c3ed8018b3d9889942c2bf3824dfa2d2f284b529de74cda15a723), doctor11healthy,30servedassets verified; managedpreview pin240. Installed QA reproduced commit-loading stall. mb-4mfc is now a release blocker: JS loading-timer overwrite and superseded-paint pending-claim races deterministically red/green; independent review clear after fixes,35focusedpytest+2goldenblocks+types passed; managed sourcepreview renders16files, existing-checkout smoke underway; fullgate inprogress before commit/push/PR. First fullgate stopped before tests on broad public-reference wording check; documentation uses explicit public links, check now passes; preserved first failure. Future branch/worktree chooser mb-itzy remains paused/design-only. No release/tag/publication approval.

November7 final implementation checkpoint: stack331 PR328/329/330 merged at d33550455d1a44bb275d5e71492f9bdbc682f0c5; full tree exactly equals reviewed/gated519c33239, retained as ancestor. All9 CI on each head and all9 merged-main CI jobs passed (run42449868134). Full519c verify passed4917/9expectedskips,385goldens, audits/distribution/installedwheel and0filesystem errors. Both globalaliases and3previews installed exactwheel0.11.1.dev1275+519c33239 SHA780a9922e2446d7e925717457d4cb7e9e5ffc4a9f3ae70ce630298d31e085768; installed browser sessions bothsource modes passed PRtabs, stackmenus/ShiftJ preservingChecks, route restoration, Reloadkeyboard/layout, contextual actor typography. UIbeads am7d,x1v5,4kpu,xvz2 andcorpus lsm5 closed/synced. PartA audit at519 complete189files/1063indexedhunks/988uniquekeys/0unclassified/0unexplained; PartsB/C/data/browser remainopen. Final10MD userguide/changelog/design/QA/plan corrections under mb-ucc1 on codex/v012-release-documentation-20261107, independent read-onlyreview noactionablefindings, fullgate running beforecommit; not yetPRd. Futureworkflow mb-itzy remainsholdpaused per latestuserinstruction; no chooserimplementation. Exp056 valid444ms>350hardgate remainsunresolved, noquiet057 result. Hostloaded/scratchlimited; otherreleasegates andownerpublicationapproval remainrequired. No tag/release/publish.

November7 stabilization checkpoint: all28 productPRs in native stack302 are merged at68534af933f0fcb38a5d81d62691bb42732d58ab; that exact main passed complete verify, CI9/9 and installed-wheel checks and is installed. New additive follow-ups are c67371c2e (linked corpus roots and release docs),24f3721c9 (shared identity typography, positional stack controls, leading GitHub brand and Reload layout),519c33239 (retained exp056 and refreshed acceptance). All three have independent senior review; UI also has dedicated security/performance reviews. A Reload keyboard finding was reproduced and fixed. Normal pre-push full makeverify is running before publication; no newPR numbers yet. Release is not cleared: exp056 retains valid444ms>350ms hardbudget failure and incomplete comparison; exp057 on final candidate, final differentials, QA matrix and owner signoff remain. Final55file baseline comparison now has identical full CLI payloads and clean apply oracles, both browser layouts reach finalfile; finalartifact signoff pending. Future branch/worktree chooser is mb-itzy, explicitly tracked-only/deferred by latest user instruction. One unreproduced PR->Commits sourcepreview stall is mb-4mfc for finalwheel QA. Current release coordinator remains authoritative; never tag/publish before explicit user approval.

November 7, 2026: the user explicitly authorized merging the reviewed, green PR stack, followed by complete release preparation; cutting or publishing the release still requires the user's approval. The existing coordinator remains authoritative and the version decision remains 0.12.0, as decided on October 26. The current published baseline is independently confirmed as 0.11.0 on GitHub and live PyPI. Native stack302 has28 product layers; final ownership-fix verification is running at6cf001cdf before its last four forward updates. Sub-agents hit their usage limit; the root agent is continuing directly. New preparation task mb-gew9 coordinates the existing release tasks rather than replacing their acceptance bars: mb-2g6f/mb-8pyc release-head differentials, mb-cf6y installed-wheel performance rehearsal, mb-m20f full QA, mb-etqi human acceptance, and the final behavior-change/release sign-off. No tag, GitHub release or PyPI publication has occurred.

2026-11-01 status: the order of work above still holds. Done since: step 1 (#269); step 2 at 87712198, to re-run on the tagged head (mb-2g6f); step 5's documents in #272, open. make test-live-github 7 of 7 and make test-macos 19 of 19 on c934a0b4. The six open PRs #272-#277 merged together pass install, lint and 4,118 tests locally; merging them in that order conflicts only in #275 and #276, and each PR has a comment with the resolution. Still owed: required reviews of those PRs, exp-039 on a quiet machine (mb-cf6y), the full runbook (mb-m20f), the human matrix (mb-etqi), and the owner's sign-off.


2026-11-03, the pull-request layers above 277: PR 280 at 996ea90d and PR 283 at e8b7ff3d are reviewed and green; PR 284 at 9d6e0930 is green with E1 (High, performance) in progress. The Pulls tab is stack 286 on 283. Nothing is merged; merging waits for the owner.

2026-11-04 final landing update: all 23 PRs in this delivery (21 feature PRs plus #297 and #298) are merged on main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9. Postlanding Review E: https://github.com/jlevy/metabrowser/pull/298#pullrequestreview-5772391263. Final-main CI passed all nine jobs: https://github.com/jlevy/metabrowser/actions/runs/41868009781. The verified global CLI is 0.11.1.dev1154+db52ec09; final installed-wheel, browser, coordinator manual and production-cache acceptance are complete. Current feature landing is fully accepted. Earlier pending-gate or no-merge statements are historical; preserve each original build, test and measurement provenance. This does not claim a v0.12.0 release, a quiet-host performance result or completion of separate future work.

The old statements that #272–#277 or the later PR layers remain open and that nothing has merged are historical. This completes the current feature landing and local development-build installation only. Keep the release coordinator open for the quiet rehearsal, release-head differentials, full release runbook and human matrix, owner release sign-off, version/tag and publication requirements. No release tag, GitHub Release or PyPI publication is claimed.

November 8, current forward checkpoint (supersedes older current-install/awaiting-landing notes): native stack #339 is registered remotely as PR #337 at c3d093d2d222ddce74568e7c74111e2cc0c57d3f, then QA PR #336 at 0a0319daf2d99105aed2ec4c1528f2da4b1d7187. Both heads passed their complete normal gates and all nine PR CI jobs; latest #336 run is 42523716622. The installed application remains exact c3 for both default aliases and the three retained previews. The managed browsed snapshot remains e1cf; that data pin is distinct from the application source.

Local SDK-template readiness commit d69e3e71f876904bbbc116d87e5e14b5f9da1e8d adds the focused mb-vnm1 fix and two minimal plan-status corrections above QA0a. All thirteen unchanged blobs have independent review; integrated checks passed 44 focused pytest cases, one golden, both browser type projects, parity and hygiene. Startup remains twenty requests and 178592 bytes, with 1119 bytes below the unchanged ceiling. Eight live GitHub checks passed in 53.25 seconds. The normal complete gate/push is running in root session 22632; no gate completion or new SDK PR publication is claimed. The new vnm1 P1 release-blocker fix still needs its qualified artifact, CI, installation and cold direct-view replay before closure.

Selected DATA, Parts A/B/C, the corrected full396 browser run and Quick Search supplement, and the 55-file CLI/apply plus four manual browser cells are accepted at their exact historical 426 scope with raw exceptions retained. They do not qualify all later source or quiet performance. mb-06p9 and mb-4ifm retain the 18.7-second Source warning, native-stack poller diagnostics and the current slow managed refresh; causal phase attribution and quiet qualification remain open, with no c3 regression-origin or latency acceptance.

Final publication still requires the owner's approval of the exact final commit and complete notes. The full installed QA/owner matrix, quiet release/navigation/large-PR/Step9 gates remain separate. mb-itzy's future live-worktree workflow remains explicitly paused; reference draft #247 is excluded. No PR merge, release tag or publication is inferred from this checkpoint.

November 8, SDK readiness R2 checkpoint: clean forward commit a17752dd9695b3cdd4ed17926b6c0289cfd60fc0 contains the unchanged thirteen implementation blobs approved in Review A plus three fixture-only blobs approved in Review B. The original d69 normal full gate R1 failed two existing preview No Plugin assertions, with 4929 passes and nine skips; it stopped before goldens, audits, artifact build or push. R1 remains failed and supplied no qualified artifact.

The preview fixture omitted the real Mustache bundle that the production server publishes. The three-file correction uses the actual library and asset loader, retains both original No Plugin assertions and every existing displayed state, adds four expected request-list entries and one real template failure/retry scenario. It changes no production code. Integrated preflight passes 52 focused tests in 2.72 seconds, all 388 goldens in 230.78 seconds, both type projects and parity. The second normal full gate/push is running in root session 30931; no completion, new SDK PR, installer GO, qualified wheel, installation or cold direct-view replay is claimed.

Remote native stack #339 still has exactly two members: PR #337 at c3 then QA PR #336 at 0a. Both are reviewed and all nine CI jobs are green. The SDK successor will be published only after its normal push gate completes. The vnm1 release blocker remains open pending the actual qualified artifact, CI, installation, cold replay and merge reconciliation.

All global server preparation includes four ports: 8411, 8864, 8863 and concurrent 8412, whose effective target matches 8411. All remain on installed c3 now. The user authorized updating all; root will preserve each URL, target, configuration and working directory, including 8412, through controlled restart only after a qualified-wheel GO. No server or installation change has occurred in this checkpoint. The earlier 45 asset comparisons cover the three audited previews, not a new four-server validation.

Historical 426 differential acceptance and raw exceptions remain separate. Quiet performance, source warning attribution under mb-06p9/mb-4ifm, Step9, the full installed owner matrix and exact final release approval remain open. No latency pass, c3 regression origin, release tag or publication is inferred. The mb-itzy workflow remains paused and reference draft #247 excluded.
