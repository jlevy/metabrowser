# Using the Metabrowser Command Line

Metabrowser is a local file browser, and `metab` is the same program without the
browser. Every mode below runs the same server code the browser talks to, so what a mode
reports is what the browser would have drawn.

**`metab --help` is the reference.** It ships with the program, so it is authoritative
for the flags and arguments of the build you actually have, and it is what an agent or a
script should consult.
This page is the other half: what each mode is *for*, worked examples, and why the data
modes exist. Where the two disagree, believe `--help`.

`metab` and `metabrowser` are the same command.

## The Shape of a Command

```shell
metab ROOT [MODE] [OPTIONS]
```

`ROOT` is the directory to serve, or a single file to open directly.
A clone URL (`https://…`, `ssh://…`, `git@host:path`, or `file://…`) or a GitHub web URL
is a Git source, not a local path.
`https://` and `file://` sources are acquired with `--no-serve`, and also as a side
effect of `--show` or `--api`; ssh stays closed.
`--show` and `--api` inspect a pinned revision in-process; nothing binds a port, and
acquired content is not served.
A bare filesystem path is never treated as a clone origin.
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
| `--no-serve` | Acquire a `file://` Git source into the cache without starting a server |
| `--remote HOST` | Serve a remote directory over an SSH tunnel |
| `--plugins`, `--plugin NAME` | Inspect installed browser plugins |
| `--doctor` | Validate browser plugins and installed artifact capabilities |

Most modes are read-only.
`--no-serve` writes a cache entry for a `file://` source.
`--api` writes only when the route it names writes, which today means
`/api/kpress/export`.

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
`--untrusted` (`METAB_UNTRUSTED=1`) is the conservative content-trust profile: it
disables script execution on `/raw` and keeps mutations off.
`--no-active-content` (`METAB_ACTIVE_CONTENT=0`) is the individual switch for scripts.
`--allow-edits` (`METAB_ALLOW_EDITS=1`) publishes the mutations capability; no write
route consumes it yet.
A flag beats the environment, so `--untrusted` stays conservative whatever the `METAB_*`
variables say and only `--untrusted --allow-edits` lifts it.
Those variables are read from the process environment only: a `.env` or `.env.local`
file contributes only `METABROWSER_LOG_LEVEL` and `METABROWSER_REQUEST_LOG`, and every
other name — the rendering budgets, `METABROWSER_PLUGINS_DIRS`,
`METABROWSER_GCP_PROJECT`, `HOME` — must be exported.
Metabrowser warns when it ignores one of its own.
See [SECURITY.md](../SECURITY.md) for why the list runs that way.
These flags also apply to `--api`, `--show`, and `--check-api`.

## Acquiring a Git source: `--no-serve`

`--no-serve` fetches every object of an `https://` or `file://` source into the
repository cache under `METABROWSER_HOME` (default `~/.metabrowser`) and prints the
source slug, store identity, and revision, without binding a port or opening a browser.
The store is a complete, read-only clone, so later reads never need the origin.
ssh stays closed.

```shell
metab file:///path/to/origin.git --no-serve
metab file:///path/to/origin.git --api /api/cache/layout
metab file:///path/to/origin.git --show README
metab file:///path/to/origin.git --api /api/tree
```

### GitHub URLs

A GitHub URL copied from the browser opens the repository it names, pinned where it
points:

```shell
metab https://github.com/owner/repo --no-serve
metab 'https://github.com/owner/repo/blob/release/v1/docs/guide.md#L10-L20' --no-serve
metab https://github.com/owner/repo/tree/v1.0 --api /api/tree
metab https://github.com/owner/repo/commit/1a2b3c4 --show README.md
```

Every spelling of one repository — `.git`, a trailing slash, `www.`, any letter case,
`git@github.com:owner/repo.git`, and `raw.githubusercontent.com` file URLs — is one
source, `https://github.com/owner/repo`, and one store.
A `/tree/` or `/blob/` URL may name a branch whose name contains `/`; the mirror decides
where the ref ends, preferring a branch, then a tag, then a commit ID. `--no-serve`
prints what the URL selected after the identity lines (`selection`, `pin`, `path`, and
`lines` for a `#L10`, `#L10-L20`, or `#L10C5-L20C8` anchor), and `--show` and `--api`
print the same lines on stderr and pin that commit.
A `/pull/<n>` URL opens the default branch for now and reports the number; pull-request
data arrives in a later release.
Query parameters other than `?plain=1` are dropped.
Any other github.com page, `http://`, and GitHub’s own top-level pages are refused with
a message that names the shape and offers the repository URL.

These modes read the mirror as it is.
A ref or commit that is not in it is reported as `ref_not_found` or `commit_not_found`
rather than fetched; a path that is not at the pinned commit is `path_not_found`. Each
exits with status 1, but the acquisition before it succeeded, so the source stays
published.

Public repositories are cloned anonymously.
When `gh` is installed, it is Git’s credential helper for `https://github.com` and for
nothing else, so a private repository opens once `gh auth login` has signed in an
account that can read it; Metabrowser never reads or stores a token.
With `gh` installed, a first clone is also refused before it starts when GitHub reports
the repository too large to finish within the acquisition deadline.
On a terminal, a first clone reports each phase and the time elapsed.

`--api /api/cache/…` on a `file://` URL acquires as a side effect, then issues the route
against an empty throwaway directory so cache inspection cannot expose origin objects
through `/api/tree`. `--show` and other `--api` routes on that URL acquire or reuse the
store, pin the default revision, and inspect the pin in-process.
Nothing binds a port.
`--show` accepts a display path (`README`) or a `GitPath` wire.
Serving, walking, and `--check-api` still refuse Git sources.
ssh URLs stay closed.
A second `--no-serve` of the same `file://` source reuses the published store.
That cache hit reads only the application home: it runs no Git, does not need the
origin, and works against a home the current user cannot write.
Spellings that normalize to the same address, such as `FILE://localhost/path/` and
`file:///path`, are one source.

Inspect cache state from any local root after an acquire: the cache routes resolve
`METABROWSER_HOME` independently of the served directory.

```shell
metab ./notes --api /api/cache/sources
```

### Refusals, failures, and interruptions

Every refusal prints one `Error:` line and exits with status 1. None of them publishes a
source, and none changes another source already in the cache.

- **A ROOT the grammar rejects** prints `invalid ROOT (<reason>)`. The reason names the
  rule, such as `credentials_in_url` or `option_like`, and the argument itself is not
  repeated, so a token in a URL does not reach the terminal.
- **A Git below the acquisition security floor** refuses a new acquisition with the
  version it found and the versions it accepts.
  The application home is not created.
  Upgrade Git; a source already in the cache is still reused.
- **A source that cannot be fetched** — a missing path, a directory that is not a
  repository, a repository with no commits, or one whose `HEAD` is not a branch —
  publishes nothing. An https origin names why, in parentheses: `not_found_or_private`,
  `network_unreachable`, `tls_failed`, `timed_out` (an origin that stops answering; a
  transfer below 1000 bytes per second for 30 seconds counts as stopped), or
  `too_large`.
- **An acquisition that is interrupted**, by Ctrl-C or by the terminal hanging up, stops
  Git and every helper it started, and leaves nothing visible, because the source is
  published last, after its store.
  A hangup exits with status 129. The next acquisition removes the abandoned staging
  entry, fetches again, and reuses a store that was already published.
  Nothing deletes a published store.

Refusals that concern the application home say how to repair it:

| Message begins | Repair |
| --- | --- |
| `METABROWSER_HOME is set but empty`, `METABROWSER_HOME must be an absolute path` | Unset it, or set it to an absolute path |
| `The Metabrowser application home is accessible to other users` | Run `chmod 700` on it, or use another `METABROWSER_HOME` |
| `An entry in the Metabrowser application home cannot be verified` | Restore the current user’s write permission, or use another `METABROWSER_HOME` |
| `This Metabrowser application home uses format` | Upgrade Metabrowser, or use another `METABROWSER_HOME` |

A home other users can read refuses cache hits as well as new acquisitions.
A home the current user cannot write still reuses cached sources and refuses only new
ones.

## Inspecting Data: `--api`

`--api` issues one route through the real application — same middleware, same routing,
same serialization the browser receives — without binding a port or opening a browser.

Start with the route index, which lists every route this build serves:

```shell
metab ./notes --api /api/routes
```

```shell
# Any registered route, with its query string exactly as the browser would send it.
metab ./notes --api '/api/file?path=README.md'
metab ./notes --api '/api/tree?depth=2&types=.md'
metab ./notes --api '/api/git/log?limit=5'

# Repository cache state in METABROWSER_HOME (default ~/.metabrowser), which is
# reported as absent rather than created when it does not exist.
metab ./notes --api /api/cache/layout
metab ./notes --api '/api/cache/sources?limit=20'

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

### There is no server to start

Every data mode runs the server in-process for the life of the command.
Nothing binds a port, nothing is left running, and a `metab` already serving that
directory is neither required nor consulted — the two do not share state.

Most commands cost about half a second, which is mostly Python starting up.
The exceptions are the routes that read the file inventory — `/api/tree`, `/api/rollup`,
`/api/recent`, `/api/catalog`, `/api/capabilities`, `/api/index/meta`,
`/api/diagnostics/pending-tallies` — which wait for the directory scan to finish so
their answer is complete rather than partial.
That wait grows with the tree; everything else skips it.

If you are scripting several routes over a large tree, prefer one `--walk` for the
inventory over repeated `/api/tree` calls: each invocation scans again.

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

The route is lossless for platform filenames: literal percent characters stay distinct
from the `%XX` identity of a POSIX byte that is not UTF-8, and `--show` prints that
escaped identity instead of sending an unencodable native surrogate to the terminal.

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

`--doctor` validates both browser plugins and installed `metabrowser.capabilities.v1`
providers. A successful human-readable result reports the browser-plugin,
capability-provider, artifact-contract, and resource-profile counts.
`--doctor --json` exposes the same result as `plugin_count`,
`capability_provider_count`, `artifact_contract_count`, `resource_profile_count`, and
`problems`. Any discovery or registry error makes the command nonzero; a partial
capability registry is never reported as usable.

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
Deterministic browser-owned behavior has the same command-line evidence through golden
sessions that load the production JavaScript.
The rule and its enforcement are in
[CLI and functional UI parity](../AGENTS.md#cli-and-functional-ui-parity); the table of
what is covered is in
[Views, Models, and Routes](project/architecture/arch-views-models-routes.md).

For agents and scripts, that means the answer to “what does Metabrowser think this file
is” is one command with structured output, and does not require a browser.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
