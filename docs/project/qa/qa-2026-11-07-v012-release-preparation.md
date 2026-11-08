# Metabrowser 0.12.0 Release Preparation

**Status:** In progress on November 7, 2026. Feature integration is merged and verified.
The release is not tagged or published; the user must approve publication.

## Integrated Candidate

All 28 product PRs in [stack 302](https://github.com/jlevy/metabrowser/stack/302) merged
at
[main `68534af93`](https://github.com/jlevy/metabrowser/commit/68534af933f0fcb38a5d81d62691bb42732d58ab).
The landed tree exactly equals reviewed tip `6cf001cdf`, retained as an ancestor.
The
[integration review](https://github.com/jlevy/metabrowser/pull/327#pullrequestreview-5816169303)
records the final review dispositions: all 16 findings resolved and all published heads
green before the merge.
The only open PR left from that audit is #247, the deliberately excluded reference.

Post-landing `make verify` on this actual main passed 4,916 tests with nine expected
skips, all 385 golden sessions, lint and type checks, both locked dependency audits,
distribution inspection and isolated installed-wheel smoke checks.
The Python suite took 1,048.15 seconds and the golden sessions 195.28 seconds.
The filesystem observer recorded no errors.
[Exact-main CI](https://github.com/jlevy/metabrowser/actions/runs/42439267509) passed
all nine jobs.

Both installed CLI names and the three existing previews use `0.11.1.dev1272+68534af93`.
The verified wheel’s SHA-256 is
`9b5ebaad3c6271acbc15795a7651c1fc4524777f24e1d2ce0213025cd92100c7`. The installation
check matched ten served assets per preview to the installed package.
The portable skill matches source, with its source pin advanced to this main commit.
This development version is not a published 0.12.0 release.

## Post-Landing Sessions

The installed main build passed built-in-browser sessions in both the managed repository
and existing-checkout previews: PR Conversation, Changes and Checks, title and numeric
Quick Search, native-stack titles, Checks-preserving stack selection and Shift-K, and
independent Files/Pulls route restoration.
The managed preview was explicitly switched to the merged main revision.

At a 1600 × 900 viewport, the document card and first view tab share the same 324 px
left edge. The document retains 40 px horizontal inner padding; Source retains its 16 px
vertical and 24 px horizontal code padding.

A separate plain-folder fixture changes 55 files.
Its complete CLI diff contains 55 patches and applies cleanly to the exact target tree.
Scrolling reaches the final file and hydrates its content automatically in Split and
Unified views, without the routine partial-file counter.
The commit description uses the neutral surface, 15 px sans text, 22.5 px line height
and preserved newlines.
The published 0.11.0 control produced the same complete JSON payload under the identical
`--diff HEAD --format json` invocation, and its apply oracle produced the same target
hash. Both browser builds reached the final file and hydrated it in Split and Unified.
This compares the installed main artifact above; final follow-up-head sign-off remains
separate.

The additional source tiers passed 20 macOS checks and eight live, read-only public
GitHub checks, including the typed missing-or-private refusal.
The strict admitted-Git tier passed all 1,124 tests in 754.45 seconds.
These supplement the installed-wheel checks; their source and artifact provenance are
kept separate.

## Current Follow-Ups

The additional UI layer `24f3721c9` follows the reviewed corpus/documentation layer
`c67371c2e`. It shares bold normal-ink actor and repository names across PR and commit
surfaces, places stack positions beside PR numbers, presents stack-menu rows as **1/6**
· title · #123, places the page menu beside its state badge, uses a leading GitHub brand
action, and moves Reload beside the Pulls filters.
Independent review found and resolved a keyboard regression in that Reload move.
Focused production sessions and goldens, lint and both type checks passed; browser
acceptance covers shared typography, update-age placement and menu fit in narrow panes.
The new layers still require their complete exact-head gate, published CI and final
installation. The earlier main verification above is not substituted for those gates.

The branch/worktree chooser is future workflow `mb-itzy`, explicitly deferred by the
user. It does not expand this stabilization or merge scope.

## Remaining Acceptance

| Gate | State | Tracking |
| --- | --- | --- |
| Post-landing browser smoke and current documentation | Both source modes passed; documentation awaits preparation-PR review and landing | `mb-5k2w` |
| Previous-release performance comparison | [Exp-056](../../../explorations/performance-loop/experiments/exp-056-previous-release-rehearsal.md) stopped after a valid 444 ms candidate first-row result exceeded the 350 ms hard gate. A final-candidate exp-057 comparison remains required | `mb-cf6y` |
| Linked dependency roots in the benchmark corpus | Reproduced with a small behavioral test; correction in this preparation branch | `mb-lsm5` |
| Regular-folder data, test-evidence and browser differentials | Pending final candidate; require zero unexplained differences | `mb-2g6f` |
| Plain-folder comparison above 50 files | Control and installed main have identical 55-file CLI payloads, clean apply oracles and both browser layouts; final follow-up-head sign-off pending | `mb-8pyc` |
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

The lower preparation layer corrects benchmark corpus materialization and documentation.
The subsequent UI layer changes the identity and navigation presentation described
above. Measurements retain their exact application source and artifact identities.
Historical loaded-host runs, interrupted captures and mixed-cache observations are not
relabeled as successful final-candidate evidence.
The initial PR-warmup diagnostic remains a separate investigation in `mb-b0aq`.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
