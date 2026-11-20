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
A failure has two names.
Its *state* says what to do and stays as it was: `GhFailureState` in `gh.py`, and
`RemoteFailureState` in `cache/origin.py`, whose values the app’s `GitHubFailure.swift`
reads. Its *cause* says what happened, in one vocabulary both tools share (`CAUSES` in
`network_cause.py`): `dns_failed`, `connect_refused`, `connect_timeout`,
`network_unreachable`, `connect_failed`, `connection_reset`, `tls_failed`,
`proxy_auth_required`, `proxy_failed`, `stalled`, `no_answer`, `auth_refused`,
`forbidden`, `not_found`, `rate_limited`, `server_error`, and `not_signed_in`. One
classifier (`network_cause.classify`) reads it from Go’s errors, which `gh` prints, and
curl’s, which Git prints; `classify_remote_failure` now derives Git’s states from it,
and `gh.py`’s text tables are gone.
An HTTP answer’s status gives its cause directly.
The cause is an attribute of the failed process’s record and of the job or request that
asked, and the message leads with it.
The app reads only states and shows the server’s message as written, so it names the
cause with no change of its own.

`gh`’s, Git’s, and GitHub’s own error text are never shown, as before: they can carry
paths or private repository names.
The record keeps them, redacted: the process’s stderr tail, and GitHub’s `message` on a
5xx as `server_message`.

A `gh` that times out, or cannot connect, is followed by a connectivity probe
(`network_cause.probe`): DNS for `api.github.com`, then a TCP connect to each address it
returned (up to `PROBE_ADDRESSES`), through the proxy `gh` would use (`HTTPS_PROXY`,
less `NO_PROXY`), all within one `PROBE_TIMEOUT_S` deadline, at most once per
`PROBE_INTERVAL_S`, recorded as a `probe` span with every address and how its connection
ended.
It is best effort: anything it cannot do is logged and explains nothing, and never
replaces the failure it was asked about.
On macOS, when none connects and no proxy is in the way, one connection to a host
outside GitHub (`CONTROL_TARGET`, the host macOS’s own captive-portal check connects to)
tells “GitHub unreachable from this network” from “this network is down”.
On 2026-11-19 the owner’s machine showed why addresses matter: DNS answered
`api.github.com` sometimes with an address the network could not connect to and
sometimes with one it could, so the failures were intermittent.

Messages lead with the cause, and name the address when one is known:

- “GitHub could not be reached because the connection to api.github.com at 20.172.24.160
  timed out after 2 s; other sites are reachable; gh gave up after 15 s”
- “gh did not answer within 15 s; a fresh lookup of api.github.com gave 140.82.114.5,
  which accepted a connection in 38 ms; DNS answers vary, so gh may have used another
  address”: this lookup reached GitHub, which does not prove that `gh`’s did.
- “GitHub could not be reached because api.github.com did not resolve (DNS)”
- “GitHub answered HTTP 503”, and the rate limit as before, with its reset.

A failure that is not the first in an hour says how many calls could not reach GitHub in
that time (`event_log.recent_failures`). `GET /api/event-log/failures` groups the
failures since a moment by cause, with links to their records, and `/api/event-log`
filters by `cause`.

**The 15 s deadline.** `GH_TIMEOUT_S` in `gh.py` bounds `gh auth status`, which a
refresh runs twice. Its comment says it bounds a hung gh, not a slow one; `gh_status.py`
measured the same command at 0.61 to 0.65 s at load average 116. So 15 s is about 23
times the slowest measured run, and the timeouts the owner saw were network stalls: a
measurement on this machine the same afternoon found a TCP connect to `api.github.com`
hanging for 20 s while other hosts answered in about 20 ms, and a later one found DNS
returning an address no connection to which ever opened.
A connection that never opens fails at any deadline, so a shorter one would only make
the message arrive sooner, at the cost of failing a slow but working gh.
The deadline stays; the probe tells a stall from a slow gh within `PROBE_TIMEOUT_S`.

### Browser Reports

The reporter is `static/event-reports.js`, not `perf.js`, which is in the shell’s
startup scripts and their budget (`devtools/check_startup_scripts.py`): it is the last
script of the `shell-tools` bundle, which the shell loads after the first usable tree,
and the `event-reports` bundle a page that waits before then loads itself.
Each page has an ID, and each request it sends to its own server’s `/api/` carries
`<page>-<n>` in the `x-metabrowser-client` header, which the server records as the
request’s `client` and every job and process the request starts inherits;
`client=<page>` matches the page’s ID and every request’s. Requests answered before the
reporter loaded are read from Resource Timing.

It reports to `POST /api/event-log/client` (`event_log_reports.py`: bounded body and
count, each field checked and its text redacted, rate-limited across pages) a fetch
slower than `SLOW_MS`, a fetch still pending at it, a frame that froze the page for
`FREEZE_MS`, and named waits: a page marks what it is waiting for, such as a pull
request’s Diff summary, and the wait is reported when it is late (`WAIT_LATE_MS`), when
it ends late, and as `never_completed` when the page is left first.
A wait counts only the time the page was shown: a hidden tab polls nothing, so its wait
is not late until it has been late while shown, and its report says how long it was
hidden (`hidden_ms`). A page the browser keeps in its back/forward cache has not been
left: it sends what it has queued, and a wait it restores to ends as it would have.
Reports leave in batches with `fetch(..., {keepalive: true})`, not
`navigator.sendBeacon`, which cannot send the JSON type the same-origin guard requires
of a `POST`. The server writes each as a `browser` record.

A late wait says so on the page, and it and a failed refresh offer **Details**: what the
server is still running, the failures in the window by cause, the last probe, and the
page’s own records, read from `/api/event-log` and `/api/event-log/failures`. The page’s
reports are listed apart from the causes, under `page_reports`: they say what the page
saw, not why, so the server’s cause leads.
When the server’s log is off, Details says so and reads nothing.
The event log’s routes are about the server, not the served revision, so the source pin
guard lets them through, as it does `/api/source/`: a page left behind by a switch still
reports and reads its Details.

### Browsing the Log

The `event-log` built-in plugin reads a segment as spans (`event_log_views.py`): a
span’s `start`, `open`, and `end` records are one item, nested under the span that
started it (`parent`, with the process’s ID, since a copy of several segments can hold
two spans of one number), and a span with no `end` is *unfinished*, aged to the log’s
last record.
The file’s name picks the kind (`events-*.jsonl`, a filesystem `path_glob`),
so a segment is an event log wherever it is served or copied, and each view is a route
of the plugin that reads the file through the content reader, which is the same bounded
read for every source.
The kind is picked only for a file of an attached folder, since a `path_glob` is a
filesystem match: the same name in a pinned revision is a generic JSONL file, with no
event-log views. The routes are `timeline` (a page of the roots, or the children of a
`parent`, in time order), `slowest`, `kinds`, and `errors`. They take `/api/event-log`’s
filters (`kind`, `outcome`, `name`, `client`, `cause`, `min_ms`); a filtered timeline
keeps the spans that match and the spans above them.
Errors is the failures route’s grouping (`event_log_route.FailureTally`) over one file,
plus the unfinished work.
A segment is read whole up to `MAX_VIEW_BYTES`, the size the writer rolls at, and the
table built from it is kept by the content’s fingerprint; each constant records its
measurement beside it.
A server whose folder is the events directory, or inside it, opens no log of its own,
since its requests for the files on screen would change one of them, and says why: as a
warning, in Details, and in `metab --doctor`. A server whose folder only holds the
directory (`metab ~`) logs as usual and records no request whose target resolves inside
it (`event_log.quiet_request`), which is what breaks the loop without losing the rest of
that server’s latency.

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
- [x] The shared cause classifier, the connectivity probe, cause-led messages with the
  recent count, `GET /api/event-log/failures` and the `cause` filter, with stand-in `gh`
  and `git` for each class and a golden of recent failures with their causes.
- [x] A link from the page’s failure line to the failures behind it (with the browser
  reports, which touch the same page code).
- [x] The browser reports and `POST /api/event-log/client`, the pull request page’s Diff
  summary wait, and a browserless test of the reporter.

### Phase 2: Metabrowser Browses Its Own Log

- [x] A log view for the event schema, beside the agent-log and JSONL views, that the
  file kinds pick for an `events-*.jsonl` file: the `event-log` plugin
  (`builtin_plugins/event_log/`), a filesystem `path_glob` match.
- [x] Views: Timeline, which nests spans under their parents; Latency, the slowest and
  the distribution of times; By kind; and Errors, by cause with the page’s reports apart
  and the work that never ended.
  Each is a route (`event_log_views.py`) that `metab` reads, with filters of
  `/api/event-log`’s.
- [ ] A way to open the log from the app and the shell (a menu command or a link from
  the failure line), and a `metab` equivalent for each view’s query, with goldens.

## Testing Strategy

`tests/test_event_log.py` covers the records, each outcome, open records at the
threshold and each doubling, abandoned spans at shutdown, rotation and the directory’s
total, redaction, `gh` argument logging, a request’s span and the job it starts, a
refresh job that never ends, the comparison a Diff summary waits for, a `gh` stand-in
that never answers, and a failing `git`. `cli-api-event-log.tryscript.md` pins the route
on fixture segments that tell the stuck-page story.
`tests/test_network_cause.py` holds each class of `gh` failure (stand-in `gh` scripts
printing gh 2.98.0’s error forms, one captured from a real failure) to its state, cause,
message, and record, the probe to its verdicts against local ports, and a `git` that
cannot connect to its cause; `tests/test_cache_origin.py` keeps Git’s captured errors on
their states. `cli-api-event-log-failures.tryscript.md` pins the failure summary on a
segment that tells the 2026-11-19 outage.
`tests/test_event_log_reports.py` holds the report route to its fields, bounds, rate
limit, same-origin guard, and redaction, and the client ID to the request and the job it
starts; `cli-api-event-log-client.tryscript.md` pins the route and the page filter.
`tests/dom/event-reports-session.js` runs the reporter and the Details without a browser
(`cli-ui-event-reports.tryscript.md`), and `tests/test_event_reports_session.py` checks
that the route accepts every body it sends and that the Details read from a refresh job
that never ends show it running and the page’s wait never completed.
`tests/dom/github-pull-page-mount-behavior.js` pins the pull request page’s late line
and Details, and `tests/dom/event-log-details-chrome.mjs` the same in Chrome.
`tests/test_event_log_views.py` holds the spans: where one starts, what is unfinished,
nesting and what a hand-edited file may not do, filters, the distribution, percentiles,
and the failures’ grouping.
`cli-api-event-log-views.tryscript.md` pins each view’s route on a segment that tells
the stuck-page story; `tests/dom/event-log-view-session.js` runs the views without a
browser on the routes’ recorded answers (`cli-ui-event-log-view.tryscript.md`), and
`tests/dom/event-log-view-chrome.mjs` lays them out in Chrome
(`tests/test_event_log_view_chrome.py`). `tests/test_plugin_hooks_source_agreement.py`
holds the routes to the same answer for a folder and a pin.

## Open Questions

- Should the macOS app point the child’s state directory at
  `~/Library/Logs/Metabrowser/` so Console.app shows the event log beside the server
  log? Phase 1 keeps the XDG location for every platform.
- Is a connection to `captive.apple.com` the right control for the probe?
  It sends no request and goes only to a host macOS already checks, and only after
  GitHub could not be reached; `METABROWSER_NETWORK_PROBE_CONTROL` replaces or turns it
  off. Decided by the coordinator on 2026-11-19, after review A of #620, until the owner
  says otherwise: the default control runs only on macOS, which connects to that host
  itself, and never when the probe goes through a proxy, which a direct connection would
  bypass. A host named in `METABROWSER_NETWORK_PROBE_CONTROL` runs on any platform, never
  through a proxy. The host, its purpose, and both variables are named in the changelog
  and in [GitHub Failures](../../../realtime-debugging.md#github-failures).

## References

- [Real-Time Debugging](../../../realtime-debugging.md#event-log)
- [Parity Registry](../../architecture/arch-parity-registry.md)
- [Views, Models, and Routes](../../architecture/arch-views-models-routes.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
