# Plan: Plugin Sources and Out-of-Process Plugin Environments

**Date:** 2026-11-12

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Draft. Epic `mb-xbw3` tracks every item below as a bead.
Nothing is implemented yet; a spike proved the stdio hook transport.

## Overview

A system-installed Metabrowser, meaning the `metab` uv tool and the macOS app that runs
it, should use a new plugin without being reinstalled.
Today every Python plugin must be installed into Metabrowser’s own environment, which
rewrites that environment and, for the motivating domain plugin, cannot resolve at all.

This plan lets the user register **plugin sources** (directories, Python environments,
managed packages, and opt-in project declarations) in Metabrowser’s configuration home.
Metabrowser reads each plugin’s manifest and serves its assets itself, and runs its
Python in a **worker**: a small process started with the plugin environment’s own
interpreter, which serves data hooks and log parsing over stdio.
Plugin code imports a small, stdlib-only **plugin SDK** package instead of Metabrowser,
so a plugin environment never has to resolve against Metabrowser’s dependencies.

The evidence, the reproductions, and the alternatives rejected are in
[Loading Plugins from Any Source](../../research/research-2026-11-12-plugin-sources.md).

## Goals

- Adding, removing, or updating a plugin never reinstalls Metabrowser.
- A plugin’s Python dependencies never conflict with Metabrowser’s or another plugin’s.
- The macOS app uses exactly the sources the CLI uses, and adds only native consent and
  settings UI.
- Nothing served content or a browser page can do adds code that Metabrowser runs.
- A host release refuses a plugin only when the plugin needs something the host lacks or
  uses something the host removed, and says which.
- Every source, every persisted record, and every check is a `metab` mode or route with
  a golden transcript.
- Plugin authors can test hooks, adapters, and assets against the real host from their
  own repositories.

## Non-Goals

- Sandboxing plugin code.
  A worker runs with the user’s privileges, like any program the user installs;
  isolation here is of dependencies, crashes, and CPU, not of authority.
- Plugins for Git sources opened from a URL, pins, or `--untrusted` sessions beyond the
  built-ins and the user’s registered sources.
- A plugin marketplace, index, or signature scheme.
- Streaming data hooks; none exists today.

## Background

[The research brief](../../research/research-2026-11-12-plugin-sources.md) reproduces,
on the macOS app’s branch:

- discovery imports entry points from the running interpreter only, once, at server
  import;
- `--plugins-dir` plugins lose every data hook and never register their log adapters, so
  adapter-classified kinds fall back to generic JSONL;
- `uv tool install metabrowser --with <plugin>` has no solution, because Metabrowser
  pins `softschema==0.8.1` and the plugin needs `>=0.9.1,<0.10`;
- the app cannot pass a plugin directory to a server at all;
- an in-process overlay of the plugin environment silently binds the plugin to the wrong
  Softschema, and subinterpreters refuse `pydantic_core`.

A spike proxied the downstream plugins’ hooks to a stdlib-only worker in their own
environment, which held Metabrowser 0.9.1, from a 0.12.1 host: 0.13–0.17 ms median round
trip for a trivial hook, 10–27 ms of transport on a 429 KB response, exit within 5 ms of
stdin closing, and 61–121 MB per worker.
It also measured the two costs this design has to answer: CPU contention inside the
process that runs a heavy hook, and proxied log parsing at 2.5–3.5 times the parse.

The [native macOS app plan](plan-2026-11-10-native-macos-app.md) runs one `metab` server
per folder as a child, from a CLI install, with an allowlisted environment.
Its Phase 5 deferred project-provided plugins to a trust spec (`mb-m1mw`); this plan is
that spec.

## Design

### Principles

- **Register a source; never install into Metabrowser.** Metabrowser’s environment holds
  Metabrowser. Plugins live in environments the user or Metabrowser manages beside it.
- **The host owns manifests and assets; workers own plugin code.** The server reads
  every manifest with its own schema and serves static files from the plugin directory,
  so a worker is needed only for Python.
- **Third-party Python runs out of process.** Built-ins stay in the server.
  Every other Python plugin runs in a worker on its environment’s interpreter, including
  entry points installed into Metabrowser’s own environment (Phase 2), so there is one
  code path, a crash or hang ends only its worker, and a heavy hook no longer takes the
  server’s GIL.
- **Nothing the page can reach changes what runs.** Plugin JavaScript shares the page’s
  origin with every other plugin, so no route writes the registry or records trust; CLI
  modes do, and the app’s native settings run them.
- **One representation, every surface.** The registry, each source’s state, and each
  check are a model served by `metab --plugins --json`, `metab --doctor --json`, and
  `GET /api/plugins`, with goldens.

### Sources

| Source | Added by | Recorded in | Applies to | JavaScript | Hooks and adapters |
| --- | --- | --- | --- | --- | --- |
| Built-ins | the release | the wheel | every root | yes | yes, in the server |
| Entry points in Metabrowser’s environment | whoever installs into it | that environment | every root | yes | yes, in a worker on Metabrowser’s interpreter (in the server until Phase 2) |
| Registered directory | the user: `metab --plugins-add DIR` | `plugins.yml` | every root | yes | no |
| Registered environment: a venv, a uv project, or a uv tool’s environment | the user: `metab --plugins-add PATH` | `plugins.yml` | every root | yes | yes, in a worker |
| Managed package (Phase 4) | the user: `metab --plugins-install REQUIREMENT` | `plugins.yml`, environment in the data home | every root | yes | yes, in a worker |
| Project declaration (Phase 5) | the repository declares; the user trusts | `.metabrowser/plugins.toml` in the root; trust in `plugins.yml` | that root only | yes | yes, in a worker |
| `--plugins-dir DIR`, `--plugins-env PATH` | the operator, for one command | nothing | that process | yes | an environment’s, in a worker |
| A `--remote` session | the remote host’s user | the remote host’s registry | the remote root | as on that host | as on that host |

Later sources win a plugin-name collision, in the order of the table, and `--doctor`
reports every collision.
Two entries that resolve to the same interpreter are one source.
A registered environment is whatever its interpreter imports; for the downstream
application repository, registering its uv project brings all three plugins at once.

A registered environment needs the plugin SDK installed (see below), since the worker is
the SDK’s module. `--plugins-add` says so and names the range to add when it is missing.

### The Registry

`plugins.yml` lives in the configuration home (`METABROWSER_CONFIG_DIR`,
`XDG_CONFIG_HOME/metabrowser`, or `~/.config/metabrowser`) beside `config.yml`.

- It is a record with its own Softschema contract, `metabrowser:PluginSources/0.1`,
  enforced, because Metabrowser is its only writer.
  CLI modes write it by atomic replace under the home’s lock.
- It names code to run, so it is read through the home’s verified reader with sharing
  refused rather than repaired: a registry another account could have written is not
  used, and `--doctor` says why.
- Serving reads it when it exists and never creates the home, so browsing a folder still
  touches no state.

```yaml
softschema:
  contract: metabrowser:PluginSources/0.1
  envelope: plugins
  status: enforced
plugins:
  sources:
    - id: workflow
      kind: environment
      interpreter: ~/src/workflow/.venv/bin/python
      project: ~/src/workflow
      added_at: 2026-11-12T10:00:00Z
      added_by: 0.13.0
    - id: viewers
      kind: directory
      path: ~/metabrowser-plugins
  project_trust:
    - root: ~/src/app
      declaration_sha256: 3b4f…
      granted_at: 2026-11-12T10:05:00Z
```

Listing an environment means importing its entry points, which costs 250–400 ms for
three plugins (measured).
The result is cached in the cache home, keyed by a fingerprint of the environment: the
interpreter’s file identity and the modification times of its `site-packages`, each
`*.dist-info`, and each `*.pth`. A server starts from the cache and from the manifests,
which it reads itself, so registering a source adds no startup process; a stale
fingerprint re-lists in a worker.

### Trust and Consent

| Source | Who may add it | How the user approves it |
| --- | --- | --- |
| Registered directory or environment | the account owner, through `metab` | naming the path is consent to run that interpreter; `--plugins-add` lists what it found and asks before recording (`--yes` for scripts) |
| Managed package | the account owner, through `metab` | as above, after the install and before recording |
| Project declaration | the repository proposes; the account owner trusts | `metab ROOT --plugins-trust`, or the app’s confirmation, after reading the declaration |
| Per-invocation flags | whoever runs the command | the command line itself |

- **Only the owner can add a source.** The registry lives in the owner-only
  configuration home, which `home.py` refuses when another account can write to it or to
  any directory above it.
- **No route writes the registry or trust.** Any plugin’s JavaScript runs in the page
  and can call any same-origin route, so a write route would let a JavaScript-only
  plugin register Python.
  This is the one deliberate gap in route parity: the parity table lists the CLI modes
  as the surface and this reason.
- **Served content still cannot opt in.** A `.env` file cannot name a source, the served
  root is never an automatic source, and the agent front door (`metab TARGET --present`)
  never changes sources.
  An agent with a shell can run `metab --plugins-add`, as it can run `uv tool install`
  today; the Metabrowser skill tells agents to ask the user first.
- **Project declarations are data until trusted.** A declaration names directories and
  environments by paths that must resolve inside the root, and nothing in it runs before
  trust. Trust is keyed by the canonical root and the SHA-256 of the declaration, so a
  changed declaration is untrusted until approved again.
  Changes to code inside a trusted environment do not ask again, the same as running
  `uv sync` in a registered environment; a reviewer who wants to see each change keeps
  the plugin out of the declaration.
  Project plugins never load for Git sources opened from a URL, pins, mirrors, or under
  `--untrusted`.
- **Plugin code has the app’s privacy grants.** Under the app, a worker is a descendant
  of the app, and macOS attributes a descendant’s file access to the app (inferred), so
  plugin code can read what the user let Metabrowser read.
  The add and trust confirmations say so.

### Process Model

- **One worker per server and environment.** All plugins of one environment share a
  worker; a server never shares a worker with another server, so a worker serves one
  root.
- **Started on evidence, not at startup.** A worker starts at the first hook call or
  parse for one of its plugins, or when the server first classifies a file into a kind
  that plugin owns, so the hook the view issues next does not pay the 70–90 ms spawn and
  the module imports. It exits after an idle period, which Phase 1 measures before
  choosing; ten minutes is the starting point.
- **Spawned like the server.** `<interpreter> -I -m metabrowser_plugin_sdk.worker`, with
  the server’s working directory, the server’s environment without Metabrowser’s
  capability variables, and `PYTHONNOUSERSITE=1`. It stays in the server’s process
  group, so the app’s group stop reaches it, and its stdin is the lifeline: it exits
  when the server’s end closes, measured at 4–5 ms.
  Its stderr goes to the server’s log, prefixed with the source id; plugin code that
  prints to stdout is redirected to stderr so it cannot corrupt the protocol.
- **Failures stay in the worker.** A worker that exits is restarted at the next request.
  One that exits three times in a minute is marked failed until its environment’s
  fingerprint changes or the user reloads, and its hooks answer the existing degraded
  `plugin_error` envelope.
- **Bounded calls.** Each call carries a deadline (a default, overridable per hook in
  the manifest); a client disconnect sends `cancel`. A request body is at most 1 MiB and
  a response at most 64 MiB, the bound `jsonl_view` already applies to a parse; the
  largest response measured was 429 KB. Response headers pass through an allowlist
  (`content-type`, `etag`, `cache-control`, `last-modified`, `content-disposition`), and
  the host adds `Server-Timing` with the handler’s time.

### The Plugin SDK

`metabrowser-plugin-sdk` (imported as `metabrowser_plugin_sdk`) is a uv workspace member
of this repository, released with Metabrowser, stdlib-only, for Python 3.12 and later.
It holds what plugin Python needs and what the host and worker must agree on, each with
one implementation:

- the inventory identity codec, moved from `inventory_engine.contract` (the host imports
  it from the SDK);
- `resolve_path`, `resolve_directory`, `relativize_path`, `served_root`, and
  `register_root_callback`, bound to the session’s subject;
- `ArtifactPath` and its errors, moved from `gz_io`, which already uses only `gzip` and
  `zlib`;
- the content reader (`resolve_content`, `read_content_window`, `stat_content`, and
  `ContentReadError`), which in a worker calls the host, so it works on a Git pin and
  keeps the host’s bounds;
- `LogEvent`, the parser protocol, and `register_log_parser`;
- host services that stay host computations, such as the agent-log chart projection;
- `HookRequest` and `HookResponse`, the worker, and `testing`.

A hook handler keeps its shape: it takes a request and returns a response or a
JSON-compatible value, and may be `async`. `HookRequest` provides `method`,
`query_params` (`get`, `getlist`, `items`), `headers`, `path_params`, `body()`, and
`json()`. Starlette response objects are accepted by their `status_code`, `body`, and
`raw_headers`, so the three downstream plugins’ handlers run unchanged; a streaming
response is refused with a message.

The SDK versions semantically, and plugins depend on a caret range of it, such as
`metabrowser-plugin-sdk>=0.1,<0.2`. Because it is small and has no dependencies, that
range does not collide with anything a plugin needs.

### The Worker Protocol

- **Frames.** One JSON header line, then `body_len` raw bytes, in both directions.
  Every request has an id, so either side can have many in flight.
- **Host to worker:** `hello`, `list`, `check`, `call`, `cancel`, `parse`,
  `root_changed`, and `shutdown`. **Worker to host:** the content reader’s calls, host
  services, and structured log records.
- **Handshake.** The host sends its protocol major version, its capability names, the
  subject (a folder with its root, or a pin with its display name), and the trust
  profile. The worker answers with its own version, capabilities, SDK version, and Python
  version. A different major version fails fast with both versions and the SDK range to
  install; anything new is a capability, so additions never break the handshake.
- **`list`** imports the environment’s `metabrowser.plugins` entry points and returns
  each plugin directory with its distribution and version, plus per-entry errors.
- **`check`** imports every declared sidekick and parser for `--doctor`.
- **`call`** carries the plugin, route, sidekick, method, query, allowlisted request
  headers, and deadline, with the body after the header.
- **`parse`** carries an adapter, a stream id, and a batch of lines; see below.

The protocol becomes a new row in the Standing Compatibility Answers: **plugin worker
protocol, VERSION + CAPABILITIES**, because plugin environments update on their own
schedule and are the named consumer the compatibility rules require.

### Log Adapters

Detection moves into the manifest, so classifying a file never waits on a worker:

```toml
[[log_adapter]]
name = "pool"
detect = { key = "event", equals = "pool_start" }

[[log_adapter]]
name = "steps"
detect = { all = [
  { key = "event", in = ["process_start", "step_start", "item_start"] },
  { any = [{ has = "process" }, { has = "step_id" }, { key = "event", prefix = "item_" }] },
] }
```

- `detect` is a predicate over each parsed JSON object among the stream’s first 20
  lines, the window `detect_adapter` reads today, built from `equals`, `in`, `prefix`,
  `has`, `all`, and `any`. The motivating plugin’s two code detectors both fit it.
- The host evaluates it beside the built-in detectors.
  A built-in name cannot be claimed, and two plugins claiming one name is a `--doctor`
  error, as now.
- Parsing stays the plugin’s code.
  The plugin registers a parser factory for each name with `register_log_parser`; the
  host sends lines to the owning worker in batches with a stream id, one parser per
  stream, for a file view and for a live stream alike.
- Events come back without `raw`, each with its line index, and the host attaches the
  source line it already parsed.
  The spike measured this saving about 41% of the bytes and 30% of the transport.
  Phase 1 measures splicing the worker’s JSON into the response without decoding it
  before deciding whether to add it.

### SDK Compatibility

Three versions, each with one rule:

- **The browser SDK** (`sdk_version` in the manifest) adopts Cargo’s caret rule for
  `0.x`: a version is `0.MINOR.PATCH`, an addition bumps PATCH, and a break bumps MINOR.
  The host accepts a manifest with its MINOR and a PATCH no greater than its own, and
  refuses a newer PATCH as needing a newer Metabrowser.
  Today’s `0.7` reads as `0.7.0`, so no manifest changes when the rule lands.
- **Breaks are listed as data.** `plugin_loader/sdk-changes.toml` records each version’s
  additions, changes, and removals by surface name, the window globals plugins use
  (`MetabrowserCharts`, `MetabrowserTooltip`, `MetabrowserAssets`) among them.
  A refusal names the changes between the plugin’s version and the host’s, and a test
  fails when `PLUGIN_SDK_VERSION` has no entry.
- **Deprecate before removing where it is cheap.** A surface a plugin may use is kept,
  with a console warning and a `--doctor` note, for one compatibility line before it is
  removed; where keeping it costs more than a break, the break bumps MINOR. This revises
  “Plugins are upgraded, not accommodated”: plugins in other repositories now update on
  their own schedule, the condition the Standing Compatibility Answers name for
  revisiting it.
- **An author can see what breaks.** `metab --plugins-sdk-override NAME`, for one
  command and never recorded, loads a refused plugin, logs the override, and shows a
  banner in the page.
- **The plugin SDK package and the worker protocol** follow the two sections above; the
  host gates on the protocol, not on the package version.

### Lifecycle

- **Add and remove** are CLI modes.
  Until Phase 4, a change takes effect at the next server start.
- **Update** is whatever updates the environment: `uv sync` in a project,
  `uv tool upgrade`, or `metab --plugins-upgrade` for a managed package.
  A worker compares the environment’s fingerprint when it starts and when the listing
  cache is read; a changed environment is listed again.
- **Reload without a restart (Phase 4).** The registry becomes a generation object that
  the server swaps whole.
  Data hooks dispatch through one route, `/api/plugin/{plugin}/{route}`, that looks up
  the current generation, instead of one Starlette route per hook; `/plugin-static/`,
  the classifier, and the derived caches read or key by the generation.
  The server watches `plugins.yml` and each environment’s fingerprint, debounced, and
  applies a new generation; workers whose environment changed drain and restart.
  The server then emits `plugins-changed`, and an open page offers to reload, since its
  plugin JavaScript is fixed until it does, as after a server upgrade today.
  When the app plan’s host mode lands, `metab --plugins-reload` also reaches a running
  server through its control socket.
- **Managed packages (Phase 4).** `--plugins-install REQUIREMENT` creates a uv project
  per package under the runtime’s data home (`plugin-envs/<id>/` with `pyproject.toml`
  and `uv.lock`), locks it with the supply-chain cool-off (`exclude-newer = "14 days"`,
  first-party packages exempt as
  [supply-chain security](../../../../SUPPLY-CHAIN-SECURITY.md) describes), syncs it
  with `--locked` into a new directory, runs the worker’s `check`, and swaps it in,
  keeping the previous environment for rollback.
  `--plugins-upgrade` relocks and repeats; a CLI install uses the user’s uv, an
  app-managed runtime the app’s. A package that ships a command line can instead be a
  `uv tool install` and a registered environment.

### The macOS App

The app keeps its rule: `metab` owns the data, the app owns platform behavior.

- **One configuration home in Terminal and the app.** The app resolves
  `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, `XDG_DATA_HOME`, `METABROWSER_CONFIG_DIR`, and
  `METABROWSER_CACHE_DIR` from the login shell once at setup, as it resolves `git` and
  `gh`, and passes them to every server, so a server the app starts reads the same
  registry and cache as `metab` in Terminal.
  This also fixes the cache-home gap the research brief found.
- **Where plugin environments live.** Registered environments stay where the user keeps
  them. Managed packages live in the data home of the runtime the app uses: the XDG data
  home for a CLI install, `~/Library/Application Support/Metabrowser/` for an
  app-managed runtime.
  The registry belongs to that runtime’s configuration home, as state homes already do.
- **Settings > Plugins** is a native list built from `metab --plugins --json`: each
  source with its kind, location, plugins, and problems.
  Add… opens a panel for a folder, environment, or interpreter, runs
  `metab --plugins-add --dry-run --json PATH`, and shows a native confirmation with the
  interpreter, the plugins with their hooks and adapters, and the privacy-grant note;
  confirming runs `metab --plugins-add --yes --json PATH`. Remove runs
  `--plugins-remove`. Run Doctor and Reveal Logs exist already.
  The list is native, not a page, because its actions are the registry writes no page
  may reach; a read-only page can show the same model later.
- **Project trust** appears as a bar in the folder’s window when the server reports an
  untrusted declaration, with Review, which shows the declaration and the note, and
  Trust, which runs `metab ROOT --plugins-trust --yes`.
- **Applying a change.** Until Phase 4, after a change the app offers to restart the
  servers it affects (every open folder for a source, the one root for trust), through
  the same path it uses after an upgrade (`mb-895s`). After Phase 4 the servers reload
  themselves and the app does nothing.
- **Supervision.** Workers are in their server’s process group, so the app’s stop
  (SIGTERM to the group, then SIGKILL) reaches them, and each worker’s stdin lifeline
  ends it with its server however the server ends.
  A worker’s stderr is in the server’s log, which the app’s failure view already shows.
  A live test stops a folder and checks that no worker remains.
- **Signing and sandbox.** Nothing is added to the signed bundle.
  The app is not sandboxed (the Mac App Store is a non-goal), and a worker is a separate
  executable from the plugin environment, not code loaded into the app, so the app’s
  hardened runtime and library validation do not apply to it and no entitlement is
  needed (inferred from how the hardened runtime applies per executable; servers already
  run the same way).
- **Effect on the app’s other plans.** Plugin environments are independent of the base
  environment, so the optional app-managed runtime (`mb-lrcd`) no longer reinstalls
  plugins on each base swap.
  The warm-folder budget (`mb-e7im`) counts a server’s workers, and their idle exit
  returns that memory.

### Remote Sessions

`metab --remote HOST --path ROOT` runs the remote host’s `metab`, so the remote host’s
built-ins, entry points, and registry apply; the local registry does not travel, since a
local worker cannot read remote files.
`--remote` forwards `--plugins` and `--doctor` over the same SSH path, so the local user
can see what the remote session loads.
Adding a source on a remote host is `metab --plugins-add` run there.

### Diagnostics

- `metab --plugins --json` gains `sources`: id, kind, location, scope, enabled state,
  trust, interpreter, Python version, SDK version, protocol, listing freshness, plugins,
  and problems. The table form gains the source id.
- `metab --doctor` checks each source: the interpreter runs; the worker handshakes; its
  protocol and SDK are compatible; each listed manifest passes the host’s schema and SDK
  gate, with the change list on a refusal; each hook and parser imports (`check`); each
  declared adapter has a parser; names collide nowhere unreported; a declaration’s
  trust; and, when uv is available, whether a uv project’s environment matches its lock.
  It stays rootless, and closes every worker it starts.
- `GET /api/plugins` serves the same model to the page and to `--api`.
- `metab ROOT --show PATH` names the source and the process that own the selected kind.

### CLI and Routes

| Surface | Kind | Golden |
| --- | --- | --- |
| `--plugins-add SOURCE [--dry-run] [--yes]`, `--plugins-remove ID` | CLI mode, writes `plugins.yml` | add, dry run, remove, refusal of a shared registry |
| `--plugins-env PATH` | per-command source, repeatable, like `--plugins-dir` | a fixture environment’s hook through `--api`, an adapter kind through `--show` |
| `ROOT --plugins-trust`, `ROOT --plugins-untrust` | CLI mode, writes trust | trust, changed declaration, refusal on a Git source |
| `--plugins-install`, `--plugins-upgrade`, `--plugins-uninstall` (Phase 4) | CLI mode | offline install from a local wheel |
| `--plugins-reload` (Phase 4) | CLI mode through the control socket | reload after a registry change |
| `--plugins-sdk-override NAME` | per-command flag | a refused fixture loaded with the banner |
| `GET /api/plugins` | route | the fixture registry |

Each lands with its row in
[Views, Models, and Routes](../../architecture/arch-views-models-routes.md), which
`devtools/check_parity.py` enforces.
The flag names are proposals to settle in Phase 1 against the existing flat CLI.

## Implementation Plan

Each phase is one stack of pull requests.
Core work goes to `main`; the app work stacks on the macOS app’s stack until the user
decides to merge it.

**Independent fix** (`mb-hi06`), a standalone pull request to `main`: declare compatible
ranges for Metabrowser’s library dependencies (`softschema>=0.8.1,<0.10` and the like)
and keep exact versions in `uv.lock`, with a CI job that installs beside a package
needing the newer end of each range.
It helps plugins that stay in Metabrowser’s environment and is not a prerequisite for
the rest.

### Phase 1: Plugin Environments Out of Process

- [ ] The caret SDK gate, `sdk-changes.toml`, refusals that name the changes, and the
  author override (`mb-jn5e`). It lands first, so later additions to the manifest are
  patch bumps that refuse nothing.
- [ ] The registry, registered and per-command directories, `GET /api/plugins`, the
  `sources` model in `--plugins --json` and `--doctor` (`mb-mo66`).
- [ ] The plugin SDK package with the identity codec and `ArtifactPath` moved into it,
  `HookRequest` and `HookResponse`, the bindings, and the worker; and the host’s worker
  client: spawning, the lifeline, multiplexing, deadlines, cancellation, restarts, idle
  exit, and logs (`mb-3q4e`).
- [ ] Environment sources: `--plugins-add PATH` for environments, `--plugins-env`, the
  listing cache, manifests and assets served by the host, proxied hooks, the content
  reader’s host calls, and `--doctor`’s `check` (`mb-8pg5`).
- [ ] `[[log_adapter]]` with declarative detection, proxied parsing for file views and
  live streams, and the measured choice of batch size and of splicing (`mb-b11t`).

### Phase 2: Migration and the Author Harness

- [ ] The three downstream plugins depend on the plugin SDK instead of Metabrowser,
  import from it, declare their adapters, and are verified from their own environments
  under a uv tool install (`mb-uas1`). The work lands in their repositories.
- [ ] `metabrowser_plugin_sdk.testing`: an in-process hook client over a fixture root
  and a fixture that runs the real worker; the startup scripts and on-demand bundles
  served as data so browser harnesses read them instead of copying `server.py`; and the
  `--plugins-env` plus `--api` golden pattern for plugin repositories (`mb-fiju`).
- [ ] Entry points in Metabrowser’s own environment run in a worker on its interpreter;
  the in-process sidekick path for third-party plugins and the sidekick names in
  `metabrowser.__all__` go, behind the gate; `docs/plugins.md` and the Standing
  Compatibility Answers describe the new model (`mb-qdp4`).

### Phase 3: The macOS App’s Plugin Settings

- [ ] Home variables resolved at setup and passed to servers (`mb-eazg`).
- [ ] Settings > Plugins, the project-trust bar, restarting affected servers after a
  change, the worker teardown test, and the app README (`mb-mtpe`).

### Phase 4: Live Lifecycle and Managed Packages

- [ ] Reload without a restart: the generation, one dispatch route, the watches,
  `plugins-changed`, and worker drains (`mb-0e0i`).
- [ ] Managed package environments: install, upgrade, uninstall, rollback (`mb-8ii8`).

### Phase 5: Project Plugins and Remote Sessions

- [ ] Project declarations, trust by root and declaration hash, and their refusals
  (`mb-nkc3`), replacing `mb-m1mw`.
- [ ] `--remote` forwards `--plugins` and `--doctor` (`mb-9i2l`).

## Testing Strategy

- **A fixture plugin environment.** `tests/fixtures/plugin-env/` holds a tiny plugin
  package with one hook, one adapter, and one view.
  A session-scoped fixture builds a venv with `uv venv` and an offline `--no-index`
  install of the fixture and the SDK workspace member, which have no other dependencies.
- **Protocol.** A golden session of normalized frames between the host client and the
  real worker, and fault tests: a worker that exits mid-call, one that hangs past its
  deadline, garbage frames, plugin code printing to stdout, an oversized body, a
  protocol major mismatch, and stdin closing.
- **Goldens through `metab`.** `--plugins-env` with `--api` for a hook, `--show` for an
  adapter kind, `--plugins --json`, `--doctor --json`, `GET /api/plugins`, and each
  registry mode.
- **Records and trust.** The registry’s contract; refusal of a shared registry; serving
  never creating the home; trust invalidated by a changed declaration; no project source
  on a Git source or under `--untrusted`.
- **Compatibility.** The caret rule’s table; `sdk-changes.toml` covers every version.
- **Performance.** Phase 1 records worker spawn, listing, resident memory, hook
  overhead, and adapter throughput with the spike’s method in
  [the spike’s README](../../../../explorations/plugin-worker-spike/README.md), and sets
  the idle exit, batch size, and response bound from those numbers.
- **The app.** `ShellCore` tests for the settings model and the commands it runs; a live
  test that stopping a folder leaves no worker; the setup check that the home variables
  reach a server.
- **Downstream acceptance.** The motivating plugin and the other two running from their
  own environments, with hooks, adapters, and assets, under a uv tool install and in the
  app.

## Rollout Plan

- Phase 1 changes no existing plugin’s behavior: entry points keep loading in process,
  and new sources are additive.
  `CHANGELOG.md` records the SDK gate’s rule and the new sources.
- Phase 2’s move of the sidekick names is a plugin API break, announced in
  `CHANGELOG.md` and gated as the compatibility section describes.
  The three downstream plugins migrate in the same window.
- The app’s phase ships with the app; nothing in it is needed by the CLI.

## Open Questions

- The package name, `metabrowser-plugin-sdk`, and the CLI flag names.
- The idle-exit period and whether to start a worker at idle after the first
  classification rather than at the classification itself.
- Whether splicing worker JSON into responses is worth its complexity.
- The default hook deadline.
- Whether warm folders need one worker per environment shared across servers (the
  brief’s Option I).
- Whether Phase 2 removes the in-process path in the same release as the SDK move or one
  release later.

## References

- Research:
  [Loading Plugins from Any Source](../../research/research-2026-11-12-plugin-sources.md),
  [Native macOS App for Metabrowser](../../research/research-2026-11-08-macos-app-packaging.md)
- Plans: [Native macOS app](plan-2026-11-10-native-macos-app.md)
- Guides: [Plugin Authoring](../../../plugins.md),
  [Compatibility and Legacy Code](../../../development.md#compatibility-and-legacy-code),
  [supply-chain security](../../../../SUPPLY-CHAIN-SECURITY.md)
- Code: `src/metabrowser/plugin_loader/`, `src/metabrowser/plugin_api.py`,
  `apps/macos/Sources/ShellCore/Runtime/ChildEnvironment.swift`,
  `explorations/plugin-worker-spike/`
- [Cargo’s caret requirements](https://doc.rust-lang.org/cargo/reference/specifying-dependencies.html#caret-requirements)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
