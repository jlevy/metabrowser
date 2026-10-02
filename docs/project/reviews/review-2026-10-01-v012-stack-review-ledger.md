# Review: Per-Layer Review Ledger for the v0.12 Stack

**Date:** 2026-10-01

**Status:** A dated record, not a maintained table.
It lists what review each pull request of the v0.12 stack had, as the pull requests and
beads recorded it on 2026-10-01. For today’s state, run the commands under
[How This Ledger Was Built](#how-this-ledger-was-built).

**Scope:** One row per pull request, in stack order, from `main` to
[#265](https://github.com/jlevy/metabrowser/pull/265) at `481b64b7`, the top of GitHub
stack [#218](https://github.com/jlevy/metabrowser/stack/218). The landing checklist in
the
[alpha test plan](../specs/active/plan-2026-09-22-v012-alpha-testing.md#recording-results-and-landing)
asks for this ledger after all functional changes.
The previous one is the
[stack readiness review of 2026-09-22](https://github.com/jlevy/metabrowser/pull/216#issuecomment-5786877244),
a comment on #216 that covers the stack through #225. This record is evidence for the
landing decision (`mb-n2ro`), not that decision.
[#260](https://github.com/jlevy/metabrowser/pull/260), which adds this ledger, sits
above #265, changes documents only, and has no row.
Nor has the layer being written above #265 to fix the two regressions the landing gate’s
data differential found: it had no pull request when this record was last revised.

## Limits

Read these before the table; they bound what any row can mean.

- **No person has reviewed any of these pull requests.** Every review below was made by
  an agent, and most are recorded under the same GitHub account as the work, in the pull
  request’s description or comments.
- **No pull request has a GitHub review decision.**
  `gh pr view <n> --json reviewDecision` is empty for every one.
  The only review objects GitHub holds are three on #140, all of state `COMMENTED`: one
  automated Cursor Bugbot review and two entries with no body.
- **Fix rounds were mostly not re-reviewed.** Unless a row names a second round, the
  changes made in answer to a review were verified by CI and by the author’s own
  re-runs, not by a second reviewer.
- **Reviews predate the current heads.** Each review was made at the commit its row
  names. The stack was restacked by merges afterwards, so most heads are that commit plus
  merges of the layers below; where a head also carries a later commit of its own, the
  row says so. Every reviewed commit a row names is an ancestor of that pull request’s
  current head, checked with `git merge-base --is-ancestor`.
- **Nobody has reviewed the final tip as a whole, line by line.** The reviews and
  comparisons of the whole stack that exist are:
  - the readiness review of 2026-09-22 named above, of the stack through #225;
  - the landing-risk review of 2026-09-30, whose findings are the beads `mb-n80y`,
    `mb-4kuc`, `mb-2nu0`, and `mb-myum`, fixed in
    [#249](https://github.com/jlevy/metabrowser/pull/249) and
    [#250](https://github.com/jlevy/metabrowser/pull/250);
  - the regression and performance check against `main` of 2026-09-30, recorded in
    `mb-l8c2` and answered by [#254](https://github.com/jlevy/metabrowser/pull/254);
  - the acceptance runs in
    [QA: v0.12 alpha acceptance](../qa/qa-2026-09-24-v012-alpha-acceptance.md);
  - the landing gate (`mb-2g6f`) of 2026-10-01, which compares the stack with v0.11.0 on
    regular folders: an evidence audit of every test and golden that existed on v0.11.0,
    and a data differential over routes, CLI modes, headers, and plugins.
    [Changes to existing behavior](review-2026-10-01-v012-changes-to-existing-behavior.md)
    holds what they found.
    Both ran at #259’s head, below the last four layers;
  - the release rehearsal against v0.11.0 (`mb-cf6y`, exp-038,
    [#265](https://github.com/jlevy/metabrowser/pull/265)), run at #261’s head.
- **A row summarizes; the pull request is the record.** Finding counts are the ones the
  description or comment states.
  Where a description and its own table disagree, the row gives both.

## Kinds of Review

| Kind | Meaning |
| --- | --- |
| Stabilization | The foundation layers’ reviews of 2026-09-15 to 2026-09-22: passes by agents other than the author, the stabilization re-review of 2026-09-20 and 21, dispositions posted as comments on each pull request, and the readiness review that summarizes them. Bead `mb-gacf` holds the stabilization notes |
| Independent | A review by an agent other than the author, recorded in the pull request’s description, or for #225 in a comment, with its findings and what was done about each |
| Coordinator | Read by the coordinating agent only |

| None | No independent review; the row says what the change is |

## Summary

Of the 44 pull requests in the chain:

| Kind | Count | Pull requests |
| --- | ---: | --- |
| Stabilization | 7 | #125, #134, #136, #139, #140, #217, #216 |
| Independent | 32 | #225, #226, #227, #228, #229, #230, #231, #232, #233, #234, #235, #239, #236, #238, #237, #240, #243, #244, #246, #248, #249, #252, #251, #253, #255, #254, #256, #258, #257, #261, #263, #264 |
| Coordinator | 2 | #242, #259 |
| None | 3 | #241, #250, #265 |

Two pull requests are outside the chain and are the last rows:
[#247](https://github.com/jlevy/metabrowser/pull/247), the do-not-merge reference
branch, and [#262](https://github.com/jlevy/metabrowser/pull/262), the page-connection
fix, which is held until after the landing.

Every pull request’s CI passes on its current head.
#125 to #225 show seven checks and the rest nine: the two `admitted-git` jobs arrived
with #226, and the heads below it were last pushed before then.
`stack-integration` is the check that merges `main` into the head it tests.

## Ledger

Commits are abbreviated.
“Merges only since” means the head is the named commit plus merges of lower layers.

| PR | Scope | Review | Findings and disposition | CI on current head |
| --- | --- | --- | --- | --- |
| [#125](https://github.com/jlevy/metabrowser/pull/125) | Design documents for the hosted-review and GitHub architecture. The thin-mirror plan (#227) retired this design | Stabilization. Three review passes on 2026-09-15 (architecture; contracts and provider; delivery, security, and tests), then a [coverage reconciliation](https://github.com/jlevy/metabrowser/pull/125#issuecomment-5748280103) at `fde1d9b4`. Merges only since | 11 P1, 12 P2, and 1 P3, and three further items; all [fixed in `d760c5ba`](https://github.com/jlevy/metabrowser/pull/125#issuecomment-5673495341), and the closing reviewers reported none remaining. The readiness review found no replacement architecture warranted | 7 of 7 at `ed370a4e` ([run](https://github.com/jlevy/metabrowser/actions/runs/35649857449)) |
| [#134](https://github.com/jlevy/metabrowser/pull/134) | Hosted Review Format, models, and the GitHub coverage oracle (Phase 0). #246 removes this code from the stack | Stabilization. Three delegated review passes, then a reconciliation at `18ef513a`. Merges only since | R1 to R8 (two high, five medium, one low), all [fixed in `18ef513a`](https://github.com/jlevy/metabrowser/pull/134#issuecomment-5692357211) | 7 of 7 at `10990158` ([run](https://github.com/jlevy/metabrowser/actions/runs/35650509254)) |
| [#136](https://github.com/jlevy/metabrowser/pull/136) | Installed artifact-contract inventories and their gate (Phase 0C). #246 removes the hosted-review part | Stabilization. Parallel architecture, browser-boundary, contract, and delivery reviews; a reconciliation at `b907bb27`; and a [delta review at the current head](https://github.com/jlevy/metabrowser/pull/136#issuecomment-5786889586) of the four later plugin changes | R1 to R14, all [fixed in `b907bb27`](https://github.com/jlevy/metabrowser/pull/136#issuecomment-5694591401). The delta review found nothing new | 7 of 7 at `e0b713b3` ([run](https://github.com/jlevy/metabrowser/actions/runs/35651252343)) |
| [#139](https://github.com/jlevy/metabrowser/pull/139) | Source binding and provider repositories (Phase 0D). #246 removes the hosted-review part | Stabilization. A [senior review](https://github.com/jlevy/metabrowser/pull/139#issuecomment-5748280394) at `01584dba` and a [delta review at the current head](https://github.com/jlevy/metabrowser/pull/139#issuecomment-5786890069) of the eight later model and oracle changes | No actionable finding in either | 7 of 7 at `4e189c9b` ([run](https://github.com/jlevy/metabrowser/actions/runs/35652038697)) |
| [#140](https://github.com/jlevy/metabrowser/pull/140) | Owner-only application home, cache record contracts, `f01` records, and cache routes (Phase 1A) | Stabilization. A senior review, a Bugbot review (two threads, resolved), and an [independent second pass](https://github.com/jlevy/metabrowser/pull/140#issuecomment-5753914163) through `cee52937`. Merges only since | R1 to R3 fixed in `da73b878`. The second pass read the sections the first had left and reproduced four more defects, each fixed with a regression test | 7 of 7 at `93f19061` ([run](https://github.com/jlevy/metabrowser/actions/runs/35652982662)) |
| [#217](https://github.com/jlevy/metabrowser/pull/217) | Acquire a `file://` store without serving (Phase 1B-a) | Stabilization. A senior review, then an [independent second pass](https://github.com/jlevy/metabrowser/pull/217#issuecomment-5753916771) through `6dc2617c`. Merges only since | R1 to R3 fixed in `70091d81`. The second pass found a High (an ordinary clone could not be acquired, fixed in `6afb60d1`) and that R2 was incomplete (fixed in `5a5eb769` and `c290000a`). The remainders the readiness review listed for this layer are closed, in #226 and, for the stall bound (`mb-rati`), #231 | 7 of 7 at `4d25dc9a` ([run](https://github.com/jlevy/metabrowser/actions/runs/35653534570)) |
| [#216](https://github.com/jlevy/metabrowser/pull/216) | One repository subject, the immutable Git-tree source, and the `file://` pin (Phase 1B) | Stabilization. A senior review, a [completed second pass](https://github.com/jlevy/metabrowser/pull/216#issuecomment-5753920977), and a [follow-up](https://github.com/jlevy/metabrowser/pull/216#issuecomment-5756938750) through `ce07942f`. Merges only since | R1 to R5 (R5 high) fixed in `bc8dd72b` and `de0f4f5a`. The second pass found that the R1 fix was quadratic and that R5 was fixed for one function only, both fixed. The readiness review added R1 (medium, `mb-sumg`: pin modes lacked the acquisition error boundary) and kept `mb-3z4d`, `mb-99ub`, `mb-677z`, and `mb-t7qs` open; all are closed, in #226 and #229 | 7 of 7 at `b3c001a9` ([run](https://github.com/jlevy/metabrowser/actions/runs/35654160679)) |
| [#225](https://github.com/jlevy/metabrowser/pull/225) | The alpha test plan and status reconciliation. Documents only | Independent. A [technical review](https://github.com/jlevy/metabrowser/pull/225#issuecomment-5787107670) of the plan at `ff94e367`, and a second agent’s check of links and stack status. One documentation commit followed (`7a3bd1de`) | No actionable blocker | 7 of 7 at `7a3bd1de` ([run](https://github.com/jlevy/metabrowser/actions/runs/35811262120)) |
| [#226](https://github.com/jlevy/metabrowser/pull/226) | Foundation stabilization and T0 acceptance: the open foundation findings under `mb-gacf`, and the `admitted-git` CI job | Independent, two rounds: at `60d91f7b`, then of the fix commits at `b1b08009` | Round 1: 1 P1, 3 P2, 4 P3, all fixed except a SIGHUP P3 filed as `mb-163x`, which #231 closed. Round 2: 3 P2 and 1 P3, all fixed, each with a test that failed before it | 9 of 9 at `4002c608` ([run](https://github.com/jlevy/metabrowser/actions/runs/35827236719)) |
| [#227](https://github.com/jlevy/metabrowser/pull/227) | The thin-mirror design. Documents only | Independent design review, which checked the Git and `gh` behavior by experiment | Seven blocking gaps, each decided in the plan by the head commit `091d4043` | 9 of 9 at `091d4043` ([run](https://github.com/jlevy/metabrowser/actions/runs/35834447554)) |
| [#228](https://github.com/jlevy/metabrowser/pull/228) | Simplify: full clones; convergence, subject refs, leases, maintenance locks, and store reclamation removed | Independent, at `dae39296`. One test commit followed the fixes (`b4061ab0`) | No P0 or P1. Two P2 fixed in `a1e0a7ef` (quarantine could move a store under a reader; homes from earlier builds crashed pin modes), and the P3s fixed | 9 of 9 at `b4061ab0` ([run](https://github.com/jlevy/metabrowser/actions/runs/35889132988)) |
| [#229](https://github.com/jlevy/metabrowser/pull/229) | Serve a `file://` pin in the browser under the forced untrusted profile | Independent, at `7d98ac86` | No P0 or P1. One P2 and four P3 fixed at `cad7dba9`; the widened isolation sweep found and fixed a 500 | 9 of 9 at `cad7dba9` ([run](https://github.com/jlevy/metabrowser/actions/runs/35896388719)) |
| [#230](https://github.com/jlevy/metabrowser/pull/230) | Background refresh and pin switching for a served mirror | Independent, two rounds: at `76c04ddc`, then of the fixes | Round 1: one P1 (a branch rename wedged the atomic fetch), one P2 (Ctrl-C left a fetch running unlocked), and P3s, fixed at `17c4f9f8`. Round 2: six further items, fixed at `c50caa2f` | 9 of 9 at `c50caa2f` ([run](https://github.com/jlevy/metabrowser/actions/runs/35960185316)) |
| [#231](https://github.com/jlevy/metabrowser/pull/231) | GitHub URL open: the reducer, HTTPS with the `gh` credential helper, ref and path selection | Independent. The description records one review, of the branch before integration, and says a review of the integrated branch was in progress; bead `mb-bgs7` records four rounds, every finding fixed | Three P2 (unpinned `gh` host, a `nohup` override, macOS case collisions) and ten P3, all fixed. The description does not list the later rounds’ findings | 9 of 9 at `b605dd9f` ([run](https://github.com/jlevy/metabrowser/actions/runs/35985791291)) |
| [#232](https://github.com/jlevy/metabrowser/pull/232) | Pull-request data from `gh`, served from a local record | Independent: of the standalone work at `8aea9f4b`, and of the integration at `e9b53d6c`. Bead `mb-nkmq` records three rounds. One fix commit followed (`a9e80983`) | Standalone: one P1 (`CLICOLOR_FORCE` colored `gh` output), P2s, and P3s, all fixed; no secret leak. Integration: two P2 and P3s, fixed at `a6ac68bd` | 9 of 9 at `ffda89a7` ([run](https://github.com/jlevy/metabrowser/actions/runs/35985833235)) |
| [#233](https://github.com/jlevy/metabrowser/pull/233) | The pull-request page | Independent at `a4cbdeaf`, and a security review of the first hardening at `9c2e54b2` | Review: no P0 or P1; three P2 and the P3s fixed. The security review broke the denylist (SVG `url()` loads, KPress scripts through `data-kpress-*`); both layers became a strict allowlist in `eb6c728e`, which #234 moves to core | 9 of 9 at `8e5be947` ([run](https://github.com/jlevy/metabrowser/actions/runs/35990668325)) |
| [#234](https://github.com/jlevy/metabrowser/pull/234) | Inert Markdown and a Content-Security-Policy for untrusted sources | Independent security review of #233 and #234 together at `a0e60271`, then a verification pass at `7b4f3bf3` | Review: no P0 or P1; two P2 (repository files loadable as scripts through `/raw`; an inline handler broken by the policy) and the P3s fixed. Verification: two P2 (escaped dot segments; Load more ran unregistered actions) fixed at `783248c3` | 9 of 9 at `783248c3` ([run](https://github.com/jlevy/metabrowser/actions/runs/36004096792)) |
| [#235](https://github.com/jlevy/metabrowser/pull/235) | Line numbers and `#L` anchors in source views | Independent, at `3488943f` | No P0 or P1. One P2 (the highlight drifted at non-default zoom) and the P3s fixed at `e0384e2a` | 9 of 9 at `e0384e2a` ([run](https://github.com/jlevy/metabrowser/actions/runs/36044824530)) |
| [#239](https://github.com/jlevy/metabrowser/pull/239) | Line anchors on the Markdown Source tab, `?plain=1`, and keyboard anchors | Independent, at `ce2bf349` | No P0 or P1. The P2 and every P3 fixed in `aa1b16f1`, `a30a434d`, and `311e8398` | 9 of 9 at `311e8398` ([run](https://github.com/jlevy/metabrowser/actions/runs/36053574823)) |
| [#242](https://github.com/jlevy/metabrowser/pull/242) | Deletes an unused, never-run DOM test harness and one comment that named it. Two files | Coordinator | None recorded. The description shows the harness fails at load and that nothing calls it | 9 of 9 at `e5490307` ([run](https://github.com/jlevy/metabrowser/actions/runs/36055866256)) |
| [#236](https://github.com/jlevy/metabrowser/pull/236) | Branch and tag selector for a served mirror | Independent, at `f2b69aa7`. One test commit followed the fixes (`2a2ec603`), then a merge | No P0 or P1. One P2 (a malformed `view` switched the pin and then answered 500) and four P3 fixed at `05875cd4` | 9 of 9 at `14a24485` ([run](https://github.com/jlevy/metabrowser/actions/runs/36076177002)) |
| [#238](https://github.com/jlevy/metabrowser/pull/238) | Pull-request page follow-ups | Independent, at `1d182798`. Merges only since | No P0 to P2. Two P3 fixed at `57ada67e` | 9 of 9 at `35ad5efb` ([run](https://github.com/jlevy/metabrowser/actions/runs/36076180593)) |
| [#237](https://github.com/jlevy/metabrowser/pull/237) | Backslash filenames, Load more on a pin, and owner-stamped delegated controls | Independent, at `987d4e67`. Merges only since | No P0 or P1. The review found the change broke documented plugin markup, so `8bfa73ec` makes it Plugin SDK 0.7 with the migration in the changelog; four P3 fixed there too | 9 of 9 at `3a0dcd60` ([run](https://github.com/jlevy/metabrowser/actions/runs/36076227186)) |
| [#240](https://github.com/jlevy/metabrowser/pull/240) | Heading anchors and a table of contents for untrusted documents; backslash links | Independent security review. Merges only since | No P0 or P1. One P2 (backslash links had no end-to-end test) and every P3 fixed in `edef33c5` | 9 of 9 at `6fd37ce9` ([run](https://github.com/jlevy/metabrowser/actions/runs/36076244144)) |
| [#241](https://github.com/jlevy/metabrowser/pull/241) | The alpha acceptance record. Documents only; a draft | None. It is itself a record of testing | Its four findings are beads, fixed in #243 and #248 | 9 of 9 at `17d031ae` ([run](https://github.com/jlevy/metabrowser/actions/runs/36076279217)) |
| [#243](https://github.com/jlevy/metabrowser/pull/243) | Acceptance fixes: the table-of-contents toggle, raw characters in GitHub URLs, the pull-request header | Independent. One documentation commit followed (`df5bbbed`, the rerun record), then a merge | No P0, P1, or P2. Eight P3, each fixed in its own commit | 9 of 9 at `65df8653` ([run](https://github.com/jlevy/metabrowser/actions/runs/36076283885)) |
| [#244](https://github.com/jlevy/metabrowser/pull/244) | Fork-qualified pull-request header; default-ignorable characters escaped in displayed paths | Independent, on 2026-10-01 at the stack’s then tip, `373b59a9`. Its description records no review; beads `mb-2on0` and `mb-mw0t` hold the findings, and #259’s description names them | Three findings fixed in #259 (`mb-2on0`): Unicode spaces and line separators shown raw in displayed paths, a slowdown of the display function on names outside ASCII, and a ref name printed raw in the serve banner. The rest are left open in `mb-mw0t`. The coordinator reports the severities as no P0 or P1 and three P2; no record read for this ledger states them | 9 of 9 at `a896d8fe` ([run](https://github.com/jlevy/metabrowser/actions/runs/36077428696)) |
| [#246](https://github.com/jlevy/metabrowser/pull/246) | Removes the unused Hosted Review Format, provider-resource code, and the public capability surface | Independent | No P0 or P1. One P2 (stale `--doctor` help) and six P3 fixed, among them `--doctor` validating the cache record contracts and the provider-store reservations (`mb-31qs`) | 9 of 9 at `d59b600c` ([run](https://github.com/jlevy/metabrowser/actions/runs/36804946275)) |
| [#248](https://github.com/jlevy/metabrowser/pull/248) | View file at either side of a changed file | Independent | One P1 (`Cache-Control: no-store` defeated the back/forward cache; replaced by a pin check on history landings), three P2, and nine P3, all answered. The review found the feature itself correct and secure | 9 of 9 at `e4eca29f` ([run](https://github.com/jlevy/metabrowser/actions/runs/36809212257)) |
| [#249](https://github.com/jlevy/metabrowser/pull/249) | Landing fixes: folders with URL-like names, the state for an unfetched commit, not-found wording | Independent. Merges only since `f1a85ba6` | No P0 or P1. Two P2, six P3, and four minor items, each fixed in its own commit | 9 of 9 at `f54b2560` ([run](https://github.com/jlevy/metabrowser/actions/runs/36815298638)) |
| [#250](https://github.com/jlevy/metabrowser/pull/250) | Plans, roadmap, architecture documents, and changelog brought in line with the stack. Documents only | None | None recorded | 9 of 9 at `ea7fd9ba` ([run](https://github.com/jlevy/metabrowser/actions/runs/36820018225)) |
| [#252](https://github.com/jlevy/metabrowser/pull/252) | Tests: one autouse reset of process state; events and counts in place of sleeps and timing asserts | Independent | Two P1, both tests that had lost detection, restored. Three P2 and six P3 answered. All 26 rewritten tests fail under the source change each guards against. The process globals that tests still leave changed are `mb-yth5` | 9 of 9 at `bd43ab26` ([run](https://github.com/jlevy/metabrowser/actions/runs/36833903939)) |
| [#251](https://github.com/jlevy/metabrowser/pull/251) | Tests: a missing Node or Git fails; strict skips in CI; the macOS and live-GitHub tiers; a 50-second bound on inner timeouts | Independent | One P1 (the admitted-Git check missed modules asking through a helper), six P2, and nine P3, all fixed. One suggestion not taken, with its reason: the `install` prerequisite on the two new Make targets stays | 9 of 9 at `258c6c67` ([run](https://github.com/jlevy/metabrowser/actions/runs/36837688858)) |
| [#253](https://github.com/jlevy/metabrowser/pull/253) | Tests: one golden harness, a complete `make golden-update`, and `devtools/check_goldens.py` | Independent, of the first push. The restack above #251 added follow-up commits after it | No P0. One P1 (the parity clause was looser than its docstring), four P2, and several P3, fixed in `c50c12e8` to `5bd68929`; the fourth P2 was merge reconciliation, done in the restack. Follow-up `mb-y8rm` | 9 of 9 at `f9cd3e6b` ([run](https://github.com/jlevy/metabrowser/actions/runs/36844743616)) |
| [#255](https://github.com/jlevy/metabrowser/pull/255) | Tests: contract-layer trim; `make test-report`; the test-suite baseline record | Independent. The reviewer re-ran 51 of the author’s 107 mutations and ran 61 of its own | Three detections the trimmed tests had lost, and the review’s other findings, fixed in the six commits after `93be234c`. 32 mutations no test catches, before or after, are `mb-5e9n` | 9 of 9 at `b106574b` ([run](https://github.com/jlevy/metabrowser/actions/runs/36863162035)) |
| [#254](https://github.com/jlevy/metabrowser/pull/254) | Startup imports and loading tiers; `devtools/check_startup_scripts.py`; exp-037 | Independent, at `2421889b`. Merges only since `e9c33045` | No P0. The description says three P1; its table lists two (a plugin calling `renderSourceView` outside the view compositor threw; a 120-second child bound), four P2, and five P3. Each is fixed. Wall-clock pairs are still owed (`mb-67s1`) | 9 of 9 at `a7feac77` ([run](https://github.com/jlevy/metabrowser/actions/runs/36871605591)) |
| [#256](https://github.com/jlevy/metabrowser/pull/256) | Tests: the cache suite | Independent. Merges only since `8ed1bd53` | No P0 or P1. Two P2, two security gaps that the base had too, and five P3, all fixed; each of the reviewer’s mutants now fails a named test. Follow-up `mb-3hwh` | 9 of 9 at `1bceb1aa` ([run](https://github.com/jlevy/metabrowser/actions/runs/36874105098)) |
| [#258](https://github.com/jlevy/metabrowser/pull/258) | Tests: the GitHub pull-request suite and the hostile-link corpus | Independent. The reviewer re-ran 24 of the author’s 37 mutations and ran 80 of its own. Merges only since `0acc6001` | Six lost detections restored and five older gaps closed. 111 of 117 mutations fail a test; five are left to `mb-3ulm` and one is equivalent. An observation is `mb-k4ks` | 9 of 9 at `1c1e6b09` ([run](https://github.com/jlevy/metabrowser/actions/runs/36876356036)) |
| [#257](https://github.com/jlevy/metabrowser/pull/257) | Tests: the Git pin and source suite; the pin golden as six shards | Independent. The reviewer re-ran 38 of the author’s mutations and ran 61 of its own. A merge and one documentation commit followed (`373b59a9`), and the mutation tally was run again on that head | One P1 (three `READ_POLICY` assertions lost, restored in `5444c6e9`), smaller items, and safety boundaries no test held on the base either, now tested. All 83 of the author’s mutants and 57 of the reviewer’s 61 are caught; three of the rest are equivalent and one is an uncalled method (`mb-snpr`) | 9 of 9 at `373b59a9` ([run](https://github.com/jlevy/metabrowser/actions/runs/36886011227)) |
| [#259](https://github.com/jlevy/metabrowser/pull/259) | The three fixes from #244’s review: Unicode spaces replaced in displayed paths; the display function’s speed restored; the serve banner’s ref escaped | Coordinator, who read the diff. Not independently reviewed (`mb-2on0`’s close reason) | None recorded. The author compared the rewritten display function with the one before it over every code point in 14 contexts on four Python builds, with no mismatch, and names a test that fails without each fix | 9 of 9 at `f62c16b1` ([run](https://github.com/jlevy/metabrowser/actions/runs/36896717618)) |
| [#261](https://github.com/jlevy/metabrowser/pull/261) | A first clone says where it goes and shows progress; a cache hit says so | Independent | No P0 or P1. The findings are fixed in `b025d139` to `c16912f8`; `mb-4cg7` counts four P2 (exit status 120 when stderr’s reader had gone, a regression; Git’s stderr written raw at debug level; loosened no-leak tests; unpinned wiring) and the P3s. Not done, by the description: the first `gh` read for a pull-request URL is still silent | 9 of 9 at `c16912f8` ([run](https://github.com/jlevy/metabrowser/actions/runs/36920222346)) |
| [#263](https://github.com/jlevy/metabrowser/pull/263) | A mirrored repository is headed by its name and says where it is stored; `name`, `origin`, and `location` in `/api/source/status` | Independent | One P1 (a tooltip rule changed a regular folder’s tooltips; restored to the base’s), three P2, and nine smaller findings, each fixed; 76 of 76 mutations caught, the reviewer’s among them. Found afterwards, running the runbook for this record: `mb-hj9h`, a long repository name cut with an ellipsis while the note still shows, open | 9 of 9 at `76677bc7` ([run](https://github.com/jlevy/metabrowser/actions/runs/36946303494)) |
| [#264](https://github.com/jlevy/metabrowser/pull/264) | Landing-gate fixes: regular-folder behaviors restored to v0.11.0, two lost assertions re-pinned, changelog entries, start-up pairs that control bytecode | Independent. Merges only since the fixes | One P1, a third difference from v0.11.0 in the structured route, older than this pull request (bytes that are not UTF-8, and compressed files that cannot be decoded), fixed in `a2a3f1cf`; three P2 and the P3s fixed in the eight commits after `8dd19053`; 47 of 47 mutations caught. One answer still differs from v0.11.0 on purpose: an unopenable file answers 404 without a host path | 9 of 9 at `8879c4de` ([run](https://github.com/jlevy/metabrowser/actions/runs/36947448513)) |
| [#265](https://github.com/jlevy/metabrowser/pull/265) | The release checklist’s steps 1 to 5 rehearsed against v0.11.0: exp-038, ledger rows, and the regenerated performance report. No product code | None. It is a record of measurement | Its own findings, the `--doctor` cost, the `frame_missing_px` probe, and the changelog gaps, are answered in #264 or left to the user (`mb-cf6y`) | 9 of 9 at `481b64b7` ([run](https://github.com/jlevy/metabrowser/actions/runs/36947693543)) |
| [#247](https://github.com/jlevy/metabrowser/pull/247) | Outside the chain: the removed hosted-review code, kept as an unmaintained reference branch. A draft that is never merged | None of its own. It restores what #246 removes, so #246’s review is the review of the boundary | None recorded | 9 of 9 at `b10a2fa8` ([run](https://github.com/jlevy/metabrowser/actions/runs/36805938982)) |
| [#262](https://github.com/jlevy/metabrowser/pull/262) | Outside the chain: a page kept in the back/forward cache releases its event stream (`mb-tdmd`). A draft, held until after the landing | Independent | One P1 (Back onto a page with a type filter un-filters the tree), two P2 groups, and P3s, none fixed yet (`mb-tdmd`’s notes). The review is why it is held out: without it, regular pages behave as in v0.11.0, which has the same stall | 9 of 9 at `a7f7c8bc` ([run](https://github.com/jlevy/metabrowser/actions/runs/36916957466)) |

## How This Ledger Was Built

Read-only commands, run on 2026-10-01 against `jlevy/metabrowser`:

```shell
# One pull request: its description, comments, review objects and decision, and checks.
gh pr view 257 --repo jlevy/metabrowser \
  --json body,comments,reviews,reviewDecision,headRefOid,statusCheckRollup

# A bead's close reason and notes.
tbd show mb-79t3
```

- **Review and findings** come from each description’s Review or Evidence section, from
  the comments on #125 to #225, and from the close reasons of the beads the thin-mirror
  plan’s [Delivery](../specs/active/plan-2026-09-23-v012-thin-mirror.md#delivery) tables
  name.
- **What followed a review** is
  `git log --no-merges <reviewed commit>..<head> ^<base branch>`.
- **Stack order** is that of GitHub stack #218
  (`gh api repos/jlevy/metabrowser/stacks/218 --jq '[.pull_requests[].number]'`), which
  the chain command under Pins in the
  [QA runbook](../../qa-v012-repository-library.md#pins) also prints; each head was
  checked to contain the head below it.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
