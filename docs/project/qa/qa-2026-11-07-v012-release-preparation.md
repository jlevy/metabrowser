# Metabrowser 0.12.0 Release Preparation

**Status:** In progress; updated November 8, 2026. The product stacks are merged and the
reviewed build is installed locally.
Release acceptance remains incomplete; no tag or publication is authorized until the
owner approves the exact candidate and notes.

## Integrated Candidate

[Stack 331](https://github.com/jlevy/metabrowser/stack/331), PRs #328 through #330,
merged at
[main `d33550455`](https://github.com/jlevy/metabrowser/commit/d33550455d1a44bb275d5e71492f9bdbc682f0c5).
Its full tree exactly equals reviewed tip `519c33239`, retained as an ancestor.
The lower layer `c67371c2e` corrects benchmark corpus materialization and documentation;
`24f3721c9` supplies the final identity and stack presentation; `519c33239` records the
release rehearsal. Independent senior, security and performance reviews are published on
the PRs, with findings dispositioned before merging.

The complete `make verify` at exact tip `519c33239` passed 4,917 tests with nine
expected skips, all 385 golden checks, lint and both browser type checks, both locked
dependency audits, distribution inspection and isolated installed-wheel smoke checks.
The Python suite took 1,129.98 seconds, the golden suite 297.49 seconds and the full
gate 1,510.80 seconds.
The filesystem observer recorded no errors.
All nine CI jobs passed on each of the three published PR heads.
The subsequent
[merged-main CI](https://github.com/jlevy/metabrowser/actions/runs/42449868134)
completed successfully with all nine jobs green.

At the stack-331 installation checkpoint, both CLI names and all three previews used
`0.11.1.dev1275+519c33239`. The preserved wheel’s SHA-256 is
`780a9922e2446d7e925717457d4cb7e9e5ffc4a9f3ae70ce630298d31e085768`. All eleven plugins
were healthy, and ten served assets per preview matched the installed package.
The portable skill matched source, with its source pin advanced to `519c33239`. The
installed wheel predated the merge commit, whose tree is identical.
This was an unpublished development build.

### Documentation checkpoint

[#332](https://github.com/jlevy/metabrowser/pull/332) merged at
[main `240da85cb`](https://github.com/jlevy/metabrowser/commit/240da85cbb45b72defed0084aadc99ee0be234ed).
Its tree equals reviewed documentation tip `e204ce9b5`, retained as an ancestor.
Exact-head `make verify` passed 4,917 tests with nine expected skips, 385 golden checks,
lint, types, locked audits, distribution inspection and installed-wheel smoke checks.
All nine PR jobs and all nine
[merged-main jobs](https://github.com/jlevy/metabrowser/actions/runs/42455413320)
passed.

The installed checkpoint was `0.11.1.dev1277+e204ce9b5` for both CLI names and all three
previews. Its preserved wheel SHA-256 is
`fe271138444c3ed8018b3d9889942c2bf3824dfa2d2f284b529de74cda15a723`. Eleven plugins were
healthy, thirty served-asset checks matched the package, and the managed preview
selected merged main `240da85cb`. This checkpoint exposed the commit-loading race below;
it does not establish release acceptance.

### Commit-loading checkpoint

[#333](https://github.com/jlevy/metabrowser/pull/333) merged at
[main `9416b78b8`](https://github.com/jlevy/metabrowser/commit/9416b78b8dc2657a3e1745f5d6b7152c9dfc6e98).
Its tree equals reviewed tip `a2bb0d29a`, retained as an ancestor.
Exact-head `make verify` passed 4,917 tests with nine expected skips, 386 golden checks,
lint, types, both locked audits, distribution inspection and installed-wheel smoke
checks. All nine PR jobs and all nine
[merged-main jobs](https://github.com/jlevy/metabrowser/actions/runs/42465916831)
passed. Both CLI names and the three previews used the preserved wheel
`0.11.1.dev1280+a2bb0d29a`, whose SHA-256 is
`81524fde0549e9111a76c94305fb578fef544e93cf9e08d340a4ea4389479bb0`. Doctor reported
eleven healthy plugins, and all 33 served-asset comparisons matched.

### Prefetch-ownership checkpoint

[#334](https://github.com/jlevy/metabrowser/pull/334) merged at
[main `fe04a4b1c`](https://github.com/jlevy/metabrowser/commit/fe04a4b1cfb25cc16e1e8399252f4b664633a6c6).
Its tree equals reviewed tip `1ede1e220`, retained as an ancestor.
Independent reviews A through D accepted the producer-retention and traversal-pass
corrections after the review finding was fixed.
Exact-head `make verify` passed 4,917 tests with nine expected skips, 386 golden checks,
lint, types, locked audits, distribution inspection and installed-wheel smoke checks,
with no filesystem errors.
All nine [PR jobs](https://github.com/jlevy/metabrowser/actions/runs/42473368957) and
all nine
[merged-main jobs](https://github.com/jlevy/metabrowser/actions/runs/42474957597)
passed.

Both CLI names and all three previews used `0.11.1.dev1283+1ede1e220`. The preserved
wheel SHA-256 is `8987325d400ec95fe7b42ad8d3b8ba8ce41bcc43a78e8206e4fb33fe4140a4c8`.
Doctor reported eleven healthy plugins, all 33 served-asset comparisons matched, and all
45 applicable runtime pins were preserved.
[#334](https://github.com/jlevy/metabrowser/pull/334)’s Conversation, six changed files
and nine successful checks passed in both managed and checkout modes.
The checkout session also passed Quick Search and independent tab restoration.
The filesystem preview retained its original Markdown layout.
A managed PR refresh emitted a slow-response warning at 2,014 ms, including 2,010 ms of
server time. Its cause and latency qualification remain open under `mb-4ifm`.

### Release-documentation checkpoint

[#335](https://github.com/jlevy/metabrowser/pull/335) merged at
[main `e1cfca1a`](https://github.com/jlevy/metabrowser/commit/e1cfca1a66277aa86887f031f9b28b250d4a4928).
Its tree equals reviewed and gated tip `426ce7b62`, retained as an ancestor.
The change corrects fresh-release installation probes, public skill verification and the
README trust summary.
Exact-head `make verify` passed 4,917 tests with nine expected skips, 386 golden checks,
lint, types, locked audits, distribution inspection and installed-wheel smoke checks,
with no filesystem errors.
Independent senior and security/process reviews accepted the change, and all nine
[PR CI jobs](https://github.com/jlevy/metabrowser/actions/runs/42477792812) passed.
All nine
[merged-main jobs](https://github.com/jlevy/metabrowser/actions/runs/42496190135) also
passed.

Both default CLI names and all three retained previews now use the preserved
`0.11.1.dev1287+426ce7b62` wheel, SHA-256
`476aba4d52c3d3d0f24edf77efae3f3286e4065f231fbad596b4ccd3663c79ab`. Doctor reports
eleven healthy plugins, all 33 served-asset comparisons match the wheel, and all 45
applicable runtime dependency pins are unchanged.
The
[post-merge session](https://github.com/jlevy/metabrowser/pull/335#issuecomment-6723744302)
passed [#335](https://github.com/jlevy/metabrowser/pull/335)’s nine-check summary in
both source modes, the managed two-file Changes view, checkout latest-commit rendering,
independent tab restoration and Markdown alignment/padding.
Freshly reloaded sessions had no warning/error entries during that smoke; the earlier
managed-refresh warning remains a separate unresolved observation.

## Post-Landing Sessions

The
[installed-build acceptance](https://github.com/jlevy/metabrowser/pull/329#issuecomment-6717564797)
passed built-in-browser sessions in both managed-repository and existing-checkout
previews: Conversation, Changes and Checks, stack-menu navigation and Shift-J retaining
Checks, and independent Pulls/Commits route restoration.
The stack menu fits the observed 750 px viewport.
Actor names use bold normal text ink at the surrounding size: 12 px in sidebar metadata
and 14 px on PR and commit pages.
Reload remains keyboard reachable beside Open, Closed and All; the update-age line stays
below the repository summary.
View on GitHub has its leading brand icon.

The earlier intermittent PR-to-Commits loading stall recurred on installed `e204ce9b5`:
the URL selected merged main, but the preview retained only its loading placeholder.
A deterministic production-JavaScript session confirmed that a delayed loading callback
could remove the connected diff stage or overwrite ready content while paint callbacks
were deferred. Independent review also reproduced an older selection’s paint or
missing-commit completion clearing a newer selection’s pending indicator.
The focused fix installs the shared CSS-delayed spinner before staging and restricts
cleanup to its owning selection.
The fix passed independent review and landed in
[#333](https://github.com/jlevy/metabrowser/pull/333). Source and installed-browser
sessions passed in both managed-repository and checkout modes, including rapid selection
replacement and independent tab restoration.
The installed Markdown card retains its tab alignment, inner padding and right contents
rail. `mb-4mfc` and the post-landing reconciliation `mb-5k2w` are closed.

An installed-wheel negative setup session also passed with `gh` absent from the child
process’s `PATH`: Pulls returns typed `gh_missing`, shows one visible setup message and
the official installation link, and retains its separate accessible live announcement.
Files and local Commits remain usable, including a rendered four-file commit.
The isolated fixture’s initial cache-permission refusal was corrected before this check;
normal caches, credentials and preview processes were unchanged.

The initial PR-core scheduling investigation, `mb-b0aq`, now has a deterministic
reproduction. Replacing a catalog prefix during unfinished preparation releases its
producer even when the repository, reader and epoch are unchanged.
The retained attempt leases then defer the early rows while later cohorts proceed.
Source-pinned backend controls show that retaining the producer completes unchanged
members with one provider call.
The focused correction preserves that work while re-priming traversal, and keeps
cancellation for actual identity changes and disposal.
Production-controller sessions cover unchanged, changed and removed members, later
cohorts, and source, reader, epoch and disposal cancellation.
Independent review caught a late receipt advancing the restarted traversal’s cursor.
The correction binds terminal effects to their originating pass while retaining accepted
producer ownership. Six 600-row sessions cover ready, partial, failed, busy, not-owner
and malformed coverage replies across a revision outside the held prefix.
Each revisits the changed member, completes all 600 current cores and leaves no timers.
The correction passed full verification, independent review and installed-artifact
acceptance in #334, as recorded above.
The scoped correctness findings `mb-b0aq` and `mb-ygiq` are closed.
These sessions do not measure painted latency.

Part A of the differential test-evidence audit is complete at `519c33239`: 189 changed
pre-existing test files, 1,063 indexed hunks and 988 unique file/key pairs have no
current unclassified or unexplained entries.
Independent review found no lost behavioral assertion.
Historical stale keys remain separate rather than being silently discarded.
Part B also ran against the exact preserved wheels: all 22 baseline transcripts pass on
0.11.0, and their 22 current versions pass on installed `519c33239`. Of 131 baseline
blocks on the candidate, 116 match and 15 differ: nine intended surface changes, two
documented bug fixes and four obsolete test-harness assumptions.
The current semantic classification has no missing or unclassified blocks.
Original failures, retries and the initial unclassified report remain preserved.
The classified Part C comparison at `e204ce9b5` also passed independent review: 143
observed failure or error cases have specific dispositions, with no unexplained
differences. Original non-green runs and separately corrected harness profiles remain
preserved; this is not a claim that the raw comparison passed every old assertion.
The data run at that build was stopped cleanly after the new loading fix made it an
intermediate candidate.
Its completed observations remain supporting evidence.
At `426ce7b62`, Part A independently confirms 189 changed pre-existing test files, 1,070
indexed hunks and 994 current keys, with zero unclassified entries.
All seven new classifications preserve baseline assertions and behavior coverage.
The replaced combined-hunk classification remains historical alongside the earlier 61
stale keys. The other accepted classifications are inherited at unchanged keys.

The exact-candidate data comparison and headless functional browser matrix are now
running with isolated installed wheels.
The data selection includes 1,921 CLI cases, 53 HTTP groups containing 17,012 requests,
47 specials and all 33 trace rows.
The browser matrix covers 396 jobs across four viewport/theme configurations.
Capture completeness, raw failures and semantic dispositions remain under review.
Timing cases and the browser’s six ten-page Step9 sequences are excluded from these
loaded-host functional runs; their quiet-window checks remain open.
Part B also completed at exact `426ce7b62`: all 22 control transcripts and all 22
current-version selfchecks pass on their installed wheels, using one attempt per phase.
Of 131 baseline blocks on the candidate, 116 match and 15 differ.
Review accounts for all 15 differences: nine intended changes, four obsolete
test-harness assumptions and two documented bug fixes.
The original non-green execution receipt and raw failures remain preserved separately
from this semantic acceptance.
Final Part C remains separate work; its accepted `e204ce9b5` result retains that source
pin.

### Earlier integrated-main evidence

The preceding 28 product PRs in
[stack 302](https://github.com/jlevy/metabrowser/stack/302) merged at
[main `68534af93`](https://github.com/jlevy/metabrowser/commit/68534af933f0fcb38a5d81d62691bb42732d58ab).
Its tree exactly equals reviewed tip `6cf001cdf`, retained as an ancestor.
The
[integration review](https://github.com/jlevy/metabrowser/pull/327#pullrequestreview-5816169303)
records all 16 findings resolved and all published heads green before merging.
The deliberately excluded reference draft #247 remains outside the product merge scope.

Post-landing `make verify` on `68534af93` passed 4,916 tests with nine expected skips,
385 golden checks and the full lint, audit, distribution and installed-wheel gates.
The Python suite took 1,048.15 seconds and the golden suite 195.28 seconds; the
filesystem observer recorded no errors.
[CI at that main](https://github.com/jlevy/metabrowser/actions/runs/42439267509) passed
all nine jobs. Its then-installed wheel, `0.11.1.dev1272+68534af93`, has SHA-256
`9b5ebaad3c6271acbc15795a7651c1fc4524777f24e1d2ce0213025cd92100c7`.

Browser sessions on that artifact covered title and numeric Quick Search, native-stack
titles, Checks-preserving stack selection and Shift-K, and independent Files/Pulls route
restoration. At 1600 × 900, the document card and first view tab shared the same 324 px
left edge. The document retained 40 px horizontal inner padding; Source retained 16 px
vertical and 24 px horizontal code padding.

A separate plain-folder fixture changes 55 files.
The `68534af93` CLI diff contains all 55 patches and applies cleanly to the target tree.
The published 0.11.0 control produced the identical complete JSON payload under the same
`--diff HEAD --format json` invocation and the same apply-oracle target hash.
Both browser builds reached the final file and hydrated it in Split and Unified views.
The candidate omitted the routine partial-file counter, and its commit description used
the neutral surface, 15 px sans text, 22.5 px line height and preserved newlines.
The installed `519c33239` follow-up subsequently repeated this comparison: the full JSON
again equals the control, all 55 patches apply to the same target, and both fresh
Unified and Split sessions reach and hydrate the final file without a partial counter or
console warnings or errors.
This completes the fixture check at that integrated product candidate.
The exact `426ce7b62` follow-up also has an identical complete 55-file/55-patch CLI
payload and clean apply oracles against the same target.
Its four fresh browser cells, control/candidate in Split/Unified, are blocked and were
not run because browser control reported a locked Mac.
The earlier browser results retain their original source pin; current browser and owner
acceptance remain open.

Additional source tiers at `68534af93` passed 20 macOS checks, eight live read-only
public GitHub checks including the typed missing-or-private refusal, and all 1,124
strict admitted-Git tests in 754.45 seconds.
These are historical source results; they are not relabeled as tests of the newer wheel.

## Deferred Workflow

The branch/worktree chooser is future workflow `mb-itzy`, explicitly paused by the user.
It tracks the design of live working-tree and cached branch-snapshot browsing and does
not expand this stabilization or release scope.

Conversation commit summaries currently use validated GitHub destinations.
Local commit navigation without Git acquisition is a separate tracked enhancement,
`mb-g47g`; the current timeline does not claim that local destination behavior.

## Remaining Acceptance

| Gate | State | Tracking |
| --- | --- | --- |
| Post-landing browser smoke and current documentation | Product fixes through [#334](https://github.com/jlevy/metabrowser/pull/334) are merged, reviewed and installed; both source modes pass. Documentation [#335](https://github.com/jlevy/metabrowser/pull/335) is merged and installed, with all nine PR and merged-main jobs green | `mb-5k2w`, `mb-4mfc`, `mb-ucc1`, `mb-b0aq`, `mb-ygiq`, `mb-y489` closed |
| Previous-release performance comparison | [Exp-056](../../../explorations/performance-loop/experiments/exp-056-previous-release-rehearsal.md) stopped after a valid 444 ms candidate first-row result exceeded the 350 ms hard gate. A quiet final-candidate exp-057 comparison remains required | `mb-cf6y` |
| PR and Commit navigation performance | The same-identity prefetch ownership correction is accepted in #334. Cold-asset attribution, natural intent/request joining and the observed two-second managed refresh remain open. The regular-folder release comparison does not cover these interactions | `mb-4ifm`, `mb-5rm1`, `mb-97ex` |
| Large-PR performance qualifications | Quiet public comparisons and the measured render-window follow-up remain separate from regular-folder acceptance | `mb-jwfx`, `mb-mwuz` |
| Linked dependency roots in the benchmark corpus | Behavioral regression test and corpus correction merged in stack 331 | `mb-lsm5` closed |
| Regular-folder data, test-evidence and browser differentials | Parts A and B accepted at `426ce7b62`; earlier Part C retains its pin. Exact-candidate data and headless browser captures are running; final completeness, semantic review and quiet Step9 remain open | `mb-2g6f` |
| Plain-folder comparison above 50 files | Control and exact `426ce7b62` have identical 55-file/55-patch CLI payloads and clean apply oracles; four current browser cells are blocked/not run, with owner sign-off pending | `mb-8pyc` |
| Complete installed-wheel QA runbook and opt-in tiers | In progress; report every step as passed, failed, blocked or not run | `mb-m20f` |
| Cross-browser, private-access and external-plugin acceptance | Preserve prior evidence separately; current browser matrix and owner sign-off remain open | `mb-etqi` |
| Release notes, intended behavior changes and final approval packet | Drafting; version 0.12.0 is already decided | `mb-gew9`, `mb-4bd2` |
| Tag, GitHub release and PyPI publication | Await explicit user approval of the exact candidate and notes | `mb-4bd2` |
| Published metadata, pinned installs and public skill verification | Run only after approved publication | `mb-4bd2` |

The previous published release is 0.11.0. The preserved tag-built control wheel matches
its published SHA-256,
`b099786f84408968df10296fdf7226218dd8853faf1cdb02a25787c5ab396e7f`. The
[publishing checklist](../../publishing.md#release-checklist) defines the release gates
and the [QA runbook](../../qa-v012-repository-library.md) defines the manual rows.

Measurements retain their exact application source and artifact identities.
Historical loaded-host runs, interrupted captures and mixed-cache observations are not
relabeled as successful final-candidate evidence.
The exp-057 host preflight deferred collection because unrelated workloads and external
disk traffic remained active.
It collected no browser or backend pairs.
The prepared protocol now targets gated `426ce7b62` and still requires confirmed host
conditions before measurements.
The latest preflight also deferred collection, with no browser or backend pairs.
The accepted prefetch correction in #334 establishes correctness and functional
behavior; its painted-latency effect remains unmeasured.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
