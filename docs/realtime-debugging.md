# Real-Time Debugging

**Status:** Current for the built server and browser.
A standard for contributors diagnosing a slow preview or a live update that did not
arrive; what a user sees while files change is in [Browsing Files](browsing-files.md).

Metabrowser reports timing on both sides of the HTTP boundary, so a slow preview can be
classified as server work, transport delay, event-loop queueing, or browser rendering.
The live path is described in
[Live Delivery](project/architecture/arch-live-delivery.md); this document is how to
observe it.

## Timing Signals

Every response except the long-lived event streams (`_LONG_LIVED_PATHS` in `server.py`)
carries a `Server-Timing` header with the server’s duration to the response start and
the named phases finished by then (`server_timing.py`); those streams are neither timed
nor reported as slow.
Browser developer tools show the header beside the request waterfall.

A request slower than `METABROWSER_SLOW_SERVER_MS` logs a warning with its arrival time,
duration, status, size, time to first byte, and phases.
`METABROWSER_REQUEST_LOG=verbose` logs one line for every request instead, with arrival
and completion times that line up with the browser’s `perf.js` records.
Routine request timings, lifecycle events, and skipped protected directories appear only
with `--log-level debug`.

The browser’s performance helper (`static/perf.js`) measures fetches and render spans,
and a slow fetch message includes total, server, and transit time:

- **Server time close to total:** inspect parsing, filesystem access, or data hooks.
- **Transit time close to total on localhost:** inspect event-loop blocking or request
  queueing.
- **Fetch fast but render slow:** inspect DOM volume, syntax highlighting, charts, or
  plugin rendering.

## Event Log

A served process also writes a structured event log (`metabrowser/event_log.py`): one
JSON line for every request, for each background job that refreshes or prepares what a
page shows, and for every `git` and `gh` process that runs to completion, with its
duration, how it ended, and the span that started it.
The jobs are those wrapped in `event_log.job`: pull request and file list refreshes,
comparison listings, the pull request prefetch, a checkout’s idle comparison, GitHub
status checks, repository rediscovery, and the read of a Git revision’s file ages
(`file_ages.read`, whose end record carries the files dated, the commits that dated
them, and why any are not; a `git last-modified` that fails ends it `failed` with Git’s
stderr).
A streaming `git` session started with `spawn_git_process`, such as a history or
tree reader, is not a span of its own; the request that reads it is.
It covers what the stderr log cannot: a pull request’s refresh or a comparison’s listing
runs after the request that asked for it has returned, and a `gh` that times out there
writes nothing to stderr.
The design and its schema are in
[the plan](project/specs/active/plan-2026-11-19-structured-event-log.md).

The log lives in `events/` under the state directory: `METABROWSER_STATE_DIR`, else
`$XDG_STATE_HOME/metabrowser`, else `~/.local/state/metabrowser`, whether the server
runs from a terminal or inside the macOS app, which passes those variables and
`METABROWSER_EVENT_LOG` to the servers it starts (an app opened from the Finder or the
Dock sees only what `launchctl setenv` set, not a shell’s exports).
Each server writes its own owner-only segment, named for when it started and its process
ID; a segment rolls at `MAX_FILE_BYTES` and the directory is kept within
`MAX_TOTAL_BYTES` by deleting the oldest, except the segment each running server writes.
A write that fails pauses the log, which tries a fresh segment after a backoff
(`RETRY_FIRST_S` doubling to `RETRY_MAX_S`), and logging never fails the work it
records. `METABROWSER_EVENT_LOG=0` turns it off.
A one-shot command, such as `--api`, writes none.

Read it with `/api/event-log`, from a running server or from a terminal:

```shell
metab . --api '/api/event-log?outcome=timeout,failed'
metab . --api '/api/event-log?kind=job&sort=duration&limit=10'
metab . --api '/api/event-log?span=8'
```

The answer names the directory and its segments, and reads the one this server writes,
else the newest; `file=` reads another.
Filters are `kind`, `outcome`, `event`, `name`, `client` (a request’s client ID, or a
page’s, which finds every request the page sent and every report it made), `span` (that
span’s records and those of the spans it started), and `min_ms`, and `sort=duration`
puts the slowest first.
From a running server, `open` lists what it is waiting on now, each with the client that
started it.

For a page that waits and nothing arrives:

1. Find the request the page sent, such as `POST /api/plugin/github/pull-refresh`, and
   its `span`.
2. `span=<id>` shows the job it started: a `start`, `open` records at `OPEN_AFTER_MS`
   and each doubling, and its `end`, or no end when it never finished.
3. The job’s own `span` shows its `gh` and `git` processes.
   A `gh` that timed out says where it stalled (`before any answer` or partway) and the
   end of its stderr; a job whose work failed ends `failed` with the `failure` its
   refresh recorded.

At shutdown each span still open ends `abandoned`, and a turn of the event loop that
took longer than `OPEN_AFTER_MS` is a `loop` record, so a blocked loop is on record too.
The log holds request paths and folder names but never a token: command lines drop field
and header values, and process text is redacted.

### Browsing the Log

Metabrowser draws its own log.
A file named `events-*.jsonl`, wherever it is served, is an event log, and the
`event-log` plugin (`builtin_plugins/event_log/`) opens it with four views beside Raw
JSON:

- **Timeline** (`V`) nests each span under the span that started it: a request, the job
  it started, the `git` and `gh` processes the job ran, in time order, each with a bar
  on the log’s time axis.
  A row opens to its detail and, if it started work, to what it started.
  Marks, such as a server starting, and what a page reported sit among the requests.
- **Latency** (`L`) lists the slowest spans, longest first, each with the spans above
  it, over the distribution of every span’s time.
  Work that never ended counts for the time it had run when the log did.
- **By kind** (`B`) counts each kind of record and each name within it, how they ended,
  and their median, 95th-percentile, longest, and total times.
- **Errors** (`E`) groups the failures by cause, as `/api/event-log/failures` does, over
  the whole file; lists apart what the page reported, since a page says what it saw and
  not why; and lists the work that had no `end` record when the log did, which is how a
  refresh that never ended shows.

Timeline, Latency, and By kind take chips for the kind and the outcome, and a least
time, the filters `/api/event-log` takes.
A timeline with a filter shows each span that matches and the spans above it, so a slow
`git` process is shown inside the request that waited for it.

Each view is a route that `metab` reads, so what the page shows is what a terminal
shows:

```shell
metab DIR --api '/api/plugin/event-log/timeline?path=events-20261119T210201Z-p4242-000.jsonl&kind=job'
metab DIR --api '/api/plugin/event-log/slowest?path=events-20261119T210201Z-p4242-000.jsonl&limit=10'
metab DIR --api '/api/plugin/event-log/kinds?path=events-20261119T210201Z-p4242-000.jsonl'
metab DIR --api '/api/plugin/event-log/errors?path=events-20261119T210201Z-p4242-000.jsonl'
```

A timeline answers a page of the roots, or the children of `parent=<key>`, with `offset`
and `limit`; each row’s key is `<pid>:<span>`. `order=newest` lists the roots last
first, and the Timeline’s **Order** chips ask for it; the spans under a span stay in
time order. `focus=<key>` adds where that row is: each step from a root down to it, with
its place among its parent’s rows in this order and under this filter, or why it is not
shown.
The **Show in timeline** button on a row of Latency, or an example in Errors, asks
for that, opens each span above the row, reads the pages that hold them, and focuses it,
so a slow or failed row is seen with what surrounded it.
A segment is read whole up to `MAX_VIEW_BYTES` in `event_log_views.py`, the size the
writer rolls at, and a larger file is for Raw JSON. Every file the log writes, and a
copy attached to a bug report, answers the same in an attached folder.
The views are offered for a file of an attached folder only, because the name match is a
filesystem one: a segment committed to a repository is a generic JSONL file in a pinned
revision. A file that is not the log, with a time or a number no calendar holds, is read
as far as it can be and answers a 422 naming the file where it cannot.
When a later segment of the same process follows, the Errors view says that work with no
end here may have ended there (`log.continues`).

To open the log, run `metab --event-log`, which serves the directory it is in at its
newest segment. The same flag names the directory for `--api`, `--show`, and the other
modes that take a folder, and the macOS app’s Help menu has Open Event Log, which opens
the log’s own directory in a window of its own, and not in Open Recent.
A pull request page’s Details names the menu item for a server the app started, and the
command for any other.

A server whose folder holds the events directory, such as `metab ~`, writes its log as
usual, except that a request for something inside the directory is not recorded: each
would otherwise land in the segment on screen, which changes it, and the page would ask
again. A server whose folder is the events directory itself, or inside it, such as the
command above, writes no log at all, for the same reason, and says so: as a warning when
it starts, in its Details, and in `metab --doctor`. `metab --doctor` also says when
`METABROWSER_EVENT_LOG` turns the log off.

### What the Page Reports

Only the page knows what it waited for, so it reports that too
(`static/event-reports.js`, to `POST /api/event-log/client`, which
`metabrowser/event_log_reports.py` checks, bounds, and redacts).
Each page has a client ID of eight letters and digits, and every request it sends to its
own server’s `/api/` carries `<page>-<n>` in the `x-metabrowser-client` header.
The server’s record of that request has it as `client`, and so does every job and
process the request starts, so `client=<page>` reads everything one page asked for and
saw, and `client=<page>-<n>` one request and the work behind it.
Each report is a `browser` record named for its type: `fetch`, `render`, or `wait`.

| Report | When | Threshold |
| --- | --- | --- |
| `fetch … open` | A request to this server still pending | `SLOW_MS` |
| `fetch … end` | A request that took that long or longer, with its status, its `srv` Server-Timing, and `ok`, `failed`, or `cancelled`; or `never_completed` for one reported open that the page left first | `SLOW_MS` |
| `render blocked` | A frame that blocked the page, with the function, source, and invoker the browser blamed, where it reports long animation frames or long tasks, as Chrome does; WebKit, the macOS app’s engine, reports neither, so the app reports no freezes | `FREEZE_MS` |
| `wait … open` | Something the page shows as loading, still running after that long shown: the pull request page’s Diff summary and its refresh, and a mirror’s refresh | `WAIT_LATE_MS` |
| `wait … end` | That wait’s end, once it was reported: `ok`, `failed`, `cancelled`, or `never_completed` when the page was left first | `WAIT_LATE_MS` |

The thresholds are constants in `event_log_reports.py`, with the measurement that set
each beside it; the page reads them from `METABROWSER_SETTINGS.EVENT_REPORTS`. A wait
that ends before its threshold, and a request answered sooner, report nothing.
A wait’s threshold counts only the time the page was shown: a hidden page stops polling,
so its waits run long for no fault of the work behind them.
A wait that spent some of its time hidden says how long, as `hidden_ms`. A page kept in
the browser’s back/forward cache is not left, so its waits go on when it is restored.
Reports are gathered for `FLUSH_MS` and sent in bodies of at most `MAX_REPORTS`, with
`keepalive`, so the last leave with the page; a page sends at most
`PAGE_REPORTS_PER_MINUTE`, and the server takes at most `RATE_REPORTS` in
`RATE_WINDOW_S` from all pages, marking what it refused.
A server that writes no log gets no header and no report, and its Details say the log is
off rather than show what an earlier server wrote.
The event log’s routes are exempt from a pinned revision’s guard, so a page left on a
revision the server no longer serves still reports and reads the log.
The reporter is an on-demand bundle the shell loads after the first usable tree;
requests answered before it loaded are read from Resource Timing.

A wait still running at its threshold says so on the page.
On a pull request’s page the Diff summary’s placeholder becomes “The summary of changes
has not arrived after N s.”, and a failed refresh’s line ends the same way, each with
**Details**: a button that opens, under the header, what the event log holds for it.
The Details list what the server is still running, this page’s first; the failures in
the window by cause, with the message, the addresses that failed, and the latest calls;
the last probe of GitHub; and this page’s own slow, failed, or unfinished records, with
links to both answers as JSON, and the command that opens the whole log
([Browsing the Log](#browsing-the-log), the settings’ `open_command`). A failure’s
window is the hour before its refresh ended, to a minute after.

To read what one page saw from a terminal, take its ID from a request’s
`x-metabrowser-client` header in the browser’s developer tools, or from the Details’
JSON link:

```shell
metab . --api '/api/event-log?client=k3v9q2zx'
metab . --api '/api/event-log?kind=browser&outcome=never_completed'
```

## GitHub Failures

A failed `gh` or `git` call to GitHub carries a `cause` in the vocabulary
`metabrowser/network_cause.py` defines for both tools (`CAUSES`): a name that did not
resolve (`dns_failed`), a connection refused or timed out (`connect_refused`,
`connect_timeout`), a TLS or proxy failure, an answer that stalled or never came
(`stalled`, `no_answer`), or GitHub’s own refusal (`auth_refused`, `forbidden`,
`not_found`, `rate_limited`, `server_error`). The refresh message on a page leads with
it, as in “GitHub could not be reached because the connection to api.github.com at
20.172.24.160 timed out”.
GitHub’s own error text, and `gh`’s and Git’s, are never shown; the event log keeps
them, redacted.

A `gh` that gives up with no answer says nothing about why, so Metabrowser then probes
the network itself (`network_cause.probe`): it resolves `api.github.com` and connects to
each address DNS gave, through the proxy `gh` would use when `HTTPS_PROXY` is set and
`NO_PROXY` does not exempt GitHub.
The probe sends no request and no credential, finishes within `PROBE_TIMEOUT_S`, runs at
most once per `PROBE_INTERVAL_S`, never replaces the failure it explains, and is a
`probe` record in the log.
Its finding says which it was: GitHub unreachable from this network, with the addresses
that failed, or GitHub reachable from a fresh lookup (“gh did not answer within N s; a
fresh lookup of api.github.com gave 140.82.114.5, which accepted a connection in M ms;
DNS answers vary, so gh may have used another address”), with any address that failed in
that lookup or in the last hour.
A reachable probe is not proof that `gh`’s connection could open: DNS can answer the
same name with a different address each time.

On macOS, when no address of GitHub’s connects and no proxy is in the way, the probe
opens one TCP connection to `captive.apple.com` port 80 (`CONTROL_TARGET`), the host
macOS itself checks for a working network, and sends nothing on it.
That tells “other sites are reachable” (GitHub, or the route to it, is the problem) from
“other sites are not reachable either” (the network is down).
It never runs on other platforms or through a proxy, and it shares the probe’s one
deadline (`CONTROL_TIMEOUT_S` of it).
`METABROWSER_NETWORK_PROBE_CONTROL=0` turns it off and `HOST:PORT` names another host,
which then runs on any platform; `METABROWSER_NETWORK_PROBE=0` turns the whole probe
off.

To see what has been failing, and how often:

```shell
metab . --api '/api/event-log/failures'
metab . --api '/api/event-log/failures?since=2026-11-19T21:00:00Z&kind=subprocess'
metab . --api '/api/event-log?cause=connect_timeout&event=end'
```

The summary groups the failures since `since` (an hour ago by default) by cause, with
how many, which work, the addresses that failed, the latest message, a `details` link to
each example’s records, and the latest probe that failed.
A page’s own reports of failure, such as a wait that never completed, are listed apart
under `page_reports`, not counted as causes: they are the page’s view of a failure the
server’s records name, so the cause leads.
When the addresses vary between failures, DNS is answering a GitHub name with addresses
the network reaches only some of the time.

## GitHub Requests

To see what browsing asked of GitHub, and what it cost:

```shell
metab . --api '/api/plugin/github/gh-requests'
metab . --api '/api/plugin/github/gh-requests?since=2026-11-26T10:00:00Z&until=2026-11-26T10:05:00Z&pid=4242'
```

The report adds up the `gh` calls that ended since `since` (an hour ago by default), for
every call, for each lane a call served (a page on screen, what the session attends to
without showing it, the prefetch, and the background), for each budget a call was
charged to (a reader’s own action, automatic work, speculative work, and the walk that
prepares rows’ cores), and for each job the calls ran in: the calls by command, the
statuses GitHub answered, the `core` calls and GraphQL points they spent, the share
answered `304`, how long `gh` took at the median and the 95th percentile, the calls that
repeated an identical one, and how long their jobs waited for a network slot.
`in_flight` says how many calls ran at once, cut into `buckets` equal parts of the time
they ran, and `pid` keeps one server’s calls when several share the log.
`unrecorded` names what the log does not hold, such as when a page first showed GitHub’s
answer.
[The Request Report](project/architecture/arch-github-pull-requests.md#the-request-report)
says what each call records.

## Debug Endpoints

```shell
METABROWSER_DEBUG=1 uv --config-file uv.toml run --frozen metab ./path/to/directory --no-open
```

With `METABROWSER_DEBUG` set, `/_debug/tasks` lists the running asyncio tasks and
`/_debug/inventory` reports the provider and contract, lifecycle phase, coverage,
version, read count, and cumulative work: entries and directories visited, rows
returned, binding-copy bytes, lock wait, CPU time, and wall time.
A task count that grows during a stall suggests queueing or a producer that is not
applying backpressure.
Compare the work counters before and after one slow request to separate provider work
from queueing or browser time.
Do not expose a debug server on an untrusted network.

## Following a Live Update

A change travels watcher, provider, coordinator, event bus, stream, and browser store.
Each layer has a `--log-level debug` line that proves it ran:

| Layer | Debug line |
| --- | --- |
| Watcher selection | `watcher starting at … mode=… reason=…` |
| Watcher batch | `watcher: batch n=…`, then `watcher: submitted rel=… kind=…` per path |
| Watcher drop | `watcher: drop (hidden segment)`, `(outside root)`, or `root metadata` |
| Event bus | `events bus: forwarded id=… type=… conns=…` |
| Connection | `sse: attached client=… scope=…`, then `sse: yielded id=…` |

For a tree row that does not update:

1. Confirm the path is beneath the served root, not under a hidden segment, and not one
   the engine’s watcher filters out; the engine’s document lists what its watcher
   ignores, as
   [The Watcher](project/architecture/arch-inventory-engine-python.md#the-watcher) does
   for the Python engine.
2. Read `/api/capabilities`: the watcher’s mode and state, and `events.stream`. A failed
   watch reports `failed` there and in the server log.
3. Check `/_debug/inventory` for the provider’s state and version, then request the
   entry through its ordinary route, such as `/api/tree?path=…`.
4. Read the `/api/events` stream for the snapshot, a change naming the path, or a
   resynchronization. Only paths within two segments of the root arrive as rows on the
   browser’s `root-depth-2` stream; a deeper change arrives through its ancestors’
   totals and `catalog.change`.
5. Confirm the browser’s `fileStore` applied the operation, and that the panel reads the
   shared store rather than a stale copy.

A gap is repaired by a fresh snapshot, never by replaying operations whose order is no
longer known. The warning
`events bus: refreshing N slow browser connection(s) after queue overflow` means a
connection’s bounded queue filled during a burst; the server replaced its backlog with
`fs.resync_required` and the browser reconnected for a snapshot.
One is self-healing.
Repeated ones mean filesystem events arrive faster than the stream drains; report them
with the root size, filesystem type, and the slow operations around them.

## Pending Folder Totals

A folder total that stays pending for `PENDING_TALLY_DIAGNOSTIC_DELAY_MS`
(`settings.py`) produces one correlated record per unresolved episode: a browser console
warning, and a `POST /api/diagnostics/pending-tallies` that logs a server warning with
the same diagnostic ID. The browser record holds the active filters and data source, the
pending rows, cached tree values, `fileStore` values, scan progress, and event-stream
state.
The server record adds the inventory status, provider, version, and per-path state
for at most `PENDING_TALLY_DIAGNOSTIC_SAMPLE_LIMIT` paths, and the event bus’s
connection count and latest event ID. When the server’s index is already complete, the
browser then reloads the authoritative tree, which repairs a stale rendering while
keeping the evidence of how it went stale.

## Navigation Check

`metab PATH --check-api` runs the navigation scenario in process, with no browser or
port: it requests the initial tree, applies and clears the Live filter, waits for the
index, and requests the final tree.
Its normalized transcript has the status codes, an explicit index outcome, and the final
counts, and it exits nonzero when a route or envelope contract fails, so it reproduces
navigation failures on a large local tree and pins them in a golden on a checked-in
fixture. `--index-timeout` extends the wait for a slow root.
It complements focused concurrency tests, which can force a mutation at an exact
inventory operation that a filesystem timing test cannot reproduce.

## Plugin Problems

`metab --plugins --json` and `metab --doctor` show what discovery loaded and whether
each manifest, handler, and asset is sound.
Then check that `/api/file` chose the expected kind, the manifest declares the view,
`index.js` registered the same `(kind, view)` pair, and data-hook requests use the
manifest’s plugin and route names.
A renderer that works once and then fails usually retains state its disposer does not
release; views survive tab switches and are disposed when the preview pane is replaced.
See [Plugins](plugins.md).

## Reporting a Performance Defect

Include the Metabrowser and Python versions, the operating system and filesystem type,
the file’s size and kind with sensitive content removed, the total, server, transit, and
render durations, whether it reproduces with optional plugins disabled, and a minimal
fixture or generator when possible.
Do not attach private logs or absolute local paths to a public issue.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
