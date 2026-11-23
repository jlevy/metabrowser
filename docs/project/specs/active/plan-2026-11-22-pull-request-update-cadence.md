# Plan: Pull Request Update Cadence and GitHub Budget

**Date:** 2026-11-22

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Draft, for review.
Bead `mb-sjgl`.

## Overview

A merge on github.com should show on an open pull request page within seconds.
On 2026-11-22 it took 48 s: fdu #214 merged at 19:29:37 and its page showed the merge at
19:30:25. Nothing was broken.
The page reads the server every `SLOW_POLL_MS` (`pull-page.js`), and the server reads
GitHub again only once the record is older than `FRESHNESS_WINDOW_S`
(`mirror_refresh.py`), so a change waits for both.
The worst case is about 90 s.

This plan sets one policy for every way a pull request view gets fresh data.
What the reader is looking at is checked for changes every few seconds.
Everything else the views show is refreshed in full once a minute or two.
All of it stays inside a share of the account’s GitHub budget that leaves room for the
reader’s other tools.

## Goals

- A change on GitHub to the pull request on screen (state, merge, title, body, labels,
  reviews, comments, head, base) shows within `ATTENDED_PROBE_S` plus one refresh.
- Check runs and statuses of an open pull request on screen show within `CHECKS_PROBE_S`
  plus one checks refresh while they run.
- A change to any pull request in a visible Pulls list shows within `LIST_PROBE_S` plus
  one catalog scan.
- Everything a visible view shows is read in full at least every `FULL_REFRESH_S`, so
  anything change detection cannot see (an edited comment, a reaction, a mergeability
  recomputation) is at most that late.
- Nothing recurring that spends GitHub rate limit runs for a hidden page.
  Metabrowser’s own stores are kept current whatever is visible, since fetching into
  them spends none (see [Metabrowser’s Own Stores](#metabrowsers-own-stores)).
- An idle visible page costs almost no GitHub rate limit: change detection uses
  conditional requests, which GitHub does not count when it answers `304`. The pull
  request’s probe reads its issue, whose answer changes only when the pull request does
  (see [Budget](#budget)).
- Background work yields to visible work and stops before the account’s budget runs low,
  as `BACKGROUND_FLOOR` already does.
  A change found on the page on screen is still read below the floor.

## Non-Goals

- Webhooks or a GitHub App.
  A local tool has no public endpoint to receive them, and `gh` already holds the
  reader’s credentials.
- GitHub’s Events API. Its documentation says events can be delayed from 30 s to 6 h,
  and it asks clients to poll no faster than its `X-Poll-Interval` (60 s).
- A push channel from server to page for pull requests.
  The page’s probe answer already says whether a refresh started (see
  [Design](#design)).
- Issues, which have no catalog yet.

## Background

### What GitHub Charges For

Measured 2026-11-22 with gh 2.98.0 against `api.github.com`, reading `used` from
`GET /rate_limit` (which is free) immediately before and after each call.
Other clients spend from the same account at the same time, so each call was paired with
an idle interval of the same length.

| Call | Cost in `core` | Latency |
| --- | --- | --- |
| `gh api repos/o/r/pulls/N` with `If-None-Match` answered `304` | 0 in every trial whose idle pair was 0 (5 of 6; the sixth idle pair also moved) | 0.56 to 0.96 s, five calls |
| `gh api repos/o/r/pulls/N`, `200` | 1 | about 0.7 s |
| `gh auth status --active --hostname github.com --json hosts` | 1 in 3 of 3 trials | about 0.75 s |

GitHub’s documentation agrees on the first row: a conditional request answered `304`
does not count against the primary rate limit.
The last row matters because `refresh_pull_request` checks the account twice per refresh
(`pulls.py`), and from 19:00 to 20:00 UTC the six Metabrowser servers on this account
ran `gh auth status` 235 times.

GraphQL has no conditional requests, and every query costs at least one point.

### How Much Budget Is Metabrowser’s

The budget belongs to the account, not to Metabrowser (`gh_budget.py` says the same).
From 19:00 to 20:00 UTC on 2026-11-22, the six Metabrowser servers’ event logs
(`~/.local/state/metabrowser/events/`) record 360 REST calls, 235 account checks, and 62
GraphQL queries. Over the same hour the account spent about 1,500 `core` calls of its
5,000, so most of the budget went to other clients: coding agents and CI watchers using
the same `gh` login.
GraphQL had used 28 of 5,000 points.

So REST is the scarce resource, and Metabrowser should spend it only on what the reader
sees or will see next.

### What One Refresh Costs Today

Subprocesses under each job’s span in the same event logs (2026-11-21 and 2026-11-22):

| Job | `gh` per run | `core` spent when every read answers `304` | Git |
| --- | --- | --- | --- |
| Pull request record (`_pull_job`) | 6 `gh api` and 2 `gh auth` | 2 | A fetch of `refs/pull/<n>/head` and 10 to 15 local commands |
| The same, `checks_only` | 3 `gh api` and 2 `gh auth` | 2 | Local commands only |
| Catalog scan (`pull_list_route._run_refresh`) | 1 GraphQL and 1 `gh auth` | 1, plus at least 1 GraphQL point | None |
| Changed files (`_run_files_refresh`) | 1 `gh api` and 2 `gh auth` | 2 | None, or local diff when cached |
| Mirror (`_refresh_job`) | None | 0 | `ls-remote` and a fetch |

The account checks are what an unchanged refresh pays for.
A conditional `gh api user` answered `304` in 4 of 4 trials and reports the login of the
token `gh` uses, which is what the check needs to know.
It cost 0 in 3 of them; the fourth moved `used` by 1 while its idle pair did not, which
another client can explain but this measurement cannot rule out.

### How Each View Is Updated Today

This section describes the code at `0047ed0ab`, the commit this plan was written
against; the constants it names hold the current values.
No server timer starts GitHub work: every automatic read starts from a visible page’s
request, except a stale mirror’s fetch at server startup.
Each poller stops when `document.visibilityState` is not `visible`.

| Path | What asks, and how often | Server gate | GitHub per run |
| --- | --- | --- | --- |
| Mirror fetch | Status poll every 30 s; one ask per visible period when stale | `FRESHNESS_WINDOW_S`; goes first at the store | None; `ls-remote` and a fetch |
| Pull request record | Page poll every 30 s; an ask when the envelope says `stale`, at most once per `fresh_for_s` | `ServedPull.is_stale`; `MAX_PULL_JOBS`; store turn; network slot | 2 account checks, the pull, five parts, a head fetch |
| Record, `checks_only` | The same ask, when the catalog’s verdict is `checks` | The same, once a window | 2 account checks, the pull, check runs, status |
| Catalog delta scan | Pulls poll every 30 s, an ask once per 60 s; the page’s `catalogScanDue` | `refresh_is_due`, 60 s; no budget check | 1 account check, 1 GraphQL page per 100 changed rows |
| Catalog backfill | The same job, after the reader’s prefix | `gh_budget.admission(("graphql",))` per page | 1 GraphQL page per 100 rows |
| Cores | Visible rows, then a background walk, batches of 8 | Visible preempts background; no budget check | 1 GraphQL per batch |
| Changed files | Expanded tree, an ask once per 60 s, and at once when the head moves | Head and base, then 60 s | Local diff, or 2 or more account checks and a page per 100 files |
| Stacks | Shared poll every 30 s, an ask once per 300 s | `STACK_FRESHNESS_S`; no budget check | 2 account checks, up to 10 pages |
| Labels | Once per page, when a label has no color | `LABEL_FRESHNESS_S`; no budget check | 2 account checks, up to 50 pages; 29 pages of `304` took 14 to 16 s |
| Timeline | Once per record revision on Conversation | A sidecar by discussion revision; no budget check | Up to 2 GraphQL pages |
| Prefetch | Once per published scan, and file asks after a dwell | `gh_budget.admission(("core",))`; 40 records and 100 lists an hour | As a record refresh or a files refresh |

Three things in that table explain the 48 s and shape this plan:

- **The page throttles itself.** The server makes a record due at once when the catalog
  reports a change no attempt has seen (`ServedPull.is_stale`), but the page asks again
  only once `fresh_for_s` has passed since its last automatic ask (`staleRefreshDue` in
  `pull-page.js`). A merge just after an ask waits out the window.
- **Staleness is noticed only at a poll.** The page checks whether to ask only after a
  read, and it reads every 30 s.
- **Only the backfill and prefetch ask the budget.** The cores walk, stacks, labels, and
  the timeline run without `gh_budget.admission`, and the budget is known only from the
  last response’s headers.

### How Soon GitHub Reports a Change

A script read jlevy/metabrowser’s most recently updated pull request
(`pulls?state=all&sort=updated&direction=desc&per_page=1`) every 3 s with its last ETag,
from 20:06 to 20:31 UTC on 2026-11-22, and logged each `200` against the row’s
`updated_at`. Over nine changes to four pull requests the probe saw the new ETag 1.3 to
14.2 s after `updated_at`, with a median of 3.4 s and two changes past 10 s, so GitHub’s
ETags usually move within a probe interval of a change.
Twice, at 20:11:04 and 20:11:23, the ETag changed while the first row’s number and
`updated_at` did not.
Both were very likely pushes: a pull request’s REST representation embeds its base and
head repository objects, whose `pushed_at` moves on every push to any branch.
Review A of #696 read one unchanged pull request three times across pushes and got three
`200`s whose bodies differed only in `pushed_at`. So a `200` is a hint, not proof: the
design compares the pull request before starting a full read.

The issue representation of a pull request, `repos/o/r/issues/<n>`, embeds no
repository. Bead `mb-2ppr` measured both on 2026-11-23, from 01:47 to 02:32 UTC with gh
2.98.0: conditional reads of each representation of ten open pull requests every 15 to
20 s, six in NixOS/nixpkgs, two in jlevy/metabrowser, and one each in pytorch/pytorch
and rust-lang/rust, 661 rounds in all.

- The pull answered `200` with its `updated_at` unchanged 90 times.
  In the bodies kept, what differed was the base repository’s `open_issues_count`, which
  moves when any issue or pull request opens or closes, its `pushed_at`, and the pull’s
  `mergeable` as GitHub recomputed it.
  So more than pushes moves a pull’s ETag, and one of those moves is something the page
  shows: `mergeable`, which the issue does not carry.
- The issue answered `304` in all 90 of those rounds.
- The issue answered `200` twice, each in the round the pull’s `updated_at` moved:
  labels a bot added, seen 19 s later, and a force-push of the head, seen 10 s later.
- Of ten recently updated nixpkgs pull requests, the issue’s `updated_at` was the time
  of a merge on four, of a force-push on one, and of a label on two.
  The first page of the other three’s timelines did not say what had moved it.

`PROBE_RESOURCE` in `pulls.py` records the same numbers beside the path.

One conditional `gh api` used 0.06 s of CPU and 45 MB of memory for 0.6 s (three runs,
load average 295).

## Design

### Three Kinds of Read

Every automatic read of GitHub is one of three kinds, and each has its own cadence.

1. **A probe** asks whether something changed.
   It is one conditional REST request carrying the newest ETag the probe saw for that
   path, kept apart from the record’s own.
   A `304` costs nothing and changes nothing.
   A `200` costs one call; when its `updated_at` is not the record’s (for the list: the
   first row’s number and `updated_at`), it marks the record changed and the matching
   full read starts at once.
   Otherwise it keeps the new ETag for the next probe and leaves the record alone.
   A pull request’s probe keeps what it saw of the issue, its `updated_at` and ETag,
   across records, so a `304` still says which `updated_at` GitHub has.
   A full read that leaves the record behind the change a probe saw, as when the pull’s
   answer lags its issue’s, is tried again once a window, not on every probe.
   A record marked changed is not probed again until a full read of it has been tried,
   and a failed one holds probes for a freshness window, so a full read that cannot run
   does not turn every probe into a paid `200`. A probe needs no account check: it
   publishes nothing, and the full read it starts checks the account as it does today.
2. **A full read** is what runs today: the record refresh, the catalog scan, the files
   refresh, stacks, and labels.
   It runs when a probe saw a change, when a reader asks, and otherwise once every
   `FULL_REFRESH_S` for what is visible.
3. **Background preparation** is the prefetch of what the reader may open next.
   It is unchanged: it runs only while the account is above `BACKGROUND_FLOOR` and
   yields to the other two.

### Cadence by What Is Visible

| What | Probe | Probe cadence | Full read when nothing changed |
| --- | --- | --- | --- |
| The pull request on a visible page | `GET repos/o/r/issues/<n>` with the ETag the last probe saw | `ATTENDED_PROBE_S` | Record, every `FULL_REFRESH_S` |
| Its checks, while open and `checks_pending` or inside `NO_CHECKS_GRACE_S` | First page of `commits/<head>/check-runs` and `commits/<head>/status`, with the record’s ETags | `CHECKS_PROBE_S` | `checks_only` record refresh, every `FULL_REFRESH_S` |
| A visible Pulls list, or the repository of a visible page | `GET repos/o/r/issues?state=all&sort=updated&direction=desc&per_page=1` with the last answer’s ETag (as built; proposed as the `pulls` page, see [Server Changes](#server-changes)) | `LIST_PROBE_S` | Catalog delta scan, every `FULL_REFRESH_S` |
| Its stacks | None | — | Every `FULL_REFRESH_S` |
| Its changed files | None; the list follows the head and base the record and the catalog name | — | Whenever the head or base moves. A list no catalog row vouches for, every `FULL_REFRESH_S`; a vouched one is not read again on a clock (decided 2026-11-23) |
| Its labels | None | — | `LABEL_FRESHNESS_S`, as today: a full read of a large label set is 29 or more `gh` processes, and only chip colors depend on it |
| Its timeline and cores | None; keyed by the record’s discussion revision and the catalog | — | When those change |
| Anything on a hidden page | None | — | None; becoming visible probes at once |

The list probe works because `sort=updated` puts the most recently changed pull request
first, so its one-row page changes, and its ETag with it, whenever any pull request’s
`updated_at` moves or a new one appears.
The pull request probe covers what moves `updated_at` on one pull request: state, merge,
title, body, labels, new comments and reviews, and pushes.
A later edit of a review comment does not move it (review A of #726). `mergeable` does
not move `updated_at` either, and the issue does not carry it.
GitHub computes it after the read that first asks, so a full read often stores
`unknown`: all 12 open nixpkgs pull requests read cold on 2026-11-23 answered `null`,
and all 12 an answer 3 to 4 s later.
So while an open record holds `unknown`, the probe also asks the pull itself, for
`MERGEABLE_SETTLE_S` from the first probe that found that head’s mergeability unknown,
and an answer starts a read of the checks alone, below the floor too.
Past that time the pull is asked no more and no probe vouches for the record, so the
window’s read asks again above the floor.
Below it nothing reads the record, the envelope turns stale, and the page asks once a
window, so until the budget is back it says unknown and shows a change up to a window
late. A wait that ended unanswered is renewed for a record read after it ended, at most
once a `FULL_REFRESH_S`, and a probe that fails does not spend it (review B2 of #726). A
mergeability GitHub recomputes for a record that holds an answer, as when its base
moves, shows at the next `FULL_REFRESH_S` read.
Check runs and statuses are not in the pull request at all, which is why checks have
their own probe and `pull_freshness.py` has its `checks` verdict.

Proposed values, each to be set by measurement beside its constant:

- `ATTENDED_PROBE_S = 5.0`. Once GitHub reports a change (its ETag moves), the page
  shows it after half a probe interval on average (2.5 s), one probe (0.6 to 1.0 s), one
  record refresh (median 5.2 s, as the note on `MAX_PULL_JOBS` in `mirror_refresh.py`
  records), and half a fast poll (`FAST_POLL_MS`): a median of about 9 s, plus any wait
  for the store turn. GitHub’s own lag comes before that (see
  [How Soon GitHub Reports a Change](#how-soon-github-reports-a-change)). That is 720
  probes an hour per visible page, free while their ETag holds, at one `gh` process
  each.
- `CHECKS_PROBE_S = 10.0`. While CI runs, check runs change every few seconds, so most
  checks probes find a change.
  Each costs the probe’s `200`s and the `checks_only` refresh’s `200`s for the same
  paths, 2 to 4 `core`, so up to six a minute cost 12 to 24 `core` a minute, 120 to 240
  for a ten-minute run.
- `LIST_PROBE_S = 10.0`. The list’s scan costs a GraphQL point and an account check, so
  the list can afford a slower probe than the page.
- `FULL_REFRESH_S = 90.0`, inside the “every minute or two” the owner asked for.
  With conditional reads and a conditional account check, an unchanged full record
  refresh costs about 0 `core` between pushes, so this bounds work and latency for what
  probes cannot see more than rate limit.

### Priority

From first to last:

1. A reader’s own action (Retry, Reload, Fetch), as today: never held by the floor, only
   by a rate-limit hold.
2. Probes and the full reads they start, for the attended pull request and then the
   visible list. Probes do not take a turn at the store or one of
   `MAX_CONCURRENT_REFRESHES`’ network slots: they run no Git and end within a second,
   and a probe queued behind a record refresh would defeat its purpose.
   Each key (one number, or one repository’s list) has one probe in flight at a time,
   and `ATTENDED_PROBE_S` or `LIST_PROBE_S` is the least time between two, however many
   tabs ask. A per-server cap on probes in flight bounds the number of keys, since each
   probe is a `gh` process (bead `mb-et0k`); an ask past the cap answers `not_due`, and
   the page asks again at its next interval.
   A full read a probe starts is not held by `BACKGROUND_FLOOR`: the floor is a reserve
   for the reader, and this is the page the reader is looking at.
   The rate-limit hold and the self-ceiling still hold it.
3. The `FULL_REFRESH_S` reads of what is visible, admitted by `gh_budget.admission` as
   background work is.
4. Background preparation, as today.

### Budget

The account’s budget is shared with the reader’s other tools, so the plan keeps two
guards and adds one:

- `BACKGROUND_FLOOR` (kept): below it, the `FULL_REFRESH_S` reads and preparation stop.
  Probes keep running, and a change one finds on the attended pull request or the
  visible list still starts its full read, as [Priority](#priority) says (the owner’s
  rule, 2026-11-22). Built for the pull request on screen: `ServedPull.below_floor`
  holds the reads its clock alone asks for, and the floor’s sizing comment and the
  docstring of `gh_budget.py` say what goes below it.
  While the floor holds the full read, an unchanged probe keeps the record current in
  the envelope, since the page asks every `probe_every_s` only for a current record.
- The rate-limit hold (kept): nothing automatic runs before `reset_at`.
- **Admission everywhere** (new): the cores walk, stacks, labels, and the timeline ask
  `gh_budget.admission` before automatic work, as the backfill and prefetch already do.
  A reader’s own action still never asks.
- **Probes that pay only for the pull request’s own changes** (built, Phase 1): a probe
  is free only while its ETag holds, and a pull’s ETag moves with its whole repository
  (see [How Soon GitHub Reports a Change](#how-soon-github-reports-a-change)). So the
  pull request’s probe reads its issue, `pulls.probe_path`, whose ETag held through
  every such move measured.
  The bound first proposed here, a probe interval that doubles after `200`s that changed
  nothing (bead `mb-y7ut`), is not built: with the issue such a `200` is a reaction or
  the like, not every push.
  What a probe saw of the issue is kept in memory, so the first probe of a number in a
  process is one paid read, where the pull’s probe sent the record’s own ETag: one
  `core` per number per server run, and one per one-shot `metab --api` automatic ask.
  Keeping it on disk would need a new file beside the record, with its transcript and
  its place in the cache’s clearing, or one more `gh` process in every full read, and
  neither is worth one call a run (review A2 of #726). The list probe of Phase 2 reads a
  pull’s row, which embeds the same repository objects, so it needs its own measurement,
  and that bound if it pays per push.
- **A self-ceiling** (new), `AUTOMATIC_CORE_PER_HOUR`, in `gh_budget.py`: the `core`
  this process’s automatic work may spend in a rolling hour, counted from what the
  process spends itself, which it knows exactly: one `core` for each REST answer that is
  not `304`, and each GraphQL query’s reported cost.
  `x-ratelimit-used` cannot count it, because it is the account’s counter: two of one
  process’s responses 204 s apart differed by 208 calls, one of them its own.
  Past the ceiling, probes slow to `FULL_REFRESH_S` and full reads to five minutes until
  the hour rolls. The ceiling is per process, and six servers ran on this account in
  [Background](#how-much-budget-is-metabrowsers), so the proposal is sized for six: 300
  a server, at most 1,800 of the account’s 5,000 if all six reach it.
- **A share of the ceiling for speculative work** (new, review A1 of #737),
  `SPECULATIVE_CORE_PER_HOUR` in `gh_budget.py`: what work nobody is looking at may
  spend of the ceiling in a rolling hour.
  That work is the prefetch of records and files lists, the catalog’s backfill past
  every reader’s prefix, the cores walk past the rows on screen, and the label set’s
  periodic read. It runs inside `gh_budget.speculative`, so what it spends counts toward
  the share as well as the ceiling, and admission refuses it once the share is spent.
  With one counter for both, the prefetch’s own caps allowed more than the ceiling by
  themselves, so it could spend the whole hour, and the page on screen then paid with
  slowed probes, held cores, and a refused timeline.
  What is on screen is never refused for the share, so it keeps the rest of the ceiling,
  as the owner’s rule asks: what is on screen updates within seconds, and everything
  else every minute or two, inside the rate limit.
  The prefetch’s `RECORDS_PER_HOUR` and `FILES_PER_HOUR` are priced to fit the share,
  with the arithmetic beside them in `pull_prefetch.py`. Neither number has been
  measured against a real session: `GET pulls-prefetch` reports both and what the hour
  has used of each under `governor.ceiling`.

GitHub’s secondary limits count every request, `304`s included: at most 100 in flight,
and 900 points a minute for each REST endpoint, a `GET` being one point.
A visible page probes its pull request 12 times a minute and its checks up to 12 more,
so one endpoint would need more than 35 visible pages on one account to near its limit,
and the per-server probe cap bounds requests in flight.

Steady-state cost for one visible page with nothing changing on GitHub, from the
measurements above: probes 0 while the pull request does not change, whatever is pushed
to its repository, after one paid read of the issue for each pull request a process
probes; full reads about 0 once the account check is conditional; and 40 record
refreshes and 40 catalog scans an hour, at most 40 GraphQL points.
Mergeability is the exception.
Where the base moves often enough that each full read stores `unknown`, the probe that
sees GitHub answer is a paid `200`, and so is the pull in the read of the checks it
starts: about two `core` per `FULL_REFRESH_S`, 80 an hour for one visible page, and
spent below the floor too (review B4 of #726). Today the same page costs about 3 `core`
a minute in account checks alone: two per record refresh and one per catalog scan, each
about once a minute.

### Server Changes

- **`gh_lists.py` and `gh.py`** (built): a conditional account check.
  `gh_lists.active_account` is `gh.gh_account`, which reads `gh api user` with the ETag
  of this process’s last answer for the host, treats `304` as “the same login”, and
  still names the account to `gh_budget.note_account`. `gh_api` admits `user` beside
  `repos/…` paths. The status route keeps `gh.gh_active_account` and `gh auth status`,
  which alone reports the token’s source and scopes; the account check asks it too when
  it finds no account, so the failure names what to do as before, and when GitHub cannot
  be reached, since gh names its saved account without the network.
  A `gh` too old for `auth status --json` now passes the account check, and only the
  status check reports it.
- **`served_pull.py`:** `ServedPull` keeps `probed_at`, when a probe last found the
  record unchanged, and `full_read_at`, when it was last read in full.
  `automatic_due` decides each automatic ask: a full read when the record is stale or
  its last full read is older than `FULL_REFRESH_S`, a probe when one is due
  (`probe_due`, no closer than `PROBE_FLOOR_S` to the last), and nothing otherwise.
  A probe that finds a change makes the record stale until an attempt starts after it,
  so the refresh starts at once and does not loop.
  The `POST` waits for the probe up to `PROBE_WAIT_S`. Built since: the probe reads the
  pull request’s issue (`probe_path` in `pulls.py`) and `ServedPull` keeps what it saw
  across records; `below_floor` holds the reads the clock alone asks for; and a probe is
  a coordinator job, at most `MAX_PROBES_IN_FLIGHT` of them in a server.
- **`pull_list_probe.py` and `pull_list_route.py`** (built): an automatic ask that finds
  nothing else due probes the list, and the catalog’s delta scan runs only when the
  probe found a pull request the catalog lacks, when the last scan is older than
  `FULL_REFRESH_S`, or when a reader asked.
  The probe asks the issues list,
  `issues?state=all&sort=updated&direction=desc&per_page=1`, not the pulls page this
  plan proposed: over 120 rounds on three repositories the pulls page answered `200` for
  an unmoved row 8 times and the issues page never, since an issue’s row embeds no
  repository. When an issue is the newest row the one-row pulls page is asked too, with
  its own ETag. The newest pull request is compared with the catalog’s row of the same
  number, not with the probe’s last answer, so a row costs one `200` however long its
  scan takes, and a row still missing after its scan (GraphQL behind REST) starts no
  second one. An unchanged list probe moves the probe’s `checked_at`, as an unchanged
  record probe moves `verified_at`, and `record_freshness` in `pull_freshness.py` takes
  it as the catalog’s age, so the catalog keeps vouching between scans; otherwise it
  would vouch for nothing in the last third of each `FULL_REFRESH_S`. A visible pull
  request page sends no ask of its own for the list: the server takes its automatic ask
  for the record as one for the repository’s list too (`attend_list`).
- **`pull_files_route.py`** (built): a files list is a function of the head and base it
  names, so one the catalog’s row or the record vouches for is read when either moves
  and never on a clock.
  Only a list nothing vouches for ages, by `FULL_REFRESH_S`. Ageing a vouched list would
  also unsettle the stack and row change lines, which read the same verdict, and spend
  the prefetch’s hourly lists.
- **The envelope:** `verified_by` gains `probe`, and `verified_at` moves with each
  unchanged probe, so the page’s age line says when GitHub last confirmed the record.
  `probe_every_s` gives the interval of the page’s asks; `fresh_for_s` still says how
  long a record is fresh without probes.
  The list envelope gains the same `probe_every_s`, and `checked_at`, when a list probe
  last found the catalog unchanged; its entity tag leaves `checked_at` out, so a poll of
  an unchanged list stays a `304`.

The routes are internal contracts and change in one commit with the page, the CLI, and
the transcripts, with no compatibility layer.

### Page Changes

- `pull-page.js`: while visible, the page asks every `probe_every_s` for a current
  record, and a window after its last ask for a stale one, so a record that goes stale
  when its full read comes due is asked for at once.
  An ask that starts nothing leaves the poll on its own interval, so the poll still
  reports a server that stops answering, and so does the failed ask.
  The server’s attempt rules stop a changed record from looping.
  It polls fast only while a refresh runs, as today.
  An unchanged probe is one `POST` answered without a job, local to the machine.
  While probes vouch for the record the page asks for no catalog scan: the scan would
  only vouch for what the probes already did.
  What else the scan fed, the stack the page shows and the list behind it, is kept by
  the list probe, which the server runs on the page’s own ask (see
  [Server Changes](#server-changes)).
- `pulls-panel.js` (built): while the tab is shown and visible it asks every
  `probe_every_s` of the list envelope, on a timer of its own, current or stale; an ask
  that could not be sent waits a whole interval.
  Its poll still asks for a stale list once a window, as before.
- Visibility, focus, and coming back online wake both at once, as they do now.

### Metabrowser’s Own Stores

The owner set the rule on 2026-11-22: a store Metabrowser keeps is fetched as often as
it usefully can, so what it shows is not out of date whenever that can be avoided.
A fetch into its own store is safe to repeat: it is atomic, it removes no commit, the
store is read-only to everything else, and a reader’s checkout is never written
([What Is Never Written](../../architecture/arch-open-modes.md#what-is-never-written)).
It spends no GitHub rate limit, since Git over HTTPS is not the REST or GraphQL API. So
the limits on how often are its process time and network, not a budget.

What a refresh costs when nothing changed, measured 2026-11-22 against the stores of
jlevy/metabrowser (469 refs) and bluesky-social/social-app (3,053 refs), three runs
each, at a load average of about 330:

| Step | Wall time | CPU | Peak memory |
| --- | --- | --- | --- |
| `ls-remote` of one branch | 1.0 to 1.9 s | 0.07 s | 12 MB |
| `ls-remote --symref HEAD`, the refresh’s first step | 1.0 to 1.7 s | 0.07 s | 12 MB |
| The fetch with the store’s refspecs (`--dry-run`) | 1.7 to 5.3 s | 0.2 to 0.6 s | 28 to 35 MB |

A probe of one branch costs about a tenth of a refresh’s CPU, so it is the probe that
runs often and the fetch that runs when the probe saw a move or the interval is up.
The first two rows are built
([Refresh Cadence](../../architecture/arch-mirror-acquisition-and-refresh.md#refresh-cadence)),
and each constant is in `mirror_refresh.py` beside the measurement that set it:

- **A visible page of a mirror on a branch:** the served branch is probed every
  `STORE_PROBE_S`, and the fetch starts at once when its tip moved.
  Everything is fetched every `FRESHNESS_WINDOW_S` while such a page is visible.
  Before this, a page asked for a fetch once each time it became visible, not once a
  window, so the plan’s “as today” was wrong and this is new.
- **A served store with no visible page:** fetched every `STORE_IDLE_REFRESH_S` while
  the server runs, as background work that yields to everything a reader waits on, so a
  page opened later starts at most that old and its first ask catches up.
  Before this, a hidden server never fetched.
- **A store beside a checkout** (not built): a repository folder shows its origin’s
  branches and tags as Metabrowser last fetched them into its own store, which borrows
  the checkout’s objects, and that store is fetched by the same rules; the checkout
  itself is still never fetched into
  ([Origin Branches in a Repository Folder](../../architecture/arch-open-modes.md#origin-branches-in-a-repository-folder)).
- **The guards:** one fetch per store at a time (its fetch lock), another process’s
  fetch followed rather than repeated, and a failed fetch or probe tried again only
  after a window. The server has no test for being offline, so that case is the last one:
  an origin it cannot reach is asked once a window by a visible page and once an idle
  interval otherwise, and each attempt fails at the name lookup.

### Alternatives Considered

- **Lower `FRESHNESS_WINDOW_S` and `SLOW_POLL_MS`.** Simple, but every check would be a
  full refresh: eight `gh` processes, a Git fetch, and 2 `core` in account checks, every
  few seconds. Probes give the same latency for one process and no budget.
- **A push channel from server to page.** `/api/events` carries file-system changes
  only. Pushing “record changed” would save the page’s local polls, which cost nothing
  that matters, and would not reduce GitHub traffic, which is the cost that matters.
- **GitHub’s Events API, or webhooks:** see [Non-Goals](#non-goals).

## Implementation Plan

Three phases. The first fixes what the reader saw; the second brings every other GitHub
view under the same policy; the third keeps Metabrowser’s own stores current.

### Phase 1: The Pull Request on Screen

Phase 1 lands in more than one pull request: the probes first, then the conditional
account check and the bounds on probes.

- [x] `ATTENDED_PROBE_S`, `CHECKS_PROBE_S`, `FULL_REFRESH_S`, and `PROBE_WAIT_S` in
  `served_pull.py`, each beside its measurement.
- [x] The pull request probe and the checks probe (`probe_pull_request` in `pulls.py`),
  run by `ServedPull.probe` outside the store turn and the network slots, with the field
  comparison that ignores an ETag-only change, `probed_at`, and `verified_by: probe`.
- [x] The envelope’s `probe_every_s`, the interval of the page’s asks, rather than
  `fresh_for_s`, which still says how long a record is fresh without probes.
- [x] The page’s ask scheduling in `pull-page.js`: a current record is asked for every
  `probe_every_s` while the page is visible, and a stale one a window after the last
  ask.
- [x] The architecture documents: Serving Pull Requests and Freshness Verdicts in
  `arch-github-pull-requests.md`, and Refresh Cadence in
  `arch-mirror-acquisition-and-refresh.md`.
- [x] A conditional account check in `gh_lists.active_account`, which every job’s
  account check uses (bead `mb-1bir`).
- [x] The `BACKGROUND_FLOOR` rule for probes (see [Priority](#priority)): below the
  floor, a change a probe finds on the page on screen still starts its full read, and
  the `FULL_REFRESH_S` reads stop (bead `mb-qngw`).
- [x] Probes that are not paid for per push (see [Budget](#budget)): the pull request’s
  probe reads its issue, measured under bead `mb-2ppr`, so the doubling interval of bead
  `mb-y7ut` is not built.
- [x] The pull itself asked while a record’s mergeability is unknown, bounded by
  `MERGEABLE_SETTLE_S` (review A1 of #726).
- [x] A per-server cap on probes in flight, `MAX_PROBES_IN_FLIGHT` in `served_pull.py`,
  and probes as coordinator jobs, which shutdown cancels (bead `mb-et0k`).

### Phase 2: Lists and Everything Else

- [x] The list probe, which gates the catalog’s delta scan, and `LIST_PROBE_S`
  (`pull_list_probe.py`), with the bound on paid probes for the list’s key
  (`MAX_PAID_PROBE_S`). A list probe counts toward the server’s `MAX_PROBES_IN_FLIGHT`
  with its pull requests’ probes, and is a coordinator job as theirs are.
- [x] `FULL_REFRESH_S` for the catalog scan, the files list, and stacks.
  The scan is due that often while list probes vouch (`scan_is_due`), and stacks are
  read again that long after a snapshot (`remaining_freshness` in `pull_stacks.py`). A
  files list ages by it only when no catalog row vouches for it: a list the row or the
  record vouches for is a function of the head and base it names, is read at once when
  either moves, and is not read again on a clock.
- [x] Budget admission for the cores walk, stacks, labels, and the timeline, and for the
  catalog’s periodic scan and a files list’s periodic read.
  A batch of cores the budget holds answers `held`. The floor holds only the background
  walk: cores for rows on screen are held by a rate-limit hold and the self-ceiling
  alone, by the owner’s floor rule.
  A held timeline answers `unavailable` and `retryable`. The scan a list probe’s change
  starts is not asked, as [Priority](#priority) says.
- [x] `AUTOMATIC_CORE_PER_HOUR` in `gh_budget.py`, counted by `gh_api` and `gh_graphql`
  as they answer; each query asks for `rateLimit { cost }`. A reader’s own action is
  told apart by the context its route starts the job in (`readers_own`), so a job a
  reader’s click only joins is still counted.
  `GET pulls-prefetch` reports the ceiling and the hour’s use.
  A job’s account check is a conditional `gh api user`, so it is counted as any answer
  is: nothing for a `304`, one for a `200`.
- [x] `SPECULATIVE_CORE_PER_HOUR`, speculative work’s share of that ceiling, with the
  prefetch’s caps priced to fit it (see [Budget](#budget)).

### Phase 3: Metabrowser’s Own Stores

- [x] A visible mirror page on a branch probes that branch’s tip every `STORE_PROBE_S`
  between fetches, so a followed branch follows a push within seconds rather than a
  freshness window and a poll later (bead `mb-6pzh`): `MirrorSession.page_ask`, the
  status’s `probe_every_s`, and the page’s own ask in `static/source-freshness.js`. Core
  stays provider-agnostic (`ls-remote` of the one ref).
- [ ] The GitHub plugin’s conditional read of the ref (`git/ref/heads/<branch>` with an
  ETag), if it measures cheaper than `ls-remote`. Not measured: it would spend a `core`
  call on every push, where `ls-remote` spends none.
- [x] A served store with no visible page is fetched every `STORE_IDLE_REFRESH_S` as
  background work (bead `mb-l89x`): `MirrorSession.run_idle_refresh`.
- [ ] A repository folder keeps a store beside its checkout and lists its origin’s
  branches and tags from it (bead `mb-ay84`); the design so far is in
  [Origin Branches in a Repository Folder](../../architecture/arch-open-modes.md#origin-branches-in-a-repository-folder).
- [ ] Both measured again on an idle machine.
  The constants were set from measurements at a load average near 300, recorded beside
  them; no idle machine was to hand.

## Testing Strategy

- **Server:** the fake `gh` the plugin’s server-flow tests put on `PATH` answers `304`,
  `200` with the same fields, and `200` with changed fields.
  Tests check that a probe starts a full read only for a real change, that a probe never
  runs an account check, that two tabs asking at once get one probe, that a hold stops
  probes, that below the floor a change a probe finds is still read while the
  `FULL_REFRESH_S` reads stop, and that a push which moves the pull’s ETag leaves the
  probe’s alone.
- **Goldens:** `--api` transcripts for `pull-refresh` answered by a probe (unchanged,
  changed, ETag-only), and the envelope’s `verified_by: probe`, as the parity registry
  requires.
- **Page:** the browserless session (`tests/dom/github-pull-page-session.js`) on a fake
  clock: an unchanged page asks every `ATTENDED_PROBE_S` and reads GitHub data only when
  a probe said so; a changed record is asked for at once; a hidden page asks nothing;
  becoming visible asks at once.
- **Live:** one real pull request page open in a browser, a change made on github.com,
  and the time from GitHub’s `updated_at` to the page’s paint, from the event log.
  Target: a median under 10 s from when GitHub’s ETag moves, with GitHub’s own lag
  reported beside it. Also one hour of a visible, unchanged page, with `core` spent read
  from `GET /rate_limit` before and after, against the steady-state cost above.

## Open Questions

- Is 5 s right for the page on screen, or should it be faster?
  Each probe is one `gh` process (0.06 s of CPU, 45 MB for 0.6 s). Below about 2 s,
  probes would overlap their own latency.
- Is 300 `core` an hour per server the right self-ceiling for automatic work, given how
  much of the account’s hour other tools use, and is a third of it the right share for
  speculative work? Neither has been measured: `governor.ceiling` in `GET pulls-prefetch`
  reports what an hour used, and a few real sessions’ readings should be recorded beside
  the constants. Should the servers of one home share a ceiling instead, through a file
  beside their event logs?
- Below the floor nothing automatic observes the GraphQL budget again: the catalog’s
  periodic scan was the only regular GraphQL read, and it now waits with the rest.
  The floor then lifts only at the budget’s reset, on a reader’s Reload, or when a list
  probe finds a change and its scan runs.
  Should one cheap GraphQL read be let through to observe it, say once a freshness
  window?
- A reader’s own action is told from automatic work by the context its route starts the
  job in (`gh_budget.readers_own`). A job a reader’s click only joins is still counted
  toward `AUTOMATIC_CORE_PER_HOUR`, and a backfill that runs on inside a Reload’s job is
  not. Is that attribution good enough, or should each job say what it is?
- The live test needs a real change on GitHub.
  A throwaway draft pull request in this repository, edited and closed by the test,
  would do; that publishes to GitHub, so it needs the owner’s go-ahead.

## References

- [Plan for Watching GitHub Pull Requests](../done/plan-2026-11-06-pr-watch-and-reconnect.md),
  which set today’s 30 s and 60 s cadences.
- [GitHub Pull Requests](../../architecture/arch-github-pull-requests.md) and
  [Mirror Acquisition and Refresh](../../architecture/arch-mirror-acquisition-and-refresh.md).
- GitHub’s REST documentation on
  [conditional requests](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api#use-conditional-requests)
  and
  [rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api).

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
