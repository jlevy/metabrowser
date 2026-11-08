# Metabrowser 0.12.0 Release Preparation

**Status:** In progress on November 7, 2026. The product stacks are merged and the
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
are healthy, and ten served assets per preview match the installed package.
The portable skill matches source, with its source pin advanced to `519c33239`. The
installed wheel predates the merge commit, whose tree is identical; it is not a
published 0.12.0 release.

### Documentation checkpoint

[#332](https://github.com/jlevy/metabrowser/pull/332) merged at
[main `240da85cb`](https://github.com/jlevy/metabrowser/commit/240da85cbb45b72defed0084aadc99ee0be234ed).
Its tree equals reviewed documentation tip `e204ce9b5`, retained as an ancestor.
Exact-head `make verify` passed 4,917 tests with nine expected skips, 385 golden checks,
lint, types, locked audits, distribution inspection and installed-wheel smoke checks.
All nine PR jobs and all nine
[merged-main jobs](https://github.com/jlevy/metabrowser/actions/runs/42455413320)
passed.

The installed checkpoint is `0.11.1.dev1277+e204ce9b5` for both CLI names and all three
previews. Its preserved wheel SHA-256 is
`fe271138444c3ed8018b3d9889942c2bf3824dfa2d2f284b529de74cda15a723`. Eleven plugins are
healthy, thirty served-asset checks match the package, and the managed preview selects
merged main `240da85cb`. This checkpoint exposed the commit-loading race below; it does
not establish release acceptance.

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
were deferred. Independent review also reproduced an older selection’s paint completion
clearing a newer selection’s pending indicator.
The focused fix installs the shared CSS-delayed spinner before staging and restricts
cleanup to its owning selection.
The source preview opens the previously stalled commit and renders its sixteen changed
files. Full gating, review, merge and installed-artifact verification remain required in
`mb-4mfc`; earlier passing repetitions remain history.

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
All three release differentials still require the frozen final candidate.

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
This completes the fixture check at the integrated product candidate; final release-head
and owner sign-off remain separate.

Additional source tiers at `68534af93` passed 20 macOS checks, eight live read-only
public GitHub checks including the typed missing-or-private refusal, and all 1,124
strict admitted-Git tests in 754.45 seconds.
These are historical source results; they are not relabeled as tests of the newer wheel.

## Deferred Workflow

The branch/worktree chooser is future workflow `mb-itzy`, explicitly paused by the user.
It tracks the design of live working-tree and cached branch-snapshot browsing and does
not expand this stabilization or release scope.

## Remaining Acceptance

| Gate | State | Tracking |
| --- | --- | --- |
| Post-landing browser smoke and current documentation | Documentation [#332](https://github.com/jlevy/metabrowser/pull/332) is merged and installed; the reproduced commit-loading race still blocks completion | `mb-5k2w`, `mb-4mfc`; `mb-ucc1` closed |
| Previous-release performance comparison | [Exp-056](../../../explorations/performance-loop/experiments/exp-056-previous-release-rehearsal.md) stopped after a valid 444 ms candidate first-row result exceeded the 350 ms hard gate. A quiet final-candidate exp-057 comparison remains required | `mb-cf6y` |
| Linked dependency roots in the benchmark corpus | Behavioral regression test and corpus correction merged in stack 331 | `mb-lsm5` closed |
| Regular-folder data, test-evidence and browser differentials | Audit Parts A and B complete at `519c33239`; classified Part C accepted at `e204ce9b5`; intermediate data run stopped cleanly; all three final-candidate differentials remain pending | `mb-2g6f` |
| Plain-folder comparison above 50 files | Control and installed `519c33239` have identical 55-file CLI payloads, clean apply oracles and both browser layouts; final release-head and owner sign-off remain | `mb-8pyc` |
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
No quiet exp-057 result has been collected while functional verification runs.
Its prepared protocol still needs the final gated artifact and confirmed host conditions
before measurements.
The initial PR-warmup diagnostic remains a separate investigation in `mb-b0aq`.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
