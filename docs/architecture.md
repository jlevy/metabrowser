# Architecture

**Status:** Describes the code on `main`. Each layer’s document carries its own status
line; the aims below say which parts ship and which are planned, and link the plans.

Metabrowser is a local, live browser for everything you and your coding agents work
with: files, Markdown, logs, data, diffs, commits, and pull requests.
It is a Python server, a browser shell, and a manifest-driven plugin system, shipped as
one package, with an optional native Mac app around them.
Core owns safe file access, the inventory, live updates, Git, and the plugin lifecycle;
plugins own how each kind of file is drawn.

## Aims

Each aim ships in part today; the planned rest links its plan.

- **Agents show you content.** The `metabrowser` agent skill
  (`skills/metabrowser/SKILL.md`) lets an agent hand you a path or a pull-request URL in
  the macOS app, or serve it and hand you the page.
  `metab --api`, `--show`, and `--walk` give an agent the same data the page draws,
  which the [Parity Registry](project/architecture/arch-parity-registry.md) enforces,
  the `agents` plugin draws coding-agent logs as timelines, and the `event-log` plugin
  draws Metabrowser’s own event log as spans, latencies, and failures
  ([Real-Time Debugging](realtime-debugging.md#browsing-the-log)). `metab --present`
  hands a folder, a file, or a GitHub URL to the macOS app; planned: a reply from the
  app, and a browser when there is no app
  ([native macOS app plan](project/specs/active/plan-2026-11-10-native-macos-app.md),
  Phase 3).
- **Local, in your browser or a Mac app.** `metab` serves on `127.0.0.1` by default to
  any browser; `--remote` reaches another host over an SSH tunnel; cached repositories
  read offline. The native macOS app is an alpha built from source
  ([macOS app](project/architecture/arch-macos-app.md)). Planned: a signed, notarized
  download.
- **Live and large.** The served tree is watched and its changes stream to the page;
  indexing runs in the background, so the first view does not wait for a full crawl; and
  serving stops at `INVENTORY_MAX_FILES` (`settings.py`).
  [Scale Benchmark](scale-benchmark.md) measures it.
  Planned: a second inventory engine behind the provider contract
  ([inventory provider plan](project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md),
  Phase 2), and a million-file tree browsed rather than cut off
  ([load-time plan](project/specs/active/plan-2026-08-21-load-time-performance.md)).
- **Any file type, through plugins.** Kinds and views come from plugin manifests, and
  every built-in view is a plugin under `builtin_plugins/`, gated by
  `PLUGIN_SDK_VERSION` (`plugin_loader/manifest.py`). Planned: editing
  ([trusted-local editing plan](project/specs/active/plan-2026-07-16-trusted-local-file-editing.md)).
- **Git and GitHub review.** The Commits tab and `/commit/<rev>` pages, `metab --diff`
  for any range, and the Pulls tab and pull-request pages with conversation, reviews,
  inline comments, checks, and stacks; a cached pull request reads offline.
  Planned: working-tree status and diffs
  ([Git status plan](project/specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md)).

## Layers

```text
metab CLI (cli/)                          native macOS shell (apps/macos/)
  │ serves, or answers --api in process     │ runs one metab server per folder
  ▼                                         ▼
server and routes (server.py)  ◄──  kinds and plugin system (plugin_loader/)
  ├─ source session (source.py): a folder’s working tree, or a pinned revision
  ├─ inventory provider (inventory_engine/): the contract above, an engine below
  ├─ live delivery (events_route.py): the change feed as server-sent events
  ├─ Git (git/) and diff (diff/)
  └─ repository cache and mirrors (cache/), GitHub provider (builtin_plugins/github/)
  │ HTTP and server-sent events
  ▼
browser shell and SDK (static/)  ──►  renderers (builtin_plugins/*/)
```

Module paths are under `src/metabrowser/` unless they start with `apps/`.

| Layer | Modules | Job | Document |
| --- | --- | --- | --- |
| CLI | `cli/` | Parse the one flat command, start the server and open the page, run `--api`, `--show`, `--walk`, and `--diff` in process, and tunnel to a remote host | [CLI](project/architecture/arch-cli.md) |
| Server and routes | `server.py`, `view_routes.py`, `paths_safe.py`, `gz_io.py`, `http_caching.py`, `asset_stamps.py`, `inert_html.py`, `kpress_adapter.py` | Resolve every path beneath the served root, answer envelopes, raw bytes, and assets, and apply the content-trust model | [Server and Content](project/architecture/arch-server-and-content.md), [the map](project/architecture/arch-views-models-routes.md) |
| Inventory provider and engine | `inventory_engine/` (`contract.py`, `coordinator.py`, `factory.py`, engines under `providers/`), `inventory_rollup.py`, `file_type_registry.py`; the Python engine’s `walker.py` and `watch_backends.py`; `walk.py` for `--walk` | Hold a bounded index of the served tree and answer bounded, versioned queries over it | [Inventory Provider](project/architecture/arch-inventory-provider.md), [Python Engine](project/architecture/arch-inventory-engine-python.md) |
| Live delivery | `events.py`, `events_route.py`, `sse.py`, `active_tracker.py`, `activity.py`; `static/catalog-feed.js` | Carry the provider’s change feed to the browser’s stores, and recover a client that falls behind | [Live Delivery](project/architecture/arch-live-delivery.md) |
| Git | `git/` | Run every Git command on a served repository through one bounded process boundary (`git/process.py`), and serve history, graph checkpoints, commit detail, and Git trees | [Git](project/architecture/arch-git.md) |
| Source sessions and pins | `source.py`, `source_routes.py`, `root_identity.py`; `static/source-pin-guard.js` | Hold the one view a server shows, a folder’s working tree or a pinned revision, with its capabilities, and switch the pin | [Open Modes](project/architecture/arch-open-modes.md), [Source Sessions and Pins](project/architecture/arch-source-sessions-and-pins.md) |
| Diff | `diff/`, `builtin_plugins/diff/` | Build change sets from patch files, commits, and pull requests in File Diff Format, and hydrate them file by file | [Diff Pipeline](project/architecture/arch-diff-pipeline.md) |
| Repository cache and mirrors | `cache/`, `mirror_refresh.py` | Acquire repositories into the application cache as mirrors, keep their records, and refresh them in the background | [Repository Cache](project/architecture/arch-repository-cache.md), [Mirror Acquisition and Refresh](project/architecture/arch-mirror-acquisition-and-refresh.md) |
| GitHub provider | `builtin_plugins/github/`, behind `cache/providers.py` | Reduce GitHub URLs to sources and pins, and serve pull-request records, the catalog, changed files, checks, and stacks through `gh` | [GitHub Pull Requests](project/architecture/arch-github-pull-requests.md) |
| Kinds and plugin system | `plugin_loader/`, `plugin_api.py`, `file_kinds.py`, `builtin_plugins/*/manifest.toml` | Discover and validate manifests, classify files into kinds, mount data hooks and plugin assets, and gate the SDK version | [Plugin System](project/architecture/arch-plugin-system.md), [the map](project/architecture/arch-views-models-routes.md) |
| Browser shell and SDK | `static/` (`app.js`, `navigation.js`, `main-tabs.js`, `plugin-sdk.js`, `asset-loader.js`) | Own navigation, the tree, tabs, client stores, view mounting and disposal, asset loading, and the `window.metabrowser` SDK | [Browser Shell](project/architecture/arch-browser-shell.md), [Plugins](plugins.md) |
| Renderers | `builtin_plugins/*/` views; KPress for Markdown | Draw each kind within the bounds of the large-content rules | [the map](project/architecture/arch-views-models-routes.md), [Rendering Large Content](large-content-rendering.md), [Design System](design-system.md) |
| Recent targets | `recent_targets.py`, `cli/recent_cli.py` | Keep the one list of folders and repositories the user opened lately, which every shell reads through `metab` | [Recent Targets](project/architecture/arch-recent-targets.md) |
| Native macOS shell | `apps/macos/` | Supervise one `metab` server per folder and show it in an AppKit window with `WKWebView`: windows, recent items, and restore | [macOS App](project/architecture/arch-macos-app.md) |

## Rules That Cross Layers

- **One artifact.** The server, the browser shell, and the built-in plugins ship
  together. A page takes its settings, inlined, and its assets, at content-stamped
  addresses, from the server that answered it, so `/api/*`, `window.metabrowser`, and
  the plugin manifest are internal contracts that change everywhere in one commit
  ([Compatibility and Legacy Code](development.md#compatibility-and-legacy-code)). A
  page already open keeps the scripts it loaded until it is reloaded.
- **The engine sits behind a provider contract.** Everything above
  `inventory_engine/contract.py` relies only on what a provider guarantees, so the
  engine can change without the layers above it.
  One exception: `metab --walk` (`walk.py`) drives the Python walker directly, to show
  what it yields, so it does not go through the provider.
  `inventory_engine/factory.py` lists the engines a build ships, and
  `METABROWSER_INVENTORY_PROVIDER` selects one.
  Engine detail (the walker, its threads, the watcher backend, and unit costs) lives
  only in the [Python Engine](project/architecture/arch-inventory-engine-python.md)
  document.
- **Core is consumer-agnostic.** Core knows generic capabilities and the built-in kinds;
  domain schemas, routes, renderers, and styles belong in plugins, which use only the
  `window.metabrowser` SDK.
- **Every surface has a command line.** Each route the page reads is pinned by a golden
  transcript through `metab` or exempt with a stated reason, and each user-visible
  behavior has a parity row ([AGENTS.md](../AGENTS.md#cli-and-functional-ui-parity),
  [Parity Registry](project/architecture/arch-parity-registry.md)).
- **Work is bounded.** Reads and synchronous work on a request path are bounded, and a
  bound is set at a measured size, with the measurement beside its constant
  ([Rendering Large Content](large-content-rendering.md)).

To add a file type, start with
[Adding Something](project/architecture/arch-views-models-routes.md#adding-something) in
the map and the [Plugin System](project/architecture/arch-plugin-system.md).

## Reading Order

1. This document, then
   [Views, Models, and Routes](project/architecture/arch-views-models-routes.md), the
   map of kinds, views, formats, and routes.
2. [Server and Content](project/architecture/arch-server-and-content.md): how a request
   is served and what content is trusted to do.
3. [Inventory Provider](project/architecture/arch-inventory-provider.md) and
   [Live Delivery](project/architecture/arch-live-delivery.md): what the server knows
   about the tree and how changes reach the page.
4. [Plugin System](project/architecture/arch-plugin-system.md) and
   [Browser Shell](project/architecture/arch-browser-shell.md): how kinds are claimed
   and views are mounted.
5. For Git and review: [Open Modes](project/architecture/arch-open-modes.md), the model
   of what a folder or a URL opens; then [Git](project/architecture/arch-git.md),
   [Source Sessions and Pins](project/architecture/arch-source-sessions-and-pins.md),
   [Diff Pipeline](project/architecture/arch-diff-pipeline.md),
   [Repository Cache](project/architecture/arch-repository-cache.md),
   [Mirror Acquisition and Refresh](project/architecture/arch-mirror-acquisition-and-refresh.md),
   and [GitHub Pull Requests](project/architecture/arch-github-pull-requests.md).
6. The entry points: [CLI](project/architecture/arch-cli.md) and
   [macOS App](project/architecture/arch-macos-app.md), and the list of
   [Recent Targets](project/architecture/arch-recent-targets.md) they share.
7. The standards, before changing a bound or a hot path.

## Architecture Documents

In `docs/project/architecture/`:

| Document | Subject |
| --- | --- |
| [arch-cli.md](project/architecture/arch-cli.md) | Modes, the serve lifecycle, in-process `--api` dispatch, remote tunnels, and process exit |
| [arch-server-and-content.md](project/architecture/arch-server-and-content.md) | Request flow, safe paths, validators, and the content-trust model |
| [arch-threat-model.md](project/architecture/arch-threat-model.md) | Assets, adversaries, trust boundaries, and each threat’s policy, evidence, and accepted risk |
| [arch-views-models-routes.md](project/architecture/arch-views-models-routes.md) | Kinds, views, formats, the URL grammar, and the route index |
| [arch-parity-registry.md](project/architecture/arch-parity-registry.md) | The route and functional-aspect tables `devtools/check_parity.py` reads |
| [arch-inventory-provider.md](project/architecture/arch-inventory-provider.md) | The engine-independent contract: queries, lifecycle, the cap, and change feeds |
| [arch-inventory-engine-python.md](project/architecture/arch-inventory-engine-python.md) | The Python engine: walker, concurrency, watcher backend, and unit costs |
| [arch-live-delivery.md](project/architecture/arch-live-delivery.md) | From the change feed to the browser’s stores: events, recovery, and invariants |
| [arch-git.md](project/architecture/arch-git.md) | The process boundary, history sessions, graph checkpoints, and commit detail |
| [arch-source-sessions-and-pins.md](project/architecture/arch-source-sessions-and-pins.md) | Subjects, capabilities, path projection, and the pin guard |
| [arch-diff-pipeline.md](project/architecture/arch-diff-pipeline.md) | Diff sources, hydration, caches, and Markdown projection |
| [arch-repository-cache.md](project/architecture/arch-repository-cache.md) | Cache layout, identity, record contracts, locks, and sweep |
| [arch-mirror-acquisition-and-refresh.md](project/architecture/arch-mirror-acquisition-and-refresh.md) | Transports, credentials, the lending checkout, and refresh cadence |
| [arch-github-pull-requests.md](project/architecture/arch-github-pull-requests.md) | Pull-request records, the catalog, files, checks, stacks, and routes |
| [arch-plugin-system.md](project/architecture/arch-plugin-system.md) | Manifests, discovery, classification, the SDK gate, containers, and adding a file type |
| [arch-browser-shell.md](project/architecture/arch-browser-shell.md) | Shell modules, stores, lifecycle, and asset loading tiers |
| [arch-macos-app.md](project/architecture/arch-macos-app.md) | Server supervision, windows, restore, and WebKit differences |
| [arch-app-contract.md](project/architecture/arch-app-contract.md) | What the macOS app reads of `metab`: the declaration, the golden of the whole surface, and the checks on both sides |
| [arch-recent-targets.md](project/architecture/arch-recent-targets.md) | The recent targets store, what records an open, its `metab` modes, and the app’s Open Recent |
| [arch-collection-format.md](project/architecture/arch-collection-format.md) | Collections: ordered annotated items, the format guided reviews carry |
| [file-diff-format/](project/architecture/file-diff-format/file-diff-format.md) | File Diff Format v1, a tool-neutral change-set format |
| [file-rollup-format/](project/architecture/file-rollup-format/file-rollup-format.md) | File Rollup Format, file classification and directory totals |

The contributor standards, in `docs/`:

| Document | Subject |
| --- | --- |
| [large-content-rendering.md](large-content-rendering.md) | What is expensive in a browser, and the rules for setting a limit |
| [web-performance-framework.md](web-performance-framework.md) | How a performance change is measured in a real browser while the page stays correct |
| [realtime-debugging.md](realtime-debugging.md) | Timing on both sides of the HTTP boundary, to place a slow preview |
| [engine-performance-model.md](engine-performance-model.md) | What may run once per entry, for any engine behind the provider contract |

[Project Design and Plans](project/README.md) indexes these with the plans, research,
and reviews behind them.
The [security policy](../SECURITY.md), [plugin guide](plugins.md),
[design system](design-system.md), [end-to-end testing](e2e-testing.md), and
[development guide](development.md) cover the rest of the contributor’s path.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
