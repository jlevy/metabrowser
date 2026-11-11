# Plan for Event-Based Pull-Request Freshness and Budgeted Prefetch

**Status.** Draft. This is the second pull request of the spinner-free refresh stack
(epic `mb-c93s`, bead `mb-wlx0`), based on the presentation pull request (`mb-wl9x`,
branch `claude/pr-refresh-without-spinners`). One GraphQL query per record refresh is a
later, separate change (`mb-xhtc`) and is out of scope.

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

| Catalog | Row | Result | `verified_by` | `verified_at` |
| --- | --- | --- | --- | --- |
| usable, any age | `updated_at` newer than the record’s `pull.updated_at` | `stale`: changed on GitHub; `head_moved` when the row’s `head_oid` differs from the record’s head | `fetch` | the record’s `fetched_at` |
| usable, scan within the window | not newer, and no pending checks | `current` | `catalog` | the newer of the scan’s `fetched_at` and the record’s |
| otherwise | — | the 60-second clock, as before | `fetch` | the record’s `fetched_at` |

A record written with no store stays stale on a server that has one, as before.

**Checks keep their own age.** `updated_at` does not move when a check run, a commit
status, or `mergeable` changes.
An open pull request whose record has a check run not `completed`, a combined status
`pending` with contexts, or `mergeable: unknown` has `checks_pending: true`, and the
catalog does not vouch for it: it ages by its own fetch, so a visible page refreshes it
once a window, with ETags, until its checks settle.
Its age is `fetched_at`, which the page shows as such.

**When the automatic refresh is due.** A request that is not a reader’s own action
refreshes a record that is:

- *changed*: due when no attempt was made since the catalog publication that showed the
  change (the checkpoint’s `count_at`), and otherwise once a window; a rate-limit hold
  still holds. So a pushed head is refreshed at once, and a REST answer that lags the
  catalog cannot loop.
- *current*: not due.
- *unverified*: the existing clock and attempt-window rules.

`ServedPull` keeps the newest verdict the routes computed (`verified_at`, the change’s
publication time), so the attended pull request’s share of a mirror’s `stale` follows
the same rule from memory.

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
| T0 | Catalog delta scan | Pulls panel and PR page on start, show, visibility, focus, online, page show, and at `fetched_at` + 60 s | the window passed | one per window: at most 60 an hour | 1 account check, plus 1 GraphQL point per page |
| T1 | Changed records this server recently served | the panel, after a scan publishes | catalog says changed | shares T2’s caps | at most 8 |
| T2 | The anchored row, its J/K neighbours, the top open PRs, the visible rows | the panel, after a walk settles | missing, or changed | 8 per catalog revision, 40 an hour, T1 and T2 together | at most 8 |
| T3 | Changed-files lists of the selected and T2 pull requests | the panel and PR page | missing, incomplete, or head or base moved | 20 an hour | 1 account check, then a page and an account check per page: 3 for one page |
| T4 | Changes | the existing idle prefetch only | — | — | — |
| T5 | Pending checks | the visible PR page | the record’s own window | foreground: visible page only | at most 8 |

A record refresh costs at most 8 core points: two account checks, the pull, and five
parts of one page each; a `304` is free, an account check is not.
At the caps T1 to T3 spend at most 40 × 8 + 20 × 3 = 380 core points an hour, 7.6% of a
5,000-point limit, and T0 at most 60 core and 60 GraphQL points.
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

Each server keeps one lane per repository, a coordinator job that runs one item at a
time. Before each item, off the event loop, it reads again whether the item is due, then
whether the governor admits it and the caps have room.
A record item is due when it is missing (a named number only) or changed; a files item
when the files route would start an automatic refresh.
An item another process has refreshed meanwhile is no longer due, because the record and
the list on disk are what is read.

The lane stops, dropping the rest of its queue, when the governor refuses, a cap is
reached, or a reader’s pull-request job of the repository is queued or running.
The page asks again later.
A job is started under the item’s ordinary key, so a reader’s request for the same pull
request joins it.

`GET /api/plugin/github/pulls-prefetch` reports the lane from memory: the running item,
the queue, the caps and their use (`scan`, the catalog revision the per-scan count
belongs to), the governor’s observations and verdict, and the outcomes of the last 16
items. The `POST` answers `202` with `prefetch: "started"` or `"joined"` and that route
as its `status_route`, or `200` with `"not_due"` (nothing named) or `"deferred"` and a
`reason`, `below_floor` or `rate_hold`, when the governor admits nothing.
An item the lane does not run says why in the report: `skipped:current`,
`skipped:unverified`, `skipped:not_cached`, or `skipped:not_due`, or the stop,
`deferred:` and one of `below_floor`, `rate_hold`, `hourly_cap`, `scan_cap`, or
`foreground_busy`; one a reader preempted is `preempted`. A one-shot `--api` waits for
the lane and prints that report.

### The Rate-Limit Governor

`gh.py` passes the rate-limit headers of every response it parses, including refusals,
to `gh_budget.py`, which keeps the newest observation per resource for the process:
limit, remaining, and reset time.
An observation expires at its reset.
A `rate_limited` failure holds every resource until its `reset_at`, or for a window when
GitHub gave none.

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
The caps and the governor’s observations are per process; the floor is read from
GitHub’s account-wide `remaining`, so several servers stop together.

## API Changes

- `GET pulls`: each row adds `head_oid`.
- `GET pull`: adds `verified_at`, `verified_by` (`catalog`, `fetch`, or `null` with no
  record), `head_moved`, and `checks_pending`. All four are in its entity tag.
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
3. Browser, on top of the presentation pull request: T0 on the PR page, T2 and T3 from
   the Pulls panel and the PR page, the list revalidated on show, visibility, focus,
   online, and at the window, T5 through the existing staleness re-ask, “Checked” and
   “Fetched” ages, and the head-moved notice on Changes; browserless sessions.

## Testing Strategy

- Unit tests: the record verdict table, pending checks, due-ness of a changed record and
  its loop guard, the files head rule and its fallback, the governor’s floor, expiry,
  and holds, caps and their reset, store-turn priority, preemption, promotion, and a
  forgotten attempt after preemption.
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
| Files list from the store’s comparison | no `gh` request | the same transcript, pull requests 7 and 8 |
| Files list from GitHub | 1 account check, then a page and an account check per page | `cli-github-pull-files-refresh.txt` |
| `catalog_member` on every `GET pull` | median 1.09 ms, at most 1.94 ms (200 runs, load 23) | the fixture’s 102-row catalog |
| A reader’s refresh behind a running prefetch | 0.46–0.47 s, against 0.63–0.72 s alone (4 runs); 4.61–4.71 s without preemption (3 runs) | `test_a_readers_refresh_is_never_queued_behind_a_prefetch`, 2 s per prefetch request, load 16–23 |

## Risks

- `updated_at` misses checks, statuses, and `mergeable`; pending checks fall back to the
  clock, and settled ones show their own age.
- The catalog may be old or another reader’s; the clock remains the fallback.
- The rate budget is shared with other clients; the floor keeps a reserve, and holds
  stop everything.
- Cancelling a background job wastes up to one refresh’s requests.
- `verified_at` changes with every scan, so a polled page receives its record again
  about once a window instead of `304`; the browser phase measures that parse cost.

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
