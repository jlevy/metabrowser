# Architecture

MetaBrowser is a Python server, a browser shell, and a manifest-driven plugin system.
The package deliberately keeps file navigation, safe filesystem access, live updates,
and plugin lifecycle management in core while delegating file-kind rendering to plugins.

## Runtime Shape

The `metab` CLI starts a Starlette application with four main layers:

1. **Safe filesystem access.** `paths_safe.py`, `gz_io.py`, and the file endpoints
   resolve every requested path beneath the selected root.
   Gzipped artifacts retain their logical extension and can be read transparently.
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

## Plugin Boundary

Core knows only generic capabilities and built-in file kinds.
It does not contain consumer-specific schemas, endpoint routes, view identifiers, or
renderers. Transparent compression is a core filesystem capability because it applies
uniformly before classification and rendering.
Specialized binary stores and their value schemas belong in separately installed
plugins.

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

- [Plugin authoring](plugins.md)
- [Design system](design-system.md)
- [End-to-end testing](e2e-testing.md)
- [Real-time debugging](realtime-debugging.md)
- [Development](development.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
