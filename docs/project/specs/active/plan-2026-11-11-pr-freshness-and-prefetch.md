# Plan for Event-Based Pull-Request Freshness and Budgeted Prefetch

**Status.** Implemented in draft pull request #355, revised for its first reviews (A and
B); not merged. This is the second pull request of the spinner-free refresh stack (epic
`mb-c93s`, bead `mb-wlx0`), based on the presentation pull request (`mb-wl9x`, branch
`claude/pr-refresh-without-spinners`). One GraphQL query per record refresh is a later,
separate change (`mb-xhtc`) and is out of scope.

## Reader Behavior

The reader’s requirements, condensed:

- Whenever the reader looks at a list of pull requests, it was fetched recently.
- Opening a pull request shows the cached version at once and refreshes it in the
  background, never behind a spinner.
- Metabrowser prefetches a reasonable amount, so what the reader opens is usually
  already current when they arrive.

The presentation pull request removes the spinners over rendered content and the “may be
out of date” suffix.
This plan makes the data current more often and cheaply, so a background refresh has
less to do and runs less often.

## Background

Every cached pull-request datum is judged by one 60-second clock (`FRESHNESS_WINDOW_S`,
`mirror_refresh.py`), and nothing revalidates a record or a changed-files list until the
reader is looking at it.
After any absence longer than a minute, opening a pull request starts its GitHub
refresh: a record refresh is two account checks, one pull read, five parts read
together, and on a mirror a fetch of the head, measured at 4.7 to 7.0 s (median 5.2 s)
beside `MAX_PULL_JOBS`. Most of that work rediscovers that nothing changed.

The repository catalog already holds what is needed to know that cheaply.
Its delta scan (`pull_list_refresh.py`) reads pull requests ordered by `UPDATED_AT`
until the stored watermark, so one GraphQL point says which pull requests changed since
the last scan.

Measured on github.com on 2026-11-11, read-only, with gh 2.98.0:

- On five open `cli/cli` pull requests, GraphQL `updatedAt` and `headRefOid` were equal
  to REST `updated_at` and `head.sha`, character for character.
  The comparison below relies on that equality.
- Six `gh auth status --active --json hosts` calls raised the account’s core
  `x-ratelimit-used` by exactly six, and the next `rate_limit` read by none: each
  account check costs one core point.
- A 100-row catalog page of `cli/cli` was 58,811 bytes and with `headRefOid` 64,410
  bytes (9.5% more); GitHub reported a cost of 1 for both.
- The account’s budget is shared: before any of these reads it had already used 416 core
  and 162 GraphQL points that hour, from other clients.
- Every REST and GraphQL response carries `x-ratelimit-limit`, `-remaining`, `-reset`,
  `-used`, and `-resource` (`core` or `graphql`).

## Design

### Principles

1. Judge freshness by events, not a clock: the catalog’s delta scan says which pull
   requests changed.
2. Revalidate before the reader looks, within a budget.
3. Foreground work is never budget-gated and never waits behind background work.
4. Validate only within one source and one reader, and say honestly how old each part
   is.

### The Catalog Knows Each Head

The catalog query adds `headRefOid`, and `PullListRow` gains `head_oid`, a full commit
ID or `null` for a row written before this change.
`CATALOG_PROJECTION` becomes 2, so the existing projection upgrade rescans `all` once
and enriches cached rows without discarding the offline view.
Every row of `GET pulls` carries `head_oid`.

### When a Record Is Current

A record is checked against the catalog row of its number, read with the catalog
checkpoint in one SQLite transaction.
The catalog is usable only when its `source` and `reader` equal the record’s.

| Catalog | Row and record | Result | `verified_by` | `verified_at` |
| --- | --- | --- | --- | --- |
| usable, any age | row’s `updated_at` newer than the record’s `pull.updated_at`, or equal with another `head_oid` | `stale`, *changed*: `head_moved` when the row’s `head_oid` differs from the record’s head | `fetch` | the record’s `fetched_at` |
| usable, scan within the window, or the next one running and the last within the window and `SCAN_GRACE_S` | not changed; the pull request closed, or the record read within the window | `current` | `catalog` | the newer of the scan’s `fetched_at` and the record’s |
| the same | not changed; an open pull request read longer ago than the window | `stale`, *checks*: its checks are read on their own | `catalog` | the same |
| otherwise | — | the 60-second clock, as before | `fetch` | the record’s `fetched_at` |

A record written with no store stays stale on a server that has one, as before.

A second’s tie with another head is a change: `updated_at` has whole seconds, and a push
within the second the record was read leaves the times equal.

**A running scan vouches for a bounded time.** The page asks for the next scan before
its read, so the read usually lands while that scan runs.
The last scan then still vouches, but only for `SCAN_GRACE_S`, 15 s, past the window: a
delta scan with nothing new is one account check and one GraphQL page, about 1 s, and it
can wait for a network slot behind a record refresh, 4.7 to 7.0 s; 15 s is twice the
slowest.
An older catalog is unverified whatever runs, so a page reopened on it is judged
by the clock and refreshes a stale record at once, as before.
While the scan runs, a catalog verdict’s `x-metabrowser-verified` header ends in
` scanning`, and the page polls fast until it ends, so a change that scan publishes is
refreshed within a fast poll, not a slow one.

**Checks are read on their own.** `updated_at` does not move when a check run, a commit
status, or `mergeable` changes: CI that registers after the record was read, a re-run of
settled checks, a conflict a moved base made.
So the catalog vouches for an open pull request’s conversation and head, never for its
checks: an open record read longer ago than the window is *checks*, `stale`, and its
automatic refresh reads them on their own (T5). That refresh asks for the pull, its
check runs, and its status, each with its ETag, and keeps the comments, reviews, and
review comments, while the pull names the cached head, base, and `updated_at`, which
those parts move; a mirror then keeps its comparison and fetches nothing.
A pull that moved takes the full read.
`checks_pending` reports checks still settling, for the page to say: a check run not
`completed`, a combined status `pending` with contexts, `mergeable: unknown`, or no
check run and no status in a record read within `NO_CHECKS_GRACE_S`, five minutes, of
the pull request’s last update, since its CI may not have registered.
It decides no verdict, since an open record past the window is read again anyway.

**When the automatic refresh is due.** A request that is not a reader’s own action
refreshes a record that is:

- *changed*: due when no attempt was made for the row that reported the change, its
  `updated_at` and head, and otherwise once a window; a rate-limit hold still holds.
  So a pushed head is refreshed at once, and a REST answer that lags the catalog is
  asked for again once a window, however many pages later scans publish.
- *checks*: due once a window, the checks-only refresh.
- *current*: not due.
- *unverified*: the existing clock and attempt-window rules.

`ServedPull` keeps the newest verdict the routes computed (`verified_at`, the changed
row, and whether only checks are due), so the attended pull request’s share of a
mirror’s `stale` follows the same rule from memory.

**Head moved.** A changed record whose catalog head differs is `stale` with
`head_moved: true`, and its refresh is due at once.
The refresh writes the new record and comparison; the page keeps the diff it displays
and offers the newer changes, as it does today when a refresh finds a newer head
(`issued_comparison`). It never switches the diff under the reader.

### When a Changed-Files List Is Current

A list read from GitHub records the head commit and base branch name it describes,
`head` and `base_ref`, observed from the newer of the record and the catalog row just
before its first page is read.
A push between that observation and a page read can only make the list look older than
it is, which costs one more refresh and never shows a stale list as current.

A GitHub list is current while its `head` and `base_ref` equal the newest known head and
base, the newer of the record’s and the catalog row’s by `updated_at`. A comment, a
review, or a label no longer makes it stale.
When the list or the newest source names no head, the existing rule applies: the pull
request’s `updated_at` is no newer than the list’s `fetched_at`, or the window when
neither is known. The local comparison’s list keeps its exact base-and-head rule.

### Prefetch Tiers and Budgets

Every tier runs only while a page of the repository is visible and online, because only
a visible page asks.
Nothing on the server starts background work by itself.

| Tier | What | Asked by | Due when | Budget | Core points each |
| --- | --- | --- | --- | --- | --- |
| T0 | Catalog delta scan | the Pulls panel on start, show, visibility, focus, online, page show, and at `fetched_at` + 60 s; a PR page whose record the catalog vouched for, when that check is a window old, before it reads | the window passed | one per window: at most 60 an hour | 1 account check, plus 1 GraphQL point per page |
| T1 | Changed records this server recently served | the panel, after a scan publishes | catalog says changed | shares T2’s caps | at most 8 |
| T2 | The anchored row, its J/K neighbours, the top open PRs, the visible rows | the panel, after a walk settles | missing, or changed | 8 per catalog publication, 40 an hour, T1 and T2 together | at most 8 |
| T3 | Changed-files lists of the selected row and its neighbours | the panel, with T1 and T2 | missing, incomplete, or head or base moved | 20 an hour | 1 account check, then a page and an account check per page: 3 for one page |
| T4 | Changes | the existing idle prefetch only | — | — | — |
| T5 | Checks of an open pull request | the visible PR page | read longer ago than the window | foreground: visible page only, once a window | 2 account checks, then the pull, its check runs, and its status, each free on a `304` |

A record refresh costs at most 8 core points when each part fits on one page: two
account checks, the pull, and five parts; a `304` is free, an account check is not.
A part of more than 100 comments, reviews, or check runs costs a point a page more.
The lanes and their caps are in memory, one per repository a server process serves, so
at the caps, at one page a part, T1 to T3 spend at most 40 × 8 + 20 × 3 = 380 core
points an hour for each repository in each process, 7.6% of a 5,000-point limit, and T0
at most 60 core and 60 GraphQL points.
The account as a whole is bounded by the governor’s floor, which is read from GitHub’s
own count of what remains.
The per-test measurements against the fake `gh` are in [Measurements](#measurements).

T4 never prefetches a checkout’s store acquisition; idle comparison stays gated on an
attached store, as now.

### The Prefetch Lane

`POST /api/plugin/github/pulls-prefetch` takes `records` and `files`, each at most 16
distinct pull-request numbers in the page’s priority order, and `changed`, which adds
T1: the numbers this server most recently answered `GET pull` for (at most 16), when the
catalog says they changed.
The request replaces the lane’s queue; the newest intent of the page wins, so a J/K walk
that moved on drops what it no longer needs.
The panel sends one request at a time: an ask made while one is on its way waits as the
one pending ask, sent when that request answers and built from the panel as it is then,
with `changed` when any ask that waited had it.

Each server keeps one lane per repository, a coordinator job that runs one item at a
time. Before each item, off the event loop, it reads again whether the item is due, then
whether the governor admits it and the caps have room.
A record item is due when it is missing (a named number only) or changed; a files item
when the files route would start an automatic refresh.
An item another process has refreshed meanwhile is no longer due, because the record and
the list on disk are what is read.

The lane stops, dropping the rest of its queue, when the governor refuses, a cap is
reached, or a reader’s job preempts its job.
The page asks again later.
A job is started under the item’s ordinary key, so a reader’s request for the same pull
request joins it.
The lane does not stop merely because a reader’s work is running, since
it cannot delay it: its record jobs wait at the store turn behind a reader’s and are
cancelled when one starts waiting, and no background job holds a network slot.
(Stopping then dropped every prefetch a reader’s landing asked for, because the page’s
own refresh of the row was running.)
A job a reader preempts gives its place in the caps back, since it made nothing current;
the requests it spent are in the governor’s observations.
The lane stops there, because what it had queued would wait behind the reader too.

`GET /api/plugin/github/pulls-prefetch` reports the lane from memory: the running item,
the queue, the caps and their use (`scan`, the catalog publication the per-scan count
belongs to, its epoch and `fetched_at`, which a scan of several pages publishes once),
the governor’s observations and verdict, and the outcomes of the last 16 items.
The `POST` answers `202` with `prefetch: "started"` or `"joined"` and that route as its
`status_route`, or `200` with `"not_due"` (nothing named) or `"deferred"` and a
`reason`, `below_floor` or `rate_hold`, when the governor admits nothing.
An item the lane does not run says why in the report: `skipped:current`,
`skipped:checks` (only an open pull request’s checks are due, which its visible page
reads), `skipped:unverified`, `skipped:not_cached`, or `skipped:not_due`, or the stop,
`deferred:` and one of `below_floor`, `rate_hold`, `hourly_cap`, or `scan_cap`; one a
reader preempted is `preempted`. A one-shot `--api` waits for the lane and prints that
report.

### The Rate-Limit Governor

`gh.py` passes the rate-limit headers of every response it parses, including refusals,
to `gh_budget.py`, which keeps the newest observation per resource for the process:
limit, remaining, and reset time.
An observation expires at its reset.
A `rate_limited` failure holds every resource until its `reset_at`, or for a window when
GitHub gave none. Both belong to the account the last account check named: each
`gh auth status` tells the governor its login, and another login forgets the
observations and the hold, since its token has its own budget.
A response already in flight at the switch can be observed for the new account until its
next check, at most one refresh’s requests.

Background work is admitted only while every observed resource it spends has more than
25% of its limit remaining, no hold applies, and the catalog’s persisted list stamp
holds no rate limit.
With nothing observed yet it is admitted, and its own first response is observed.
Foreground work is never gated: a reader’s request, the page’s automatic refresh of what
it shows, and T5 run whatever the governor says.

The 25% floor is a reserve, not a measurement of Metabrowser’s use: 1,250 of 5,000 core
points cover a reader who refreshes a pull request every 30 s for two hours, 240
refreshes at 8 points, with room for the other clients that share the account, which
spent 416 that hour before any of these reads.

### Foreground First

- **Slots.** A background job takes no coordinator network slot.
  The lane runs one at a time, so background work adds at most one job beside the
  coordinator’s two.
- **Store turn.** A background job waits at a store turn only behind every other waiter,
  and is never counted for `MAX_FIRST_IN_A_ROW`. When any other job starts waiting while
  a background job holds the turn, the background job is cancelled: its Git and `gh`
  processes stop, the record on disk stays as it was, and its attempt is forgotten, so
  the reader’s automatic refresh of that pull request is not held by a window.
  The same holds for a checkout’s turn, which serializes its pull jobs with or without a
  store.
- **Promotion.** A reader’s request for a pull request whose background job is queued or
  running promotes it: from then on it waits as an ordinary job, cannot be preempted,
  and counts toward `MAX_PULL_JOBS`.
- **Bounds.** Background jobs count toward neither `MAX_PULL_JOBS` nor the file-list
  bound, so they cannot make a reader’s request answer `too_many`.

### Offline and Hidden

The browser asks for T0 to T3 only while visible and online; a hidden or offline page
asks for nothing, and the lane, which only runs what it was asked, ends.
A lane item that meets a network failure records it and the lane stops; the existing
attempt windows hold the next automatic attempt.

### Several Servers on One Cache

Records and file lists are replaced atomically and the catalog is SQLite, so each
process reads the others’ writes.
Each lane item rereads the record, the list, and the catalog on disk before it runs, and
the persisted refresh stamps carry attempt windows and rate holds across processes.
The caps are per repository and per process, and the governor’s observations per process
and account; the floor is read from GitHub’s account-wide `remaining`, so several
servers stop together.

## API Changes

- `GET pulls`: each row adds `head_oid`.
- `GET pull`: adds `verified_at`, `verified_by` (`catalog`, `fetch`, or `null` with no
  record), `head_moved`, and `checks_pending`. The entity tag covers `head_moved`,
  `checks_pending`, and `state` but not `verified_at` or `verified_by`, which move with
  every scan: `x-metabrowser-verified: <verified_by> <verified_at>` carries them on a
  `200` and a `304` alike, so a polled page is not sent its record again each window.
  A catalog verdict given while the next scan runs adds ` scanning`.
- `GET pull-files` and its refresh answer: `head` is set for a GitHub list too, and
  `base_ref` is added.
- New `POST` and `GET pulls-prefetch`, as above, with a parity row and goldens.
- `CHANGELOG.md` records the new fields and route.

## Implementation Plan

One phase, one pull request, in this order:

1. This spec.
2. Server: catalog `head_oid`; the record verdict and its envelope fields; the files
   head check; the governor; the background lane, store-turn priority, preemption, and
   promotion; their unit tests and `--api` goldens, measured against the fake `gh`.
3. Browser, on top of the presentation pull request: T0 on the PR page, T1 to T3 from
   the Pulls panel after each scan and each landing, the list revalidated on show,
   visibility, focus, online, and at the window as before, T5 through the existing
   staleness re-ask, “Checked” and “Fetched” ages, and the head-moved notice on Changes;
   a browserless behavior session.

The PR page sends no prefetch of its own: the request replaces the lane’s queue, so it
would drop the panel’s, and the changed-files list it would warm is the tree under the
panel’s row, which the panel already names.
While a lane it started works, the panel reads its report once a fast poll, and the row
whose record the lane is reading joins `refreshingRows`, so its title breathes as a core
batch’s rows do (the presentation pull request’s `.mb-refreshing`).

## Testing Strategy

- Unit tests: the record verdict table, the bounded scan grace, pending checks and the
  three cases `updated_at` misses, the checks-only read, due-ness of a changed record
  and its loop guard across publications, the files head rule and its fallback, the
  governor’s floor, expiry, and holds, caps and their reset, store-turn priority,
  preemption, promotion, and a forgotten attempt after preemption.
- `--api` goldens with the fake `gh`: rows with `head_oid`; a record current by the
  catalog, changed, head moved, and with pending checks; a files list current across a
  comment and stale after a push; and a prefetch run that refreshes, skips, and defers
  below the floor, with the `gh` calls each made.
- Measurement tests against the fake `gh`: requests per scan, per background record
  refresh and files list, the cost at the caps, and the time a foreground open waits
  while background work runs.
- Parity: rows for `pulls-prefetch` and the new fields in
  [Views, Models, and Routes](../../architecture/arch-views-models-routes.md);
  browserless sessions for the browser prefetch policy.

## Measurements

Filled in as each budget lands, beside its constant.

| Quantity | Value | How |
| --- | --- | --- |
| Catalog page with `headRefOid` | 64,410 bytes vs 58,811; cost 1 | `cli/cli`, 100 rows, 2026-11-11 |
| Account check | 1 core point | six `gh auth status`, `rate_limit` before and after |
| Delta scan with nothing new to page | 1 account check and 1 GraphQL page | `cli-github-pulls-prefetch.txt` |
| Background record refresh, cold or changed | 2 account checks and 6 REST reads (304s free) | the same transcript, pull requests 7, 9, and 10 |
| Checks-only refresh of an open pull request (T5) | 2 account checks and 3 conditional REST reads: the pull, its check runs, its status; no fetch | `test_a_checks_only_refresh_reads_the_pull_its_checks_and_its_status_alone`, the same transcript |
| First check run after its check suite was created | 1 to 2 s on three `cli/cli` heads | `check-suites` and `check-runs` of `e5137cb6`, `b557a232`, `38aef55a`, 2026-11-11; `NO_CHECKS_GRACE_S` is 300 s |
| Delta scan with nothing new, end to end | `gh auth status` 0.46–0.58 s, the page 0.48 s | gh 2.98.0 on `cli/cli`, 2026-11-11; `SCAN_GRACE_S` is 15 s |
| Files list from the store’s comparison | no `gh` request | the same transcript, pull requests 7 and 8 |
| Files list from GitHub | 1 account check, then a page and an account check per page | `cli-github-pull-files-refresh.txt` |
| `catalog_member` on every `GET pull` | median 1.09 ms, at most 1.94 ms (200 runs, load 23) | the fixture’s 102-row catalog |
| A reader’s refresh behind a running prefetch | about what the same refresh takes alone: 0.49–0.56 s behind, 0.51–0.53 s alone (3 back-to-back pairs, load 16–17); 4.61–4.71 s without preemption (3 runs) | `test_a_readers_refresh_is_never_queued_behind_a_prefetch`, 2 s per prefetch request; alone is the same sequence, 10 then 9, with no prefetch |
| A polled page’s bytes a minute, one scan a minute | none (two 304s, the verdict in `x-metabrowser-verified`), against 3,836 with the verdict’s time in the entity tag | `test_a_catalog_scan_does_not_send_a_polled_record_again`, pull request 8’s 3,834-byte envelope; `served_pull.py` measures a 295 KB record (pallets/click#3030) |

## Risks

- `updated_at` misses checks, statuses, and `mergeable`; a visible open pull request
  reads them on their own once a window, so a closed one, or an open one no page shows,
  can hold settled checks until it is opened.
- The catalog may be old or another reader’s; the clock remains the fallback.
- The rate budget is shared with other clients; the floor keeps a reserve, and holds
  stop everything.
- Cancelling a background job wastes up to one refresh’s requests.

## References

- [Watching pull requests](plan-2026-11-06-pr-watch-and-reconnect.md)
- [The Pulls tab](plan-2026-10-01-github-pulls-tab.md)
- [Review mirror and checkout](plan-2026-11-02-pr-review-mirror-and-checkout.md)
- [Repository sources and provider mirrors](../../architecture/arch-repository-sources-and-provider-mirrors.md)
- [Reviewing pull requests](../../../reviewing-pull-requests.md)
- [GitHub REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
