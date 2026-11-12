# Plan: Plugin Sources and Out-of-Process Plugin Environments

**Date:** 2026-11-12 (last updated 2026-11-12)

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Draft, awaiting the owner’s answers to the Key Decisions below.
Epic `mb-xbw3` tracks every item as a bead.
Nothing is implemented; two spikes proved the stdio transport and a host-shipped
runtime.

## Overview

A system-installed Metabrowser, meaning the `metab` uv tool and the macOS app that runs
it, should use a new plugin without being reinstalled, and should pick up the plugins a
repository checks in or locks through a library, with no Metabrowser-specific setup.
Today every Python plugin must be installed into Metabrowser’s own environment, which
rewrites that environment and, for the motivating domain plugin, cannot resolve at all.

In this design Metabrowser reads every plugin’s manifest and serves its assets itself,
and runs plugin Python in a **worker**: a process started with the plugin environment’s
own interpreter. Metabrowser injects its own **plugin runtime** into that worker, so the
documented `from metabrowser import resolve_path` resolves to Metabrowser’s code,
whatever the environment holds.
**Plugin sources** live in one registry, each with a scope: everywhere, a set of
folders, or one clone of a repository.
A repository’s plugins are found by reading its environment’s metadata and load after
one consent per clone that names their providers.

The evidence, the reproductions, and the alternatives rejected are in
[Loading Plugins from Any Source](../../research/research-2026-11-12-plugin-sources.md).

## Key Decisions

Each is awaiting the owner.
Where this plan agrees with a recommendation, the design below follows it; the other
options stay here so the choice can be made differently.

### 1. Who supplies the plugin-side runtime

**The concept.** Plugin Python calls a dozen helpers (contained paths, bounded reads,
log events) and needs a loop that speaks to the host.
Something must put that code into the plugin’s process, and whoever supplies it decides
who can fix it and how many versions of it exist at once.

| Option | Leads to | Cost |
| --- | --- | --- |
| Each plugin environment installs an SDK package | Plugins pin the SDK they tested; host and worker negotiate a protocol | A third long-lived compatibility surface; path and decompression bounds frozen per environment, so a fix waits for every environment to relock; two plugins in one environment must agree on one SDK range; checked-in directory plugins have nothing to bring the SDK |
| Metabrowser injects its runtime under a new import name | Nothing to install; one artifact | Every plugin changes its imports once; plugin code runs against a newer runtime than it was tested with |
| Metabrowser injects its runtime as `metabrowser` | Nothing to install, and today’s plugin code runs unchanged: the second spike ran all three downstream plugins that way | Inside a worker, `metabrowser` is the runtime, not the environment’s installed package, so importing anything beyond the documented names fails there; the same newer-runtime risk, held by the plugin API gate |

**Recommendation:** inject the runtime as `metabrowser`.

### 2. What a trust decision binds to, and what ships first

**The concept.** Trusting a repository means “code from this place may run as me.”
What the decision binds to decides what happens when the place changes: a pull, a branch
from a fork, a new dependency, an agent’s edit.

| Option | Leads to | Cost |
| --- | --- | --- |
| The path | Never asks again | Anything that can write the tree or add a dependency runs code |
| The clone, with the named plugin providers | Asks once per clone, and again only when a new distribution or directory starts providing a plugin; version bumps of an approved provider do not ask | One prompt per new provider |
| The content of the plugin set | Every change asks | In the example workspace, with 10 editable members, nearly every pull asks, with a diff no one reviews |
| A parent folder scoped by origin URL | Fewest prompts | Not a boundary: a directory’s own `.git/config` can claim any origin (reproduced with two hand-written files) |

**Recommendation:** ship three states first (undecided, trusted for its named providers
per clone, and denied) and defer content trust and parent folders.
If parent-folder trust is added later, describe it as “everything placed under this
folder runs code.”

### 3. Where plugin code comes from when the browsed folder is elsewhere

**The concept.** “What code runs” and “what folder is browsed” are different questions.
One checkout holds the environment, while its worktrees, its run folders, and data kept
elsewhere are what gets browsed.

| Option | Leads to | Cost |
| --- | --- | --- |
| Only the browsed repository’s own environment | Each worktree needs its own consent and its own sync; data outside the repository gets nothing | Manual steps in the owner’s daily cases |
| A linked worktree uses its clone’s decision and primary environment | A new worktree works with no sync, and code an agent edits in a worktree does not run | A worktree whose branch changes a plugin shows the primary checkout’s plugin until its author opts in for one command |
| A source’s scope can name more folders | Run folders and data outside the repository get the repository’s plugins | One more field per source |
| Checked-in directory plugins run on an isolated interpreter when there is no environment | Python hooks work in a repository with no Python environment | Those hooks see only the standard library and the runtime |

**Recommendation:** adopt the last three together, with repository discovery proposing a
source for the one registry rather than being a second mechanism.

### 4. Whether Metabrowser creates or changes a repository’s environment

**The concept.** A missing environment is the commonest reason a discovered plugin
cannot load, and building one runs the repository’s build code and writes into the
developer’s checkout.

| Option | Leads to | Cost |
| --- | --- | --- |
| Guess a command such as `uv sync --locked` | One click | Wrong for the example repository, which initializes submodules and syncs `--all-packages`; the default sync also removes packages it did not install |
| Run a command the repository declares | Correct per repository | One more thing the consent covers |
| Report only | Never wrong | One manual step |

**Recommendation:** report only at first, and add a declared command later.
Always use the repository’s whole environment, never a reduced one: the motivating
plugin loads the consuming repository’s own extensions, so a reduced environment would
render its processes wrongly.

### 5. Which commands an agent may run outside its sandbox

**The concept.** The app’s agent design exempts `metab` from an agent’s sandbox so that
`metab TARGET --present` works.
This design adds commands that run plugin code or record trust.
A flat command line cannot be split by a prefix pattern, and the existing
`--remote … --ssh-options` already makes a blanket `metab *` exemption unsafe.

| Option | Leads to | Cost |
| --- | --- | --- |
| Leave it to the skill’s wording | No code | One exemption grants everything |
| A separate executable for every mode that runs plugin code without a recorded decision, or records one | `metab *` stays safe to exempt | One more command name |
| Trust writes need a person: a terminal answer, or the app’s confirmation bound to the plugin set it showed | No one-flag self-approval | Scripts use per-command flags, which record nothing |

**Recommendation:** both the separate executable, named `metab-plugins` here, and no
`--yes` on trust writes, decided before the first per-command environment flag ships.
Nothing can tell a person from an unsandboxed process running as the same account; these
measures keep sandboxed agents out and make approval deliberate.

### 6. The order of the work, and when the in-process path goes

**The concept.** The consumers are blocked today, and the first version of this plan
gave them nothing for three phases.

| Option | Leads to | Cost |
| --- | --- | --- |
| Mechanism, then repository trust, then migration | A complete system before the first real use | The riskiest pieces are tested last against a real plugin |
| Unblock first, then one vertical slice | Dependency ranges and the app’s home variables now; then the real plugin served from its own environment through a per-command flag; then adapters, the registry, repository discovery, and the app | The registry arrives later |

**Recommendation:** unblock first.
Remove the in-process path for third-party plugins only after the three plugins have run
in workers for a release.

### 7. Where plugin sources and trust live

**The concept.** Sources and trust decisions name local paths and authorize code on this
machine. Configuration is what users copy between machines with their dotfiles.

| Option | Leads to | Cost |
| --- | --- | --- |
| The configuration home, beside `config.yml` | One home | A dotfile sync carries a grant to another machine, where the path can hold other code |
| A new state home (`METABROWSER_STATE_DIR`, `XDG_STATE_HOME/metabrowser`, or `~/.local/state/metabrowser`) | Grants stay on the machine that made them | A third home to resolve, pass from the app, and document |
| A file in each repository | No central record | Served content could write its own trust; rejected |

**Recommendation:** the state home, with the configuration home’s ownership checks.

### 8. One plugin API version, or several

**The concept.** A plugin depends on the browser SDK and, when it has Python, on the
runtime. Both now come from the host.

| Option | Leads to | Cost |
| --- | --- | --- |
| One version in the manifest gates both, by Cargo’s caret rule | One number for authors to read | A Python-only change bumps the number browser-only plugins declare |
| Separate browser and Python versions | Finer refusals | Two numbers per plugin |
| Either, plus a worker protocol version | Separate host and worker releases | Pointless once the host ships the worker |

**Recommendation:** one plugin API version.

## Goals

- Adding, removing, or updating a plugin never reinstalls Metabrowser.
- A plugin’s Python dependencies never conflict with Metabrowser’s or another plugin’s.
- A repository that checks in a plugin, or locks a library that ships one, works for a
  teammate after one consent per clone, its worktrees included, with no
  Metabrowser-specific configuration.
- The macOS app uses the sources that the `metab` of the runtime it runs uses, and adds
  only native consent and settings.
- Served content runs code only in a clone the user has trusted, and a browser page
  never changes what runs.
- A host release refuses a plugin only when the plugin needs something the host lacks or
  uses something the host removed, and says which.
- Every source, persisted record, and check is a `metab` mode or route with a golden.
- Plugin authors test hooks, adapters, and assets against the real host from their own
  repositories and CI.

## Non-Goals

- Sandboxing plugin code.
  A worker runs with the user’s privileges, like any program the user installs; this
  design isolates dependencies, crashes, CPU, and the environment variables a plugin
  sees, not authority.
- Plugins for Git sources opened from a URL, pins, or `--untrusted` sessions beyond the
  built-ins and the user’s sources scoped everywhere.
- A plugin marketplace, index, or signature scheme.
- Streaming data hooks; none exists today.
- Windows. Workers rely on descriptor passing and process groups; the in-process path is
  not removed on Windows until a Windows worker exists.

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

The downstream application repository is the pattern repository plugins must serve: a uv
workspace whose members include its own two plugin packages and the workflow library,
vendored as a Git submodule.
All three declare `metabrowser.plugins` entry points and load today only when that
workspace’s own `metab` runs from its environment, which is why the workspace locks an
exact Metabrowser.

Two spikes ran against that environment, which holds Metabrowser 0.9.1, from a 0.12.1
host. The first measured the transport: 0.13–0.17 ms median for a trivial hook, 10–27 ms
on a 429 KB response, 61–121 MB per worker.
The second ran the plan’s shape: a runtime the host ships, importable as `metabrowser`,
on descriptors 3 and 4. All three plugins’ current code served their hooks unchanged,
including two calls back to the host in the middle of one hook, and a handler past its
deadline was killed and replaced in 369–426 ms.

The [native macOS app plan](plan-2026-11-10-native-macos-app.md) runs one `metab` server
per folder as a child, from a CLI install, with an allowlisted environment.
Its Phase 5 deferred project-provided plugins to a trust spec; Repository Plugins below
is that spec.

## Design

### Principles

- **Register a source; never install into Metabrowser.** Metabrowser’s environment holds
  Metabrowser. Plugins live in environments beside it.
- **The host owns manifests, assets, and the runtime; workers run plugin code.** The
  server reads every manifest with its own schema and serves static files from the
  plugin directory. A worker is needed only for Python, and its runtime is the host’s.
- **Third-party Python runs out of process.** Built-ins stay in the server.
  Every other Python plugin runs in a worker on its environment’s interpreter, so a
  crash or hang ends only its worker and a heavy hook no longer takes the server’s GIL.
- **A repository is browsed before it is trusted.** Discovery reads only metadata, and
  nothing from an undecided clone runs or reaches the page.
- **Nothing the page can reach changes what runs.** Plugin JavaScript shares the page’s
  origin with every other plugin, so no route writes a source or a decision.
- **One representation, every surface.** Sources, decisions, and checks are one model,
  served by `metab --plugins --json`, `metab --doctor --json`, and `GET /api/plugins`.

### Sources and Scopes

Every source has a kind and a scope.
The scope says which servers use it.

| Kind | How it arrives | Scope | JavaScript | Python |
| --- | --- | --- | --- | --- |
| Built-ins | the release | everywhere | yes | in the server |
| Entry points in Metabrowser’s environment | whoever installs into it | everywhere | yes | in the server until Phase 5, then a worker on Metabrowser’s interpreter |
| A directory | `metab-plugins --add DIR` | everywhere, or named folders | yes | in a worker on an isolated interpreter |
| An environment: a venv, a uv project’s, or a uv tool’s | `metab-plugins --add PATH` | everywhere, or named folders | yes | in a worker on that environment |
| A repository clone | proposed by discovery, decided by the user | that clone, its linked worktrees, and named folders | yes | in a worker on the clone’s primary environment |
| A managed package (Phase 5) | `metab-plugins --install REQUIREMENT` | everywhere | yes | in a worker |
| `--plugins-dir DIR` | the operator, for one `metab` command | that process | yes | none |
| `--env PATH`, `--repo` | the operator, for one `metab-plugins` command | that process | yes | in a worker |

- **Precedence.** Later rows win a plugin-name collision, and `--doctor` reports every
  collision. A source other than a built-in may not take a built-in plugin’s name; its
  kinds and views still compete by priority, as any plugin’s do, and `--doctor` reports
  a built-in kind it overrides.
- **Environment identity.** An environment is its prefix, the directory holding
  `pyvenv.cfg`. Its interpreter, in a uv environment, is a symlink to the shared base
  Python, so it identifies nothing.
  Two entries with one prefix are one source.
- **Python floor.** The runtime runs on Python 3.12 and later, Metabrowser’s own floor;
  `--doctor` refuses an older environment and says why.

### The Registry

`plugins.yml` lives in the new state home (Key Decision 7).

- It is a record with the Softschema contract `metabrowser:PluginSources/0.1`,
  permissive like `config.yml`: known fields validate strictly, and unknown ones are
  kept and written back, because several Metabrowser versions can share one home.
  `metab-plugins` writes it by atomic replace under the home’s lock.
- It names code to run, so it is read through the home’s verified reader with sharing
  refused rather than repaired, and `--doctor` says why a refused registry was not used.
- Serving reads it when it exists and never creates the home.
  Serving does not import the home module today, a boundary
  `tests/test_plugin_public_api.py` holds, so Phase 3 adds a small reader whose import
  cost it measures, and moves that boundary deliberately as Deferred Imports requires.

```yaml
softschema:
  contract: metabrowser:PluginSources/0.1
  envelope: plugins
  status: permissive
plugins:
  sources:
    - id: workflow
      kind: environment
      environment: ~/src/workflow/.venv
      scope: everywhere
      added_at: 2026-11-12T10:00:00Z
      added_by: 0.13.0
    - id: viewers
      kind: directory
      path: ~/metabrowser-plugins
      scope: everywhere
    - id: app
      kind: repository
      decision: trusted
      clone: ~/src/app
      clone_identity: 16777235:972619991
      origin: github.com/example-org/app
      providers: [app-viewer, workflow-lib]
      folders: [~/data/app-runs]
      decided_at: 2026-11-12T10:05:00Z
    - id: stranger
      kind: repository
      decision: denied
      clone: ~/src/stranger
      clone_identity: 16777235:972620144
```

`clone_identity` is the device and inode of the clone’s Git common directory.
A clone deleted and recloned at the same path gets a new one and is undecided again; the
clone’s linked worktrees share it.
`origin` is shown, normalized, for the user to read, and binds nothing.

**Listing.** Where a packaged plugin’s directory is can be known only by importing its
entry point, which cost 251–469 ms for three plugins in the first spike.
The listing is cached in the cache home, keyed by the environment’s fingerprint: its
`pyvenv.cfg`, the base interpreter’s identity, and the modification times of
`site-packages`, each `*.dist-info`, and each `*.pth`. A server with a warm cache spawns
nothing at start. A cold or stale listing is taken before the classifier is built, once
after an environment changes; `metab-plugins` takes it ahead of time when it adds or
decides a source.
Serving writes the cache only for sources the user added or decided, so
an ordinary browse still creates no state.

### The Plugin Runtime

The runtime is a package inside the Metabrowser wheel.
The server puts its folder first on each worker’s `sys.path`, where it is importable as
`metabrowser`, so a plugin’s documented imports resolve to it whatever the environment
holds (Key Decision 1). It is standard library only, runs on the environment’s
interpreter, and holds one implementation of each thing the host and plugins must agree
on:

- the inventory identity codec, moved out of `inventory_engine.contract`, which the
  server imports from the same place;
- `resolve_path`, `resolve_directory`, `relativize_path`, `served_root`, and
  `register_root_callback`, bound to the worker’s subject;
- `ArtifactPath`, its errors, and the content error family (`gz_io` and
  `content_errors`, which already use only the standard library);
- the content reader: `resolve_content`, `resolve_content_container`,
  `read_content_window`, `stat_content`, `open_content`, `source_capabilities`,
  `require_source_capability`, `MAX_CONTAINER_INNER_DEPTH`, the `ContentRef`,
  `ContentStat`, and `ContentWindow` types, and `ContentReadError`. In a worker it calls
  the host, so it reads a Git pin and keeps the host’s bounds; a `ContentRef` there
  carries a handle into a table the host keeps for that call and releases at its end;
- `LogEvent`, the parser protocol, `register_log_adapter`, `detect_adapter`, and
  `JsonlParseLimitError`, with the built-in detectors separated from their `prettyfmt`
  dependency so they can ship in the runtime;
- `CLIError`, host services such as the agent-log chart projection, the worker loop, and
  `HookRequest` and `HookResponse`.

That is every name `metabrowser.plugin_api` and the sidekick part of
`metabrowser.__all__` export today.
A hook takes a request and returns a response or a JSON-compatible value, and may be
`async`. `HookRequest` provides `method`, `query_params`, `headers`, `path_params`,
`body()`, and `json()`. A Starlette response is accepted by its `status_code`, `body`,
and `raw_headers`, so the three downstream plugins’ handlers run unchanged; the
motivating plugin’s environment keeps Starlette, which its `browser` extra brings, until
its handlers return the runtime’s responses.
A streaming response is refused with a message.

Entry points still installed into Metabrowser’s own environment import the real
`metabrowser` in process until Phase 5, with the same names, so nothing binds them
differently during the transition.
Plugins type-check against a published copy of the runtime (Open Questions).

### Process Model

- **One worker per server and environment.** Plugins of one environment share it; a
  worker serves one server and one root.
- **Started on evidence.** A worker starts at the first hook call or parse for one of
  its plugins, or when the server first classifies a file into a kind one of them owns,
  so the view’s next hook does not pay the start.
  It exits after an idle period that Phase 1 sets from measurements, ten minutes as the
  starting point, and never while it holds an open live stream.
- **Spawned like the server.** `<interpreter> -I -B <runtime>/worker.py`, by
  `posix_spawn`, in the server’s process group, so the app’s group stop reaches it, with
  the server’s working directory.
- **Its own descriptors.** The request pipe is descriptor 3 and the reply pipe 4, both
  close-on-exec in the worker; descriptor 0 is `/dev/null`, descriptor 1 is stderr,
  which goes to the server’s log under the source id, and SIGINT is ignored, since the
  server owns Ctrl-C. A plugin’s `print` or subprocess cannot reach the protocol (the
  second spike: `Bad file descriptor` on 4), and the worker exits when the request pipe
  closes (2–4 ms).
- **An allowlisted environment.** A worker gets `HOME`, `USER`, `LOGNAME`, `TMPDIR`,
  `TZ`, the locale and proxy names, the server’s `PATH`, and `PYTHONNOUSERSITE=1`, plus
  the names its plugins’ manifests declare in `[plugin] environment`, which the consent
  shows. A key exported in the user’s shell does not reach plugin code unless a manifest
  asks for it.
- **Deadlines end the worker.** A call carries a deadline, a default that a hook’s
  manifest entry can raise, and a client disconnect sends `cancel`. A Python thread
  cannot be cancelled, so after the deadline plus a grace period the server kills the
  worker and fails its other in-flight calls with the degraded `plugin_error` envelope;
  the next call starts a new one (the second spike: killed at 2.0 s with 1 s plus 1 s,
  back and listed in 369–426 ms).
- **Changes under a running worker.** Before each call the server compares the
  environment’s fingerprint, and in author mode each editable plugin’s source tree, with
  the worker’s. On a change it stops the worker.
  If the manifests it serves are unchanged, the next call starts a worker on the new
  code, so a Python change needs no server restart.
  If a manifest changed, those plugins report that a restart applies it, until reload in
  Phase 5.
- **Streams survive a new worker.** A live stream’s parser state is in its worker, so a
  replacement worker re-primes the parser by replaying the stream from its start up to
  the cursor, as `sse.py`’s `_prime_parser_to_cursor` does for a resumed cursor today.
- **Repeated failure.** A worker that exits three times in a minute is marked failed
  until its environment changes or the user reloads.
- **Bounds.** A request body is at most 1 MiB. The response bound is set in Phase 1 from
  measurements; the largest response measured was 429 KB, and the nearest existing bound
  is the 64 MiB `jsonl_view` allows a parse’s input.

### Hook Response Headers

A hook can serve another site’s HTML, as the data-room plugin serves captured pages, and
`/api` accepts a top-level navigation, so headers decide whether that HTML runs scripts
on the application origin.

- **Passed through:** `content-type`, `content-disposition`, `content-language`,
  `cache-control`, `etag`, `last-modified`, `vary`, and every header that restricts:
  `content-security-policy`, `x-content-type-options`, `referrer-policy`,
  `x-frame-options`, `permissions-policy`, and the `cross-origin-*-policy` family.
- **Refused:** headers that widen access or move the client: `set-cookie`,
  `access-control-*`, and `location`, and anything not listed.
- **Added by the host:** `X-Content-Type-Options: nosniff` on every hook response, and
  `Content-Security-Policy: sandbox; default-src 'none'` on a `text/html`, SVG, or XML
  response that carries no policy of its own.
  The same defaults apply to in-process hooks, built-ins included; a policy on a fetched
  response does not affect the page that fetches it, so views that insert hook output
  are unchanged.
- **Request headers passed in:** `accept`, `content-type`, `if-none-match`,
  `if-modified-since`, and `x-metabrowser-pin`, which hooks already read for
  revalidation and pins.
- The host adds the handler’s time to the `Server-Timing` header the server already
  emits.

### Log Adapters

Detection moves into the manifest, so classifying a file need not wait on a worker:

```toml
[[log_adapter]]
name = "batch"
detect = { key = "event", equals = "batch_start" }

[[log_adapter]]
name = "steps"
detect = { all = [
  { key = "event", in = ["run_start", "step_start", "item_start"] },
  { any = [{ has = "run" }, { has = "step_id" }, { key = "event", prefix = "item_" }] },
] }
```

- `detect` is a predicate over each parsed JSON object among a stream’s first 20 lines,
  built from `equals`, `in`, `prefix`, `has`, `all`, and `any`. Both of the motivating
  plugin’s code detectors fit it.
  Plugin detectors run before the built-in ones on each line, as plugin code detectors
  do today. A built-in name cannot be claimed, and two plugins claiming one name is a
  `--doctor` error.
- **The JSONL paths change order.** `/api/file` and the pin content routes parse the
  whole file and then classify from the parse summary, and `charts.py` detects and then
  parses. Each will detect from the head first, classify, and only then parse, in the
  owning worker for a plugin’s adapter.
- **An unknown adapter name** gets the generic JSONL parser instead of the Claude parser
  `create_parser` falls back to today, a core behavior change that `CHANGELOG.md`
  records.
- **Parsing stays the plugin’s code,** batched, one parser per stream id in the owning
  worker, for a file view and a live stream alike.
- **The wire shape is measured first.** Today’s in-process pipeline (parse, `asdict`,
  one `json.dumps`) costs about 2.4 times the bare parse by an independent measurement,
  and proxying cost 2.5–3.5 times in the first spike.
  Phase 2 measures the worker serializing events into the response’s own shape for the
  server to splice without decoding, and keeps the existing `raw` field unless omitting
  it wins end to end.

### Plugin API Compatibility

- **One version.** `sdk_version` in the manifest names the plugin API, browser SDK and
  runtime together (Key Decision 8), and follows Cargo’s caret rule for `0.x`: a version
  is `0.MINOR.PATCH`, an addition bumps PATCH, and a break bumps MINOR. The host accepts
  a manifest with its MINOR and a PATCH no greater than its own, and refuses a newer
  PATCH as needing a newer Metabrowser.
  Today’s `0.7` reads as `0.7.0`, so no manifest changes when the rule lands.
- **Gate before the schema.** The gate reads `sdk_version` from the raw TOML before the
  manifest model validates, because the model forbids unknown fields: an older host
  would otherwise report a newer manifest’s `[[log_adapter]]` as a schema error instead
  of naming the Metabrowser version it needs.
- **Changes are data.** `plugin_loader/sdk-changes.toml` records each version’s
  additions, changes, and removals by surface name, the window globals plugins use
  (`MetabrowserCharts`, `MetabrowserTooltip`, `MetabrowserAssets`) among them.
  A refusal names the changes between the plugin’s version and the host’s, and a test
  fails when the current version has no entry.
- **Deprecate only what a named plugin uses.** A surface that a named external plugin
  uses, recorded with that consumer in `sdk-changes.toml`, keeps working with a console
  warning and a `--doctor` note for one compatibility line before removal; any other
  change breaks and bumps MINOR.
- **An author can see what breaks.** `metab-plugins --sdk-override NAME`, for one
  command and never recorded, loads a refused plugin, logs it, and shows a banner in the
  page.
- `AGENTS.md`, the Standing Compatibility Answers, and `CHANGELOG.md` change in the same
  pull request as the gate.
  No worker protocol row is added: host and worker ship together.

### Repository Plugins

A repository carries plugins in two ways, and discovery finds both with no
Metabrowser-specific file:

- **Its own plugin:** a package in its Python project (in the downstream application
  repository, two workspace members declaring `metabrowser.plugins` entry points), or a
  directory checked in under `.metabrowser/plugins/<name>/`.
- **A library’s plugin:** any distribution in the clone’s environment that declares a
  `metabrowser.plugins` entry point, from an index or, like the workflow library, from a
  vendored submodule. The clone pins it as it pins anything, in `uv.lock` or a gitlink.

#### Discovery

For a folder server, never a Git source opened from a URL, a pin, a mirror, or an
`--untrusted` session:

1. **The clone.** Discovery’s own reader finds the nearest `.git` at or above the served
   folder and no higher than the home directory, requires the ownership rule (Trust and
   Consent), and reads the common directory, so a linked worktree resolves to its clone.
   The server’s existing repository context answers only for GitHub origins and checks
   no ownership, so it is not used.
   Outside Git, the clone is the served folder itself.
2. **The environment.** The nearest uv project or workspace root at or above the served
   folder in the clone’s primary worktree, preferring one with `[tool.uv.workspace]`,
   and its `.venv`; or a `.venv` with `pyvenv.cfg` at the clone’s top level; or what
   `[tool.metabrowser.plugins] environment` names.
   A linked worktree uses its clone’s primary environment, so a new worktree needs no
   sync and edits in it do not run until its author opts in for one command
   (`metab-plugins --repo --dev`).
3. **The providers.** Read as data: each `*.dist-info/entry_points.txt` for the
   `metabrowser.plugins` group, each workspace member’s `pyproject.toml`, so a provider
   is known before the environment exists, and each
   `.metabrowser/plugins/*/manifest.toml`. A provider is a distribution or a checked-in
   directory, shown with its version and where it was installed from.
   Nothing in that metadata tells the repository’s own plugins from a library’s (the
   brief), so the consent lists providers, not owners.
4. **Optional configuration**, which no repository needs by default, in
   `[tool.metabrowser.plugins]` of the root `pyproject.toml`, or in
   `.metabrowser/config.toml`: `environment`, `exclude` by provider name, and further
   plugin `dirs`.

For an undecided clone discovery runs after first paint, off the startup path, reads at
most 2,000 distributions and 64 plugin directories, escapes every name it shows, and is
not cached. For a decided clone its result rides on the listing cache.

#### Decisions

| Decision | What is recorded | What happens automatically |
| --- | --- | --- |
| Undecided, the default | nothing | The page shows a bar naming the providers found, `metab` prints one line on stderr, and `--plugins` and `--doctor` list them as undecided. No interpreter runs, and no plugin JavaScript, style, asset, kind, or view is served. |
| Trusted | the clone’s path and identity, its normalized origin for display, the approved providers, and any further folders | Every server for a folder in the clone, its linked worktrees, or its further folders loads the approved providers’ plugins: manifests, assets, JavaScript, and a worker on the clone’s primary environment. Version bumps, pulls, and environment updates take effect at the next worker start or server start without asking. A new provider is reported in the bar and loads only once approved. |
| Denied | the clone’s path and identity | Nothing loads, and nothing is reported beyond `--plugins --json`. |

- **One decision per clone.** Its linked worktrees share it, and a reclone at the same
  path is undecided again.
- **Review lists what can be known.** Before trust, the bar and
  `metab-plugins ROOT --trust` show each provider’s name, version, and install location,
  and, for checked-in directories and providers already in the listing cache, their
  hooks, adapters, and declared environment names.
  They also show the plugin set’s hash, the environment’s path, and the privacy-grant
  note. A provider not yet listed shows only its name until it is trusted, since listing
  imports it.
- **What the person saw is what is approved.** A trust write takes a terminal answer, or
  the app’s confirmation, which runs `metab-plugins ROOT --trust --expect SHA256` with
  the hash it displayed; the mode refuses when the set no longer matches.
  There is no `--yes`.
- **Commands:** `metab-plugins ROOT --trust`, `--deny`, `--untrust`, and
  `--scope-add ID FOLDER`.
- **Never trusted:** a Git source opened from a URL, a pin, a mirror, an `--untrusted`
  session, and a clone inside Metabrowser’s cache home.
  Repository plugins come only from a working tree and its environment, never from a
  revision a pull-request page or pin shows, so reviewing a pull request in Metabrowser
  never runs the plugin code it changes.
- **Deferred:** content-bound decisions, as direnv makes, and parent-folder decisions
  (Key Decision 2).

#### The Clone’s Environment

- **Present:** used as it is, the whole environment; Metabrowser never writes to it.
- **Missing or incomplete:** discovery compares the providers the workspace members
  declare with those the environment holds, and the bar and `--doctor` name the missing
  ones and say to set up the environment the way the repository documents.
  No command is guessed (Key Decision 4).
- **Unusual:** a `.venv` tracked by Git, or one whose prefix resolves outside the clone,
  is named in the consent.

#### Checked-In Plugin Directories

A directory under `.metabrowser/plugins/<name>/` is a provider like a distribution.
Its Python runs in the clone’s worker, each plugin’s modules loaded from its own
directory under a package name of its own, so two plugins’ `sidekick.py` neither collide
nor shadow the environment’s modules.
In a clone with no environment, its hooks run in a worker on Metabrowser’s base
interpreter started with `-I -S`, where only the standard library and the runtime are
importable (Key Decision 3).

#### For Libraries That Ship a Plugin

- Declare a `metabrowser.plugins` entry point.
  Nothing else is required: the runtime comes from the host.
- Do not depend on `metabrowser` at run time.
  A consumer’s lock then never carries an exact Metabrowser for the plugin’s sake, as
  the downstream workspace’s does today.
- The consumer’s lock or gitlink decides the plugin version.
  A consumer that wants none of a library’s plugins lists it in `exclude`.

#### One Convention for Repository Extensions

The workflow library finds its own extensions through entry points in the running
environment, and its design document describes walking up to the uv workspace root for
members that are not installed (see the brief).
One convention serves both tools:

1. A repository’s extensions are entry points of its locked environment, one group per
   tool.
2. A tool running inside that environment reads them with `importlib.metadata`. A tool
   running outside it, as a system Metabrowser does, finds the environment by walking up
   to the workspace root, no further than the Git top level, and reads the metadata as
   data before running anything.
3. Content that is not a package lives under a dot directory named for the tool, and
   per-repository settings under `[tool.<name>]`.
4. Nothing from a repository runs until the user decides to trust it.

This plan changes only Metabrowser.

### Trust and Consent

| Source | Who adds it | How it is approved |
| --- | --- | --- |
| A directory or environment | the account owner, with `metab-plugins --add` | it shows what the metadata declares, imports nothing first, and asks on a terminal |
| A repository clone | discovery proposes; the account owner decides | the bar or `metab-plugins ROOT --trust`, as above |
| A managed package | the account owner, with `metab-plugins --install` | as for an environment, after the install |
| Per-command flags | whoever runs the command | the command line; nothing is recorded |

- **Only the owner records anything.** The state home is owner-only, with the
  configuration home’s checks on every directory above it.
- **Only code the user’s account alone can change runs.** Before a source is recorded or
  decided, and again before each worker spawns, the environment prefix, its interpreter
  and the base interpreter it links to, each plugin directory, and the clone’s top level
  and common directory pass the rule the app applies to `metab` (`ExecutableTrust`):
  every component of the path owned by the user or root, none writable by its group or
  by every account, and no access-control entry granting a write.
  A clone another account owns is refused, as Git’s `safe.directory` refuses one.
- **No route writes a source or a decision.** Plugin JavaScript can call any same-origin
  route, so a write route would let a JavaScript-only plugin register Python.
  Every write is a `metab-plugins` mode with a golden, and the read model is a route, so
  no surface lacks a transcript.
- **The read route shows no local paths.** `GET /api/plugins` names sources by id and
  shows locations relative to the served root or `~`, as the home’s errors avoid naming
  paths; full paths appear only in command-line output.
- **Served content cannot opt itself in.** A `.env` file cannot name a source or record
  a decision, an undecided clone is only reported, and `metab TARGET --present` changes
  nothing.
- **Agents.** Key Decision 5 keeps every mode that runs plugin code without a recorded
  decision, or records one, in `metab-plugins`, so `metab *` stays safe to exempt from
  an agent’s sandbox, and trust writes have no `--yes`. The Metabrowser skill tells
  agents to ask the user before running `metab-plugins`.
- **Plugin code has the app’s privacy grants.** Under the app a worker is a descendant
  of the app, and macOS attributes a descendant’s file access to the app (inferred), so
  plugin code can read what the user let Metabrowser read.
  Every consent says so.
- `SECURITY.md` and the trust section of `docs/plugins.md` describe the served root as
  never a plugin source; both change in the pull request that lands repository plugins,
  and `SECURITY.md` gains the hook header defaults with the runtime.

### Lifecycle

- **Add, remove, and decide** are `metab-plugins` modes.
  Until reload lands, a change to sources or manifests takes effect at the next server
  start; a Python-only change takes effect at the next worker start (Process Model).
- **Update** is whatever updates the environment: `uv sync` or the repository’s own
  setup in a clone, `uv tool upgrade`, or `metab-plugins --upgrade` for a managed
  package.
- **The author’s loop.** `metab-plugins ROOT --repo --dev` watches the plugin’s source
  tree and restarts its worker on a Python change; JavaScript and styles are served from
  disk, so a page reload shows them; a manifest change needs a server restart until
  reload lands.
- **A root that moves.** A server whose root moves to a folder in another clone
  restarts, until reload exists to swap repository-scoped sources in place.
- **Reload without a restart (Phase 5).** The registry becomes a generation the server
  swaps whole. Data hooks dispatch through one route, `/api/plugin/{plugin}/{route}`,
  that looks up the current generation and refuses a method the hook does not declare;
  `/plugin-static/`, the classifier, and the derived caches key by generation.
  The server watches `plugins.yml`, environment fingerprints, and manifests, debounced,
  emits `plugins-changed`, and an open page offers to reload.
  When the app’s host mode lands, `metab-plugins --reload` reaches a running server
  through its control socket.
- **Managed packages (Phase 5).** `--install REQUIREMENT` creates a uv project per
  package under a data home Metabrowser does not have yet, locks it with the 14-day
  cool-off applied to every package unless the user names an exemption with
  `--exclude-newer-package`, syncs it with `--locked` into a new directory, checks it,
  and swaps it in, keeping the previous environment for rollback.
  A CLI install uses the user’s uv, an app-managed runtime the app’s.

### The macOS App

The app keeps its rule: `metab` owns the data, the app owns platform behavior.

- **One set of homes in Terminal and the app.** Only the login shell knows whether the
  user set `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, `XDG_STATE_HOME`, `XDG_DATA_HOME`, or a
  `METABROWSER_*_DIR` override.
  Setup runs the login shell today only when its earlier lookups miss, because that run
  can take seconds and raise privacy prompts.
  So setup runs it once for these names, saves them with the runtime, passes them to
  every server, and Find Again refreshes them.
  This also fixes the cache-home gap the brief found, which is why it comes first (Key
  Decision 6).
- **Where things live.** Sources and decisions are in the state home of the runtime the
  app uses, so an app-managed runtime and its command-line launcher share them and a
  separate CLI install keeps its own.
  Both builds already share `~/Library/Application Support/Metabrowser/`.
- **Settings > Plugins** is a native list built from `metab --plugins --json`: each
  source with its kind, scope, location, providers, and problems.
  Add… opens a panel, runs `metab-plugins --add --dry-run --json PATH`, which reads
  metadata and imports nothing, and shows a native confirmation with the environment,
  the providers, the declared environment names, the privacy-grant note, and the hash;
  confirming runs `metab-plugins --add --expect SHA256 --json PATH`. Remove runs
  `--remove`. The list is native because its actions are writes no page may reach.
- **The repository bar** appears when a folder’s server reports an undecided clone or a
  new provider: “This clone provides 3 plugins: …”, with Trust, Review, and Not Now.
  When the environment is missing it says so and what the repository documents; it runs
  no setup.
- **Applying a change.** Until reload lands, after a change the app offers to restart
  the servers it affects, through the path it uses after an upgrade.
- **An older `metab`.** The settings pane reads the `sources` field of
  `metab --plugins --json`; when it is absent, the pane shows the upgrade command
  instead of the plugin settings.
- **Supervision.** Workers are in their server’s process group, so the app’s stop
  reaches them, and each worker’s request-pipe lifeline ends it with its server.
  A worker’s stderr is in the server’s log.
  A live test stops a folder and checks that no worker remains.
- **Signing and sandbox.** Nothing is added to the signed bundle.
  The app is not sandboxed, and a worker is a separate executable from the plugin
  environment, so the app’s hardened runtime and library validation do not apply to it
  (inferred; servers run the same way).
- **Effect on the app’s other plans.** Plugin environments are independent of the base
  environment, so the optional app-managed runtime no longer reinstalls plugins on each
  base swap. The warm-folder budget counts a server’s workers, and their idle exit
  returns that memory (113–121 MB each, measured).

### Remote Sessions

`metab --remote HOST --path ROOT` runs the remote host’s `metab`, so the remote host’s
built-ins, sources, and decisions apply.
The local registry does not travel, and `--remote` forwards no per-command sources; a
short-lived remote host loses its decisions with it.
Discovery runs on the remote host against the remote clone and its environment.
The `--remote` wrapper gives the remote command `/dev/null` as stdin and no terminal, so
a trust write there cannot ask through it: the page’s bar names
`ssh -t HOST metab-plugins ROOT --trust`, and Phase 5 forwards `--plugins` and
`--doctor`, and runs the trust mode over a terminal-allocating SSH session.

### Diagnostics

- `metab --plugins --json` gains `sources`: id, kind, scope, decision, location,
  environment prefix, Python version, listing freshness, providers, plugins, and
  problems.
- `metab --doctor` checks each source: the interpreter runs and meets the floor; the
  ownership rule holds; the worker starts; each listed manifest passes the schema and
  the gate, with the change list on a refusal; each hook and parser imports; each
  declared adapter has a parser; collisions are reported.
  Without a root it stays rootless; given a root, it also reports that root’s clone, its
  decision, its missing providers, and why each plugin is or is not loaded.
  It closes every worker it starts.
- `GET /api/plugins` serves the same model to the page and to `--api`.
- `metab ROOT --show PATH` names the source and the process that own the selected kind.

### CLI and Routes

`metab-plugins` is the same command line as `metab`, serving and data modes included,
that also accepts the flags that run plugin code without a recorded decision or record
one; `metab` refuses those flags and names `metab-plugins`.

| Surface | Kind | Golden |
| --- | --- | --- |
| `metab --plugins [--json]`, `--plugin NAME`, `--doctor [ROOT]` | read-only modes | sources, decisions, and problems on a fixture registry |
| `GET /api/plugins` | route | the fixture registry, with no absolute path |
| `metab-plugins --env PATH` | per-command source | a fixture environment’s hook through `--api`, an adapter kind through `--show` |
| `metab-plugins ROOT --repo [--dev]` | per-command decision | a fixture clone’s hook through `--api` |
| `metab-plugins --add PATH [--dry-run] [--expect SHA256]`, `--remove ID`, `--scope-add ID FOLDER` | writes `plugins.yml` | add, dry run, a set changed after the dry run, remove, refusal of a shared registry and of an environment another account can write |
| `metab-plugins ROOT --trust [--expect SHA256]`, `--deny`, `--untrust` | writes a decision | each decision on a fixture clone, a new provider, a reclone at the same path, a linked worktree, refusal on a Git source |
| `metab-plugins --sdk-override NAME` | per-command flag | a refused fixture loaded with the banner |
| `metab-plugins --install`, `--upgrade`, `--uninstall` (Phase 5) | writes a managed environment | an offline install from a local wheel |
| `metab-plugins --reload` (Phase 5) | control socket | a reload after a registry change |

Each lands with its row in
[Views, Models, and Routes](../../architecture/arch-views-models-routes.md), which
`devtools/check_parity.py` enforces.
Flag and executable names are proposals.

### Workflows

**An author adds a plugin to a repository.** As a package: a workspace member with a
`metabrowser.plugins` entry point and its `plugin/` directory, then the repository’s
usual setup; no SDK dependency is needed.
Without packaging: `.metabrowser/plugins/<name>/` with a manifest, `index.js`, and a
`sidekick.py` if it needs hooks.
The author’s clone is already trusted, so the bar reports the new provider once, and
after approval `metab-plugins . --repo --dev` gives the inner loop described under
Lifecycle.

**A teammate clones the repository and opens it**, in the app or with `metab <repo>`.
Discovery finds the providers and the bar lists them.
If the environment is missing, the bar says so and names the setup the repository
documents. After Trust, the plugins load at the next start of the folder’s server.
Later opens, and every linked worktree of that clone, ask nothing.
A run folder outside the clone gets the same plugins once the teammate adds it to the
clone’s scope.

**A pull request changes the plugin.** In Metabrowser’s pull-request pages the changed
plugin never runs, since plugins load from a working tree and never from a revision a
page shows. A local checkout of the branch in a linked worktree runs the primary
checkout’s plugin, not the branch’s, until the reviewer opts in for one command with
`metab-plugins --repo --dev`. Checked out in the primary worktree of a trusted clone,
the branch’s plugin runs, as its tests would; a provider the branch adds asks first.

**A library releases a new plugin version.** Nothing changes for a consumer until its
lock moves: a pull request upgrades the library or advances the submodule, CI validates
it, and after the merge each teammate’s environment update changes the fingerprint.
The next call starts a worker on the new code if the manifests are unchanged; otherwise
the plugins say a restart applies it.
An approved provider’s new version does not ask.
A version that needs a newer plugin API is refused with the Metabrowser version it
needs, and the other plugins still load.

**A repository pins a library’s plugin version** with the lock or gitlink it already
has.
Once its plugins rely on the injected runtime it stops pinning Metabrowser for their
sake, keeping a pin only if it also wants `uv run metab` to run a fixed host.
`exclude` drops a library’s plugin it does not want.

**A remote session** discovers on the remote host, where the clone and its environment
are, and the decision is recorded there through `ssh -t`, as Remote Sessions describes.

**CI validates the plugin.** After the repository’s own setup:

```shell
uvx --from metabrowser==0.13.0 metab-plugins . --repo --doctor --json
uvx --from metabrowser==0.13.0 metab-plugins . --repo --api '/api/plugin/<name>/<route>?path=<fixture>'
uvx --from metabrowser==0.13.0 metab-plugins . --repo --show <fixture>
```

`--doctor` fails on a refused manifest, an unimportable hook, or a missing parser; the
other two are golden transcripts of the plugin’s routes and kinds.
A matrix over the oldest and newest Metabrowser the repository supports covers the
plugin API range. These check editable installs.
A library that publishes wheels also builds its wheel, installs it into a scratch
environment, and runs `metab-plugins --env <that environment> --doctor`, which checks
what the wheel contains.

## Implementation Plan

Each phase is one stack of pull requests.
Core work goes to `main`; the app’s work stacks on the macOS app’s stack until the user
decides to merge it.

### Phase 0: Unblock Now

Independent pull requests, each useful on its own:

- [ ] Declare compatible ranges for Metabrowser’s library dependencies
  (`softschema>=0.8.1,<0.10` and the like), keep exact versions in `uv.lock`, and add a
  CI job that installs beside a package needing the newer end of each range (`mb-hi06`).
  The workflow library carries a Softschema override until a release does this.
- [ ] The app resolves the home variables at setup and passes them to servers
  (`mb-eazg`).

### Phase 1: A Real Plugin’s Hooks from Its Own Environment

- [ ] The plugin API gate: one version, Cargo’s caret rule, read from the raw TOML,
  `sdk-changes.toml`, refusals that name the changes, and the override (`mb-jn5e`).
- [ ] The plugin runtime and the worker client: the runtime package injected as
  `metabrowser`, with the identity codec, `ArtifactPath`, and the content errors moved
  into it; the worker loop on descriptors 3 and 4; spawning, the lifeline, the
  environment allowlist, deadlines that end the worker, restarts, idle exit, logs, and
  the hook header policy (`mb-3q4e`).
- [ ] Per-command environment sources and the `metab-plugins` executable: `--env PATH`,
  the listing cache, manifests and assets served by the host, proxied hooks, the content
  reader’s host calls, and `--doctor`’s checks (`mb-8pg5`). Acceptance: the motivating
  plugin’s hooks served from its own environment under a uv tool install, with no change
  to the plugin.

### Phase 2: Adapters and the Three Plugins

- [ ] `[[log_adapter]]` with declarative detection, the reordered JSONL paths, parsing
  in the owning worker for file views and live streams, stream re-priming, and the
  measured wire shape (`mb-b11t`).
- [ ] The three downstream plugins declare their adapters, drop their exact Metabrowser
  pins, and are verified from their own environments (`mb-uas1`). Their code otherwise
  stays as it is.
- [ ] The author harness: a published copy of the runtime for type checks and in-process
  hook tests, a fixture that runs the real worker, the startup scripts and on-demand
  bundles served as data for browser harnesses, and the CI pattern above (`mb-fiju`).

### Phase 3: One Registry and Repository Plugins

- [ ] The registry in the state home, with scopes, added directories and environments,
  `GET /api/plugins`, the `sources` model, and the ownership rule (`mb-mo66`).
- [ ] Repository discovery, per-clone decisions with named providers, linked worktrees
  on the primary environment, further folders, missing-provider reports, the bar’s
  model, and the `SECURITY.md` and `docs/plugins.md` changes (`mb-nkc3`).
- [ ] Checked-in `.metabrowser/plugins/` directories, with their Python in the clone’s
  worker or on an isolated interpreter (`mb-wpq3`).

### Phase 4: The macOS App’s Plugin Settings

- [ ] Settings > Plugins, the repository bar, restarting affected servers after a
  change, the older-`metab` fallback, the worker teardown test, and the app README
  (`mb-mtpe`).

### Phase 5: Live Lifecycle, Managed Packages, Remote Sessions, and One Path

- [ ] Reload without a restart (`mb-0e0i`).
- [ ] Managed package environments (`mb-8ii8`).
- [ ] Remote sessions forward `--plugins` and `--doctor`, and the trust mode over a
  terminal (`mb-9i2l`).
- [ ] After the three plugins have run in workers for a release, entry points in
  Metabrowser’s own environment move to a worker on its interpreter, and the in-process
  path for third-party plugins goes, except on Windows (`mb-qdp4`).

## Testing Strategy

- **A fixture plugin environment.** `tests/fixtures/plugin-env/` holds a tiny plugin
  package with one hook, one adapter, and one view, installed offline into a venv built
  once per session. It imports only the documented `metabrowser` names, so it exercises
  the injected runtime.
- **A fixture clone.** A Git repository with a uv workspace holding a plugin member, a
  distribution from outside the clone, a `.metabrowser/plugins/` directory, and a linked
  worktree.
- **The runtime and protocol.** A golden session of normalized frames between the host
  and the real worker, and fault tests: a worker that exits mid-call, one that overruns
  its deadline, garbage frames, plugin code printing to stdout, a plugin subprocess that
  writes to its stdout, reads its stdin, and tries descriptor 4, SIGINT, an oversized
  body, a worker-to-host call in the middle of a hook, and the request pipe closing.
- **Goldens through `metab` and `metab-plugins`.** Every row of the CLI and Routes
  table.
- **Headers.** A hook returning HTML with and without its own policy, through the proxy
  and in process; the refused headers; and a top-level navigation to a hook URL.
- **Records and decisions.** The registry’s contract with unknown fields kept across a
  write; refusal of a shared registry; serving never creating a home; for each decision,
  exactly what loads and what is reported; a new provider; a reclone at the same path; a
  linked worktree sharing the decision and running the primary environment’s code; a
  further folder; `--expect` refusing a changed set; the ownership rule refusing an
  environment, a plugin directory, or a clone another account can write; no repository
  plugins on a Git source, a pull-request page, or under `--untrusted`; an undecided
  clone whose page requests no plugin asset; and `GET /api/plugins` naming no absolute
  path.
- **Compatibility.** The caret rule’s table; the gate refusing a newer manifest by
  version, not by schema; `sdk-changes.toml` covering every version.
- **Performance.** Phase 1 records worker start, listing, memory, hook overhead, and
  kill and respawn times with the spikes’ method; Phase 2 records end-to-end log parsing
  against today’s in-process pipeline.
- **The app.** `ShellCore` tests for the settings model and the commands it runs; a live
  test that stopping a folder leaves no worker; the setup check that the home variables
  reach a server.
- **Downstream acceptance.** The three plugins from their own environments, with hooks,
  adapters, and assets, under a uv tool install and in the app.

## Rollout Plan

- Phase 0 and Phase 1 change no existing plugin’s behavior: entry points keep loading in
  process, and the new sources are additive.
  `CHANGELOG.md` records the gate’s rule and the hook header defaults.
- Phase 2 records the generic parser for unknown adapter names.
- Phase 3 changes nothing for a clone until the user decides; the first open shows the
  bar.
- Phase 5 removes the in-process path for third-party plugins only after a release with
  all three running in workers.
- The app’s phase ships with the app; nothing in it is needed by the CLI.

## Open Questions

- The Key Decisions above.
- The names `metab-plugins`, `.metabrowser/`, and `[tool.metabrowser.plugins]`, and the
  name of the published runtime copy, which should not match the
  `metabrowser-plugin-<name>` pattern plugins use.
  Publishing it brings release mechanics for a second distribution: versioning, publish
  order, and the first-party cool-off exemption.
- The idle-exit period, the default deadline and grace, and the response bound.
- Whether warm folders need one worker per environment shared across servers.
- A Windows worker.
- Whether the workflow library adopts the same repository convention.

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
