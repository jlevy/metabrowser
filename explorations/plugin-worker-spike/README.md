# Plugin Worker Spike

One-time spikes, not a measured-improvement loop.
They answer whether Python data hooks and log parsing can be served from a plugin’s own
environment, what that costs, how such a worker fails, and whether the operating system
can confine it. The results and their reading are in
[Loading Plugins from Any Source](../../docs/project/research/research-2026-11-12-plugin-sources.md);
the design that follows from them is
[Plugin Sources, Process Isolation, and Out-of-Process Plugin Environments](../../docs/project/specs/active/plan-2026-11-12-plugin-sources.md).

## Two Shapes

**The first shape** (`worker.py`, `host.py`) runs a stdlib-only worker over stdin and
stdout, and binds plugin code to the plugin environment’s own Metabrowser through
private names (`_set_root_dir`, `_PLUGIN_ADAPTERS`). It measured transport, memory, and
log-parsing cost. The plan rejects its binding.
A week after the runs, Metabrowser 0.13.0 replaced `_PLUGIN_ADAPTERS` with `_ADAPTERS`
and a public `registered_log_adapters`, so this worker now runs only on an environment
older than 0.13.0. That is the skew the second shape removes.
Its large-hook timing wraps a loop that sleeps 20 ms, so the transport overhead it
reports for that hook is not one; `probes.py transport` times it directly.

**The second shape** (`runtime_worker.py`, `runtime_metabrowser.py`, `host_runtime.py`)
is the plan’s:

- The host assembles a runtime folder from its own code: `runtime_metabrowser.py`
  installed as `metabrowser/__init__.py`, beside verbatim copies of the host’s
  `gz_io.py` and `content_errors.py`.
- The worker puts that folder first on `sys.path`, so plugin code that imports the
  documented sidekick names (`from metabrowser import resolve_path`) gets the host’s
  runtime, whatever Metabrowser version its own environment holds.
  The plan’s second revision gives the runtime an import name of its own; the mechanism
  is the same.
- The host passes the protocol pipe numbers to `subprocess.Popen` with `pass_fds`. The
  worker marks both close-on-exec.
  Stdin is `/dev/null`, stdout goes to the stderr log, and the worker ignores SIGINT. A
  platform confinement prefix precedes the worker command when requested.
- The worker can ask the host something in the middle of a call (`wid` frames).
  The spike uses that for built-in adapter detection and the agent-log chart projection.
- Hooks get a small request object with `query_params`, not a Starlette `Request`.

What it still leaves out: the identity codec (path containment here is a plain `resolve`
and `relative_to`), the content reader and its handle table, cancellation of an async
handler, and live streams.
The spike host imports Metabrowser’s built-in agent adapters so the downstream chart
hook can ask the host to classify and project an agent log.

## Probes

`probes.py` asks what the two shapes left open, on a stand-in plugin so that it needs
neither a network nor the downstream plugins, which are not public.
It builds a plugin environment itself: a standard-library venv, with the stand-in’s
entry point written by hand into a `dist-info` folder and its source added by a `.pth`
file.

- `lifecycle`: the lifeline while a hook blocks the worker’s event loop, what a kill at
  a deadline takes with it and leaves behind, and a forked child writing to the reply
  pipe.
- `transport`: what a response costs by its size.
- `confined`: the same worker behind this platform’s confinement prefix, chosen by
  `confine_backend.py`, and what a hook can then reach.
- `identity`: whether a Git common directory’s device and inode identify a clone, three
  ways a folder can claim to be a trusted clone’s worktree, and a worktree moved by
  hand.
- `watchdog`: whether a group leader that holds its own lifeline ends a target that
  ignores signals, and that target’s child, when the server is killed.
- `locate`: a provider’s plugin directory found from `RECORD` or a `.pth` path line,
  with nothing imported.
- `pth`: whether an environment’s `.pth` code runs as its interpreter starts, and
  whether the confinement prefix is in place before it.
- `pdf` (Linux): the repository’s own PDF render child, unmodified, behind
  `confine_linux.py` through the `Sandbox` seam it already has.

`standin/` is that plugin: an entry point, two log adapters, and hooks that import only
the documented names.
It stands in for the mechanism, and says nothing about what a real plugin costs.

## Confinement on Linux

`confine_linux.py` is a command prefix, as `sandbox-exec -p PROFILE` is on macOS: the
host’s interpreter applies a Landlock ruleset and a seccomp filter to itself and then
replaces itself with the child.
Standard library only.
Its policy names what to read and write, whether the internet families are allowed, and
whether the child may start programs.
`confine_probe.py` runs one checking program bare and under four policies, and times the
prefix. One of the four leaves `io_uring_setup` open, to show the hole a filter on
`socket` alone has: a socket made by `IORING_OP_SOCKET` reaches a Unix socket outside
every grant. A second review of this design found that hole in the launcher’s first
version, and several of the probes here are its checks, rewritten to run on the
stand-in.

## Confinement on macOS

`confine_macos.py` renders the same policy as a deny-by-default `sandbox-exec` profile,
starting from the PDF render child’s grants in
`src/metabrowser/builtin_plugins/pdf/preview_isolation.py`; the prefix is
`sandbox-exec -p PROFILE`. `confine_backend.py` picks it or the Linux launcher, so
`probes.py` runs on both.

`macos_probe.py` is the spike `mb-gmut` asks for, and runs only on a Mac.
Its `learn` probe serves the stand-in’s ordinary hooks under the default profile and
reports kernel denials for that worker’s PID. It keeps those observations out of the
profile. It also covers what only macOS has: the internet granted alone, the Mach
services `getpwuid` and the resolver use, a descriptor handed over by a same-number
`dup2`, `sandbox-exec` inside another sandbox, the privacy controls, and the prefix’s
cost. With `--real`, it does the same for the downstream plugins.

The macOS runs used macOS 26.5.2 on Apple Silicon.
Each profile served the stand-in’s hooks.
The default allowed the served files and scratch writes and refused reads, writes, and
network access outside its grants.
The internet profile restored TCP, UDP send, and DNS while leaving the test Unix socket
inaccessible. Libinfo restored `getpwuid` on its own.
The stand-in and downstream hooks completed without it.

## Results

`results/` holds the JSON each probe printed, named by date and platform, with no path
in it.
The 2026-11-26 files are from Linux 6.18 on ext4, x86-64, Python 3.13.18, as root,
at a load average near 0. The two without a suffix are the first run, whose launcher
refused `socket` alone; the two ending `-2` are the run after the launcher was fixed and
the later probes were added.

[The macOS run](results/2026-11-26-macos.json) records the working hooks and grants, and
the bare and confined timing samples.
All three downstream entry points loaded from a separate environment.
The workflow plugin’s process model and its nonempty chart responses matched byte for
byte. The [downstream follow-up](results/2026-11-26-macos-downstream.json) adds six
read-only routes from the other two providers with matching responses, including a raw
HTML response with CSP and `nosniff`. It also records the `.pth` control.
Both interpreters ran the control command, and only the bare interpreter wrote the
marker. Startup timing varied with host load, so these samples do not isolate the
prefix’s cost. The watchdog cleaned up its supervised group after the server died.
APFS did not reuse the Git directory identity in five reclones.

An ad-hoc signed Swift launcher with Hardened Runtime enabled started the host, which
then served the confined stand-in.
The two protocol pipes survived via `pass_fds`. The installed app’s privacy attribution,
privacy prompt ordering, and folder-stop workflow remain unverified.

## Running It

The probes need only the repository:

```shell
uv --config-file uv.toml run --frozen python -I -B \
  explorations/plugin-worker-spike/probes.py tmp/probes-run
uv --config-file uv.toml run --frozen python -I -B \
  explorations/plugin-worker-spike/confine_probe.py tmp/confine-run
```

`probes.py` takes the names of the probes to run after the folder, and runs all of them
without one. The folder is scratch that a rerun recreates.

The two shapes’ own hosts need a plugin environment whose plugin has `info`,
`viz-model`, and `charts` hooks and two log adapters, as the motivating domain plugin
does; a root it can serve with a process specification inside it; and a fixture folder
with `pool.jsonl`, `process.jsonl`, and `agent.jsonl`.

```shell
uv --config-file uv.toml run --frozen python -I -B \
  explorations/plugin-worker-spike/host_runtime.py \
  PLUGIN_ENV/bin/python ROOT RELATIVE/PROCESS/SPEC.md FIXTURE_DIR tmp/runtime-run
```

`host.py` takes the same arguments with an output file in place of the folder.
`-B` keeps the worker from writing bytecode into the plugin environment, so a run leaves
that environment unchanged.

On a Mac, from a checkout after `make install`:

```shell
uv --config-file uv.toml run --frozen python -I -B \
  explorations/plugin-worker-spike/macos_probe.py tmp/macos-run > tmp/macos.json
```

Set `TMPDIR` to a writable scratch directory.
The Unix socket path under it must fit in macOS’s socket address.
Add `--real PLUGIN_ENV/bin/python ROOT RELATIVE/SPEC.md FIXTURE_DIR` for the downstream
plugins. Add `--cases FILE` to compare more read-only calls.
The file maps a public result label to an object with `plugin` (entry-point name),
`route`, `query` (query parameters), and optional `headers` (lowercase response header
names to record). Use synthetic fixtures.
The probe prints response lengths and hashes and the selected headers.
Use `--privacy FILE` with a synthetic file in a privacy-protected folder and watch the
desktop for a prompt.
Unified-log access depends on the local account’s permissions.
These probes run outside CI.

[HardenedLauncher.swift](HardenedLauncher.swift) can run the same probe from a signed
parent. Build it with `swiftc` in scratch, sign it with
`codesign --force --sign - --options runtime LAUNCHER`, and run
`LAUNCHER HOST_ENV/bin/python -I -B macos_probe.py SCRATCH backend worker descriptors`.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
