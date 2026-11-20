# Plan for a Structured Event Log

**Date:** 2026-11-19

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Phase 1 in implementation as a stack of pull requests; bead `mb-wr5e`. The
first pull request (the log, its server-side records, and `/api/event-log`) is written;
the rest of Phase 1 and Phase 2 are planned here.

## Overview

The owner asked, on 2026-11-19:

> “also I’m seeing cases where data like the PR diff summary are not loading after many
> seconds, is latency like this captured in our logs correctl so we can debug and
> identify when it happens always”

> “the goal would be to have a clean json log that we can browse in metabrowser itself
> in different ways, [with] a full ui based on the logs of metabrowser, but initially
> it’s okay if it’s an internal log to facilitate debugging.
> itshould be both.”

and later the same day:

> “also I am seeing “The last refresh failed: gh did not answer within 15 s” often” and
> “this should be captured and surfaced and easy to debug”

> “we should capture, log, and surface the underlying error e.g. network or github
> error”

This plan adds one structured log, JSON Lines in the user’s state directory, that
records every request, the background jobs that refresh and prepare what a page shows,
and every `git` and `gh` process a served Metabrowser runs to completion, with how long
each took and how it ended, and what the browser waited for.
A streaming `git` session (`spawn_git_process`) is not a span of its own in Phase 1; the
request that reads it is.
It is first an internal debugging log, read through a `metab` route, and then a log
Metabrowser browses in its own views.

## What Was Captured Before

A survey of `origin/main` at `2db4515f9`, and a reproduction against
jlevy/metabrowser#615 and #600 on 2026-11-19 while GitHub was intermittently unreachable
from this machine.

**How a pull request page’s Diff summary loads.** The row is filled twice.
A placeholder line comes from `GET /api/plugin/github/pull-files-summary`, read once at
mount from a cache the Pulls panel fills, with no retry and no error text.
The summary itself is drawn from `GET /api/plugin/github/pull-comparison`, which the
page asks for only once the pull request’s record names a comparison.
The page learns that by polling `GET /api/plugin/github/pull` every second while a
refresh runs (`POST /api/plugin/github/pull-refresh` starts it), and every 30 s
otherwise. The refresh is a background job (`RefreshCoordinator` in `mirror_refresh.py`)
that runs `gh` (`gh auth status`, then GraphQL and REST reads) and `git fetch`; the
comparison’s listing is a shared task (`ComparisonCache.manifest`) running `git`.
Neither job has a deadline of its own; each `gh` and `git` process does (15 s for
`gh auth status`, 30 s for `gh api`, 15 s for a store read, 900 s for a fetch).

**What the logs said.**

- A request slower than 2 s (`METABROWSER_SLOW_SERVER_MS`) wrote one stderr line, and
  `METABROWSER_REQUEST_LOG=verbose` one line per request.
  The app’s server logs held such lines for `pull-comparison` taking 2.5 to 5.4 s, all
  of it in the `git` phase.
- A background job was never timed.
  Its start, its duration, and its end were in no log; the coordinator logged only an
  exception.
- A `gh` process that timed out raised `GhError("gh did not answer within 15 s")` and
  logged nothing, not even at debug level.
  In the reproduction, the refresh of #615 ran 15 s and failed with no line in stderr at
  `--log-level debug`; the only trace was `last_refresh` in the record’s JSON, which the
  page shows as “The last refresh failed: gh did not answer within 15 s”. A
  `git ls-remote` that exceeded 30 s did log, at debug level.
- A job that never finished left no record at all.
- In the browser, `perf.js` recorded a fetch only when it settled, so a request that
  never answered left no sample; the Diff summary row pulsed “Loading the summary of
  changes” with no timeout, console message, or report to the server.

**Where the logs go in the macOS app.** The app runs one `metab` per folder and sends
its stderr to `~/Library/Logs/Metabrowser/<folder>-<8 hex>.log` (`ServerLog.swift`,
rotated at 5 MB with one previous file kept), which Console.app shows under Log Reports.
The app passes no `--log-level`, so only warnings and the slow-request lines reach it.
The browser’s console messages reach no file.

## Goals

- Always capture latency: every request, job, and `git` or `gh` process, with its
  duration on the monotonic clock, without an opt-in.
- Diagnose “never arrived”: work that started and has not ended is on record within
  seconds, with what started it.
- Capture the cause of a failed GitHub or network call, and surface it in the page in
  plain words with the detail one step away.
- One clean JSONL schema, versioned, readable by `metab`, and browsable in Metabrowser.
- Negligible cost per request, bounded disk, and no secrets.

## Non-Goals

- Replacing the stderr log.
  Its warnings stay as they are; the event log is beside it.
- Distributed tracing across machines, or exporting to a tracing service.
- Request bodies or responses in the log.
- A log of what the user browses for its own sake: the log is for diagnosing
  Metabrowser.

## Design

### Records

One JSON object per line.
Fields, in order (`EventLog.record` in `event_log.py`):

| Field | Meaning |
| --- | --- |
| `v` | Schema version, `1`. A reader skips a line of another version. |
| `ts` | When the line was written, UTC to the millisecond. |
| `event` | `start`, `end`, `open`, or `mark`. |
| `kind` | `request`, `job`, `subprocess`, `browser`, `lifecycle`, `loop`, or `probe`. |
| `name` | `GET /api/plugin/github/pull`, `mirror_refresh.MirrorSession._pull_job`, `gh auth`, `git fetch`. |
| `span`, `parent` | The span’s ID within its process, and the span current where it started. |
| `client` | The browser’s ID for the request it sent, where it sent one. |
| `dur_ms` | Monotonic duration; on an `open` record, the age so far. |
| `outcome` | `ok`, `failed`, `timeout`, `cancelled`, `abandoned`, or `never_completed`. |
| `pid` | The process that wrote it. |
| `attrs` | The kind’s own detail: status and phases, a job’s key and queue wait, a process’s command, deadline, exit, stderr tail, and where it stalled. |

A span writes an `end` record.
A job also writes a `start`, because when and from what it started matters most when it
never ends. A span still open 2 s after it began (`OPEN_AFTER_MS`, the slow-request
threshold) writes an `open` record, and another each time its age doubles, so a hung job
costs a handful of lines.
At shutdown, by a signal or gracefully, each open span ends `abandoned`. A watcher
thread also pings the event loop each second, and a turn the loop takes 2 s or more to
run is a `loop` span.

The `parent` chain is the correlation: a job started by a request names the request, and
a process the job ran names the job, through a context variable that tasks and threads
inherit. The browser’s side joins it through `client` (Phase 1, browser reports).

### Where the Log Lives

`$METABROWSER_STATE_DIR`, else `$XDG_STATE_HOME/metabrowser`, else
`~/.local/state/metabrowser`, then `events/` (`home.state_directory`): the XDG directory
for logs and history, which survives a restart, unlike `/tmp` (AGENTS.md, Durable
Storage), and which a cache clear does not touch.
The directory is `0700` and each file `0600`, through `metabrowser.home`. Each served
process writes its own segment, `events-<UTC start>-p<pid>-<NNN>.jsonl`, so servers
sharing the directory never interleave lines or race a rotation.
A one-shot command writes none; `METABROWSER_EVENT_LOG=0` turns it off, and the test
suite and goldens set that.

### Bounds

`MAX_FILE_BYTES` per segment, the size below which Metabrowser’s JSONL view parses a
file whole; `MAX_TOTAL_BYTES` for the directory, enforced by deleting the oldest
segments at every open and roll; `MAX_LINE_BYTES` per line.
Each constant records its measurement beside it in `event_log.py`: a pull request page
visit wrote 278 records, 72 KB, about 270 bytes a record, and the log adds about 23 µs
to a request.

### Privacy

The log is the user’s own and holds request paths and the folders they name.
It never holds a token: a `gh` command line keeps field and header names but not their
values (`gh.loggable_args`), a `git` command line drops its `-c` settings, and all
process text passes through `event_log.redact`, which removes GitHub tokens, URL
credentials, authorization values, and escape codes.

### Reading the Log

`GET /api/event-log` (`event_log_route.py`) answers where the log is, its bounds, its
segments, and one segment’s records filtered by `kind`, `outcome`, `event`, `name`,
`client`, `span` (a span and the spans it started), and `min_ms`, sorted by time or by
duration, with the spans this process has open now.
`metab ROOT --api /api/event-log?outcome=timeout,failed` reads it from a terminal
without a server, per the CLI parity rule, and `cli-api-event-log.tryscript.md` pins it.

### GitHub and Network Failures

Each failed `gh` or `git` network call keeps its cause.
One shared classifier, extended from the ones that exist (`GhFailureState` and
`_NETWORK_TEXT` in `gh.py`, `classify_remote_failure` in `cache/origin.py`, and the
app’s `GitHubFailure.swift`, which reads the server’s states), names it from what the
process reported: DNS failure, connection timed out or refused, TLS error, proxy error,
GitHub’s HTTP status (401 or 403 for sign-in, 403 or 429 for the rate limit with its
reset, 404, 5xx with GitHub’s message), gh not signed in, an exit with gh’s or Git’s own
error line, or a timeout with no answer.

A timeout with no answer runs a bounded connectivity probe, at most once a minute: DNS
for `api.github.com`, then a TCP connect to port 443, each with a short deadline and its
time recorded as a `probe` span.
It says whether GitHub was reachable from this machine when `gh` stalled, which a 15 s
deadline alone cannot.

The page’s failure line leads with the cause in plain words, such as “Couldn’t reach
GitHub from this machine: the connection timed out” or “GitHub answered 503: …”, says
how often it has happened in the last hour, and links to the records behind it through
`/api/event-log`.

**The 15 s deadline.** `GH_TIMEOUT_S` in `gh.py` bounds `gh auth status`, which a
refresh runs twice. Its comment says it bounds a hung gh, not a slow one; `gh_status.py`
measured the same command at 0.61 to 0.65 s at load average 116. So 15 s is about 23
times the slowest measured run, and the timeouts the owner saw were network stalls: a
measurement on this machine the same afternoon found a TCP connect to `api.github.com`
hanging for 20 s while other hosts answered in about 20 ms.
The deadline stays; the probe tells a stall from a slow gh.

### Browser Reports

`perf.js` gives each fetch an ID it sends as a request header, which the server records
as the request’s `client`. It reports to `POST /api/event-log/client` (bounded body,
rate-limited) a fetch slower than its slow threshold, a fetch still pending past it, and
named waits: a page marks what it is waiting for, such as a pull request’s Diff summary,
and the wait is reported when it is late, when it ends late, and as `never_completed`
when the page is hidden or left first, through `navigator.sendBeacon`. The server writes
each as a `browser` record.

## Implementation Plan

### Phase 1: An Internal Debugging Log

One stack of pull requests.

- [x] The log: spans, records, segments, rotation and pruning, the watcher and its
  event-loop ping, and the signal-handler close (`event_log.py`).
- [x] Records for every request (`_SlowRequestLogMiddleware`), every coordinator job and
  comparison listing, and every `git` and `gh` process, with the `gh` timeout’s stall
  point and stderr tail.
- [x] `GET /api/event-log` with its golden, parity row, and route map row; the location
  in `docs/realtime-debugging.md`; overhead and sizes measured beside the constants.
- [ ] The shared failure classifier, the connectivity probe, and the page’s failure line
  that leads with the cause, with stand-in `gh` and `git` for each class and a golden of
  recent failures with their causes.
- [ ] The browser reports and `POST /api/event-log/client`, the pull request page’s Diff
  summary wait, and a browserless test of the reporter.

### Phase 2: Metabrowser Browses Its Own Log

- [ ] A log view for the event schema, beside the agent-log and JSONL views, that the
  file kinds pick for an `events-*.jsonl` file.
- [ ] Views: by latency, by kind, slowest, errors, and a timeline that nests spans under
  their parents.
- [ ] A way to open the log from the app and the shell (a menu command or a link from
  the failure line), and a `metab` equivalent for each view’s query, with goldens.

## Testing Strategy

`tests/test_event_log.py` covers the records, each outcome, open records at the
threshold and each doubling, abandoned spans at shutdown, rotation and the directory’s
total, redaction, `gh` argument logging, a request’s span and the job it starts, a
refresh job that never ends, the comparison a Diff summary waits for, a `gh` stand-in
that never answers, and a failing `git`. `cli-api-event-log.tryscript.md` pins the route
on fixture segments that tell the stuck-page story.

## Open Questions

- Should the macOS app point the child’s state directory at
  `~/Library/Logs/Metabrowser/` so Console.app shows the event log beside the server
  log? Phase 1 keeps the XDG location for every platform.

## References

- [Real-Time Debugging](../../../realtime-debugging.md#event-log)
- [Parity Registry](../../architecture/arch-parity-registry.md)
- [Views, Models, and Routes](../../architecture/arch-views-models-routes.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
