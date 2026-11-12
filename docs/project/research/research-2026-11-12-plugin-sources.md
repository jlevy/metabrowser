# Research: Loading Plugins from Any Source

**Date:** 2026-11-12

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Complete

Extends [Native macOS App for Metabrowser](research-2026-11-08-macos-app-packaging.md)
(2026-11-08), whose section Adding Plugins Without Rebuilding the App kept every Python
plugin inside a runtime’s own environment.
The decisions this brief supports are in
[Plugin Sources and Out-of-Process Plugin Environments](../specs/active/plan-2026-11-12-plugin-sources.md).

## Overview

A system-installed Metabrowser should use plugins without being reinstalled each time a
plugin is added. “System-installed” means the `metab` uv tool, and also the macOS app,
which is a native shell over that CLI install.

The motivating case is a downstream domain plugin for a workflow engine.
Its plugin has six Python data hooks and registers two JSONL log adapters, and its
library depends on a newer Softschema than Metabrowser pins.
Two plugins in a downstream application repository are the other consumers.
All three are packaged behind `metabrowser.plugins` entry points.

The owner then widened the scope: a repository that checks in a plugin, or that depends
on a library shipping one, should have it picked up automatically, in internal
repositories and for libraries that expose Metabrowser views.
The downstream application repository is the example of both: two of its plugins are its
own workspace members, and the third comes from the workflow library, vendored as a Git
submodule and also a workspace member.

This brief reproduces today’s behavior on the macOS app’s branch
(`claude/v1-final-review`, the top of the stack that starts at jlevy/metabrowser#341),
evaluates a candidate out-of-process design that a downstream session proposed from
reading the source, and measures a spike of its riskiest piece: proxying data hooks over
stdio to a worker that runs in the plugin’s own environment.

## Summary

- **Every Python plugin today must live in Metabrowser’s own interpreter.** Discovery
  imports `metabrowser.plugins` entry points from the running environment once, at
  server import. Operator directories (`--plugins-dir`) are JavaScript-only: their hooks
  are dropped and their adapters never register, so their adapter-classified kinds fall
  back to generic JSONL. Reproduced below.
- **Installing the plugin into Metabrowser’s environment fails on exact pins.**
  Metabrowser 0.12.0 pins `softschema==0.8.1`, and the motivating plugin needs
  `softschema>=0.9.1,<0.10`; uv reports no solution.
  Reproduced.
- **The macOS app cannot use operator directories at all.** Its child environment is an
  allowlist without `METABROWSER_PLUGINS_DIRS`, a `.env` file may not name that
  variable, and the app passes no plugin flags.
  Only entry points inside the CLI install reach an app window.
  The `.env` refusal is reproduced; the allowlist is read from source.
- **Overlaying a plugin environment onto Metabrowser’s interpreter is silently wrong.**
  After `site.addsitedir` of the downstream environment, the plugin imported against
  Metabrowser’s Softschema 0.8.1, although its own environment holds 0.9.1. Reproduced.
- **Subinterpreters cannot host these environments.** `pydantic_core` refuses to load in
  a PEP 734 subinterpreter.
  Reproduced.
- **Stdio hook proxying works and costs little per call.** A stdlib-only worker in the
  downstream environment, with that environment’s own Metabrowser 0.9.1 and Python
  3.14.7, served the plugin’s hooks to a 0.12.1 development host: 0.13–0.17 ms median
  round trip for a trivial hook, 10–27 ms of transport on a 429 KB response, and exit
  within 5 ms of its stdin closing.
  A worker costs 61 MB after importing three plugins and 121 MB after one large hook
  call.
- **Two costs need design, not just transport.** CPU-heavy hook work contends with
  everything else in its process: small calls beside a 1.2–1.4 s hook rose from 0.14 ms
  to about 8 ms median and up to 68 ms.
  Out of process, that contention leaves the server’s event loop; in process, it is the
  server’s. And proxied log parsing cost 2.5–3.5 times the parse itself in each run on a
  synthetic 100,000-line log, mostly JSON encoding and decoding.
  An independent measurement put the server’s own in-process pipeline (parse, `asdict`,
  one `json.dumps`) at about 2.4 times the bare parse, so the proxied path is a modest
  regression over today’s (the reviewer’s measurement under a load average near 30, not
  reproduced here).
- **The candidate design’s transport and process model hold; its binding does not.** A
  worker that imports the plugin environment’s own `metabrowser` must set private module
  state of whatever Metabrowser version that environment holds (the spike had to),
  cannot read content on a Git pin, and keeps every plugin environment carrying all of
  Metabrowser and its exact pins.
  The plan replaces that binding with a runtime the host ships and injects.
- **A host-shipped runtime runs the real plugins unchanged.** A second spike put the
  host’s own runtime first on the worker’s path, importable as `metabrowser`, and ran
  the three downstream plugins’ current code from their own environment, which still
  holds Metabrowser 0.9.1. The process-graph hook returned the same 429,248 bytes; the
  charts hook asked the host twice in the middle of a call; a plugin subprocess could
  not reach the protocol descriptors; SIGINT left the worker running; and a synchronous
  handler past its deadline was killed at deadline plus grace, with the worker back and
  listed in 369–426 ms.
  Reproduced twice.
- **A repository’s plugins can be found without running any of its code.** Reading each
  `*.dist-info/entry_points.txt` in the downstream repository’s environment found all
  three plugins in 31 ms over 127 distributions.
  `direct_url.json` does not tell the repository’s own plugins from the library’s: all
  three are editable installs from paths inside the repository, and only the library’s
  `vendor/` path differs.
  Its workspace members’ `pyproject.toml` files declare the same entry points, so they
  are visible before the environment exists.
  Reproduced.
- **Today the repository’s plugins work only inside its own frozen environment.**
  Running that environment’s `metab` finds them; a system `metab` and the macOS app find
  none. The workspace’s lock carries Metabrowser 0.12.0 only because both plugin packages
  and the library’s `browser` extra pin it to share its environment.
- **The trust models people already use split two ways.** VS Code Workspace Trust and
  `mise trust` record a folder path, and VS Code’s trust of a parent folder covers its
  subfolders. direnv records approved content: after an edit, direnv 2.36.0 blocked the
  `.envrc` until it was allowed again (reproduced), and mise’s paranoid mode does the
  same. Neither a path nor an origin URL is a boundary on its own: two hand-written files
  under `.git` make Git report any origin (reproduced).
  The plan records consent per clone, keyed by the clone’s Git common directory, with
  the plugin providers it approved.
- **The example repository’s environment is not what a guessed command builds.** Its
  `make install` initializes submodules first and then runs
  `uv sync --all-packages --locked`; a plain `uv sync --locked` fails on a fresh clone
  and otherwise builds an environment without the plugins (read from its Makefile and
  `uv sync --help`; no sync was run).
  Its lock has 10 editable members, so hashing editable source trees would ask again on
  nearly every pull.
- **An isolated interpreter has only the standard library.** `python -I -S` on
  Metabrowser’s own interpreter found none of Starlette, Pydantic, Softschema, or
  Metabrowser (reproduced), so a checked-in plugin in a repository with no environment
  can still run hooks, against the standard library and the host’s runtime.

## Questions to Answer

1. Which sources can supply a plugin today, and what does each lose?
2. Why does each obvious fix (reinstall with `--with`, operator directories, an
   in-process overlay) fail?
3. What do the three downstream plugins actually need from the host process?
4. Is out-of-process hook proxying fast and robust enough, and what does it cost?
5. What constraints does the macOS app add?
6. How can a repository’s own plugins, and a library’s, be picked up automatically, and
   what has to be true before any of their code runs?

## Scope

In scope: plugin sources, automatic discovery of a repository’s plugins, trust, process
and dependency isolation, SDK compatibility, lifecycle, the macOS app’s part,
diagnostics, migration, and an author test harness.
Out of scope: the downstream issues that do not concern sources, such as the 256 KB JSON
classification cap and the visualization palette’s missing dark-theme values.

## Findings

### How Plugins Load Today

Read on this branch and reproduced with its `metab` (0.12.1.dev426) and with the
installed uv tool (0.12.1.dev38).

| Source | Recorded | JavaScript | Python hooks | Log adapters |
| --- | --- | --- | --- | --- |
| Built-ins in `builtin_plugins/` | the wheel | yes | yes, in process | built-in names only |
| `metabrowser.plugins` entry points in Metabrowser’s environment | that environment | yes | yes, in process | registered as an import side effect |
| `--plugins-dir` and `METABROWSER_PLUGINS_DIRS` | per invocation | yes | dropped with a warning | never registered |

`discover_plugins` (`plugin_loader/discovery.py`) runs once when `metabrowser.server` is
first imported, calls `importlib.metadata.entry_points(group="metabrowser.plugins")` on
the running interpreter, and imports each entry point’s module to get its plugin
directory. `build_plugin_routes` (`plugin_loader/static_assets.py`) imports each
`[[data_hook]]` sidekick in process and mounts one route per hook.
For a plugin whose source starts with `local:` it skips every hook and logs that
operator-directory plugins are JavaScript-only.

The uv tool install lists only built-ins:

```text
$ metab --version
metab 0.12.1.dev38+1db567f77
$ metab --plugins
NAME           SOURCE   KINDS       VIEWS  HOOKS
agent-log      builtin  agent-log   3      charts
...
unknown-jsonl  builtin  -           2      -
```

The motivating plugin, at its SDK 0.7 port, loaded through `--plugins-dir`:

```text
$ metab --plugin <plugin> --plugins-dir <checkout>/…/plugin-parent
data hooks:
  (disabled for operator-directory plugins: info, viz-model, and its four other hooks)
$ metab --doctor --plugins-dir …
metab --doctor: 1 problem(s):
  • plugin '<plugin>' declares Python data hooks, but operator-directory plugins are
    JavaScript-only; package the plugin behind an installed metabrowser.plugins entry point
```

Against a fixture with one line of each of its two log formats, its adapter-classified
kinds fall back, and its hooks are absent:

```text
$ metab <fixture> --plugins-dir … --show pool.jsonl
kind: unknown-jsonl
$ metab <fixture> --plugins-dir … --show process.jsonl
kind: unknown-jsonl
$ metab <fixture> --plugins-dir … --api '/api/plugin/<plugin>/info'
status: 404
```

The SDK gate is strict equality (`PluginManifest.validate_consistency`): the same
plugin’s earlier copy, which declares `sdk_version = "0.5"`, is refused by a host that
provides 0.7, with “update the plugin for the current SDK and set sdk_version
accordingly”.

### Installing into Metabrowser’s Environment Fails on Exact Pins

Metabrowser 0.12 pins `kpress==0.3.5`, `markdown-it-py==4.2.0`, and `softschema==0.8.1`
in `pyproject.toml`. Resolving what `uv tool install metabrowser --with <plugin>` must
solve:

```text
$ printf 'metabrowser==0.12.0\nsoftschema>=0.9.1,<0.10\n' | uv pip compile --no-config --python-version 3.14 -
  × No solution found when resolving dependencies:
  ╰─▶ Because metabrowser>=0.12.0 depends on softschema==0.8.1 and you require
      metabrowser==0.12.0, we can conclude that you require softschema==0.8.1.
      And because you require softschema>=0.9.1,<0.10, we can conclude that
      your requirements are unsatisfiable.
```

The published plugin release resolves only by taking an older Metabrowser: its `browser`
extra, resolved alone, selects `metabrowser==0.9.1` with `softschema==0.9.1`, and a
plugin built for 0.9.1 declares SDK 0.5, which 0.12 refuses.
Requesting `metabrowser==0.12.0` beside that extra has no solution.

Even with ranges instead of pins, `--with` couples every plugin to Metabrowser and to
every other plugin in one resolution, and adding a plugin rewrites Metabrowser’s
environment, which the owner’s requirement rules out.

### The App Adds Two More Limits

- **No operator directories reach a server.** `ChildEnvironment.build`
  (`apps/macos/Sources/ShellCore/Runtime/ChildEnvironment.swift`) passes only identity,
  locale, temporary-directory, ssh-agent, and proxy names, so `METABROWSER_PLUGINS_DIRS`
  from a Terminal profile never arrives.
  `CLIServeLaunch` passes no `--plugins-dir`. A `.env` file cannot supply the name
  either (`metabrowser/dotenv.py`), reproduced:

  ```text
  $ cd <folder whose .env sets METABROWSER_PLUGINS_DIRS> && metab --plugins
  …/.env: ignored METABROWSER_PLUGINS_DIRS — a dotenv file may only set
  METABROWSER_LOG_LEVEL, METABROWSER_REQUEST_LOG. Export the others in the environment
  instead; see SECURITY.md.
  ```

  The `.env` rule is a deliberate trust boundary and should stay.
  The consequence is that an app window can only use entry points installed into the CLI
  install, which is the path the exact pins block.

- **The configuration home can differ between Terminal and the app (inferred from
  source).** The allowlist also drops `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`,
  `METABROWSER_CONFIG_DIR`, and `METABROWSER_CACHE_DIR`. A user who sets one in a shell
  profile gets one home in Terminal and the default home in app-launched servers.
  This already affects the repository cache; a plugin registry in the configuration home
  would inherit it.

### What the Downstream Plugins Need from the Host

Read from the three plugins’ current sources.

| Need | Used by | Where it lives today |
| --- | --- | --- |
| `resolve_path`, `resolve_directory`, `relativize_path` | all three | `metabrowser.paths_safe`, keyed by the module-level `ROOT_DIR` |
| `ArtifactPath` (gzip and zlib, bounded) | the motivating plugin | `metabrowser.gz_io`, stdlib only |
| `register_log_adapter`, `detect_adapter`, `LogEvent` | the motivating plugin | `metabrowser.logutil.parsing`, a module-level registry |
| `register_root_callback` | the motivating plugin | `metabrowser.paths_safe` |
| `extract_agent_charts_cached` | the motivating plugin | Metabrowser’s own agent-log projection |
| A Starlette `Request` | all three | only `request.query_params` is read |
| A Starlette `Response` | all three | `JSONResponse`, and one HTML `Response` |

Every hook is a `GET` that reads its query string and returns JSON or bytes; none
streams. The motivating plugin’s log adapters register when its entry-point module is
imported, and its parsers wrap its own library’s parsers.
Its plugin library declares `metabrowser==0.12.0` as a dependency of its `browser` extra
only to import these names.

The source-agnostic content reader (`resolve_content`, `read_content_window`) is the
documented way to read bytes on both a folder and a Git-revision pin; none of the three
uses it yet, and an out-of-process design must still serve it.

### The Spike: Data Hooks Over Stdio

`explorations/plugin-worker-spike/` holds two scripts.
`worker.py` is stdlib-only and runs as `<env-python> -I -B worker.py` inside a plugin
environment. It lists that environment’s `metabrowser.plugins` entry points, calls hook
handlers with a Starlette `Request` built from the request’s fields (Starlette is the
plugins’ own dependency), and answers with status, headers, and body.
`host.py` runs with the host Metabrowser’s interpreter, spawns the worker, reads every
listed manifest with the host’s own schema, and measures.
Frames are one JSON header line followed by `body_len` raw bytes; requests carry ids, so
several can be in flight.

The plugin environment was the downstream application repository’s locked environment:
Python 3.14.7, Metabrowser 0.9.1, and all three plugins at their SDK 0.5 releases.
The host was this branch’s Metabrowser 0.12.1.dev426. The served root was that
repository’s checkout, and the large hook was the motivating plugin’s process-graph
model for a real process specification.
Two shortcuts are marked in the code: the worker sets the root by calling that
environment’s private `metabrowser.paths_safe._set_root_dir`, and it reads adapter names
from the private `_PLUGIN_ADAPTERS`. Hooks were called past the host’s SDK gate, which
refused all three 0.5 manifests as expected.

Measured on an Apple M1 Pro with 32 GB, macOS 26.5.2, under a load average near 8 from
other work. Four runs; the ranges are across runs.

| Measure | Result |
| --- | --- |
| Spawn to first reply | 68–89 ms |
| Listing three plugins (imports their modules) | 251–469 ms |
| Worker resident memory after listing | 61 MB |
| Worker resident memory after the large hook | 121 MB |
| Trivial hook round trip, 300 calls | median 0.13–0.17 ms, p95 0.17–0.30 ms |
| Transport overhead on the trivial hook | 0.10 ms median |
| Large hook: handler time, response size | 1.23–1.43 s, 429,248 bytes |
| Large hook: transport overhead | 10–27 ms |
| Trivial hooks issued beside the large one | median 8.2–8.5 ms, max 47–68 ms |
| Adapter detection on a 20-line head | 0.2–0.7 ms |
| 100,000-line log, 2,000-line batches, events echo `raw` | 1.23–1.34 s total, 0.36–0.39 s parsing, 41.8 MB of events |
| The same, events without `raw` (three runs) | 1.01–1.10 s total, 0.40–0.43 s parsing, 24.6 MB of events |
| Exit after stdin closes | 4.2–4.6 ms, status 0 |

What this shows:

- **Transport is not the cost.** A tenth of a millisecond per call and 10–27 ms on a 429
  KB body are small beside a 1.3 s handler, and well inside the shell’s 50 ms spinner
  threshold for small hooks.
- **The lifeline works.** The worker exits when its stdin closes (in the second spike,
  its request pipe), so a worker cannot outlive the server that started it, the same
  mechanism as `metab --exit-on-eof`.
- **Version skew between host and plugin environment is harmless at this boundary.** The
  host read the manifests itself and the worker answered from a different Metabrowser
  version, because only manifests, frames, and the plugin’s own code cross it.
- **CPU-heavy hooks contend in whatever process runs them.** Small calls slowed from
  0.14 ms to about 8 ms median beside the large hook, because the handler thread holds
  the GIL in bursts. In the worker this stays inside the worker; in process today it
  lands on the server’s event loop, which may be what a downstream observation of a
  plugin script timing out during a 10-second hook describes (inferred, not reproduced).
- **Proxied log parsing needs its own design.** Transport and JSON codec work cost more
  than the parse: 0.87–0.96 s against 0.36–0.39 s with `raw` echoed, and 0.62–0.67 s
  against 0.40–0.43 s without it.
  Dropping the echoed `raw` saved about 41% of the bytes and 30% of the transport, but
  the measurement only decoded the events: the host would also have to reattach each
  source line and encode again, so the saving is not net.
  The plan makes detection declarative, so classification need not wait on a worker, and
  measures splicing the worker’s serialized events into the response before choosing a
  wire shape.
- **Memory is per worker.** 61–121 MB for one environment is close to a server’s own
  footprint, so workers start on demand and exit when idle rather than with every
  server.

### The Second Spike: A Host-Shipped Runtime

`host_runtime.py`, `runtime_worker.py`, and `runtime_metabrowser.py` in the same folder
try the shape the plan now recommends.
The host assembles a runtime folder from its own code, the shim installed as
`metabrowser/__init__.py` beside verbatim copies of its `gz_io.py` and
`content_errors.py`, and spawns the worker with `posix_spawn`: the request pipe on
descriptor 3 and the reply pipe on 4, `/dev/null` on 0, the log on 1 and 2. The worker
puts the runtime first on `sys.path`, marks 3 and 4 close-on-exec, and ignores SIGINT.
Hooks get a small request object with `query_params`, not a Starlette `Request`. The
worker asks the host for built-in adapter detection and for the agent-log chart
projection, which the host computes after checking the path against that worker’s root.

The same downstream environment and checkout as above, two runs, under a load average
near 30:

| Measure | Result |
| --- | --- |
| Plugins listed from the environment, through the injected runtime | all three, no errors; both adapters registered through the public `register_log_adapter` |
| Spawn to listed (imports included) | 779–898 ms |
| Trivial hook round trip, 200 calls | median 0.26–0.52 ms |
| Process-graph hook | status 200, 429,248 bytes, 1.8–2.6 s in the handler |
| Charts hook on a pool log | status 200, through the runtime’s `ArtifactPath` and `register_root_callback` |
| Charts hook on an agent log | status 200, one chart, after two host calls (built-in detection, chart projection) |
| A plugin subprocess printing, reading stdin, and writing to descriptor 4 | its output went to the log, `cat` saw end of file, `Bad file descriptor` on 4, and the next hook answered |
| SIGINT sent to the worker | the next hook answered |
| A synchronous handler that sleeps 60 s, deadline 1 s plus 1 s grace | killed after 2.0 s; respawned and listed in 369–426 ms |
| Resident memory after the large hook | 113–118 MB |
| Exit after the request pipe closes | 2–4 ms, status 0 |

So the plugins’ current code needs no change to run this way, and the environment does
not need the SDK or Metabrowser installed for it.
What the spike leaves out is in its README: the identity codec, the content reader’s
handle table, cancelling an async handler, and live streams.
The host’s log-parsing module imports `prettyfmt`, so the built-in detectors are
answered by the host here; shipping them in the runtime means separating them from that
dependency.

### Subinterpreters and In-Process Overlays

Two in-process alternatives were tested directly, because each would avoid a second
process:

```text
$ <plugin env python 3.14> -I -B  # import inside a PEP 734 subinterpreter
pydantic_core -> ExecutionFailed ImportError: module pydantic_core._pydantic_core does not support loading in subinterpreters
yaml -> imported

$ <host python> -I -B  # site.addsitedir(<plugin env site-packages>) after Metabrowser loaded
metabrowser module : 0.12.1.dev426+41858a3d (host)
softschema version first on path: 0.8.1
plugin env holds softschema ['0.9.1']
plugin sidekick imported from <plugin>/metabrowser_plugin/sidekick.py
```

The overlay imported the plugin without an error while binding it to the wrong
Softschema, which is the worst outcome: it works until a code path that differs between
0.8 and 0.9 runs.

### Repository Plugins Today

The downstream application repository is a uv workspace.
Its members include its two plugin packages, which declare `metabrowser.plugins` entry
points in their `pyproject.toml`, and the workflow library, a Git submodule under
`vendor/` whose own `pyproject.toml` declares the third.
`uv sync` installs all three into the workspace’s `.venv` as editable packages, so the
plugins are found when that environment’s own `metab` runs, as
`uv run --frozen --package <library> metab ...`. A system `metab` or the macOS app sees
none, by the mechanism in How Plugins Load Today.
The plugin packages and the library’s `browser` extra each pin `metabrowser==0.12.0` on
the repository’s main branch, which puts that exact Metabrowser into the workspace lock;
the repository validates its plugin wheels with a script that builds an isolated
environment around a pinned Metabrowser.

An import-free reading of the same environment, run with the host’s interpreter:

```text
127 dist-infos scanned in 30.6 ms; plugin dists:
  ('<library>-0.5.1.dev43+bff0827.dist-info', {...}, 'editable', 'file://<repo>/vendor/<library>')
  ('<plugin-a>-0.0.1.dist-info', {...}, 'editable', 'file://<repo>/<plugin-a>')
  ('<plugin-b>-0.0.1.dist-info', {...}, 'editable', 'file://<repo>/<plugin-b>')
  member vendor/<library> declares {...}
  member <plugin-a> declares {...}
  member <plugin-b> declares {...}
```

It reads `entry_points.txt` and `direct_url.json` from each `*.dist-info`, and each
workspace member’s `pyproject.toml`, all of which are data.
One run, warm page cache.
An entry point’s value is `module:callable`, so where its plugin directory is can be
known only by importing the module; the static reading gives names, distributions,
versions, and where each was installed from, which is what a consent prompt needs.
It cannot say which plugins are the repository’s own: `direct_url.json` records all
three as editable installs from `file://` paths inside the repository, and the library
differs only by living under `vendor/`. Entry points are not conditional on extras, so a
library that puts its plugin’s dependencies behind an extra advertises a plugin that a
consumer without the extra cannot import (inferred from the packaging metadata format).

The workflow library discovers its own extensions the same way Metabrowser does today:
`importlib.metadata.entry_points` for several groups in the running environment.
Its design document describes a second phase that walks up from the working directory to
the uv workspace root and scans members that are not installed; a search of its source
found no implementation of that phase (inferred, not run).
Its processes are files referenced by path, so they need no registry (not verified
further).

### How Other Tools Decide to Trust a Folder

| Tool | Records | After a change | Parent folder | Revoking |
| --- | --- | --- | --- | --- |
| VS Code Workspace Trust | the folder path | not described as asking again | trusting a parent trusts its subfolders | “Don’t Trust”, or remove it from the list |
| `mise trust` | the config path; a hash in paranoid mode | paranoid mode: the edited file is untrusted again | `trusted_config_paths` trusts by path, without a hash | `--untrust`, `--ignore` |
| `direnv allow` | the approved content (the allow file is named by a hash) | blocked until allowed again: “Run `direnv allow` to approve its content” (direnv 2.36.0, reproduced with a scratch data home) | each `.envrc` on its own | `direnv deny` |

Sources: the VS Code Workspace Trust guide, mise’s `trust` and paranoid pages, and the
direnv manual. VS Code’s Restricted Mode also disables tasks, debugging, the terminal,
and extensions that have not declared support, which is the closest analog to what an
untrusted repository may do here: be browsed, and run nothing.

## Options Considered

### Option A: Reinstall Metabrowser with `--with` (Rejected)

The earlier brief’s plugin mode would re-run
`uv tool install metabrowser==<current> --with <every plugin>`. It is exactly the
reinstall the requirement rules out, it fails today on exact pins, and with ranges it
still makes Metabrowser and every plugin co-resolve, so one plugin’s upgrade can block
another or Metabrowser itself.
Declaring ranges is still worth doing for plugins that do live in Metabrowser’s
environment, as an independent fix.

### Option B: Operator Directories Only (Rejected)

Persisting `--plugins-dir` values would reach the app, but every view of the motivating
plugin depends on a hook or an adapter, and a directory carries no environment to run
them in. Directories stay a source for JavaScript-only plugins.

### Option C: Overlay the Plugin Environment In Process (Rejected)

`site.addsitedir`, `.pth` injection, or `sys.path` edits bind the plugin to whatever
Metabrowser already imported, as reproduced, and also mix native extensions built for
another interpreter when the Python versions differ.

### Option D: Subinterpreters (Rejected)

PEP 734 subinterpreters have separate module state, but extension modules must opt in
and `pydantic_core` refuses, as reproduced.
They would also require the plugin environment to match the host’s exact Python build.

### Option E: Delegate Serving to the Plugin Environment’s Own `metab` (Rejected)

The downstream environment already contains a Metabrowser, so `metab` could re-execute
the server from it. That environment’s Metabrowser was 0.9.1, so the user would get
whatever version each project pins, and versions would then share one cache and
configuration home: a newer release migrates the layout, after which an older one fails
with `FutureLayoutFormatError` (`cache/layout.py`). The app would also face a different
host protocol per folder.

### Option F: JavaScript-Only Plugins with Declarative Data (Rejected)

The motivating plugin’s hooks compute a process-graph model in its own Python library,
1.2–1.4 s of work in the spike.
Moving that into the browser means rewriting the library.

### Option G: Out-of-Process Worker Using the Environment’s Own `metabrowser` (Rejected as Written)

The downstream candidate: one worker per registered plugin environment, static assets
served by the host, hooks proxied over stdio, each environment keeping its own lock.
The spike confirms the transport, the lifeline, the process model, and the version
independence of manifests.
Its binding is the problem.
The worker must set the root in the environment’s own `metabrowser` through private
names (the spike used `_set_root_dir` and `_PLUGIN_ADAPTERS`, whose shapes differ by
version), it has no session from which to read a Git pin’s content, and every plugin
environment must still install all of Metabrowser, with its exact pins, only to import a
dozen helpers.

### Option H: Out-of-Process Workers over a Runtime the Host Injects (Recommended)

Option G’s transport and process model, with the plugin-side runtime (the sidekick
names, the worker loop, and the bounded readers) shipped inside Metabrowser and put
first on the worker’s path at spawn, importable under the documented name `metabrowser`.
Host and worker are then one artifact, as the repository’s rule for internal contracts
assumes; security fixes to path and decompression bounds reach every plugin with the
next Metabrowser; and nothing is installed in plugin environments.
The second spike ran the three downstream plugins this way unchanged.
The plan specifies it.

### Option O: A Plugin SDK Package Installed in Each Environment (Rejected)

An earlier revision of this design: a stdlib-only `metabrowser-plugin-sdk` package that
each plugin environment installs, with a negotiated worker protocol.
It freezes security-sensitive code at whatever version each environment locked, makes
two plugins in one environment agree on one SDK range, leaves checked-in directory
plugins with nothing to bring the SDK, gives plugin authors three version axes, and was
never what a spike ran.

### Option I: One Shared Worker per Environment Across Roots (Deferred)

A per-user worker per environment would save the 61–121 MB that each server’s worker
costs, but needs a supervisor outside any one server, a root on every call, and cache
isolation between roots inside plugin code.
The plan starts with per-server workers that start on demand and exit when idle, and
revisits this if the app’s warm-folder budget needs it.

### Option K: Load a Repository’s Plugins Automatically Without Trust (Rejected)

Every folder a user browses, a cloned stranger’s repository included, would run its
plugin JavaScript in the page and its Python in a worker.
The served root has never been a plugin source for exactly this reason.

### Option L: An Opt-In Declaration File per Repository (Superseded)

The first version of this design had a repository list its plugin sources in a file that
the user then trusted.
The owner asked for automatic pickup instead, and the declaration duplicates what the
workspace’s `pyproject.toml` files and lock already say.

### Option M: What a Trust Decision Binds To (Per Clone with Named Providers)

- **Path only**, as in VS Code: never asks again, so anything that can write the tree or
  add a dependency runs code.
- **A parent folder scoped by origin**: fewest prompts, but not a boundary, because the
  origin is data inside the directory being judged (reproduced above).
  Kept only as a later convenience whose description says that everything under the
  folder runs code.
- **Content**, as in direnv: asks on nearly every pull in a workspace with 10 editable
  members.
- **Per clone, with the named plugin providers** (recommended): asks once per clone, and
  again only when a new distribution starts providing a plugin; version bumps of an
  approved provider do not ask.
  The clone is identified by its Git common directory, so its linked worktrees share the
  decision.

### Option N: Metabrowser Builds Its Own Environment for Each Repository (Rejected)

Syncing the lock into a Metabrowser-owned environment in the cache would leave the
developer’s `.venv` alone, but doubles disk use and downloads for every repository and
still runs the workspace’s build backends.
The repository’s own environment is the one its developers already keep current.

### Option J: HTTP over a Unix Socket Instead of Stdio (Not Chosen)

An HTTP worker needs an HTTP server in every plugin environment, socket-path management,
and a separate lifetime signal.
Stdio gives the lifeline for free and needed no dependencies in the spike.

## Recommendations

Adopt Option H, specified in
[Plugin Sources and Out-of-Process Plugin Environments](../specs/active/plan-2026-11-12-plugin-sources.md):
a runtime the host injects into one worker per plugin environment per server, a registry
of scoped plugin sources, declarative log-adapter detection, a semantic-version gate on
one plugin API version, and native app settings that run the same CLI modes.
Discover a repository’s plugins statically and load them after a per-clone consent that
names their providers (Option M). The plan’s Key Decisions section lists the choices
still open.
Declare dependency ranges in Metabrowser’s `pyproject.toml` as an independent
fix.

## Methodology

- Read the plugin loader, server startup, CLI plugin modes, dotenv rules, configuration
  home, and the macOS app’s supervisor and child environment on `claude/v1-final-review`
  at `41858a3d`.
- Reproduced with `uv --config-file uv.toml run --frozen metab` on this branch and with
  the installed uv tool.
  Scratch files lived in the checkout’s gitignored `tmp/`.
- Resolved dependencies with `uv pip compile --no-config --python-version 3.14`, which
  installs nothing.
- Ran the spike four times; `explorations/plugin-worker-spike/README.md` gives the
  command. The plugin environment was used read-only, with `-B` so no bytecode was
  written into it.
- Read the downstream repository’s workspace and plugin `pyproject.toml` files on its
  main branch through the GitHub API, and scanned its local environment’s `*.dist-info`
  metadata with a short script that imports nothing from it.
- Checked direnv’s behavior with direnv 2.36.0 and scratch `XDG_DATA_HOME` and
  `XDG_CONFIG_HOME`, so the user’s own allow list was not touched; read the VS Code and
  mise trust documentation.
- Ran the second spike twice against the same environment and checkout, and checked a
  forged origin with two hand-written files under a scratch `.git`.
- Read the example repository’s `Makefile` install target and counted the editable
  members in its lock; ran `python -I -S` on Metabrowser’s own interpreter.
- An independent design review checked this brief and the plan.
  Its in-process parsing baseline is quoted with its conditions and was not reproduced
  here.
- Claims marked inferred rest on reading alone.

## References

- [Plugin Authoring](../../plugins.md)
- [Native macOS App for Metabrowser](research-2026-11-08-macos-app-packaging.md)
- [Setup Flows for `metab` and the Native macOS App](research-2026-11-11-uv-and-macos-app-install.md)
- [Compatibility and Legacy Code](../../development.md#compatibility-and-legacy-code)
- `apps/macos/README.md` (A Folder’s Server, The Child’s Environment)
- [PEP 734](https://peps.python.org/pep-0734/), multiple interpreters in the standard
  library
- [VS Code Workspace Trust](https://code.visualstudio.com/docs/editing/workspaces/workspace-trust),
  [`mise trust`](https://mise.jdx.dev/cli/trust.html),
  [mise paranoid mode](https://mise.jdx.dev/paranoid.html), and the
  [direnv manual](https://direnv.net/man/direnv.1.html)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
