# Real-Time Debugging

Metabrowser reports timing on both sides of the HTTP boundary so a slow preview can be
classified as server work, transport delay, event-loop queueing, or browser rendering.

## Default Signals

Every response includes a `Server-Timing` entry for measured server duration.
Browser developer tools display it alongside the request waterfall.

Slow server requests log a warning.
The default threshold can be overridden with `METABROWSER_SLOW_SERVER_MS`.

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
METABROWSER_REQUEST_LOG=verbose uv --config-file uv.toml run --frozen metab ./artifacts --no-open
```

The events and tail routes are intentionally long-lived and are excluded from ordinary
slow-request warnings.

## Task Snapshot

Enable the debug endpoint only for local investigation:

```shell
METABROWSER_DEBUG=1 uv --config-file uv.toml run --frozen metab ./artifacts --no-open
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
- artifact size and kind, with sensitive content removed;
- total, server, transit, and render durations;
- whether the issue reproduces with optional plugins disabled;
- a minimal fixture or generator when possible.

Do not attach private logs or absolute local paths to a public issue.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
