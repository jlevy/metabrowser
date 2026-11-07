# Plan for Watching GitHub Pull Requests

**Status.** Implementation and verification tracked in `mb-bzhx`. The design is
`mb-lz7e`, catalog refresh and recovery are `mb-ad70`, the Pulls UI is `mb-81f2`, and
session verification is `mb-khc4`. Shared row arrivals are tracked in `mb-x9v7`.

## Reader Behavior

While Pulls or a PR page is visible, Metabrowser checks the repository for new PRs and
changes to cached PR summaries.
Titles, draft and open states, closures, merges, timestamps, and filter tallies update
in place. The list keeps the active filter, scroll anchor, and selection when the row
remains in that filter.
If a PR moves out of the active filter, its open page stays available and the list keeps
an available keyboard anchor.

Showing the panel, restoring a visible browser page, focusing it, or coming back online
wakes a local cache read immediately.
A due provider check can follow.
Hiding Pulls, hiding the document, or closing the page suspends the recurring watch.
A GitHub checkout opened on Files keeps its lazy Pulls start.
A managed repository keeps its existing idle initial catalog warm-up, after the first
tree work. Eligibility uses the same served-repository discovery as the Pulls tab.

The watch covers the repository’s PR catalog.
The selected PR’s description, conversation, checks, and comparison continue through
their existing routes.
GitHub Issues belong to a separate catalog design.
See the [Pulls plan](plan-2026-10-01-github-pulls-tab.md#catalog-revision).

## Catalog and Request Ownership

Use the existing private SQLite catalog, conditional Pulls GET, and shared refresh POST.
The active Pulls controller owns one presentation timer and one in-flight top-window
read. The idle cadence is 30 seconds and the active-job cadence is one second.
Foreground wake signals use the same read ownership guard.
A hidden or superseded read loses ownership and its result cannot replace the active
filter or source. Page restore wakes the same controller and keeps the DOM and selection
intact. The watch uses the existing deferred GitHub assets.

The cache-only GET reads the current filtered window.
Its ETag lets the browser keep an unchanged prefix.
A changed generation is staged through the normal bounded pages before it replaces
displayed rows. Older cache pages keep their cursor and scroll behavior.
The Quick Search projection sees the same committed summaries.

The server admits one catalog refresh job per served repository and app coordinator.
A passive refresh joins existing work without changing a filter or paging priority.
A newly visible filter with missing rows can set the active demand, including when its
selection comes from a direct address or browser history.
Automatic checks follow the persisted freshness and failure cadence.
Setup, sign-in, and access failures get a quiet probe after two minutes while the list
is visible, or after the usual freshness window on a foreground wake.
A reconnect can request one early probe per source per 60-second window after a GitHub
network error. It joins any active job and leaves its priority in place.
Reload can request a refresh outside that cadence and still follows the server’s
rate-limit gate. An accepted job can finish and publish while the initiating page is
hidden. A failed local GET uses the local read’s retry path.

A refresh uses the existing `UPDATED_AT` GraphQL scan and saved watermark.
It reads newest updates first through the prior watermark, including ties at its
timestamp. An interrupted scan resumes from its saved cursor.
Summaries, counts, generation, and checkpoint publish together in each bounded
transaction. The response viewer and repository identity are checked before publication.
A different account or repository starts a new catalog generation on the first verified
page. Previous cached data remains readable under the local cache’s access policy while
GitHub access is unavailable.
See [Views, Models, and Routes](../../architecture/arch-views-models-routes.md).

## Live Arrivals

A newly created pull request uses the Files watcher’s arrival highlight when it enters
the visible list. See [Live Row Arrivals](../../../design-system.md#live-row-arrivals).
The first coherent top window from a complete, settled catalog establishes a neutral
baseline for its source, reader, catalog epoch, and filter.
A filter or account change, a hidden view, and a connection failure start a new baseline
on the next settled read.

The active top-window read qualifies new rows using their creation time after the
visible baseline. A qualifying row flashes once if it is in the viewport when it is
painted. Paging, historical backfill, title edits, and state changes of existing PRs use
normal row updates. Connection and refresh state own the list’s live region.

The existing cache read and shared catalog refresh deliver the rows.
The Pulls controller owns their interpretation, and another provider can reuse the
visual primitive with its own arrival signal.

When the reader is at the top, keep the pane there so prepended rows can be seen.
Farther down, retain the existing row and offset as the scroll anchor.
Keep the active page and keyboard selection with their PR number when the row remains in
the filter.

## Status and Recovery

Keep one status row in Pulls chrome beside the persistent **Reload** action.
The repository total and current display window keep their own labels.
Show the last successful update age when idle and the shared spinner while work is
active. A retry keeps the last failure visible and keeps its announcement steady until
the result changes. Announce meaningful status changes through the existing live region.
The empty PR landing keeps its selection prompt.
The Pulls status row owns repository catalog errors and recovery instructions.

| Condition | Status and Recovery |
| --- | --- |
| Cold or partial catalog | Show activity while the catalog fills. Reveal cached rows as each page publishes and keep the filter and selection available. |
| Missing or old `gh` | Offer the GitHub CLI setup link. Later attempts resolve the executable again. An installation or upgrade on the server’s existing `PATH` can recover in place. |
| Signed out or refused credentials | Show `gh auth login --hostname github.com` as the next step. Later attempts read the active account again. |
| Repository unavailable to the active account | Ask the reader to check the repository and account access. Keep prior cached rows visible. |
| GitHub connection or service failure | Distinguish a connection failure from an unavailable GitHub service. Continue with cached rows and use the shared retry policy. |
| Local Metabrowser server unreachable | Say the local server could not be reached. Re-read the cache when the connection returns. |
| Rate limit | Show the next eligible time when known. The server enforces the hold for automatic checks and Reload. With no provider reset time, show the local retry time after a hold of at least one minute. |
| Cache write failure | Say updates could not be saved and give the applicable cache recovery guidance. Keep any readable cache. |
| Recovery | A successful refresh replaces the old failure in the same status row. Newly published rows and totals flow into the current filter through the ordinary cached read. |

The minimum rate-limit hold follows the
[GitHub GraphQL rate-limit guidance](https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api#exceeding-the-rate-limit).

The [installation guide](../../../installation.md#git-and-github-setup) is the reference
for setup. If installing a binary changes the terminal’s `PATH`, restart a server that
inherited the earlier path.

## Acceptance and Evidence

- A fake `gh` session publishes a new PR, retitles a cached PR, and moves a PR between
  filters while a catalog is open.
  Check the GraphQL scan, saved cursor and watermark, resulting generations, exact
  counts, and stable selected page.
  Concurrent demand shares one source job.
- A fake-clock browserless session covers the first show, idle and active cadence,
  duplicate focus and online signals, hiding, a restored page, and disposal.
  Verify stale responses lose ownership and the controller coalesces foreground reads.
- Exercise missing or old `gh`, logged-out credentials, wrong account or repository
  access, provider network failure, local server loss, and known and unknown rate reset.
  Compare the cache before and after failure, restore the dependency or connection, and
  observe a successful update in the same page.
  Verify a reconnect gets one early provider probe and subsequent wakes respect the
  cooldown.
- In the browserless Pulls session, compare an initial baseline, a newly created PR, a
  title edit, an older PR changing filters, and cached paging.
  Verify that a refresh highlights a new visible row once, retains edited rows in place,
  and starts a neutral baseline after filter changes, account changes, or reconnects.
  Check the scroll and selection at the top and farther down.
  In the browser, check the shared highlight under both motion preferences.
- Check one status row and one accessible Reload action.
  Check that a held reset refuses early provider work and that a settled request can be
  tried again.
- In the built-in browser, repeat the cached-first and recovery flow for both an
  existing checkout and a managed GitHub repository.
  Confirm cached Files, Commits, and PR details remain usable and opening a checkout’s
  Files view stays lazy.
  Record the run in the [end-to-end playbook](../../../e2e-testing.md).

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
