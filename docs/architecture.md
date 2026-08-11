# Architecture

Metabrowser is a Python server, a browser shell, and a manifest-driven plugin system.
The package deliberately keeps file navigation, safe filesystem access, live updates,
and plugin lifecycle management in core while delegating file-kind rendering to plugins.

## Runtime Shape

The `metab` CLI starts a Starlette application with four main layers:

1. **Safe filesystem access.** `paths_safe.py`, `gz_io.py`, and the file endpoints
   resolve every requested path beneath the selected root.
   Gzip and zlib files retain their logical extension and can be read transparently
   within shared resource bounds.
2. **Inventory and change events.** `inventory.py` builds a bounded in-memory index.
   Watch backends and the active-file tracker publish normalized changes through the
   event bus and server-sent events.
3. **Plugin discovery and routing.** `plugin_loader/` validates manifests, compiles kind
   classifiers, serves plugin assets, and mounts optional Python data hooks.
4. **Browser shell.** `static/app.js` owns navigation, the tree, recent files, tabs,
   caching, and view mounting.
   `static/plugin_sdk.js` exposes the supported renderer API under `window.metabrowser`.

The browser loads critical local assets first.
Optional third-party assets enhance syntax highlighting, charts, or specialized
renderers after the shell can already paint a useful first view.

## Request Flow

Opening a file follows this sequence:

1. The URL hash or tree selection supplies a served-root-relative path.
2. `/api/file` safely resolves the path, determines its logical extension, and runs
   plugin classifiers before built-in fallbacks.
3. The response includes the chosen kind and the ordered view descriptors contributed by
   manifests.
4. The shell creates one container per view and resolves each `(kind, view)` pair in the
   JavaScript registry.
5. The default renderer mounts immediately.
   Other renderers mount lazily the first time their tab is selected.
6. A plugin may render from the file envelope, fetch a KPress view, or call one of its
   declared data hooks.

Replacing the preview pane disposes mounted plugin views.
Switching tabs does not: their DOM and captured state remain available until a different
file replaces the pane.

## Git

Read-only repository history lives in core, under `git/`, with its own endpoint
collection at `/api/git/` and its own wire model in `git/wire.py`.

Git is infrastructure here rather than a consumer domain: `ignore_filter.py` implements
gitignore semantics, `tree.build_gitignore_check` performs repository-root discovery,
and both the tree and recent wire models carry a `gitignored` flag.
History reading extends a dependency core already has.

Every git call goes through `git/process.py`, which spawns `git` with a fixed argument
vector, a wall-clock timeout, and a cap on buffered stdout.
Revisions are validated against a full-SHA pattern before they can reach an argument
vector. Git’s stderr is logged and dropped: it contains absolute local paths.

Swimlane layout is a browser concern.
The server returns commits, parents, and references; `static/git_graph.js` assigns lanes
and draws them, carrying lane state across pages.
This is the same split `recent.py` makes, where clustering belongs to the renderer.

## Plugin Boundary

Core knows only generic capabilities and built-in file kinds.
It does not contain consumer-specific schemas, endpoint routes, view identifiers, or
renderers. Transparent compression is a core filesystem capability because it applies
uniformly before classification and rendering.
Specialized binary stores and their value schemas belong in separately installed
plugins.

The nav-panel tab list is a registry in `app.js` rather than fixed markup, which is what
lets the Git tab appear only inside a repository.
No plugin-facing registration API is exposed for it yet: the registry is reachable
through `window.MetabrowserShell`, an internal seam for core modules, and is not part of
the `window.metabrowser` SDK contract.

Plugins own:

- classification rules for their domain formats;
- view declarations and labels;
- browser rendering and plugin-specific styles;
- optional extra scripts and styles;
- optional server-side extraction through declared data hooks.

The stable browser-side boundary is the `window.metabrowser` API. Plugins should not
reach into variables or functions defined privately by `app.js`. Cross-view navigation
uses `openPath`, and plugin HTTP calls use `fetchPluginData`.

## Startup and First Paint

The CLI binds before beginning expensive recursive work.
Inventory walking, ignore-file parsing, and watcher setup run without blocking the event
loop’s first response.

When a URL names an initial file, `/api/file` begins independently of tree indexing.
Without a hash, the server may seed a root `README.md` preview.
Inventory endpoints return current partial state plus progress metadata instead of
waiting for a complete walk.

The CLI opens a browser only after the index route returns an HTTP success response.
A free TCP port alone is not considered ready.

## Live Update Model

The inventory is the server-side source of truth.
Producers attach generation-aware write tokens so an observation made before
invalidation cannot overwrite newer state.
The event stream carries snapshot, change, and resynchronization events.

The browser keeps a normalized file store.
Tree panels and recent-file views subscribe to that store rather than maintaining
independent copies. If a client falls behind the bounded event buffer, it requests a
fresh snapshot.

## Where Filtering Happens

Navigation filtering is split across two tiers, and which tier owns a dimension is a
consequence of where the information lives rather than a preference.

**Client, over rendered rows.** Type, size, and gitignored visibility are decided in the
browser by walking the rows already in the DOM. Every predicate input — extension, byte
count, gitignore flag — is on the row before any filter runs, so this costs one pass and
no round trip, and it stays responsive while the user toggles.
Its ceiling is what has been rendered: a collapsed subtree is unknown, so the pass keeps
those folders and reports how many it could not speak for.

**Server, as the source of the tree.** Recency is different.
`/api/recent` scans the whole inventory rather than the loaded subtrees, which is the
one thing a DOM walk cannot do, so setting a recency window swaps the panel’s data
source instead of decorating it.
Gitignored visibility rides along as a request parameter because it changes what the
response cap is spent on, not just which rows are painted.

The extension tally behind the type menu comes from the index too
(`InventoryIndex.extension_tally`), because the Quick File catalog excludes gitignored
entries and a menu built from it would undercount everything the tree still shows.

### Response Caps Are a Ranking Problem

Any server-side filter that caps its response has to decide what to drop.
Newest-first alone is not enough: a dependency install touches thousands of files at
once, so a 2 000-row cap on a day window can be entirely `node_modules` while none of
the user’s own work appears.
`collect_recent_entries` therefore drops gitignored files before tracked ones and
re-sorts the selection, and reports `total_matching` and `truncated` so the client can
say what it is not showing.
Treat that as the rule for any future filtered endpoint: decide the priority order
before the cap, and report the shortfall.

### Moving More Filtering Upstream

Client-side filtering is bounded by what is rendered, so a very large directory reaches
a point where the honest answer needs the index.
The tiers are not fixed, and the vocabulary was built so a dimension can move without
changing what it means: `FilterState` holds the values, and the predicate helpers are
shared, so a dimension evaluated server-side still has to agree with the same
definition.

Worth understanding before moving anything:

- **What server-side filtering buys.** Completeness — an answer over the whole index
  rather than the expanded subset — plus the ability to filter what was never loaded,
  and aggregates that reflect the filter rather than the whole tree.
- **What it costs.** A round trip per change, so a control that felt instant becomes
  latency-bound; cache keys multiply by the filter combination; and every dimension
  evaluated in two places is a chance for the two to disagree.
- **Which dimensions are natural candidates.** Extension and size are cheap index
  predicates and compose with the existing recency scan.
  Activity is not: the tracker’s live set is small, client-held, and already complete.
- **The rule of thumb.** Move a dimension upstream when its client-side answer is
  *incomplete*, not when it is slow.
  Incompleteness is a correctness problem and the user cannot see it; slowness they can.

Two things should stay true whichever tier owns a dimension: with no filters set the
rendered DOM is unchanged from an unfiltered render, and any filter that cannot see the
whole tree says so rather than implying completeness.

## Caching

File responses use stable ETags derived from file metadata.
Expensive projections use mtime-aware caches whose keys change when file size or
modification time changes.
Changing the served root clears root-scoped caches.

Plugins should keep domain caches on their own side of the boundary.
Core provides no global plugin payload cache.

## Package Layout

```text
src/metabrowser/
├── builtin_plugins/   # Built-in manifests and renderers
├── cli/               # serve, remote, walk, and plugins commands
├── git/               # Read-only history: process, repo, log, detail, wire, routes
├── logutil/           # Generic agent-log normalization
├── plugin_loader/     # Discovery, manifests, classification, and routes
├── static/            # Browser shell, SDK, charts, icons, and styles
├── inventory.py       # In-memory filesystem index
├── server.py          # Starlette application and HTTP endpoints
└── watch_backends.py  # Filesystem change producers
```

Tests mirror these layers.
Node `vm` shims validate browser-side plugin registration without adding a full DOM
dependency, while Python integration tests exercise the real application lifespan and
route stack.

## Related Documentation

- [Security policy and content trust model](../SECURITY.md)
- [Plugin authoring](plugins.md)
- [Design system](design-system.md)
- [End-to-end testing](e2e-testing.md)
- [Real-time debugging](realtime-debugging.md)
- [Development](development.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
