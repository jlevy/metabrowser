# Real-Time Debugging

Metabrowser reports timing on both sides of the HTTP boundary so a slow preview can be
classified as server work, transport delay, event-loop queueing, or browser rendering.

## Default Signals

Every response includes a `Server-Timing` entry for measured server duration.
Browser developer tools display it alongside the request waterfall.

Slow server requests log a warning.
The default threshold can be overridden with `METABROWSER_SLOW_SERVER_MS`. Routine
request timings, lifecycle events, and skipped protected directories stay quiet unless
`--log-level debug` is set.

The browser performance helper measures fetches and render spans.
A slow fetch message includes total, server, and transit time.
Interpret it as follows:

- server time close to total: inspect parsing, filesystem access, or data hooks;
- transit time close to total on localhost: inspect event-loop blocking or request
  queueing;
- fetch fast but render span slow: inspect DOM volume, syntax highlighting, charts, or
  plugin rendering.

## Verbose Request Logging

Enable one line for every request when correlation is more useful than log volume:

```shell
METABROWSER_REQUEST_LOG=verbose uv --config-file uv.toml run --frozen metab ./path/to/directory --no-open
```

The events and tail routes are intentionally long-lived and are excluded from ordinary
slow-request warnings.

## Navigation API Check

Run the navigation scenario directly against the ASGI application:

```shell
metab ./path/to/directory --check-api
```

The command starts the normal inventory lifecycle in-process, requests the initial tree,
enables the Live filter, clears it, waits for the index to finish, and requests the
final tree. It does not open a browser or bind a network port.
The normalized output includes HTTP status codes, an explicit index outcome, and the
final row, file, byte, and index counts.
The command exits nonzero if a route or response contract fails.
For an unusually large or slow root, extend the default 60-second wait:

```shell
metab ./path/to/directory --check-api --index-timeout 180
```

This scenario is suitable for reproducing navigation failures on a large local directory
and for a deterministic golden test on a checked-in fixture.
It complements focused concurrency tests, which can force a mutation at an exact
inventory operation that a filesystem timing test cannot reproduce reliably.

## Task Snapshot

Enable the debug endpoint only for local investigation:

```shell
METABROWSER_DEBUG=1 uv --config-file uv.toml run --frozen metab ./path/to/directory --no-open
```

During a stall, request `/_debug/tasks` from another terminal.
A rapidly growing task count suggests queueing or a producer that is not applying
backpressure.
Treat the response as diagnostic data; do not expose the debug server on an
untrusted network.

## Live-Update Problems

For a tree row that does not update:

1. Confirm the file path is beneath the served root and is not ignored.
2. Check the inventory endpoint for the current entry and generation.
3. Inspect the `/api/events` stream for a snapshot, change, or resynchronization event.
4. Confirm the browser file store applied the operation.
5. Verify the relevant panel subscribes to the shared store instead of a stale local
   copy.

If an event buffer gap occurs, the client should replace state from a fresh snapshot.
Do not repair a gap by replaying operations whose order is no longer known.

A message that Metabrowser is refreshing browser connections after queue overflow means
the bounded event buffer filled during a producer burst.
The server discards the incomplete delta backlog, sends a resynchronization marker, and
the browser reconnects for a fresh snapshot.
One refresh is self-healing.
Repeated refreshes are worth reporting with the root size, filesystem type, and
surrounding slow-operation messages because they indicate that filesystem events are
arriving faster than the browser stream can consume them.

### Pending Folder Totals

A folder count, size, or modification time that remains pending for five seconds emits
one warning in the browser console and one correlated warning in the server log.
The warning is reported once per unresolved episode, so a long scan does not repeat the
same message.

Use the shared diagnostic ID to compare the two records.
The browser record includes the active filters and data source, visible pending rows,
cached tree values, file-store values, scan progress, and event-stream state.
The server record adds the inventory and walker status, pending-directory count,
subscriber and connection counts, event position, and aggregate and generation state for
a bounded sample of affected paths.

When the server inventory is already complete, the browser reloads the authoritative
tree after recording the warning.
This safety refresh repairs a stale rendered snapshot while preserving the diagnostic
evidence needed to find how it became stale.

## Plugin Problems

Start with the registry:

```shell
uv --config-file uv.toml run --frozen metab --plugins --json
uv --config-file uv.toml run --frozen metab --doctor
```

Then verify:

- the installed wheel contains `manifest.toml`, `index.js`, and every declared extra
  asset;
- the classifier chose the expected kind in `/api/file`;
- the manifest declared the expected view;
- `index.js` registered the same `(kind, view)` pair;
- data-hook requests use the plugin and route names from the manifest;
- the renderer uses SDK methods instead of private shell functions.

For a renderer that works once and then fails, inspect disposal and retained module
state.
Views persist across tab switches but must release resources when the preview pane
is replaced.

## Reporting a Performance Defect

Include:

- Metabrowser version and Python version;
- operating system and filesystem type;
- file size and kind, with sensitive content removed;
- total, server, transit, and render durations;
- whether the issue reproduces with optional plugins disabled;
- a minimal fixture or generator when possible.

Do not attach private logs or absolute local paths to a public issue.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
