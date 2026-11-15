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

1. Confirm the path is beneath the served root and not under a hidden segment.
   The Python engine’s watcher also ignores what `watchfiles`’ default filter ignores,
   such as `node_modules` and `__pycache__`; see
   [Python Inventory Engine](project/architecture/arch-inventory-engine-python.md#the-watcher).
2. Read `/api/capabilities`: the watcher’s mode (`native` or `polling`), its state, and
   `events.stream`. A failed watch reports `failed` there and in the server log.
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
