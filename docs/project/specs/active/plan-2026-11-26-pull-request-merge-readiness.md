# Feature: Pull Request Merge Readiness

**Date:** 2026-11-26

**Author:** Drafted with LLM assistance for the project owner’s review

**Status:** Implemented in review: layers 0 to 6 are open as one stack.

Epic `mb-u16j`; Phase 1 is `mb-pcvm` and Phase 2 is `mb-ntnz`, built as one stack (see
[Implementation Plan](#implementation-plan)); Phase 3, `mb-om2v`, follows it.

## Overview

A reader can tell at a glance whether a pull request is open, a draft, merged, or
closed: the Pulls tab draws its state icon and the pull request page leads its header
with a colored state badge.
They cannot tell whether it is ready to merge.
The only sign today is one sentence at the end of the Checks tab, “Conflicts with the
base branch.”, which says nothing about failing checks, reviews, rules, or the merge
queue, and the Pulls tab shows nothing at all.

This plan makes merge readiness as obvious as the lifecycle state:

- **One verdict for each open pull request**, such as Ready to merge, Merge conflicts,
  Checks failing, Changes requested, Checks pending, Review required, Not up to date,
  Blocked, or Queued, classified and colored as GitHub classifies and colors them: green
  when it can merge, red when the author must change something, yellow while it waits on
  someone or something or GitHub has not answered.
- **On the pull request page**, a readiness badge beside the state badge, and a Merge
  status section at the top of the Checks tab with one row per requirement, as
  github.com’s merge box has, each linking to its details.
- **In the Pulls tab**, a readiness glyph in a column of its own on every open pull
  request’s row, in the same colors, so the list reads like a checks column.

It also separates a pull request’s **operational status** (conflicts, checks, reviews,
GitHub’s merge verdict, the merge queue) from its **core** (title, author, branches,
lifecycle, conversation).
The two change for different reasons, at different rates, and are detected differently,
so they become separate models with separate stores, revisions, and refresh paths.

The plan starts with the background: GitHub’s model of merge readiness in detail, how
github.com shows it, and how Metabrowser models and shows it today.

## Goals

- Every open pull request’s readiness is visible wherever its state is: on its page’s
  header, in its Pulls row, and on a stack’s member rows.
- One server-side derivation decides the verdict, and the page, the row, and `metab` all
  show what it decided, so no two surfaces can disagree.
- The verdict follows GitHub: whether a pull request can merge is GitHub’s
  `mergeStateStatus`, never Metabrowser’s reconstruction of branch protection.
  The inputs say why.
- Each requirement links to where the reader can act: the failing check’s details, the
  conflicts, the reviews, the merge queue, or the pull request on GitHub.
- Operational status is a model of its own, stamped with the head commit and the base
  branch it describes.
  A status for another head or base is never shown as current.
- A check finishing does not change the pull request’s core record, its revision, or the
  Conversation tab’s rendering.
- The colors are GitHub’s roles (success, danger, attention, neutral) expressed in
  Metabrowser’s tokens, with GitHub’s hue for each, held to the design system’s contrast
  tests in both themes.
- Every new route and field has its `metab` equivalent and golden transcript, and the
  verdict derivation is tested by invariants, not by restating its table.
- Browsing pull requests makes as much progress as quickly as GitHub allows: what is
  visible is read first, independent reads run in parallel, throttling keeps the
  account’s budget, and the cache answers what it can, all measured
  ([Phase 3](#phase-3-github-request-performance)).

## Non-Goals

- Merging, updating a branch, enabling auto-merge, or joining a merge queue from
  Metabrowser. Each requirement links to GitHub, where those actions are.
- Reading branch protection or rulesets to explain a `BLOCKED` pull request rule by
  rule. Most of it needs admin rights (see
  [Rules](#rules-branch-protection-and-rulesets)), and GitHub’s verdict already accounts
  for it.
- Filtering or sorting the Pulls tab by readiness.
  A follow-up can add a filter chip once the data is there.
- Readiness for closed and merged pull requests, whose lifecycle state is the whole
  answer.
- Repository-specific merge policies beyond GitHub’s, such as this repository’s own rule
  that `main` be green before a merge.

## Background: GitHub’s Model of Merge Readiness

Everything in this section was read on 2026-11-26 from GitHub’s GraphQL schema by
introspection (`gh api graphql` against `api.github.com`), from GitHub’s REST and
branch-protection documentation, and from Primer, GitHub’s design system
(`@primer/primitives` 11.10.0, `@primer/react` 38.47.0, and `@primer/octicons` 19.43.0).
Live values are from this repository’s open pull requests on the same day.
Where a statement describes what github.com shows rather than what an API returns, it
says so.

### Three Layers

A GitHub pull request has three layers of state.
They change for different reasons and at different rates.

1. **Lifecycle** (`state`, `isDraft`): `OPEN`, `CLOSED`, or `MERGED`, and for an open
   pull request whether it is a draft.
   A person changes it, and it moves the pull request’s `updatedAt`.

2. **Readiness inputs**, each a fact about the current head commit against the current
   base:
   - **Conflicts**: `mergeable`.
   - **Checks**: `statusCheckRollup` on the head commit.
   - **Reviews**: `reviewDecision`, and the reviews and review requests behind it.
   - **Up to date**: whether the head contains the base, enforced only by a rule.
   - **Other rules**: conversation resolution, signed commits, linear history,
     deployments, code owners, a locked branch, a required merge queue.

3. **GitHub’s verdict**: `mergeStateStatus`, which combines the inputs with the base
   branch’s protection rules and rulesets.
   Beside it are the mechanisms that merge for the author later: auto-merge and the
   merge queue.

Layers 2 and 3 change without anyone touching the pull request: a check finishes, the
base branch moves, or GitHub finishes computing `mergeable`. None of these moves
`updatedAt`, which is why `pull_freshness.py` and `pulls.py` already treat checks and
`mergeable` as needing reads of their own.

### Lifecycle

| Field | Values |
| --- | --- |
| `state` (`PullRequestState`) | `OPEN`, `CLOSED` (closed without merging), `MERGED` |
| `isDraft` | `true` only while `OPEN` |

`MergeStateStatus.DRAFT` is deprecated (“Use PullRequest.isDraft instead”), and GitHub
no longer reports it.
On 2026-11-26 this repository’s drafts read `CLEAN` (#380, #520) or `UNSTABLE` (#508) in
GraphQL, and REST’s `mergeable_state` read `clean` for #380. Whether a pull request is a
draft comes from `isDraft` alone, and a draft reports the merge state it would have if
it were ready for review.

### Conflicts: `mergeable`

`mergeable` (`MergeableState`) is `MERGEABLE`, `CONFLICTING`, or `UNKNOWN` (“still being
calculated”). REST spells the same field `true`, `false`, or `null`.

GitHub answers it by building a test merge commit (`potentialMergeCommit`) in a
background job. The REST documentation says the job starts when a client gets, creates,
or edits the pull request, and that a client seeing `null` should “resubmit the request”
after giving the job time.
The answer is a fact about one head and one base, so a push to either makes it unknown
again until the next job finishes.
On 2026-11-26 the first GraphQL read of #810 and #570 answered `UNKNOWN`; a REST read
seconds later answered `clean` and `dirty`. `served_pull.py` already waits
`MERGEABLE_SETTLE_S` for this, with its measurement.

`mergeable` says only whether Git can merge the two commits.
It says nothing about checks, reviews, or rules.

### Checks: `statusCheckRollup`

GitHub has two kinds of check, and the rollup combines both for the head commit:

- A **check run** (`CheckRun`), made by a GitHub App, GitHub Actions among them, has a
  `status` (`CheckStatusState`: `REQUESTED`, `QUEUED`, `IN_PROGRESS`, `WAITING`,
  `PENDING`, `COMPLETED`) and, once completed, a `conclusion` (`CheckConclusionState`:
  `SUCCESS`, `FAILURE`, `NEUTRAL`, `SKIPPED`, `CANCELLED`, `TIMED_OUT`,
  `ACTION_REQUIRED`, `STARTUP_FAILURE`, `STALE`).
- A **commit status** (`StatusContext`), posted by an external service, has a single
  `state` (`StatusState`: `SUCCESS`, `FAILURE`, `ERROR`, `PENDING`, `EXPECTED`).

`statusCheckRollup.state` is a `StatusState`: the combined result for the commit.
Its `contexts` connection holds both kinds of node.
Without fetching any node it counts them by state: `checkRunCountsByState`, by
`CheckRunState`, which folds a run’s status and conclusion into one 14-value enum, and
`statusContextCountsByState`.

Each context has `isRequired(pullRequestNumber:)`, true when the base branch’s rules
require it for this pull request.
A required check must end `SUCCESS`, `SKIPPED`, or `NEUTRAL`. GitHub’s documentation
says a skipped job reports success and “will not prevent a pull request from merging,
even if it is a required check.”

### Reviews: `reviewDecision`

`reviewDecision` (`PullRequestReviewDecision`) is `APPROVED`, `CHANGES_REQUESTED`,
`REVIEW_REQUIRED`, or `null`. Every open pull request in this repository read `null` on
2026-11-26, and `main` has no protection or ruleset (`protected: false`, no branch
rules). Whether `null` always means no rule requires a review is to be confirmed (see
[Open Questions](#open-questions)).

Behind it are `latestOpinionatedReviews` (each reviewer’s latest approving or
changes-requested review), `reviewRequests` (who has been asked), and each review’s
`state` (`PullRequestReviewState`: `PENDING`, `COMMENTED`, `APPROVED`,
`CHANGES_REQUESTED`, `DISMISSED`).

### Rules: Branch Protection and Rulesets

The base branch’s rules decide which inputs block a merge.
GitHub’s branch-protection documentation lists these requirements:

- required approving reviews, with code owner review, dismissal of stale approvals, and
  approval of the most recent push;
- required status checks;
- required conversation resolution;
- signed commits;
- linear history;
- a required merge queue;
- required deployments;
- a locked branch.

Admins and holders of the bypass permission are exempt unless the rule forbids
bypassing.

**Up to date** is not an input of its own.
Under strict required checks (“Require branches to be up to date before merging”), a
head that does not contain the base must be updated first, and GitHub reports `BEHIND`.
Without that rule, a pull request behind its base is still `CLEAN`.

A reader without admin rights cannot read most of these rules.
The schema describes `Ref.refUpdateRule` as the branch protection rules “viewable by
non-admins”, beside the full `Ref.branchProtectionRule`, and `Ref.rules` lists ruleset
rules. Metabrowser therefore takes GitHub’s verdict as the answer to “can this merge”,
and uses the inputs only to say why.

### GitHub’s Verdict: `mergeStateStatus`

`mergeStateStatus` (`MergeStateStatus`), with GitHub’s own descriptions:

| Value | GitHub’s description | Can merge now |
| --- | --- | --- |
| `CLEAN` | Mergeable and passing commit status. | Yes |
| `HAS_HOOKS` | Mergeable with passing commit status and pre-receive hooks. | Yes |
| `UNSTABLE` | Mergeable with non-passing commit status. | Yes: the failing or pending checks are not required |
| `BLOCKED` | The merge is blocked. | No: a rule’s requirement is unmet |
| `BEHIND` | The head ref is out of date. | No: a strict rule requires updating the branch |
| `DIRTY` | The merge commit cannot be cleanly created. | No: conflicts |
| `UNKNOWN` | The state cannot currently be determined. | Not yet known |
| `DRAFT` | Deprecated; use `isDraft`. | Never reported |

REST’s `mergeable_state` carries the same values in lower case.
Its documentation lists the field without its values.
The field needs no preview header: `gh api graphql` returned it with none.

GitHub documents no precedence among the causes.
This plan relies only on the descriptions and on what was observed:

- Conflicts win over checks: #872 read `CONFLICTING` and `DIRTY` with every check
  successful.
- Non-required failures do not block: #508 read `UNSTABLE` with three failing checks, in
  a repository that requires none.
- A draft reports the state it would have if it were ready for review.

### Merging Later: Auto-Merge and the Merge Queue

- **Auto-merge** (`autoMergeRequest`, with `enabledAt`, `enabledBy`, `mergeMethod`,
  `commitHeadline`, and `commitBody`) merges the pull request when its requirements are
  met. The repository must allow it (`autoMergeAllowed`, which is false here).
- **The merge queue** (`isMergeQueueEnabled`, `isInMergeQueue`, `mergeQueueEntry`): an
  entry has a `state` (`MergeQueueEntryState`: `QUEUED`, `AWAITING_CHECKS`, `MERGEABLE`,
  `UNMERGEABLE`, `LOCKED`), a `position`, `enqueuedAt`, and `estimatedTimeToMerge` in
  seconds. On a branch that requires a queue, **Merge when ready** enables auto-merge
  until the pull request can join the queue.
  GitHub removes an entry whose merge-group checks fail or time out.
- **What the viewer may do**: `viewerCanUpdateBranch`, `viewerCanMergeAsAdmin`,
  `viewerCanEnableAutoMerge`, and `viewerCanDisableAutoMerge`.

### What Reading It Costs

GitHub prices a GraphQL query by its connections, not its scalar fields.
`rateLimit(dryRun: true)` priced every variant of a 100-row `pullRequests` page at 1
point on 2026-11-26:

- with `title` alone;
- with `mergeable`, `mergeStateStatus`, `reviewDecision`, `isInMergeQueue`, and
  `autoMergeRequest`;
- with `mergeQueueEntry`;
- with `statusCheckRollup` and its counts by state (`contexts(first: 0)`);
- with all of these together.

`isRequired` and the list of checks need the contexts’ nodes, which only the pull
request page reads. The REST read of one pull request (`GET pulls/<n>`) already returns
`mergeable`, `mergeable_state`, `rebaseable`, `auto_merge`, and `requested_reviewers`.

### How github.com Shows It

Primer’s `StateLabel` (`@primer/react`, `StateLabel.js` and its stylesheet) is the
filled badge in a pull request’s header.
Its pull-request statuses:

| Status | Octicon | Background token | Light | Dark |
| --- | --- | --- | --- | --- |
| `pullOpened` | `git-pull-request` | `bgColor-open-emphasis` (success) | `#1f883d` | `#238636` |
| `draft` | `git-pull-request-draft` | `bgColor-draft-emphasis` (neutral) | `#59636e` | `#656c76` |
| `pullMerged` | `git-merge` | `bgColor-done-emphasis` | `#8250df` | `#8957e5` |
| `pullClosed` | `git-pull-request-closed` | `bgColor-closed-emphasis` (danger) | `#cf222e` | `#da3633` |
| `pullQueued` | `git-merge-queue` | `bgColor-attention-emphasis` | `#9a6700` | `#9e6a03` |

So GitHub gives a queued pull request a badge of its own, like a lifecycle state, in
attention yellow.

Primer’s foreground roles color status icons and text.
The values are from `dist/css/functional/themes/light.css` and `dark.css`, with their
OKLCH conversions:

| Role | Light | Dark | Light, OKLCH | Used for |
| --- | --- | --- | --- | --- |
| `fgColor-success` (`open`) | `#1a7f37` | `#3fb950` | `oklch(52.4% 0.140 148)` | Passing, approved, no conflicts, open |
| `fgColor-danger` (`closed`) | `#d1242f` | `#f85149` | `oklch(55.7% 0.206 25)` | Failing, changes requested, conflicts, closed |
| `fgColor-attention` | `#9a6700` | `#d29922` | `oklch(55.4% 0.117 75)` | Pending, running, review required, queued |
| `fgColor-done` | `#8250df` | `#ab7df8` | `oklch(56.3% 0.207 295)` | Merged |
| `fgColor-neutral` (`draft`, `muted`) | `#59636e` | `#9198a1` | `oklch(49.5% 0.022 251)` | Draft, skipped, neutral, cancelled, unknown |
| `fgColor-severe` | `#bc4c00` | `#db6d28` | `oklch(55.7% 0.160 45)` | Between attention and danger |

What github.com’s interface shows, which GitHub does not document:

- **The pull request list** shows the lifecycle as a colored octicon, the checks rollup
  as one icon after the title (a green `check`, red `x`, or yellow `dot-fill`), and the
  review decision as text in the metadata line (“Approved”, “Changes requested”, “Review
  required”). It shows nothing about conflicts or the merge state.
- **The pull request page’s merge box** stacks one row per input: reviews, checks,
  conflicts or out of date, then rules.
  Each row has a green, red, or yellow icon and a one-line headline, such as “All checks
  have passed”, “Some checks were not successful”, “This branch has conflicts that must
  be resolved”, “This branch is out-of-date with the base branch”, “Review required”,
  “Changes requested”, or “Merging is blocked”.
  The merge button below them is green only when the pull request can merge.

So GitHub answers “is this ready” only on the pull request’s own page.
Its list answers “are checks green” and “is it reviewed”, but not “does it conflict” or
“can it merge”.

### How GitHub Classifies Each State

The owner decided on 2026-11-26 that whether a state shows as passing, failing, or
pending follows GitHub by default.
GitHub’s web interface is not open source, but two GitHub sources are exact.

**The server’s rollup.** `statusCheckRollup.state` is GitHub’s own verdict for a commit.
Over this repository’s 813 pull requests with a rollup on 2026-11-26, it read:

| Conclusions present besides `SUCCESS` | Rollup |
| --- | --- |
| None | `SUCCESS` (445) |
| `SKIPPED` | `SUCCESS` (306) |
| `NEUTRAL` | `SUCCESS` (37) |
| `IN_PROGRESS` | `PENDING` (1) |
| `FAILURE`, with or without `SKIPPED` | `FAILURE` (15) |
| `CANCELLED` and `FAILURE`, with or without `SKIPPED` | `FAILURE` (9) |

**GitHub’s CLI.** `gh` 2.97.0, the version this repository’s tooling installs, read from
its module source:

- **Each check.** `gh pr checks` sorts each check into a bucket, with a mark and a color
  (`pkg/cmd/pr/checks/aggregate.go`, `output.go`):

| Bucket | States | Mark and color |
| --- | --- | --- |
| pass | `SUCCESS` | green `✓` |
| fail | `FAILURE`, `ERROR`, `TIMED_OUT`, `ACTION_REQUIRED` | red `X` |
| pending | `EXPECTED`, `REQUESTED`, `WAITING`, `QUEUED`, `PENDING`, `IN_PROGRESS`, `STALE`, and anything else, `STARTUP_FAILURE` among them | yellow `*` |
| skipping | `SKIPPED`, `NEUTRAL` | muted `-` |
| cancel | `CANCELLED` | muted `-`, with the status “fail” |

It lists checks failing first, then pending, then the rest.
It keeps only the latest run of each check (`eliminateDuplicates`): a check run is one
check by its name, its workflow, and the event that ran it, and a commit status one by
its context, apart from the runs.
So a job that a push and a pull request both ran is two checks: psf/requests#7619 had
two failing `lint` runs of one workflow, and `gh pr checks` listed all 61 of its
contexts on 2026-11-26. It counts the checks it lists, not the rollup’s contexts, and
summarizes in this order of precedence: “Some checks were not successful”, “Some checks
are still pending”, “Some checks were cancelled”, “All checks were successful”.

- **A pull request’s summary.** `gh pr status` counts a cancelled run as failing, as the
  rollup does (`parseCheckStatusFromCheckRunState` in `api/queries_pr.go`), and prints
  each part of an open pull request, drafts included (`pkg/cmd/pr/status/status.go`,
  `pkg/cmd/pr/shared/display.go`):

| Part | Green | Yellow | Red | Muted |
| --- | --- | --- | --- | --- |
| Checks | “Checks passing” | “Checks pending” | “n/m checks failing” | “No checks” |
| Reviews (`reviewDecision`) | “Approved” | “Review required” | “Changes requested” | Nothing when `null` |
| Conflicts (`mergeable`) | “No merge conflicts” | “Merge conflict status unknown” | “Merge conflicts” |  |
| Up to date, under strict checks | “Up to date” | “Not up to date” |  |  |
| Auto-merge | “Auto-merge enabled” |  |  |  |

The lifecycle colors match Primer: open green, draft gray, closed red, merged magenta.

GitHub’s documentation adds one rule the CLI does not need: “Draft pull requests cannot
be merged, and code owners are not automatically requested to review them.”
A draft leaves that stage when its author marks it “ready for review”
([About pull requests](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests#draft-pull-requests)).

## Background: Metabrowser Today

This section describes `main` at `c0ea0894`.

### What Is Read

| Read | Where | Merge-readiness fields |
| --- | --- | --- |
| Catalog page, GraphQL `Catalog` | `pull_list_refresh.py` `_QUERY` | None, deliberately: the catalog never reads a check or review (module docstring) |
| Cores, GraphQL `_CORE_FIELDS` | `pulls.py`, `pull_cores.py` | `mergeable` only |
| Full record, REST, six reads | `pulls.py` `_read_api` | `pulls/<n>` (`mergeable` kept; `mergeable_state`, `auto_merge`, `requested_reviewers` read and discarded by `_pull`), `reviews`, `commits/<head>/check-runs`, `commits/<head>/status` |
| Probes, conditional REST | `pulls.py` `probe_path`, `mergeability_probe_path`, `checks_probe_paths` | The issue; the pull while `mergeable` is unknown; the first pages of checks while they settle |
| Stacks | `pull_stacks.py`, `pull_stack.py` | None: membership and lifecycle state only |

`mergeStateStatus`, `reviewDecision`, `statusCheckRollup`, `isRequired`,
`autoMergeRequest`, and the merge queue are read nowhere.

### How It Is Modeled

There is one record per pull request, `PullRecord` in `pull_record.py`, written to
`pulls/<n>.json`.

- **The core and the operational status are mixed.** `PullRequest`, the record’s `pull`,
  holds the title, body, lifecycle, branches, and labels, and also `mergeable`
  (`Mergeable = Literal["mergeable", "conflicting", "unknown"]`). `CachedCore.pull`
  (`pull_core_cache.py`) and the envelope’s `core_preview` carry the same `PullRequest`,
  so a core has a `mergeable` too.
- **Checks are top-level parts of the same record**: `check_runs` (`CheckRun`), `status`
  (`CombinedStatus`), `truncated.check_runs` and `truncated.statuses`, and
  `unavailable["check_runs"]` and `unavailable["status"]`. `record_revision` digests the
  whole record, so a check that finishes gives the pull request a new revision.
- **The server keeps no rollup.** `pull_freshness.py` derives two booleans,
  `mergeability_pending` and `checks_settling`, for freshness alone.
  The counts are made in the browser (`checks()` in `pull-page.js`, through
  `CONCLUSION_TONES` and `STATUS_TONES`).
- **There is no review decision**, only each review’s state.
- **A list row (`PullListRow` in `pull_list.py`) and a stack member
  (`StackMemberWire.state`) carry the lifecycle and nothing else.**

### How It Is Kept Fresh

`updated_at` does not move for checks, statuses, or `mergeable`. The catalog’s delta
scan reads by `UPDATED_AT` and stops at its watermark, so a field added to catalog rows
would never be read again for an unchanged pull request.
A row field that changed with every check would also change the row’s fingerprint and
re-prepare its core (`pull_catalog.py`, `pull_core_cache.py`).

For the record:

- `record_freshness` (`pull_freshness.py`) gives the verdict `checks` to an open record
  past the freshness window, which starts a `checks_only` read.
- While checks settle, a visible page probes their first pages every `CHECKS_PROBE_S`.
- While `mergeable` is unknown, it probes the pull for `MERGEABLE_SETTLE_S`.
- Everything is read in full every `FULL_REFRESH_S`.
- `_same_mergeability` (`pulls.py`) compares `mergeable` alone, so a known answer that
  GitHub recomputes, for example after the base moved, waits for the full read.

The [update cadence plan](plan-2026-11-22-pull-request-update-cadence.md) measured all
of this. It found REST to be the scarce budget and GraphQL nearly unused: 28 of 5,000
points in an hour on an account whose agents spent 1,500 REST calls.

### How It Is Shown

- **Lifecycle.** `pull-state.js` holds one vocabulary, `PULL_STATES`, with a Lucide
  glyph and a label for each of the four states, and the plugin’s tokens
  `--github-pull-open`, `-draft`, `-merged`, and `-closed` (`styles.css`). The four
  tokens are Primer’s `fgColor-success`, `-neutral`, `-done`, and `-danger` re-expressed
  in OKLCH: the light values match the conversions above to the digit, with GitHub’s hue
  held in both themes.
  The Pulls row draws the glyph alone, named for screen readers.
  The page header draws it beside the title and leads its row of ages with an outlined
  text badge (`stateBadge` in `pull-page.js`: ink and a `currentcolor` border, no fill),
  in a slot as wide as the widest state.
  [A Pull Request’s State](../../../design-system.md#a-pull-requests-state) is the
  design.
- **Checks.** Only the pull request page’s Checks tab has them: a summary of counts by
  tone, in the order first met, then one row per run or status with an outlined badge,
  the name, and a link to its details (`paintChecks`). Success uses
  `--status-success-text`, failure `--status-error-text`, pending
  `--status-warning-text`, and the rest `--muted`. **The Pulls tab has no checks
  column**, nor any column model: a row is a run (state glyph, title, stack place,
  number, author) and a last line (the change line and the age, in a two-column grid
  with `--github-pulls-age-column`).
- **Mergeability.** One sentence at the end of the Checks tab, from `MERGEABLE`: “No
  conflicts with the base branch.”, “Conflicts with the base branch.”
  in the error ink, or “Merge status unknown.”
  (`describeCore`, `paintChecks`). The header, the Pulls tab, and stacks show nothing.
- **Reviews.** Each review in the Conversation timeline has a badge for approved,
  changes requested, or dismissed; there is no decision.

### What the Design System Asks

- Color has one meaning, and comes from a token
  ([Principles](../../../design-system.md#principles)). A plugin’s domain tokens live in
  its stylesheet.
- Every color is OKLCH, and a token keeps its hue in both themes
  ([Color and Theming](../../../design-system.md#color-and-theming)).
- Status set as text uses a `-text` ink at 4.5:1 or better on its grounds
  ([Status Text Inks](../../../design-system.md#status-text-inks)). Amber,
  `--status-warning-text`, is for a degraded or partial result only.
- Status never relies on color alone
  ([Accessibility Checklist](../../../design-system.md#accessibility-checklist)).
- The Pulls column has no tooltips; a mark’s meaning is its accessible name
  ([Tooltips Add Information](../../../design-system.md#tooltips-add-information)).
- An icon means one thing, and each is catalogued
  ([Icon Catalog](../../../design-system-icons.md)). Lucide `git-merge` already means
  merged and `circle-dot` a GitHub issue.
- The page header’s box is decided at first paint
  ([The Pull Request Page](../../../design-system.md#the-pull-request-page)).

## Design

### Approach

Seven decisions shape everything below.

1. **GitHub classifies; Metabrowser follows.** Whether a state shows as passing,
   failing, pending, or muted is what GitHub shows it as
   ([How GitHub Classifies Each State](#how-github-classifies-each-state)): the server’s
   rollup for a commit’s checks, and GitHub’s CLI for each check and each part of a pull
   request, by the owner’s decision of 2026-11-26. Where those differ from Metabrowser
   today, Metabrowser changes.
2. **GitHub’s verdict decides; the inputs explain.** Whether a pull request can merge is
   `mergeStateStatus`. Metabrowser never recomputes it from rules it cannot read.
   `mergeable`, the checks rollup, the review decision, and the queue entry say why, and
   which link helps.
3. **Operational status is a model of its own.** It describes one head against one base
   at one time. It is kept, refreshed, versioned, and served apart from the core, and
   nothing that changes with a check lives in the core record.
4. **One store, one derivation.** The Pulls tab’s scan and the pull request page’s read
   write the same status store.
   One pure function, on the server, turns a status into requirements and a verdict.
   The page, the row, the stack member, and `metab` read its answer.
5. **Tone is derived, not tabulated.** Each requirement has a status (met, waiting,
   unmet, unknown). The verdict’s tone is the worst status among the requirements, and
   its headline is the first requirement at that status, so a red verdict always names
   something the author must change.
6. **GitHub’s colors, in Metabrowser’s tokens.** Each tone takes GitHub’s hue: success
   green, danger red, attention yellow, neutral gray.
   Each uses an existing token where one already carries that hue, and a new plugin
   token where none does.
7. **Glyph in the list, word on the page**, as the lifecycle state already is.

### Core and Operational Status

|  | Core | Operational status |
| --- | --- | --- |
| What | Title, body, author, labels, branches, lifecycle (`state`, `draft`, `merged`, `merged_by`, `merge_commit_sha`, `commits`), conversation, comparison | Conflicts, checks, review decision, GitHub’s merge verdict, auto-merge, merge queue |
| Changes when | A person edits the pull request, pushes, comments, or reviews | A check runs, the base moves, GitHub finishes a computation, the queue advances |
| Detected by | `updated_at` (catalog scan, issue probe), the head | The head, the base’s commit, check probes, the clock |
| Model | `PullRecord`, `PullRequest`, `PullListRow`, cores | `PullStatus`, `PullChecks` (new, `pull_status.py`) |
| Revision | `record_revision` | The status’s own `observed_at` and head |

Moving to this split takes `mergeable` out of `PullRequest`. It also takes `check_runs`,
`status`, their `truncated` flags, and their `unavailable` parts out of `PullRecord`,
into the status store.
`PULL_RECORD_SCHEMA` is raised, so a cached record of the older schema is read again, as
any schema change is.
The server, browser, and built-in plugins ship as one artifact, so the envelope changes
in the same commit and no compatibility layer is needed.

A review stays in the core: it is conversation, and submitting one moves `updated_at`.
The review *decision* is operational, since it is GitHub’s judgment against the rules.

### The Status Model

`PullStatus` describes what GitHub said about one pull request’s readiness, at one head,
at one time. It is small enough for every open row:

| Field | Type | From |
| --- | --- | --- |
| `number` | int |  |
| `head` | `Sha` | `headRefOid`: the commit it describes |
| `base_ref`, `base` | name, `Sha` | `baseRefName`, `baseRefOid` |
| `observed_at` | `Timestamp` | When GitHub answered |
| `observed_by` | `scan` or `read` | The Pulls tab’s scan or the page’s read |
| `conflicts` | `mergeable`, `conflicting`, `unknown` | `mergeable` |
| `merge_state` | `clean`, `has_hooks`, `unstable`, `blocked`, `behind`, `dirty`, `unknown` | `mergeStateStatus` |
| `review_decision` | `approved`, `changes_requested`, `review_required`, or null | `reviewDecision` |
| `checks` | `ChecksSummary` | `statusCheckRollup` |
| `auto_merge` | `{method, enabled_by, enabled_at}` or null | `autoMergeRequest` |
| `queue` | `{state, position, enqueued_at, estimated_s}` or null | `isInMergeQueue`, `mergeQueueEntry` |

`ChecksSummary` has:

- `state`: GitHub’s rollup, `statusCheckRollup.state`, as GitHub gave it (`success`,
  `failure`, `error`, `pending`, or `expected`), or `none` when the head has no checks;
- `counts`: how many checks are in each of GitHub’s buckets, pass, fail, pending,
  skipping, and cancel, folded from `checkRunCountsByState` and
  `statusContextCountsByState` by the mapping `gh pr checks` uses;
- `required_failing` and `required_pending`, when the read had the contexts’ nodes, and
  otherwise null. A cancelled required check is among the failing.
  They say whether the checks can be why GitHub blocks a merge (see
  [Readiness](#readiness)); no sentence prints them beside `counts`, which count every
  context where a list counts each check once.

The buckets replace `CONCLUSION_TONES` and `STATUS_TONES` in `pull-page.js` and move to
the server, so the counts a row shows and the counts the Checks tab shows have one
source, and both are GitHub’s. Three checks change color: a cancelled check stays muted
but counts as failing in the summary, as the rollup does, and a stale check and one that
failed to start are pending, as `gh` shows them, where the Checks tab draws them muted
and failing today.

`PullChecks` is the list of checks for one head, which only the Checks tab needs.
Each item has its name, its kind (run or status), its bucket, its raw status and
conclusion, `required`, its details address, its app, and its description.
Like `gh`, it keeps only the latest run of each check, by the same keys.
It carries the truncation and unavailability that `PullRecord` carries for checks today.

### Readiness

`pull_readiness.py` turns a lifecycle and a status into a `Readiness`: a list of
requirements, then the verdict.
It is a pure function, and the only place readiness is decided.

**Requirements.** Each has a status:

- `met`;
- `waiting`: nothing the author must change; it waits on a check, a reviewer, the queue,
  or a one-click branch update;
- `unmet`: the author must change something;
- `unknown`: GitHub has not answered yet.

A row is present only where GitHub would show one: Reviews only when `reviewDecision` is
set, Up to date only when GitHub reports `behind`, and Queue only while queued.

| Requirement | `met` | `waiting` | `unmet` | `unknown` |
| --- | --- | --- | --- | --- |
| Conflicts | `mergeable` |  | `conflicting`, or `dirty` | `unknown` |
| Checks | Rollup `success`, or no checks | Rollup `pending` or `expected` | Rollup `failure` or `error` |  |
| Reviews | `approved` | `review_required` | `changes_requested` |  |
| Up to date |  | `behind` |  |  |
| Rules | Not `blocked`, or `blocked` explained by a row above |  | `blocked` that no row above explains | `merge_state` `unknown` |
| Queue |  | `QUEUED`, `AWAITING_CHECKS`, `MERGEABLE`, `LOCKED` | `UNMERGEABLE` |  |

“Explained” means another requirement is `waiting` or `unmet` and could be why GitHub
blocks the merge. Checks no rule requires never block one (`unstable`), so once the
page’s read knows the required checks’ counts and they are zero, pending or failing
checks explain nothing: kubernetes/enhancements#6506 read `BLOCKED` and `APPROVED` on
2026-11-26 with every required check passing and only the unrequired `tide` pending, and
its verdict is `blocked`, not `checks_pending`. Without those counts, as for a status
the Pulls tab’s scan read, a check that waits or fails still explains a block.
GitHub does not say which rule blocks a pull request, so the Rules row says that a rule
blocks it and links to the pull request on GitHub.

Checks follow the rollup, so failing checks that no rule requires (`unstable`) are
`unmet` and red, as `gh pr status` and the merge box show them.
The row adds what `unstable` says: GitHub allows the merge, since none of the failing
checks is required. Its sentence counts the page’s whole list of the head’s checks where
there is one, as `gh pr checks` counts what it lists, so it says what the list under it
says, with the required ones named beside the failing and the cancelled tallies; with no
list, as on the Pulls tab, it counts the rollup’s contexts, as `gh pr status` does, and
names no required count.
python/cpython#162697 shows why the two never mix: its rollup counted 5 failing contexts
where both lists showed 2 failing checks.

**Verdict.** Each status has a tone: `unmet` danger, `waiting` and `unknown` attention
(GitHub’s CLI shows an unknown mergeability in yellow), and `met` success.
The worst status among the requirements, ordered unmet, then waiting, then unknown, then
met, gives the verdict’s tone.
The first requirement at that status, in the order Queue, Conflicts, Checks, Reviews, Up
to date, Rules, gives the headline:

| Verdict | Requirement and status | Tone |
| --- | --- | --- |
| `ready` | Every requirement met | success |
| `ready_for_review` | Every requirement met, on a draft | success |
| `conflicts` | Conflicts unmet | danger |
| `checks_failing` | Checks unmet | danger |
| `changes_requested` | Reviews unmet | danger |
| `blocked` | Rules unmet | danger |
| `queue_failing` | Queue unmet | danger |
| `queued` | Queue waiting | attention |
| `checks_pending` | Checks waiting | attention |
| `review_required` | Reviews waiting | attention |
| `behind` | Up to date waiting | attention |
| `checking` | Anything unknown, nothing worse | attention |

Three rules sit outside the requirements:

- **Closed and merged** pull requests have no readiness.
  Their lifecycle is the answer.
- **A status for another head or base** gives `checking`. A status is never shown for a
  pull request it does not describe.
  A base changes under a status when GitHub retargets the layer above a stacked pull
  request that merged, which keeps its head.
- **A draft** is judged as an open pull request is, as GitHub’s `mergeStateStatus` and
  `gh pr status` judge it, since a draft reports the state it would have if it were
  ready. GitHub never merges a draft, so a draft with every requirement met is
  `ready_for_review`, in the words GitHub uses for a draft’s next step, rather than
  `ready`.

Auto-merge is not a requirement.
When it is on, the verdict keeps its tone, and the Merge status section and the
verdict’s accessible name add “Auto-merge enabled (squash)”, `gh`’s words.

`Readiness` on the wire has the verdict, its tone, and each requirement with its status,
a sentence, and its link.
`metab` prints the same.

### Reading and Freshness

**The pull request page** reads its status with one GraphQL query, `PullStatus`, on
every full read and on every change a probe finds.
It reads the status fields above and the contexts’ nodes, with `isRequired` for this
pull request number, a page at a time up to the bound `MAX_CHECK_RUNS` sets today.
This replaces the REST reads of `check-runs` and `status` in the full read.
The conditional REST probes stay as the change detectors, since GitHub answers a `304`
without charging it: the issue, the checks’ first pages while they settle, and the pull
while its mergeability is unknown.
A change one finds starts a status read where it starts a `checks_only` read today.
Only the GraphQL reads write a status, so every status has the same fields.

**The Pulls tab** reads the status of every open pull request with one GraphQL query a
page (`PullStatuses`), with the summary fields and no contexts’ nodes.
Layer 4 measured a page of 100 failing on a repository with many checks, at GitHub’s
time and resource limits, so a page is `SCAN_ROWS` rows and a scan at most
`MAX_SCAN_PAGES` pages, the open pull requests updated last, as the tab orders them
(`pull_status_scan.py` has the measurements).
It runs while the tab is visible: when the list’s probe finds a change, when a fetch
moves a base branch that open pull requests target, and otherwise every
`FULL_REFRESH_S`. A page with `unknown` answers is read once more after
`MERGEABLE_SETTLE_S`, since GitHub computes them after the first ask.
It is reader work, held by the governor and the `BACKGROUND_FLOOR` as the catalog’s scan
is.

**What makes a status stale:**

- the head moves (a catalog row’s `headRefOid` or the record’s head);
- the pull request is retargeted (the record’s or the row’s base branch is not the
  status’s `base_ref`), so a status read is due at once;
- the base moves (the mirror’s base branch differs from the status’s `base`), which can
  change conflicts and up-to-date;
- a check probe finds a change;
- `FULL_REFRESH_S` passes while visible.

The settle logic for `mergeable` (`MERGEABLE_SETTLE_S`, `mergeability_pending`) extends
to `merge_state`, and `_same_mergeability` compares the probe’s `mergeable_state` as
well as its `mergeable`. GitHub recomputes a known answer when the base moves, which the
base trigger above catches; nothing probes a known answer otherwise, so other
recomputations wait for `FULL_REFRESH_S`, as they do today.

**The store.** A `pull_status` table in the repository’s catalog database holds the
newest status for each pull request, keyed by number and stamped with its head.
It is a table of its own, not a catalog row field, so a status change touches no row
fingerprint, core, or window generation.
A write keeps the newer `observed_at` for the same head, under the catalog’s lock and
transaction discipline, with no network work under the lock.
`PullChecks` is written to `pulls/<n>.checks.json` beside the record, published
atomically through the plugin’s existing safe-path helpers.
Clearing the cache clears both.

**Budget.** Both reads are GraphQL, the budget the update cadence plan found nearly
unused.

- The Pulls tab’s scan costs 1 point a page, as priced by dry run above and measured,
  and each page spaces the next scan by `SCAN_POINT_GAP_S`, which bounds what it spends
  an hour whatever starts it.
- The page’s read costs 1 point for each 100 checks per full read.
- The REST reads it replaces are among the record’s six.

Phase 1 measures both reads’ cost and latency on this repository and on a large public
one, and records them beside their constants.

### Routes and CLI

- **`GET /api/plugin/github/pull`** gains `status` (`PullStatus`), `readiness`
  (`Readiness`), and `checks` (`PullChecks`), siblings of `record`, not inside it.
  `checks_pending` stays, read from the status.
  The entity tag keeps the status’s head and `observed_at`.
- **`GET /api/plugin/github/pull-statuses?numbers=<n>,...`**, a new route that reads
  only from the cache, as `pull-files-summary` does.
  For up to 100 numbers it answers each pull request’s `status` and `readiness`, or
  `absent` with a reason.
  The Pulls tab and the stack page ask it for the rows they draw.
- **`POST /api/plugin/github/pulls-refresh`**, the list’s existing ask, also starts the
  status scan when it is due, so no new refresh route is needed.
  Its answer says whether it did (`status_scan`) and when the last scan ended
  (`status_scan_at`), so a page learns of a scan that ended since its last ask whoever
  started it.
- **`metab --show /pull/<n>/checks`** prints the verdict and each requirement on the
  model line, beside today’s `check_runs=N statuses=N`.
- **`metab <repo> --api '/api/plugin/github/pull-statuses?numbers=...'`** reaches the
  new route, as `--api` reaches every route.

The parity registry gains the route row and a data row for readiness, and
[the map](../../architecture/arch-views-models-routes.md) gains the route and the status
model.

### Surfaces

**Page header.** The row of ages begins with the state badge and then the readiness
badge: `[Open] [Conflicts] Opened 3 days ago …`. The readiness badge is the outlined
`stateBadge` form in the verdict’s tone, so the two read as one vocabulary.
It has a slot of its own, as wide as its widest label, so a verdict that changes as
checks finish moves nothing in the row.
It links to the Checks tab’s Merge status section.
Its tooltip lists the requirements that are not met, which is what the badge
abbreviates. A closed or merged pull request leaves the slot empty.
Layer 5 measures whether the slot fits the row’s 420 px and 560 px limits, and shortens
the widest labels if it does not.

**Checks tab.** A **Merge status** section opens the tab, before the checks:

- the verdict’s badge and one sentence, such as “Conflicts with main must be resolved
  before this can merge.”;
- one row per requirement, each with its status word in its tone and a link:
  - Conflicts: to GitHub’s conflict page;
  - Checks: to the first failing or running check in the list below;
  - Reviews: to the latest changes-requested review in Conversation, or the reviews on
    GitHub;
  - Up to date: to the pull request on GitHub, where Update branch is;
  - Rules: to the pull request on GitHub;
  - Queue: to the base branch’s merge queue, with the position and the estimate;
- an Auto-merge row while it is on.

This replaces the sentence at the end of the tab.
The checks below it are ordered failing, then pending, then the rest, as `gh pr checks`
orders them; each is drawn in its bucket’s color, and a required check carries a compact
“Required” chip. The summary of counts takes the same order and leads with `gh`’s
sentence, such as “Some checks were not successful”.

**Pulls tab.** An open pull request’s last line gains a readiness glyph in a column of
its own, between the change line and the age: `+1,234 −567 › ⊗ 3d`. Aligned down the
list, it reads as a checks column.
The glyph’s accessible name is the verdict’s label, and the row’s name (`rowSaid`) says
it after the state, as the state icon’s does.
Where the pane is wide enough, the label follows the glyph, by a container query
measured as the stack tally’s noun is.
Closed and merged rows leave the column empty.

**Stacks.** A stack member’s row (`stackMemberRow`, in the stack menu, on the stack
page, and in a Pulls run) shows the same glyph.

### Vocabulary and Colors

`pull-readiness.js` holds one vocabulary, as `pull-state.js` does for the lifecycle: for
each verdict, a label, a glyph, and a tone.
A test holds its keys to the server’s verdict enum.

| Verdict | Label | Glyph (Lucide) | Tone | GitHub’s equivalent |
| --- | --- | --- | --- | --- |
| `ready` | Ready to merge | `circle-check` | success | Green merge button |
| `ready_for_review` | Ready for review | `circle-check` | success | A draft marked “ready for review” |
| `conflicts` | Merge conflicts | `triangle-alert` | danger | `gh`: red “Merge conflicts” |
| `checks_failing` | Checks failing | `circle-x` | danger | `gh`: red “checks failing”; red `x` |
| `changes_requested` | Changes requested | `file-diff` | danger | `gh`: red “Changes requested” |
| `blocked` | Blocked | `ban` | danger | Merge box: “Merging is blocked” |
| `queue_failing` | Leaving queue | `list-ordered` | danger | Removed from the queue |
| `queued` | Queued | `list-ordered` | attention | Primer `pullQueued`, `git-merge-queue` |
| `checks_pending` | Checks pending | `clock` | attention | `gh`: yellow “Checks pending”; yellow `dot-fill` |
| `review_required` | Review required | `eye` | attention | `gh`: yellow “Review required” |
| `behind` | Not up to date | `arrow-up-to-line` | attention | `gh`: yellow “Not up to date” |
| `checking` | Checking | `circle-dashed` | attention | `gh`: yellow “Merge conflict status unknown” |

The labels are `gh`’s words where `gh` has them.
`ready` and `ready_for_review` share a glyph because they mean one thing, that nothing
blocks the pull request; the label says which.

All of these glyphs are in Lucide 1.17.0, the version the plugin draws, and none is in
the icon catalog yet.
`git-merge` is not used for Ready, since it already means merged, nor `circle-dot` for
running, since it means an issue.

| Tone | Token | Light | Dark | GitHub’s hue |
| --- | --- | --- | --- | --- |
| success | `--status-success-text` (core) | `oklch(51% 0.15 149.18)` | `oklch(72% 0.16 149.18)` | 148 |
| danger | `--status-error-text` (core) | `oklch(55% 0.2 27.2)` | `oklch(72% 0.18 27.2)` | 25 |
| attention | `--github-pull-attention` (new, plugin) | `oklch(55.4% 0.117 75)` | about `oklch(72% 0.14 75)`, tuned to the tests | 75 |
| neutral | `--muted` (core) |  |  | Gray |

- **Success and danger** use the core status inks, which already carry GitHub’s hues
  within 3°, so the Checks tab’s badges and the readiness badge are one color.
  The lifecycle tokens `--github-pull-open` and `-closed` stay the lifecycle’s, since a
  color has one meaning.
- **Attention** needs a token of its own.
  The core’s only warning ink, `--status-warning-text`, is orange (hue 50) and reserved
  for a degraded or partial result.
  GitHub’s pending and queued yellow is hue 75. `--github-pull-attention` is Primer’s
  `fgColor-attention` in light, with the hue held in dark, and
  `test_pull_state_colors_keep_their_hue_and_read_on_both_grounds` extends to it.
  The Checks tab’s pending checks move to it from `--status-warning-text`, so waiting is
  one color across the plugin.
- **Neutral** is `--muted`, for the checks `gh` mutes, skipped, neutral, and cancelled,
  and for “No checks”.
  No verdict is neutral: GitHub shows every unknown in yellow.

No color is the only signal: each verdict has its own glyph and its label, in the
accessible name in the list and as text on the page.

### Alignment With the Object Data Model

[Object Data Model and Views](plan-2026-11-14-object-data-model-and-views.md#summary-and-facets)
sketches a `pull-request` type whose facets include
`merge{mergeable, merged_by, commits}` and `checks`. This plan suggests one `status`
facet, holding `PullStatus` and its `Readiness`, since they are one observation of one
head. `merged_by` and `commits` stay with the summary as lifecycle.
That plan’s corpus work settles the facet list.

## Implementation Plan

The work lands as one formal stack on `main`. Each layer is one pull request that
builds, passes, and can be reviewed and reverted on its own.
The two phases are the data, which `metab` shows, and the surfaces that draw it.

### Phase 1: Status Model, Readiness, and Data

**Layer 0: this plan** (epic `mb-u16j`).

**Layer 1: the status model and readiness** (`mb-epm3`).

- [x] `pull_status.py`: `PullStatus`, `ChecksSummary`, and `PullChecks`, with their
  bounds, their wire forms, and GitHub’s buckets for each check state.
- [x] `pull_readiness.py`: requirements and verdict, with the invariant tests in
  [Testing Strategy](#testing-strategy).

**Layer 2: reading and keeping the status** (`mb-8bp1`).

- [x] The page’s `PullStatus` GraphQL read, started on every full read and where a
  `checks_only` read is started today, with fixtures and the fake GraphQL answering it.
- [x] The `pull_status` table in the catalog database and `pulls/<n>.checks.json`,
  cleared with the cache.
- [x] The envelope’s `status`, `readiness`, and `checks`, and the `--show` model line.
- [x] Goldens, the parity registry, and
  [the map](../../architecture/arch-views-models-routes.md).
- [x] Measure the read’s cost and latency, and record them beside its constants.
- [x] Check whether `mergeStateStatus` depends on the viewer: not settled, since no
  protected branch was at hand to measure against (`pull_status_read.py`).
- [x] A changelog fragment.

**Layer 3: the core without operational status** (`mb-1iru`).

- [x] Take `mergeable` out of `PullRequest` and cores, and the checks parts out of
  `PullRecord`, and raise `PULL_RECORD_SCHEMA`. The full read stops reading `check-runs`
  and `status` over REST; the probes stay.
- [x] `mergeability_pending`, `checks_settling`, `record_freshness`, and
  `_same_mergeability` read the status.
- [x] The Checks tab draws its list from the envelope’s `checks`, in GitHub’s buckets.
- [x] [GitHub Pull Requests](../../architecture/arch-github-pull-requests.md) describes
  the split.

**Layer 4: every open pull request’s status** (`mb-0vb0`).

- [x] The Pulls tab’s `PullStatuses` scan, started by `pulls-refresh` when due, with the
  `MERGEABLE_SETTLE_S` re-read and the base-moved trigger, measured.
- [x] The `pull-statuses` route, its parity row, golden, and route-table row.
- [x] A changelog fragment.

### Phase 2: Readiness on the Page, the List, and Stacks

**Layer 5: readiness on the pull request page** (`mb-io36`).

- [x] `pull-readiness.js` vocabulary and the glyphs, with their catalog rows.
- [x] `--github-pull-attention`, its dark twin, and its contrast and hue tests; pending
  checks move to it.
- [x] The header’s readiness badge and slot, measured at 420 px and 560 px in Chrome: it
  fits, so no label is shortened (the measurement is beside
  `.github-pull-readiness-slot` in the plugin’s `styles.css`).
- [x] The Checks tab’s Merge status section, `gh`’s order and summary sentence, and the
  Required chip.
- [x] [Design System](../../../design-system.md) sections beside
  [A Pull Request’s State](../../../design-system.md#a-pull-requests-state).
- [x] A changelog fragment.

**Layer 6: readiness in the Pulls tab and on stacks** (`mb-3n21`).

- [x] The Pulls tab’s readiness column, its accessible name, and the container query for
  its label, measured in Chrome a pixel at a time (the measurement is beside
  `@container github-pulls` in the plugin’s `styles.css`). The label is in the text’s
  ink and the tone the glyph’s alone, since the success ink reads 4.47:1 on the open
  row’s tint.
- [x] Stack member rows.
- [x] The user guide’s sentence that the list does not track checks or mergeability
  ([Reviewing Pull Requests](../../../reviewing-pull-requests.md)) and the design
  system’s Pulls Tab section.
- [x] A changelog fragment.

### Phase 3: GitHub Request Performance

The owner asked on 2026-11-26 for a later phase that measures how browsing pull requests
uses `gh` and the GitHub API, finds the bottlenecks, and makes sure parallelism,
throttling, prioritization, and caching are right.
The readiness stack adds reads of its own (the page’s status read and the Pulls tab’s
scan), so this phase measures after it, and it lands as a stack of its own (`mb-om2v`).

It builds on what is already there: every `gh` subprocess is a span in the event log
with its arguments and HTTP status (`gh.py`); `gh_budget.py` counts what each answer
spent and holds the ceilings and floors; the
[update cadence plan](plan-2026-11-22-pull-request-update-cadence.md) measured what each
job costs; and the performance loop
([explorations/performance-loop](../../../../explorations/performance-loop/README.md))
drives pull request navigation in a real browser.
It absorbs `mb-mg37`, the hour of real browsing that `AUTOMATIC_CORE_PER_HOUR` and
`SPECULATIVE_CORE_PER_HOUR` still wait on.

- [ ] **A GitHub request report** (`mb-e2qx`): from the event log’s `gh` spans, for each
  lane (visible, attended, prefetch, background) and job, the requests made, REST `core`
  spent (an answer other than `304`), GraphQL points, the share answered `304`, latency
  at the median and the 95th percentile, requests in flight over time, time queued,
  duplicate reads, cache hits, and the time to the first answer the reader sees.
  It is a route, so `metab --api` reaches it, with a golden over a synthetic event log.
- [ ] **A browsing benchmark** (`mb-ulvg`): one scripted session (open the Pulls tab,
  scroll, open several pull requests, switch tabs, come back) run two ways.
  Against the fake `gh` with recorded latencies it is deterministic, and its test holds
  invariants: visible work is read before background work, requests in flight stay
  within their bounds, nothing is read twice in a window, a revisit is answered from the
  cache, and the session spends under a stated bound.
  Live, against this repository and a large public one, its numbers are recorded in the
  performance loop under its durable storage rules, with `mb-mg37`’s hour.
- [ ] **Tuning** (`mb-3i1s`): each change the measurements justify, measured before and
  after with the report and the benchmark, its constant documented beside its definition
  with the measurement.
  Candidates to test, not conclusions: independent reads of one pull request run
  concurrently; the lanes ordered visible, attended, prefetch, background; one GraphQL
  query of aliased pull requests for the rows on screen; conditional requests wherever
  GitHub answers `304`; fewer account checks per refresh (the update cadence plan found
  two per refresh); and the cache answering a revisit without asking GitHub.

## Testing Strategy

**Invariants of the derivation** (`pull_readiness.py`), over every status GitHub can
report, generated from what each `mergeStateStatus` means rather than listed, and over
answers GitHub gave for real pull requests:

- a closed or merged pull request has no readiness;
- a status for another head or base gives `checking`;
- the tone is the worst requirement status, and the headline names a requirement at that
  status, so a danger verdict always names an unmet requirement;
- `ready` and `ready_for_review` hold only when every requirement is met, and
  `ready_for_review` exactly when the pull request is a draft;
- the Checks requirement’s status is the meaning of the bucket `gh` sorts the rollup’s
  state into;
- the verdict agrees with `mergeStateStatus` and the required counts: a state GitHub
  lets merge is never blocked, `DIRTY` always shows its conflicts, and `BLOCKED` with no
  required check failing or pending always shows a Rules or Reviews block;
- the page’s sentence tallies exactly the checks it lists, and the list is the one
  `gh pr checks` lists of the same answer;
- `conflicting` or `dirty` always yields an unmet Conflicts requirement;
- `blocked` with every other requirement met yields `blocked`, never `ready`;
- a draft and an open pull request with the same status have the same verdict, but for
  `ready` and `ready_for_review`.

**Goldens.**

- `cli-github-pull.tryscript.md` shows the envelope’s `status`, `readiness`, and
  `checks`, and the `--show` model line.
- A new `cli-github-pull-statuses.txt` shows one fixture pull request for each verdict
  through the route, built by the production writers from the synthetic fixture
  accounts.
- `cli-github-pulls-prefetch.txt` keeps pinning every freshness verdict, now read from
  the status.

**Browserless sessions.**

- `tests/dom/github-pull-page-session.js` summarizes the Merge status section and the
  header’s verdict, pinned by `cli-ui-github-pull-page.tryscript.md`.
- The Pulls panel’s session summarizes each row’s verdict and accessible name.

**Construction over restatement.**

- The vocabulary’s keys are tested against the server’s enum.
- No test repeats a label, color, or order the vocabulary spells out.
- The contrast and hue tests hold the new token.
- `tests/test_icon_catalog.py` holds the glyphs.

**Chrome.**

- The header slot’s width at the row’s limits.
- The list column’s alignment, and the label’s container query.
- The painted ink of each tone in both themes, as the existing paint exemptions name.

## Rollout Plan

Both phases ship with a release, as every change does.

- The record schema bump makes each cached record read again once, on its next refresh.
- The status table fills as the Pulls tab is visible.
- Until a status is read, a row shows no glyph and the page shows Checking.

If the macOS app reads the pull envelope’s `record.pull.mergeable` or check fields, it
changes in the same commit, with `MetabRequirement.minimumRelease` raised.
Phase 1 checks this first.

## Decisions

The owner’s decisions of 2026-11-26:

1. **Follow GitHub.** Whether a state shows as passing, failing, or pending is what
   GitHub shows it as, by default
   ([How GitHub Classifies Each State](#how-github-classifies-each-state)). This settled
   two questions the draft left open: failing checks that no rule requires are red, as
   GitHub’s rollup and CLI show them, and a draft is judged as an open pull request is,
   with Ready for review in place of Ready to merge.
2. **Implement everything as one stack of pull requests**, in the layers under
   [Implementation Plan](#implementation-plan).
3. **Measure and tune GitHub request performance as a later phase**,
   [Phase 3](#phase-3-github-request-performance), tracked under the same epic.

## Open Questions

1. **Placement.** This plan reads “the checks column” as the Checks tab, since the Pulls
   tab has no column model, and also gives the Pulls tab a readiness column of its own.
2. **Labels and glyphs.** Are the glyphs in
   [Vocabulary and Colors](#vocabulary-and-colors) the right shapes?
   Should the list show a word as well as the glyph in a narrow pane?
3. **Badge form.** Outlined, as the state badge is (this plan), or filled, as GitHub’s
   `StateLabel` and the core `.badge-*` tones are?
4. **Stack header.** Should the stack page’s state tally gain a readiness tally, such as
   “3 Ready · 1 Merge conflicts”?
5. **Viewer.** Does `mergeStateStatus` depend on the viewer, such as an admin who may
   bypass? Layer 2 could not settle it: its only reader was an admin of a repository
   whose `main` has no protection or ruleset (`pull_status_read.py`).
6. **Behind without a rule.** Should the pull request say how far behind its base it is
   when no rule requires updating?
   The mirror can count it locally from the comparison’s base commit.

## References

- GitHub GraphQL reference:
  [Objects](https://docs.github.com/en/graphql/reference/objects) (`PullRequest`,
  `StatusCheckRollup`, `CheckRun`, `StatusContext`, `MergeQueueEntry`) and
  [Enums](https://docs.github.com/en/graphql/reference/enums) (`MergeStateStatus`,
  `MergeableState`, `PullRequestReviewDecision`, `StatusState`, `CheckRunState`,
  `MergeQueueEntryState`)
- [REST: Get a pull request](https://docs.github.com/en/rest/pulls/pulls#get-a-pull-request)
- [About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [About status checks](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/about-status-checks)
- [Merging a pull request with a merge queue](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/merging-a-pull-request-with-a-merge-queue)
- [Primer primitives](https://github.com/primer/primitives) (functional color themes)
  and [Primer React `StateLabel`](https://primer.style/product/components/state-label)
- [GitHub Pull Requests](../../architecture/arch-github-pull-requests.md)
- [Pull Request Update Cadence and GitHub Budget](plan-2026-11-22-pull-request-update-cadence.md)
- [Object Data Model and Views](plan-2026-11-14-object-data-model-and-views.md)
- [Design System](../../../design-system.md) and
  [Icon Catalog](../../../design-system-icons.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
