# Architecture: Live Delivery

**Status:** Built: the coordinator’s change relay, the event bus and `/api/events`
(`events_route.py`, `events.py`), file watches registered on a connection
(`file_watches.py`, `static/file-watches.js`), the Quick File catalog feed, live log
tailing on `/api/stream` (`sse.py`), and the browser’s stores.
Planned: pushed aggregates, so that Overview and Treemap stop polling during a scan
([load-time plan](../specs/active/plan-2026-08-21-load-time-performance.md)).

Metabrowser keeps one picture of the served tree in a server that watches it change and
a browser that watches the server.
This document follows a change from the provider’s change feed to the browser’s stores,
and states only what the [provider contract](arch-inventory-provider.md) guarantees; how
the Python engine observes the filesystem is in
[Python Inventory Engine](arch-inventory-engine-python.md).

Two facts shape the design.
**The tree can be large**, so no response can carry it, and every response is bounded
and says what it left out.
**The tree changes while it is read**, so no state can be fetched once and trusted: it
has to converge, which takes a delta stream, an authoritative snapshot to fall back to
when the stream has a gap, and a way to say that a number is not final yet.

## Two State Layers

|  | Entries | Aggregates |
| --- | --- | --- |
| What | One record per file, directory, and symlink | Per-directory totals, extension tallies, file-type breakdown |
| Changes | On its own path’s change | On any change beneath it |
| Transport | Pushed: `fs.change` on `/api/events` | Pulled: `/api/rollup` and `/api/tree` |
| Computed | Once per change, fanned out to every connection | Once per distinct version, path, and bounds |
| Repeat cost | None; deltas only | A `304`, or a retained body |
| Browser state | Stores patched per operation | Envelopes replaced whole |
| Scope | Rows within the connection’s scope | Any path, any depth |

A write invalidates exactly one entry but every aggregate above it, which makes
aggregates expensive to keep current and cheap to keep approximately current.
The browser’s stream carries entries only to depth two, so a change deeper than that
reaches the browser through its shallow ancestors’ updated totals and the catalog delta,
never as its own row.

## From Provider to Coordinator

The coordinator (`inventory_engine/coordinator.py`) owns the provider’s one change
iterator. `_run_change_relay` pumps `ChangeBatch` values into a bounded queue; a full
queue is drained and replaced by one reset.
`_dispatch_provider_changes` takes every batch that has queued, rejects a sequence that
does not increase or an identity that does not match the handle, and merges the group
into one `HostChange`.

A `HostChange` carries a host cursor, the host version (engine version plus overlay
revision), the provider state, and dirty paths, dirty query kinds, `all_dirty`, or
`reset`. The coordinator keeps a bounded history for resumption; a subscriber whose
queue is full, or whose cursor predates the history, gets a reset.
Invalidation listeners run after each change: `InventoryRuntime` uses one to clear the
per-file projection caches for the dirty paths.
If the relay fails, the coordinator logs it and publishes a reset, so consumers reread
rather than trusting a stream that may have lost a batch.

## The Event Bus

`_EventBus` (`events_route.py`) is the only consumer of the coordinator’s stream in a
serving process. Its relay loop projects each `HostChange`:

- With no browser connected, it advances its cursor and builds nothing; a new connection
  always starts from a snapshot.
- `reset` or `all_dirty` becomes `fs.resync_required`.
- Dirty paths become one bundled read with an `EntryQuery` per path, and the results
  become one `fs.change` of upsert and remove operations.
  A path whose presence is `unknown` becomes `fs.resync_required` instead.
- When the catalog query kind is dirty, a `catalog.change` follows its `fs.change`.
- When diagnostics are dirty, a `capability.update` carries the watcher’s mode and state
  and the index’s completeness.

If the relay raises, it resumes from the last projected cursor after a backoff.
`RingBuffer` assigns every event a process-wide id and keeps the last
`SSE_RING_BUFFER_CAPACITY` for diagnostics; it is never replayed.

Each connection has a queue of `SSE_PER_CONNECTION_QUEUE_SIZE`. A connection whose queue
fills can no longer receive a correct ordered stream, so the bus drains its backlog,
replaces it with `fs.resync_required`, and detaches it: bounded memory and an honest
signal instead of a corrupted delta stream
(`tests/test_browser_events_route.py::test_event_bus_overflow_restarts_slow_connection`).

## The Event Route

`GET /api/events?scope=` is one Server-Sent Events connection per tab.
The browser asks for `root-depth-2`; `VALID_SCOPES` lists the others.
A Git pin has no watcher, so the route answers `unsupported_for_subject`.

1. **Snapshot and attach.** `snapshot_and_attach` holds the bus lock while it assembles
   a lossless snapshot from version-pinned `DirectoryQuery` pages of
   `INVENTORY_TREE_PAGE_ROWS` (`assemble_tree_pages`), then attaches the connection’s
   queue with that snapshot’s host version as its floor.
   A change the snapshot already covers is suppressed for that connection, and every
   newer change queues after attachment, so neither a stale delta nor a gap can occur
   (`tests/test_browser_events_route.py::test_snapshot_handoff_drops_a_change_already_covered_by_the_snapshot`).
2. **Snapshot frame.** The snapshot is sent with id 0, outside the live id sequence,
   because it is a reset boundary rather than a ring event.
   `Last-Event-ID` is read only to log a resume from a previous process; nothing before
   the snapshot is replayed
   (`tests/test_browser_events_route.py::test_api_events_snapshot_supersedes_preconnect_ring_entries`).
3. **Live frames.** Each queued event is filtered to the scope: `root-depth-2` drops
   `fs.change` operations deeper than two segments, and every other event passes
   unfiltered. A quiet connection gets a `: heartbeat` comment frame every
   `SSE_HEARTBEAT_INTERVAL_S`.
4. **End.** Sending `fs.resync_required` ends the stream, and the browser reconnects for
   a fresh snapshot
   (`tests/test_browser_events_route.py::test_resync_marker_ends_stream_after_delivery`).

The response sets `Cache-Control: no-cache` and `X-Accel-Buffering: no` and is never
compressed.

| Event | Carries |
| --- | --- |
| `fs.snapshot` | The connection’s id, first in the frame, then its scope, its entries, and whether coverage is complete |
| `fs.change` | Ordered upsert and remove operations |
| `catalog.change` | Quick File upserts and removals derived from the same operations, unscoped |
| `fs.resync_required` | A reason; the stream has a gap, so drop derived state and reconnect |
| `capability.update` | Watcher mode and state, index completeness, indexed files, and the cap |
| `file.changed` | A path this connection watches and its new generation, or null when nothing is there |

`fs.change` is the one changed-path invalidation for file previews, directory
projections, SDK rollup watches, and the catalog delta beside it; the bus sends no
second per-path event.
`events.py` also defines a `Heartbeat` event and tail events (`file.append`,
`file.truncate`, `file.rotate`, `file.closed`, `file.coalesced`, `parser.reset`) that no
route constructs; live log tailing uses `/api/stream`, below.

## File Watches

The stream carries tree entries only to depth two and the catalog only for unignored
files, and a source’s content can change where no inventory path does, as a database’s
does through its `-wal`. So a view that shows a live file registers that file on its
page’s own connection, and hears of a change on the stream it already holds rather than
on a second one: a browser opens six connections to a host, and a stream per view would
spend them
([Decision 4](../specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md#decision-4-how-an-open-file-learns-it-changed)).

- **The connection.** `snapshot_and_attach` gives each connection an id, which its
  `fs.snapshot` carries as its first key; the browser compares two snapshots without it,
  so a reconnect to an unchanged tree still skips the repaint.
- **Registration.** `POST /api/events/watch` with `{connection, path, generation}`
  registers the path and answers its generation now, the baseline later polls compare
  with, and `changed` when it differs from the generation the page holds, so a change
  between the page’s read and the registration is not lost.
  `watch: false` unregisters it.
  With no connection the route registers nothing and answers the generation a watch
  would compare, which is what `metab --api` reaches.
  A connection id the process does not hold, as after a restart, is refused with
  `unknown_connection`; past `FILE_WATCH_MAX_PATHS` paths, with `too_many_watches`. A
  Git pin answers `unsupported_for_subject`, as `/api/events` does.
- **The generation** (`watch_generation`) is the table source’s own `generation()` for a
  path whose kind has one, the token every read of it samples, and the file’s identity,
  size, and modification time for any other path.
  One path is read for what it says: `HEAD_WATCH_PATH`, a checkout’s `HEAD`, whose
  generation is the branch and commit `HEAD` names.
  A linked worktree’s `HEAD` is outside the served root, and a commit leaves the `HEAD`
  file as it was, so no file’s `stat` would do.
  The ref chooser’s row watches it, to name the branch a terminal or an agent checks out
  ([The Ref Selector](../../design-system.md#the-ref-selector)).
- **The poll.** `FileWatches.run` asks each distinct watched path’s generation every
  `FILE_WATCH_POLL_INTERVAL_S`, and sooner after the relay sees an inventory change at a
  watched path, an ancestor, or a `-suffix` sidecar, but never within
  `FILE_WATCH_MIN_SPACING_S` of the end of the last poll.
  The relay asks that of every inventory change on the event loop, so `FileWatches`
  keeps an index of every watched path and its ancestors, and the question is two
  lookups for each changed path, measured beside the index.
  Each connection that saw another generation gets one `file.changed`, so a burst
  between two polls is one event.
  A path is compared as soon as it is sampled, and only with an entry written before the
  sample, so a registration answered meanwhile is never sent an older generation.
  Every watched path is polled, the ones the inventory reports too, since which paths
  the inventory covers depends on its ignore rules and its watcher’s state; the cost per
  path is measured beside `FILE_WATCH_MAX_PATHS`.
- **Delivery.** A `file.changed` is queued on its one connection under the overflow rule
  every event follows, and a connection that ends, or is sent `fs.resync_required`,
  drops its watches.
- **The page.** `static/file-watches.js`, loaded on demand by `metabrowser.watchFile`,
  keeps the page’s watches.
  `app.js` hands it each snapshot’s connection and each `file.changed`. Every new
  connection, after a resync, a server restart, or a page restored from Back
  (`createPageConnections`), registers every watch again with the generation it holds; a
  registration refused for an unknown connection waits for the next snapshot
  (`tests/dom/page-connections-session.js`). A watch released is unregistered whenever a
  registration of it was sent on the connection now open, answered or not, so leaving
  views faster than the server answers never fills the bound; a watch refused for
  another reason, such as `too_many_watches`, registers again once another watch has
  been unregistered. While the page is hidden its watches are unregistered, so a tab
  nobody looks at costs the server no polls, and shown again each registers with the
  generation it holds (`tests/dom/file-watches-session.js`).
- **Containers.** A container in the tree whose children were read follows its file
  (`createContainerFollower`): changes gather for `CONTAINER_COALESCE_MS`, one read of
  its children runs at a time with one more if a change came during it, the children are
  drawn again only when they differ, a collapsed container reads them on its next
  expand, and a row the tree drops releases its watch.

The table view refreshes on a change
([Data Tables](../../design-system.md#data-tables)), and a container in the tree reads
its children again
([Navigation Containers](arch-plugin-system.md#navigation-containers)).

## The Catalog Feed

The Quick File catalog is the set of unignored files the palette searches.
Bulk state does not ride the event stream: `GET /api/catalog` is a plain JSON response,
so gzip compresses it, its `ETag` makes a refetch after reconnect a `304`, and encoding
runs off the event loop.
Live changes arrive as `catalog.change`, which rides every scope unfiltered, so it is
also the browser’s only notice of a file change deeper than the tree stream.

`static/catalog-feed.js` owns no `EventSource`; `app.js` forwards events to it.
Deltas observed before a bulk payload is committed fold into that payload’s staged
transaction, and the store swaps one complete state and immutable snapshot, then queues
one invalidation, so a completeness subscriber never sees the bulk payload without its
buffered deltas. Changes larger than one slice use the same bounded scheduler, and
cancellation never publishes a partial stage.

The catalog keeps safe canonical POSIX-relative paths in ascending UTF-16 code-unit
order. `static/known-file-catalog.js` rejects absolute, empty-segment, dot-segment,
backslash, NUL, trailing-slash, and unpaired-surrogate spellings at every ingestion and
removal seam, so binary-search consumers share one contract, and sets no path-length
ceiling. Removal semantics are explicit:

- `remove_files` names files made ineligible by an ignored upsert; each is one exact
  delete, except a file the user opened explicitly, which stays.
- `non_file_paths` names retained files the provider observed becoming directories or
  symlinks; the browser deletes those exact paths and keeps any files under a
  replacement directory.
  The provider carries this transition through the change contract because the bus
  rereads current entries and cannot reconstruct their prior types.
- `removes` names paths that disappeared, which may be directories, so the browser
  deletes each exact-or-descendant interval found by lexical bounds.

`tests/dom/known-file-catalog-behavior.js` pins membership, ordering, provenance, and
atomicity.
`tests/dom/catalog-feed-large-session.js` drives the production modules over a
large catalog without a browser and bounds each change by the array elements it touches,
counted through `tests/dom/array-work-meter.js`, rather than by wall-clock time.

## Live Log Tailing

An open JSONL log streams on its own connection, `GET /api/stream?path=&cursor=`
(`sse.py`), which `app.js` opens for the log being viewed.
The route stats the file every `_TAIL_POLL_INTERVAL_S`, reads at most `_MAX_BATCH_BYTES`
of new bytes per cycle, parses complete lines with the same adapters as the polled view,
and sends an `append` event whose id is the byte cursor of the last complete line, so an
automatic reconnect resumes through `Last-Event-ID`. A rotated, truncated, missing, or
oversized file ends the stream with a `closed` event naming why.
Only `.jsonl` files under `_LARGE_FILE_BYTES` stream; a compressed or larger file falls
back to `/api/file`.

## Pulled Aggregates

Aggregates are pulled on purpose: a directory’s numbers change with every write beneath
it, and a pull lets the browser ask at its own cadence.

- **`/api/rollup`** serves Overview and Treemap.
  During a scan it answers with what has been counted, and the view labels it as in
  progress and refines it.
  The SDK’s `watchRollup` refetches when an inventory change touches its path;
  `createInventoryWatch` (`static/inventory-scope.js`) bounds its debounce by one
  window, because a scan emits changes continuously and a debounce that restarted on
  each would never fire.
- **`/api/tree`** answers two questions, chosen by `depth`. With `depth` absent or
  positive it returns rows; absent means `DEFAULT_TREE_DEPTH` (`tree.py`), not
  unbounded. For the root with `depth=0` it returns no rows, only the index-wide tallies
  behind the type and recency menus, which cost a pass over the index.
  Every tally field is nullable, so a row request never pays for tallies.
- **Root tallies are one request at a time.** A live tree upserts its root on every
  write. `createRootSummaryRefresh` (`static/navigation.js`) answers every ask made while
  a request is in flight with one request after it, spaces requests by the last one’s
  cost, and asks nothing while the page is hidden or no summary is on screen, so a page
  never holds a pile of identical requests.

`resource-context.js` multiplexes path-scoped envelopes, so several views of one path
share one fetch.

## The Browser’s Stores

| Store | Module | Fed by |
| --- | --- | --- |
| `fileStore` | `app.js` | `fs.snapshot`, then `fs.change`; the source of tree decoration |
| Directory totals | `directory-totals-store.js` | Directory entries in the same events; the plugin-visible cache |
| Known-file catalog | `known-file-catalog.js`, `catalog-feed.js` | `/api/catalog`, then `catalog.change` |

Applying an operation patches the store and the rendered row together, so a live update
does not re-render the tree.
A snapshot is applied atomically: the store is rebuilt before any subscriber is
notified, rows that are gone are retired, and the rest are patched in place.
Envelopes such as rollups and folder facts are replaced whole when a relevant change
arrives. View and shell state are described in [Browser Shell](arch-browser-shell.md).

## Recovery

A gap in the stream is a state, not an error.
On `fs.resync_required` the browser clears the known-file catalog, notifies `fileStore`
subscribers of a resync, restarts index progress polling, schedules an authoritative
Recent refetch, and replaces the connection.
It keeps `fileStore` and its rendered rows as the baseline: emptying them would collapse
the tree for the whole reconnect delay and lose expanded folders, during exactly the
bursts that cause an overflow.
The reconnect’s snapshot retires only rows that are gone.
Each new connection also refetches the catalog to cover deltas lost while disconnected
(`tests/test_browser_client_filestore.py::test_resync_event_reconnects_for_a_fresh_snapshot`).

`EventSource` reconnects on its own after transient errors.
Over that, `app.js` counts consecutive errors and, past `_ES_MAX_CONSECUTIVE_ERRORS`,
closes and recreates the connection with exponential backoff capped at
`_ES_BACKOFF_CAP_MS`. The backoff resets only after a connection survives
`_ES_STABLE_CONNECTION_MS`; resetting on open would let an overflow and resync cycle
reconnect tightly forever
(`tests/test_browser_client_filestore.py::test_event_source_backoff_resets_only_after_a_stable_interval`).
A page the browser keeps for Back closes its connections and reopens them when it is
restored, so a tab holds one connection however many pages its history keeps
(`createPageConnections` in `static/navigation.js`).

## Placeholders Are Not Measurements

A value the producer knows is provisional stays distinguishable from a real one all the
way to the pixel. A directory has no totals until discovery has finalized it, so the
directory totals store zero-fills its aggregate and marks it `state: "pending"`, and
`normalizeFolderTotals` (`builtin_plugins/folder/folder-totals.js`) lets an explicit
pending state win over the numbers beside it rather than reading the zeros as a settled
“0 files.”

Where two provisional sources meet, the folder Overview takes the provider’s finalized
aggregate when it exists and the rollup otherwise.
During a scan both are lower bounds that only grow and either can be the stale one, so
the panel takes whichever has counted more, whole, never mixing fields, and never
replaces numbers on screen with a spinner.

## Freshness

A `304`, or a quiet stream, means the index has not changed
([Validators and Caching](arch-server-and-content.md#validators-and-caching) says why).
It means the filesystem has not changed only while the provider is observing it:

- **Observation latency** depends on the provider’s observer: one that polls sees a
  change late, never not at all.
  [The Watcher](arch-inventory-engine-python.md#the-watcher) says when the Python engine
  polls.
- **A failed observer** marks the provider’s freshness stale with an `observation_gap`
  issue, and the bus projects it as a `capability.update` whose watcher state is
  `failed`. Nothing downstream can tell a quiet filesystem from a dead watch, so the
  failure is announced.
- **The cap** stops observation; see [The Cap](arch-inventory-provider.md#the-cap).

`/api/capabilities` reports the watcher’s mode and state, the index’s completeness, and
`events.stream` as `live` or `polling` with a reason.
None of these limits comes from the validators: a request that recomputed its body from
scratch would return the same answer from the same index.
What validators change is that a stale index is visible: a client that keeps receiving
`304` is being told the server has seen nothing.

## Invariants

Each has a test that fails when it breaks.

1. A connection receives a snapshot and then every newer change, with no stale delta and
   no gap
   (`tests/test_browser_events_route.py::test_snapshot_handoff_drops_a_change_already_covered_by_the_snapshot`).
2. A consumer that falls behind gets `fs.resync_required`, never a suffix presented as
   complete
   (`tests/test_browser_events_route.py::test_event_bus_overflow_restarts_slow_connection`).
3. A resync keeps the rendered tree and replaces the connection
   (`tests/test_browser_client_filestore.py::test_resync_event_reconnects_for_a_fresh_snapshot`).
4. A value marked provisional never renders as a settled measurement
   (`tests/test_browser_client_filestore.py::test_tree_tooltips_do_not_coerce_pending_aggregates_to_zero`).
5. A client that disconnects cancels only its own wait, never a shared computation
   (`tests/test_rollup_route.py::test_disconnecting_client_does_not_cancel_shared_build`).
6. Every conditional response builds its validator in `http_caching.py`
   (`tests/test_http_caching.py::test_no_module_builds_its_own_validator`).
7. A watch that fails announces it rather than ending quietly
   (`tests/test_browser_watch_backends.py::test_watcher_announces_a_failed_watch_instead_of_dying_silently`).
8. A change between a page’s read and its file watch’s registration reaches the page
   (`tests/test_file_watches.py::test_a_change_before_registering_is_answered_not_lost`).

## References

- [Inventory Provider Contract](arch-inventory-provider.md): `changes()` and its
  guarantees
- [Server and Content](arch-server-and-content.md#validators-and-caching): validators
  and retained bodies
- [Real-Time Debugging](../../realtime-debugging.md): observing this path
- [File Rollup Format](file-rollup-format/file-rollup-format.md): the aggregation
  contract

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
