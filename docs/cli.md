# The `metab` Command Line

Metabrowser is a local file browser, and `metab` is the same program without the
browser. Every mode below runs the same server code the browser talks to, so what a mode
reports is what the browser would have drawn.

`metab` and `metabrowser` are the same command.

## The Shape of a Command

```shell
metab ROOT [MODE] [OPTIONS]
```

`ROOT` is the directory to serve, or a single file to open directly.
With no mode flag, `metab ROOT` starts the server and opens a browser, the way `open`
opens a folder on macOS.

Mode flags are mutually exclusive: exactly one operation runs per invocation, and
passing two is an error rather than a silent preference.
Options that do not apply to the chosen mode are rejected the same way, so a flag never
looks accepted while being ignored.

## Modes

| Mode | What it does |
| --- | --- |
| *(none)* | Serve `ROOT` and open a browser |
| `--api ROUTE` | Issue one `/api/` route and print the envelope |
| `--show PATH` | Report route, kind, views, and model for one selection |
| `--walk` | Dump the inventory walker’s result |
| `--diff SPEC` | Show a change set between two snapshots |
| `--check-api` | Run the navigation scenario as a pass/fail check |
| `--remote HOST` | Serve a remote directory over an SSH tunnel |
| `--plugins`, `--plugin NAME`, `--doctor` | Inspect installed plugins |

Every mode is read-only except `--api` when the route it names writes, which today means
only `/api/kpress/export`.

## Serving

```shell
# Browse a directory, or open one file directly.
metab ./notes
metab ./notes/report.md

# Select a file relative to the served root.
metab ./notes --path documents/report.pdf

# Start without opening a browser window.
metab ./notes --no-open
```

The server binds `127.0.0.1:8411` by default and walks a bounded port range if that port
is taken.
Do not change `--host` to expose a served root to an untrusted network; see the
[security policy](../SECURITY.md).

## Inspecting Data: `--api`

`--api` issues one route through the real application — same middleware, same routing,
same serialization the browser receives — without binding a port or opening a browser.

```shell
# Any registered route, with its query string exactly as the browser would send it.
metab ./notes --api '/api/file?path=README.md'
metab ./notes --api '/api/tree?depth=2&types=.md'
metab ./notes --api '/api/git/log?limit=5'

# YAML instead of JSON.
metab ./notes --api /api/git/refs --format yaml

# A route that takes a POST body.
metab ./notes --api /api/kpress/render --data request.json
```

Output is the route, the HTTP status, and the normalized envelope:

```console
$ metab ./notes --api '/api/file?path=README.md'
api: /api/file?path=README.md
status: 200
{
  "type": "text",
  "kind": "markdown",
  "views": [ ... ]
}
```

The exit status is non-zero when the route answers outside 2xx, so a script can act on
failure without parsing the body.
Paths under the served root are rewritten to `<ROOT>` so output does not carry the
directory it happened to run in.

Two routes have no meaningful `--api` result: `/api/events` and `/api/stream` are
server-sent-event streams whose responses never terminate.
`--api` bounds the request and reports that rather than hanging.

## Understanding a Selection: `--show`

`--show` answers “what would the browser do with this path” without opening one:

```console
$ metab ./notes --show README.md
show: README.md
route: /view/README.md
kind: markdown
views: rendered (default), source
model: text envelope; size=13386 content_bytes=13386 content_truncated=False
```

Those four lines are the four layers a selection travels — the address it resolves to,
what it is classified as, the tabs a reader would see, and a summary of the data behind
them.

It accepts browser addresses as well as paths, which is the quickest way to check that a
URL resolves the way you expect:

```shell
metab ./notes --show README.md                     # a path
metab ./notes --show /view/README.md               # the same, as a route
metab ./notes --show change.patch/src/main.py      # one entry inside a container file
metab ./repo --show /commit/<revision>             # a commit's change set
metab ./repo --show /commit/<revision>/README.md   # one file inside that change set
```

`--format json` prints the same four layers as an object.

## Reading a Tree: `--walk`

```shell
metab ./notes --walk                       # human-readable report
metab ./notes --walk --format json         # the data the nav panel consumes
metab ./notes --walk --format json --stream  # one record per line
metab ./notes --walk --type .md --age 7d   # the same filters the nav panel offers
```

## Reading a Change Set: `--diff`

```shell
metab ./repo --diff main..feature      # between two revisions
metab ./repo --diff <revision>         # one revision against its first parent
metab ./repo --diff changes.patch      # a patch file under ROOT
metab ./repo --diff <revision> --diff-patch src/main.py   # one file's hunks
metab ./repo --diff <revision> --diff-check               # replay and verify
```

## Diagnostics

```shell
# Pass/fail check of the navigation request sequence.
metab ./notes --check-api

# Plugin inventory and validation.
metab --plugins
metab --plugin markdown
metab --doctor
```

`--check-api` answers “is navigation healthy” in one line.
For the underlying data, `--api` is the more direct tool.

## Remote Directories

```shell
metab --remote example-host --path /srv/shared-files
```

`metab` starts itself on the remote host over SSH and tunnels the port back, so the
browser stays local.
`ROOT` is not used in this mode; the remote directory is `--path`.

## Why the Data Modes Exist

Every route the browser consumes is reachable from `metab` and pinned by a golden
transcript, so a change to a route’s envelope shows up as a readable diff rather than as
a browser that quietly renders the wrong thing.
The rule and its enforcement are in [CLI parity](../AGENTS.md#cli-parity); the table of
what is covered is in
[Views, Models, and Routes](project/architecture/arch-views-models-routes.md).

For agents and scripts, that means the answer to “what does Metabrowser think this file
is” is one command with structured output, and does not require a browser.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
