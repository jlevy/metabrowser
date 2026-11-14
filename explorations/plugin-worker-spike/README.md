# Plugin Worker Spike

A one-time spike, not a measured-improvement loop.
It answers whether Python data hooks and log parsing can be served from a plugin’s own
environment, and what that costs.
The results and their reading are in
[Loading Plugins from Any Source](../../docs/project/research/research-2026-11-12-plugin-sources.md);
the design that follows from them is
[Plugin Sources and Out-of-Process Plugin Environments](../../docs/project/specs/active/plan-2026-11-12-plugin-sources.md).

## Two Shapes

**The first shape** (`worker.py`, `host.py`) runs a stdlib-only worker over stdin and
stdout, and binds plugin code to the plugin environment’s own Metabrowser through
private names (`_set_root_dir`, `_PLUGIN_ADAPTERS`). It measured transport, memory, and
log-parsing cost. The plan rejects its binding.

**The second shape** (`runtime_worker.py`, `runtime_metabrowser.py`, `host_runtime.py`)
is the plan’s:

- The host assembles a runtime folder from its own code: `runtime_metabrowser.py`
  installed as `metabrowser/__init__.py`, beside verbatim copies of the host’s
  `gz_io.py` and `content_errors.py`.
- The worker puts that folder first on `sys.path`, so plugin code that imports the
  documented sidekick names (`from metabrowser import resolve_path`) gets the host’s
  runtime, whatever Metabrowser version its own environment holds.
- The request pipe is descriptor 3 and the reply pipe descriptor 4, both close-on-exec
  in the worker; descriptor 0 is `/dev/null`, descriptor 1 is stderr, and SIGINT is
  ignored. The host spawns it with `posix_spawn`.
- The worker can ask the host something in the middle of a call (`wid` frames).
  The spike uses that for built-in adapter detection and the agent-log chart projection.
- Hooks get a small request object with `query_params`, not a Starlette `Request`.

What it still leaves out: the identity codec (path containment here is a plain `resolve`
and `relative_to`), the content reader and its handle table, cancellation of an async
handler, and live streams.

## Running It

You need a plugin environment whose plugin has `info`, `viz-model`, and `charts` hooks
and two log adapters, as the motivating domain plugin does; a root it can serve with a
process specification inside it; and a fixture folder with `pool.jsonl`,
`process.jsonl`, and `agent.jsonl`.

```shell
uv --config-file uv.toml run --frozen python -I -B \
  explorations/plugin-worker-spike/host_runtime.py \
  PLUGIN_ENV/bin/python ROOT RELATIVE/PROCESS/SPEC.md FIXTURE_DIR tmp/runtime-run
```

`host.py` takes the same arguments with an output file in place of the folder.
`-B` keeps the worker from writing bytecode into the plugin environment, so a run leaves
that environment unchanged.
Nothing here runs in CI.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
