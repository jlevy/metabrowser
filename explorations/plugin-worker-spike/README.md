# Plugin Worker Spike

A one-time spike, not a measured-improvement loop: it answers whether Python data hooks
and log parsing can be served from a plugin’s own environment over stdio, and what that
costs. The results and their reading are in
[Loading Plugins from Any Source](../../docs/project/research/research-2026-11-12-plugin-sources.md);
the design that follows from them is
[Plugin Sources and Out-of-Process Plugin Environments](../../docs/project/specs/active/plan-2026-11-12-plugin-sources.md).

- `worker.py` is stdlib-only and runs with the plugin environment’s interpreter.
  It lists that environment’s `metabrowser.plugins` entry points, calls hooks, detects
  adapters, and parses log batches.
- `host.py` runs with the host Metabrowser’s interpreter, spawns the worker, reads each
  listed manifest with the host’s own schema, and records the measurements as JSON.

Both halves mark the shortcuts the plan replaces: the worker sets the root and reads
adapters through private names of the environment’s own Metabrowser, and hooks are
called past the host’s SDK gate.

## Running It

You need a plugin environment whose plugin has `info` and `viz-model` hooks and two log
adapters, as the motivating domain plugin does, a root it can serve, a process
specification inside that root, and a folder holding `pool.jsonl` and `process.jsonl`
with one line of each log format.

```shell
uv --config-file uv.toml run --frozen python -I -B \
  explorations/plugin-worker-spike/host.py \
  PLUGIN_ENV/bin/python ROOT RELATIVE/PROCESS/SPEC.md FIXTURE_DIR tmp/results.json
```

`-B` keeps the worker from writing bytecode into the plugin environment, so the run
leaves that environment unchanged.
Nothing here runs in CI.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
