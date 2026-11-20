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
status checks, and repository rediscovery.
A streaming `git` session started with `spawn_git_process`, such as a history or tree
reader, is not a span of its own; the request that reads it is.
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
Filters are `kind`, `outcome`, `event`, `name`, `client`, `span` (that span’s records
and those of the spans it started), and `min_ms`, and `sort=duration` puts the slowest
first. From a running server, `open` lists what it is waiting on now.

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

## GitHub Failures

A failed `gh` or `git` call to GitHub carries a `cause` in the vocabulary
`metabrowser/network_cause.py` defines for both tools (`CAUSES`): a name that did not
resolve (`dns_failed`), a connection refused or timed out (`connect_refused`,
`connect_timeout`), a TLS or proxy failure, an answer that stalled or never came
(`stalled`, `no_answer`), or GitHub’s own refusal (`auth_refused`, `forbidden`,
`not_found`, `rate_limited`, `server_error`). The refresh message on a page leads with
it, as in “Couldn’t connect to GitHub (api.github.com at 20.172.24.160): the connection
timed out”.
GitHub’s own error text, and `gh`’s and Git’s, are never shown; the event log
keeps them, redacted.

A `gh` that gives up with no answer says nothing about why, so Metabrowser then probes
the network itself (`network_cause.probe`): it resolves `api.github.com`, connects to
each address DNS gave (through the proxy `gh` would use, when one is set), and, when
none answers, connects once to a host outside GitHub (`CONTROL_TARGET`). The probe sends
no request and no credential, runs at most once per `PROBE_INTERVAL_S`, and is a `probe`
record in the log. Its finding says which it was: GitHub unreachable from this network
("other sites are reachable"), the network down ("other sites are not reachable
either"), or GitHub reachable and `gh` or GitHub slow ("gh did not answer within N s,
although api.github.com accepted a connection in M ms"). `METABROWSER_NETWORK_PROBE=0`
turns the probe off, and `METABROWSER_NETWORK_PROBE_CONTROL=0` turns off the outside
host.

To see what has been failing, and how often:

```shell
metab . --api '/api/event-log/failures'
metab . --api '/api/event-log/failures?since=2026-11-19T21:00:00Z&kind=subprocess'
metab . --api '/api/event-log?cause=connect_timeout&event=end'
```

The summary groups the failures since `since` (an hour ago by default) by cause, with
how many, which work, the addresses that failed, the latest message, a `details` link to
each example’s records, and the latest probe that failed.
When the addresses vary between failures, DNS is answering a GitHub name with addresses
the network reaches only some of the time.

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
