# Using the Metabrowser Command Line

`metab` serves a folder, a file, or a repository to your browser, and its data modes
answer the same questions without one.
`--api`, `--show`, and `--check-api` run the server the browser talks to in process, and
`--walk` and `--diff` print the data the browser draws, so what a mode reports is what
the browser would show.
`metab` and `metabrowser` are the same command.

`metab --help` lists every option of the build you have, with its defaults.
This guide says what each mode and option is for.

## The Shape of a Command

```shell
metab ROOT [MODE] [OPTIONS]
```

`ROOT` is a directory to serve, a file to open, or a Git source.
With no mode flag, `metab ROOT` serves `ROOT` and opens your browser, the way `open`
opens a folder on macOS. `metab` with no arguments prints its help.

Exactly one mode runs per invocation: two mode flags are an error, and so is an option
the chosen mode does not use, so no flag is accepted and then ignored.
The option tables of `metab --help` name the modes each option applies to.

### What ROOT Names

A clone URL (`https://…`, `ssh://…`, `git@host:path`, or `file://…`) or a GitHub web URL
is a Git source, not a local path.
`https://` and `file://` sources are cloned into the cache and served or inspected at
the commit their URL selects; `ssh` sources are refused.
Two rules decide between a path and a source, in this order:

1. An argument that starts with `scheme://` is always a source, whatever exists on disk.
   No path is written that way, so a pasted URL opens the same thing in every working
   directory. To serve a folder with such a name, write `./https://host/x`.
2. Any other argument that names an existing path is that path.
   A folder called `file:notes` or `me@host:dir` is served, and a symbolic link is
   followed. Only an argument that names nothing on disk is read as anything else: an
   scp-like address, such as `git@github.com:owner/repo`; a GitHub URL without its
   `https://`, such as `github.com/owner/repo`, which opens as the full URL; or a
   malformed source, which is refused.
   `owner/repo` alone is a path.
   So `github.com/owner/repo` is a folder of that name when one exists; write the
   `https://` to open the repository whatever is on disk.

A path that exists but cannot be read is a usage error.
An empty argument is refused; write `.` for the current directory.

A path is served exactly as named: a folder as itself, and a file’s folder with the file
selected. Opening a path inside a Git repository at the repository’s root is planned in
[Open Modes](project/architecture/arch-open-modes.md#resolving-a-target-to-a-root).

### Exit Status

| Status | Meaning |
| --- | --- |
| 0 | Success |
| 1 | A refusal or failure, printed as one `Error:` line on stderr; `--api` when the route answers outside 2xx; `--present` when the server it started exited first |
| 2 | A usage error, such as two modes or an option the mode does not use; a `--diff` that cannot be computed |
| 3 | `--present`: ROOT cannot be presented, and the refusal says why |
| 4 | `--present`: no app takes the target under `open_in` `app`, or a browser would and `present_browser` is false, so nothing was sent; the report’s `code` says why |
| 5 | `--present`: LaunchServices could not be asked or did not take the target, as in a sandbox |
| 129, 130 | Stopped by a terminal hangup or Ctrl-C |
| 143 | Stopped by `SIGTERM` while cloning |

## Modes

| Mode | What it does |
| --- | --- |
| *(none)* | Serve `ROOT` and open a browser |
| `--api ROUTE` | Issue one `/api/` route and print the answer |
| `--show PATH` | Report the route, kind, views, and model for one selection |
| `--walk` | Print the file inventory of `ROOT` |
| `--diff SPEC` | Print a change set between two revisions, or a patch file |
| `--check-api` | Run the navigation scenario as a pass or fail check |
| `--no-serve` | Clone or reuse a Git source in the cache, and serve nothing |
| `--remote HOST` | Serve a directory on another machine through an SSH tunnel |
| `--plugins`, `--plugin NAME`, `--doctor` | List, show, or validate plugins |
| `--present` | Open a folder, a file, or a GitHub URL in the [macOS app](macos-app.md) or a browser |
| `--recent`, `--recent-add`, `--recent-forget`, `--recent-clear` | List or change the [recent targets](#recent-targets) |
| `--event-log` | Name Metabrowser’s own [event log](realtime-debugging.md#browsing-the-log) as `ROOT`, for serving or any mode that takes a folder |

The modes read, with three exceptions: a Git source is cloned into the cache by
whichever mode opens it first; `--api` writes when the route it names does, as a refresh
writes to the cache and `/api/kpress/export` writes a file under `ROOT`; and serving
records `ROOT` among the [recent targets](#recent-targets), which the three `--recent-`
modes also change.

## Serving

```shell
metab ./notes                              # browse a directory
metab ./notes/report.md                    # open one file
metab ./notes --path documents/report.pdf  # open at a path under ROOT
metab ./notes --no-open                    # serve, and leave the browser closed
```

The server prints `Serving <ROOT> at <address>` and the loaded plugins, then serves
until Ctrl-C.

- **`--port`:** the first port to try, 8411 by default.
  When it is taken, the server tries a bounded run of the ports after it and prints the
  one it took.
- **`--host`:** the address to bind, the loopback address by default.
  Do not bind a served folder to an untrusted network; see the
  [security policy](../SECURITY.md).
  The bound name is allowed by the server’s Host-header check, and
  `METABROWSER_ALLOWED_HOSTS` adds others.
  An IPv6 address works too, bare or in brackets: `--host ::1` serves at
  `http://[::1]:<port>/view/`. A wildcard, `0.0.0.0` or `::`, prints a loopback address,
  and `::` accepts IPv4 connections as well as IPv6.
- **Content trust:** `--untrusted`, `--no-active-content`, and `--allow-edits` set how
  far served content is trusted; see [Content Trust](#content-trust).
- **`--plugins-dir DIR`:** load the plugins in `DIR` too; see [plugins](plugins.md).
- **`--log-level LEVEL`:** log verbosity; `DEBUG` also traces the inventory walker.

### Stopping When the Parent Exits

```shell
metab ./notes --no-open --exit-on-eof   # serve until stdin closes: Ctrl-D in a terminal
```

`--exit-on-eof` stops the server when its stdin closes, and anything written to stdin is
discarded. It is for a program that starts `metab` and holds its stdin open, as the
[macOS app](macos-app.md) does: however that program ends, even by crashing, the pipe
closes and the server stops itself.
The server prints `Stopping Metabrowser: stdin closed.` and exits with status 0, and it
stops the Git and `gh` processes it started.
Without the flag stdin is ignored, so `metab ./notes < /dev/null` serves as usual.
The flag also turns off compression toward clients on this machine; see
[Compression](#compression).
[The CLI architecture](project/architecture/arch-cli.md#stopping-when-stdin-closes)
describes how the stop works and what it covers.

### Compression

The server gzips its answers for any client that accepts gzip, with one exception: a
server started as the [macOS app](macos-app.md) starts it sends clients on this machine
its answers uncompressed, since nothing crosses a network and gzip costs the server time
on every answer. That is a server started with `--exit-on-eof` on a loopback address
(`127.0.0.1`, the default, `::1`, or `localhost`), outside an SSH session, a Codespace,
or a Dev Container. It says so as it starts, on a line after its address:
`Compression: off for loopback clients of this machine`. Even then, a request from
another address, or one carrying a header a proxy or CDN adds, is sent gzip.

Every other server compresses for every client, including the one `--remote` starts and
one behind an SSH tunnel, a port forward, or a proxy: such a client reaches the server
from its own loopback, and the server cannot tell it from a local one.
For the same reason, a client that reaches the app’s server through a forward on the Mac
itself, such as an `ssh -L` into it, is sent uncompressed answers; that costs bytes on
that link only, and the answers are the same.
`metabrowser/delivery.py` names the environment variables and headers that decide it.

### Serving a Git Source

```shell
metab file:///path/to/origin.git
metab https://github.com/owner/repo --path docs/guide.md --no-open
```

A Git source is cloned once into the cache as a **mirror**, a bare repository with no
working tree, and later runs reuse it.
The server pins one commit, the default branch’s unless the URL selects another, and its
banner prints a `Revision:` line with the commit and the branch.
`--path` names a file or folder within that commit.
Every page reads from the mirror, so the pinned commit stays readable when the origin is
gone or offline.

A pinned source always runs under the untrusted profile: `--untrusted` is implied, the
`METAB_*` enables are ignored, `--allow-edits` is an error, and HTML files show only
their source.

The mirror refreshes from its origin in the background.
While a page on a branch is visible, the server asks the origin every few seconds
whether that branch moved and fetches at once when it did, so a push shows within
seconds; with no page visible it fetches every few minutes.
A served branch or tag follows the origin: when a refresh moves it, the server serves
its new commit, and an open page follows it there.
A commit the URL names by its ID stays put.
The [history guide](browsing-history.md#branches-and-tags-of-a-repository-url) shows how
to switch branches.
[Mirror acquisition and refresh](project/architecture/arch-mirror-acquisition-and-refresh.md)
covers the refresh cadence, the `/api/source/…` routes, and what a clone prints.

### A Branch or Tag of a Local Checkout

A folder that is a repository’s root opens on its working tree, and `--ref` opens it on
one of its branches or tags, read from the repository’s own Git objects:

```shell
metab ~/src/repo --ref release-1.2
metab ~/src/repo --ref origin/main --show README.md
metab ~/src/repo --ref v2.0 --api '/api/tree?depth=1'
```

- **What it takes:** a branch, a tag, a remote-tracking branch such as `origin/main`, or
  a commit ID, looked up in that order and never as revision syntax, so `HEAD~2` is
  refused.
- **What it shows:** that commit, as a repository URL’s page shows one.
  Nothing is checked out, fetched, or written, so the working tree, the index, and
  `HEAD` are untouched.
  The revision is read-only and runs under the untrusted profile, whatever
  `--allow-edits` and the environment say of the folder.
- **Where it applies:** when serving and with `--api`, `--show`, and `--check-api`. ROOT
  must be the repository’s root.
  A Git source names its branch or tag in its URL, so `--ref` is refused there.
- **What it needs:** a Git as recent as cloning needs
  ([installation](installation.md#git-and-github-setup)), and a newer one in a partial
  clone. With an older one `--ref` stops with the release it needs, and `metab ROOT`
  without it opens the working tree.

While serving, the page’s button switches to any other branch or tag and back to the
working tree; the
[history guide](browsing-history.md#branches-and-tags-of-a-local-checkout) shows it.

### Metabrowser’s Own Event Log

```shell
metab --event-log
metab --event-log --api '/api/plugin/event-log/errors?path=events-20261119T210201Z-p4242-000.jsonl'
```

A served `metab` writes a structured log of the requests it answered and the work it
did, and `--event-log` opens it: `ROOT` is the directory it is written to, under
`METABROWSER_STATE_DIR`, else `$XDG_STATE_HOME/metabrowser`, else
`~/.local/state/metabrowser`, and serving selects its newest segment, which opens as
Timeline, Latency, By kind, and Errors.
`--path` selects another segment, and every mode that takes a folder (`--api`, `--show`,
`--walk`, `--check-api`) reads the log as one.
The flag names the folder, so it takes no `ROOT`, and a state directory with no log yet
says where one is written.
The server that shows the log writes none of its own, which its Details and `--doctor`
say. [Browsing the Log](realtime-debugging.md#browsing-the-log) describes the views.

### GitHub URLs

A GitHub URL copied from the browser opens the repository it names, pinned where it
points:

```shell
metab https://github.com/owner/repo
metab 'https://github.com/owner/repo/blob/release/v1/docs/guide.md#L10-L20'
metab https://github.com/owner/repo/tree/v1.0 --api /api/tree
metab https://github.com/owner/repo/commit/1a2b3c4 --show README.md
metab https://github.com/owner/repo/pull/123
```

- **One source per repository:** `.git`, a trailing slash, `www.`, any letter case, and
  `git@github.com:owner/repo.git` all name one source and one mirror.
- **Refs:** a `/tree/` or `/blob/` URL may name a branch containing `/`; the mirror
  decides where the ref ends, preferring a branch, then a tag, then a commit ID.
- **Lines:** a server opens a `#L10-L20` anchor with those lines highlighted.
- **Selection lines:** `--no-serve` prints what the URL selected (`selection`, `pin`,
  `path`, `lines`, `tab`, and `file`), and `--show` and `--api` print the same lines on
  stderr.
- **Ignored:** query parameters other than `?plain=1`, and fragments other than a line
  anchor and a pull request’s file anchor.
- **Refused:** `http://` URLs and other github.com pages, with a message that offers the
  repository URL.

A one-shot mode reads the mirror as it is, so a ref, commit, or path it does not hold is
`ref_not_found`, `commit_not_found`, or `path_not_found`, with exit status 1. A server
instead serves the default branch, fetches once, and moves to the selection if that
fetch brings it.

Public repositories are cloned anonymously, and a private one opens once `gh` is signed
in to an account that can read it.
GitHub-specific failures, private repositories, and large repositories are in
[reviewing pull requests](reviewing-pull-requests.md#offline-and-cached-reading).

### Pull Requests

This is the reference for the commands; for the workflow in a browser, see
[reviewing pull requests](reviewing-pull-requests.md).
A repository URL and a checkout whose `origin` is on github.com both offer the Pulls
tab. A pull-request URL pins the pull request’s head commit; a `/pull/<n>/changes`,
`/pull/<n>/files` (GitHub’s older spelling of Changes), or `/pull/<n>/checks` URL opens
that tab, and `/pull/<n>/commits/<id>` pins that commit.

A Changes tab URL copied from a file’s header, `/pull/<n>/changes#diff-<hash>` or
`/pull/<n>/files#diff-<hash>`, opens that file at `/pull/<n>/files/<path>`. GitHub’s
`<hash>` is the SHA-256 of the file’s path, so `metab` names the file from the pull
request’s changed files, from the cache and the mirror alone, once the pull request is
open; the `file` line says which.
Where nothing cached names it, or the Changes tab has no address for its path, the URL
opens the Changes tab and the line says why, which is not an error.
A line in the anchor, such as `R12`, is reported on a `diff_line` line, and the page
opens at the file, not the line.
`--present --dry-run` reads no cache, so its `page` for such a URL is null, and its
`handoff` keeps the anchor for the server the app starts.

```shell
URL=https://github.com/owner/repo/pull/123
metab "$URL" --no-serve                                  # clone or reuse, and refresh the record
metab "$URL" --show /pull/123                            # kind, views, and counts
metab "$URL" --show /pull/123/files                      # the Changes tab
metab "$URL" --show README.md                            # one file at the head
metab "$URL" --api '/api/plugin/github/pull?number=123'  # the whole record
```

The first `--show` or `--api` of a pull request reads it through `gh` and caches the
record; later ones answer from the cache, offline too, and `--no-serve` refreshes it.
The record’s `comparison_route` serves the Changes diff as a
[File Diff Format](project/architecture/file-diff-format/file-diff-format.md) document,
and `--format json` prints the answer alone, for a tool such as `jq`:

```shell
ROUTE=$(metab "$URL" --api '/api/plugin/github/pull?number=123' --format json |
  jq -r .comparison_route)
metab "$URL" --api "$ROUTE" --format json |
  jq -r '.manifest.files[] | "\(.kind) \(.new.path // .old.path) +\(.additions) -\(.deletions)"'
```

To read a file at the head, run Git in the mirror with `pin` and `location` from
`metab "$URL" --api /api/source/status`, expanding a leading `~` in `location`:

```shell
git -C <location> show <pin>:README.md
```

A refresh and the catalog job are POST routes that take a JSON body through `--data`;
the command waits for a refresh and exits 1 when it failed:

```shell
echo '{"number": 123, "retry": true}' > refresh.json
metab "$URL" --api /api/plugin/github/pull-refresh --data refresh.json
echo '{"state": "open", "target": 500}' > catalog.json
metab https://github.com/owner/repo --api /api/plugin/github/pulls-refresh --data catalog.json
metab https://github.com/owner/repo --api '/api/plugin/github/pulls?state=open&limit=100'
```

[GitHub Pull Requests](project/architecture/arch-github-pull-requests.md#routes) lists
every route, the stack routes among them, which need the optional
[gh-stack extension](installation.md#git-and-github-setup); each handler’s docstring
holds its contract. A pull request that cannot be read does not fail the command, so a
script reads the `pull_request` line or the route’s `state`, not the exit status.
The exception is a pull request not yet cached while `gh` is missing, too old, or not
signed in: the command stops with exit status 1 and the step to take, without cloning
anything.
[When something does not open](reviewing-pull-requests.md#when-something-does-not-open)
lists the reasons and what to do.

### Beside a Checkout

If you already have the repository checked out, name that checkout once and the mirror
borrows its objects instead of cloning them:

```shell
metab https://github.com/owner/repo/pull/123 --checkout ~/src/repo
metab https://github.com/owner/repo/pull/124    # remembered from then on, from anywhere
```

`--checkout` applies to a Git source when serving and with `--api`, `--show`,
`--check-api`, and `--no-serve`. The path is a checkout, a linked worktree of it, or a
bare clone of the repository, and only what it lacks is fetched, into the mirror.
Nothing is written to the checkout and no Git runs in it.
`metab` prints `borrowing objects from <path>`.

Only a checkout you name lends.
Run `metab <url>` inside a checkout with no mirror yet, and it clones a full mirror and
prints the `--checkout` command that would have borrowed instead.
If the checkout later moves or is deleted, `metab` refuses with `lender_missing` until
you name its new place with `--checkout`.
[Mirror acquisition and refresh](project/architecture/arch-mirror-acquisition-and-refresh.md)
lists every case: a partial or shallow checkout, a full mirror already in the cache, and
a remote that names another repository.

This is a pinned view of the URL. `metab ~/src/repo` instead serves your checkout’s
working tree, which can review pull requests too.

## Acquiring a Git Source: `--no-serve`

```shell
metab file:///path/to/origin.git --no-serve
metab https://github.com/owner/repo/pull/123 --no-serve
```

`--no-serve` clones an `https://` or `file://` source into the cache, or reuses the
mirror already there, and prints the source, its slug, its store, and the revision its
URL selects, without serving.
It is the way to pay for a long first clone ahead of time, and for a pull-request URL it
also refreshes the record.
While a clone runs, stderr says where it goes and how far it has got.

A refusal prints one `Error:` line and exits 1, and publishes nothing; an interrupted
clone leaves nothing behind.
The reasons a clone can fail are in
[reviewing pull requests](reviewing-pull-requests.md#when-something-does-not-open).

## Inspecting Data: `--api`

`--api` issues one route through the real application, with the same middleware,
routing, and serialization the browser gets, without binding a port.
Start with the route index:

```shell
metab ./notes --api /api/routes
```

```shell
metab ./notes --api '/api/tree?depth=2&types=.md'   # a query string as the browser sends it
metab ./notes --api /api/identity                    # what the window is called
metab ./notes --api '/api/counterpart?page=/view/README.md'   # where View on GitHub goes
metab ./notes --api /api/cache/sources               # repositories in the cache
metab ./notes --api /api/git/refs --format json      # the answer alone, as JSON
metab ./notes --api /api/kpress/render --data request.json   # a POST body
```

Output is the route, the HTTP status, and the answer:

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

- **`--format json` or `yaml`:** stdout is the answer alone, so it parses.
- **`--data FILE`:** sends `FILE`, or stdin for `-`, as a POST body.
  A body larger than any route accepts is refused before anything is sent.
- **Following work:** a POST that starts background work, such as a refresh, waits for
  it and prints how it ended under `after:`.
- **Exit status:** non-zero when the route answers outside 2xx.
- **Paths:** paths under the served root print as `<ROOT>`.
- **Streams:** `/api/events` and `/api/stream` never end, so `--api` reports that
  instead of waiting.

Each command runs its own server in process for the life of the command, so nothing is
left running and a `metab` already serving the folder is neither needed nor consulted.
Routes whose answer depends on the whole file inventory, such as `/api/tree`, wait for
the scan to finish, at most `--index-timeout` seconds; the rest answer at once.
To script several such routes over a large tree, one `--walk` is cheaper than repeated
`/api/tree` calls, because each command scans again.

## Understanding a Selection: `--show`

`--show` answers “what would the browser do with this path” without opening one:

```console
$ metab ./notes --show README.md
show: README.md
route: /view/README.md
kind: markdown
views: rendered (default, key V), source (key S)
model: text envelope; size=13386 content_bytes=13386 content_truncated=False
```

The four lines are the layers a selection passes through: its address, its kind, the
view tabs a reader sees with their keys, and a summary of the data behind them.
`--format json` prints them as an object.

`--show` accepts browser addresses as well as paths, which checks that a URL resolves as
you expect:

```shell
metab ./notes --show /view/README.md                # a route
metab ./notes --show change.patch/src/main.py       # one entry inside a patch file
metab ./repo --show /commit/<revision>              # a commit's change set
metab ./repo --show /commit/<revision>/README.md    # one file in it
```

## Reading a Tree: `--walk`

```shell
metab ./notes --walk                          # a text report
metab ./notes --walk --format json            # the data the navigation pane uses
metab ./notes --walk --format json --stream   # one record per line, in walk order
metab ./notes --walk --type .md --age 7d      # the navigation pane's filters
```

- **`--format`:** `text`, `json`, or `yaml`. `--detail summary|dirs|all` sets how much
  the text report shows.
- **`--stream`:** one walker record per line, as the live feed sends them; the default,
  `--all-at-once`, prints the whole `/api/tree` answer.
  `--path` narrows that answer to a subtree.
- **Bounds:** `--max-depth` and `--max-files`.
- **Filters:** `--type` (an extension such as `.md`, or a whole name such as `README`,
  repeatable or comma-separated), `--age` (a window such as `7d`; `metab --help` lists
  them), `--min-size` (bytes, or a `k`, `m`, or `g` suffix), and `--no-ignored` to leave
  out gitignored files.

`--walk` reads a filesystem and refuses a Git source; for a pinned tree, use
`--api '/api/tree?depth=N'`.

## Reading a Change Set: `--diff`

```shell
metab ./repo --diff main..feature               # between two revisions
metab ./repo --diff main...feature              # from their merge base
metab ./repo --diff <revision>                  # one commit against its first parent
metab ./repo --diff changes.patch               # a patch file under ROOT
metab ./repo --diff <revision> --diff-patch src/main.py   # one file's hunks
metab ./repo --diff <revision> --diff-check               # rebuild and verify
```

`--format` is `text` or `json`.
[Browsing history](browsing-history.md#diffs-from-a-terminal) explains the output,
`--diff-check`, and the route that compares revisions of a Git source.

## Diagnostics and Plugins

```shell
metab ./notes --check-api    # pass or fail for the navigation requests
metab --plugins              # list accepted plugins and discovery errors
metab --plugin agents        # show Agent Session Browser's resolved manifest
metab --doctor               # validate plugins and check the rest of the setup
```

`--check-api` runs the browser’s navigation sequence against `ROOT`, prints each step,
and ends with `result: pass` or a failure.
For the underlying data, `--api` is more direct.
All three plugin modes accept `--plugins-dir` and `--json`. The JSON inventory includes
both `plugins` and `errors`. Discovery errors leave the accepted plugins in the output
and set a nonzero exit status.
See [inspecting plugins](plugins.md#inspecting-plugins).

After its verdict, `--doctor` reports what GitHub work needs from `gh`: the `gh` on
`PATH` and its version, the account it is signed in to, that account’s token scopes, and
one state with the step that fixes it, under `github` with `--json`.
[The GitHub status check](project/architecture/arch-github-pull-requests.md#the-github-status-check)
says where the states are listed and what reads them.
The report never changes the exit status.
A script that needs only this report issues its route, which any served root answers:

```shell
echo '{}' | metab . --api /api/plugin/github/status --data -
```

Then come the setup checks, each with a state (`ok`, `warning`, or `problem`), a
sentence, the details it read, and the step that fixes it:

- **`metab`:** its version, executable, Python, and how it was installed (uv, pipx, a
  source checkout, or another environment).
  A source checkout is a `.venv` beside the `pyproject.toml` of this project, which is
  how the macOS app tells them apart too.
  When `--present` would open the macOS app, the check compares this `metab` with the
  oldest that app runs, and an older one is a warning whose step upgrades it with the
  tool that installed it.
  Run from the app’s Check Setup…, it compares with that app instead.
- **`git`:** the `git` on `PATH`: where it is, its version, and each thing that version
  does. It is checked against the floor for cloning and fetching, the one for showing a
  branch or tag of a partial clone, and the one for file ages on a Git revision
  (`git last-modified`, Git 2.53), and a `file ages` line says whether they are
  available. Below any is a warning that names what is missing, with the step that
  upgrades Git: browsing a folder needs no Git, and a Git revision without file ages
  shows no times. Run from the app’s Check Setup…, it reports the Git the app’s servers
  use.
- **`config`:** the configuration directory: its override is valid, it is private or can
  be created, and its `config.yml` is one this release reads.
- **`cache`:** the cache directory: its override is valid, it is private and writable or
  can be created, it is apart from the configuration, and how much space its volume has
  free. Less than the largest first clone `metab` admits can take is a warning:
  `low_free_space_bytes` in `cli/doctor.py`, which follows
  `METABROWSER_MAX_FIRST_CLONE_KB`.
- **`event_log`:** whether a server writes its event log: where, and from which variable
  the directory comes.
  `METABROWSER_EVENT_LOG` turning it off is a warning, since no latency or failure is
  then recorded, and so is a state directory `metab` cannot create.
  A server whose folder is the events directory or inside it writes none, whatever the
  environment says, and its Details name that reason.

The macOS app runs its servers without `METABROWSER_CONFIG_DIR`,
`METABROWSER_CACHE_DIR`, or the `XDG_` variables, so when `--present` would open the
app, a directory one of those names here is a warning that names the directory the app’s
servers use instead.

A `problem` stops `metab` from serving a folder, so it is also listed with the plugin
problems and makes the exit status 1; a `warning` never changes it.
A configuration directory with a problem is listed once, though `--present` reads its
settings there too. None of these opens a network connection, and none checks uv, which
`metab` never runs. With `--json`, the plugins, `open_in`, and these checks are the
`checks` list, whose shape [`cli/doctor.py`](../src/metabrowser/cli/doctor.py)
documents, and `github` has its step as a `remedy` of the same shape; the
[macOS app’s Check Setup…](macos-app.md#checking-the-setup) reads them.

## Presenting a Target: `--present`

```shell
metab ./notes --present                          # a folder
metab ./notes/report.md --present                # a file, in the folder metab serves
metab https://github.com/owner/repo/pull/123 --present
metab ./notes --present --open-in browser        # in a browser, never the app
metab ./notes --present --dry-run --format json  # where it would go, sending nothing
```

`--present` opens one folder, file, or GitHub URL in the
[Metabrowser macOS app](macos-app.md) or in a browser, and reports what it did.
It reads ROOT as every mode does, and `--path` selects a file or folder inside a local
ROOT as serve mode reads it.
For the app it clones nothing, fetches nothing, and starts no server: the app runs
`metab` on what it receives, as it does for a folder opened in Finder.
For a browser it starts `metab ROOT`, which does.
Unlike serve mode, `--present` refuses `--path` with a URL (`path_with_url`): present
the URL of the file or folder itself.

### Choosing the App or a Browser

The `open_in` preference chooses where a target opens:

- **`auto`**, the default: the app when an installed build takes the target, and
  otherwise a browser.
- **`app`**: the app, or nowhere, with [status](#exit-status) 4.
- **`browser`**: a browser, without looking for the app.

It is read from the first of three places that sets it, and is `auto` when none does:
`--open-in WHERE`; the `METABROWSER_OPEN_IN` variable; and `open_in` in the `config`
mapping of `config.yml`, in the [configuration directory](#storage-locations):

```yaml
softschema:
  contract: metabrowser.config:ApplicationConfig/v1
  envelope: config
  status: permissive
config:
  format: f01
  written_by: 0.12.1
  upgrades: []
  open_in: browser
```

Metabrowser writes `config.yml` when it first clones a repository; add `open_in` to the
`config` mapping there, or, before then, write the whole file as above.
A value that is not `auto`, `app`, or `browser` is an `Error:` line that names where it
was read, before anything is looked up or started; the flag and the variable are read
first, so either still chooses while `config.yml` is broken.
Under `auto`, a target LaunchServices cannot be asked about goes nowhere with
`lookup_failed`, as under `app`: in a sandbox that keeps `metab` from LaunchServices, a
browser it started would be kept from the screen as well.
Bare `metab ROOT` does not read the preference; it serves and opens a browser as it
always has.
`present_browser: false` in the same mapping keeps `--present` from opening a
browser whatever the preference says
([Turning Browser Delivery Off](#turning-browser-delivery-off)).

### Checking a Target: `--dry-run`

`--dry-run` reads ROOT, decides where it would go, and prints both, sending nothing and
starting no server; it looks the app up unless the preference is `browser`. With
`--format json` it is one object, which is how the app checks what a user types:

```console
$ metab https://github.com/owner/repo/pull/123/files --present --dry-run --format json
{
  "kind": "pull_request",
  "root": "https://github.com/owner/repo",
  "page": "/pull/123/files",
  "handoff": [
    "https://github.com/owner/repo/pull/123/files"
  ],
  "refusal": null,
  "decision": {
    "delivers_to": "app",
    "open_in": "auto",
    "open_in_source": "default",
    "bundle_id": "io.github.jlevy.metabrowser",
    "bundle_path": "/Applications/Metabrowser.app",
    "code": "app_found",
    "reason": "the app at /Applications/Metabrowser.app takes the target",
    "fallback": null
  }
}
```

- **`kind`:** `folder`, `file`, `repository`, `tree`, `commit`, or `pull_request`. A
  file is a `file` locally and on GitHub, while a folder is a `folder` locally and a
  `tree` on GitHub; `root` tells the two apart.
- **`root`:** the absolute folder `metab` would serve, or the repository’s canonical
  URL, which never names a branch or commit, since the app keys a session by its
  repository.
- **`page`:** the address in that root, as a server of it spells one, or null where only
  the repository’s mirror can know it, which the app reads as the entry page of the
  server it starts; that server resolves the URL and opens the right address.
  For a GitHub `tree` or `blob` URL, `page` is known when the URL leaves one reading: a
  `tree` of one branch, also after `refs/heads/` or `refs/tags/`, or `HEAD` and any
  path. Otherwise the branch might hold `/`, and `page` is null: a `blob` URL’s
  `release/v1` may be one branch, which `metab URL` opens at `/view/`, or a branch and a
  file. A commit’s page is `/commit/<id>` for a full ID and null for an abbreviated one,
  which the commit page refuses; `metab COMMIT_URL` opens at the same page.
  A Changes tab URL that anchors one file, `#diff-<hash>`, has a null page: only the
  pull request’s changed files, in the cache, say which file the hash names.
- **`handoff`:** exactly what `open -b` is given after the bundle identifier: a folder;
  a file named alone; ROOT and then the file `--path` names in it, so the app opens the
  root that was named and shows the file there; or a URL’s canonical
  `https://github.com/` form.
  It is null for a folder inside ROOT, because the app opens each folder in a window of
  its own; such a target is reported and not sent.
- **`refusal`:** null, or a `code` and a one-line `message` that names the fix, with
  every other field null and the refusal’s [exit status](#exit-status).
  A path that does not exist is `not_found`, a GitHub page that is not a repository view
  keeps the reason `metab URL` gives it, such as `unsupported_github_url`, and a Git
  source that is not on GitHub is `unsupported_source`.
  `tests/golden/cli-present.tryscript.md` shows these and most others, `--path` with a
  URL among them.
- **`decision`:** null with a refusal; otherwise where the target would go,
  `delivers_to`, `app`, `browser`, or `none`, under the preference `open_in` read from
  `open_in_source`, `flag`, `environment`, `config`, or `default`. `code` is
  `app_found`, `browser_preferred`, `browser_fallback` (no app takes the target under
  `auto`, and `fallback` says why), `preference_unreadable`, or the delivery code below
  that sends it nowhere.
  The status of a dry run says only whether ROOT resolved, so a preference that cannot
  be read, which the app’s check never uses, is a decision and not a failure.

A file named alone goes where the app places any file it is handed: in the most specific
folder it has open that holds the file, and otherwise in the folder `root` reports.
A file named with `--path` opens in ROOT, unless a folder inside ROOT that holds the
file is open already, which is more specific.

### Opening in the App

Unless the preference is `browser`, `--present` asks LaunchServices for the app: the
release build, then the development build every local build is, or the one
`--app-bundle-id ID` or `METABROWSER_APP_BUNDLE_ID` names.
It sends the handoff with `open -b` and prints a report; `--format json` prints it as
one object whose `target` is the object above, without `decision`:

```json
{
  "delivered_to": "app",
  "open_in": "auto",
  "open_in_source": "default",
  "bundle_id": "io.github.jlevy.metabrowser",
  "bundle_path": "/Applications/Metabrowser.app",
  "url": null,
  "pid": null,
  "log": null,
  "target": {"kind": "folder", "root": "/path/to/notes", "page": "/view/", "handoff": ["/path/to/notes"], "refusal": null},
  "confirmed": false,
  "code": "not_confirmed",
  "reason": "LaunchServices took the target; the app does not reply yet, ...",
  "fallback": null
}
```

`delivered_to` is `app` once LaunchServices has taken the target.
That does not mean a window shows it, and the app cannot answer yet, so `confirmed` is
always `false`. `bundle_path` is the bundle LaunchServices named for `bundle_id`, or
null when none was looked up or found.
Under `auto`, a target no app takes opens in a browser instead, as the next section
describes. Otherwise `delivered_to` is `none`, and `code` is a refusal’s code or one of
these; nothing was handed over, except that an `open` that did not return in time may
still deliver what it was given:

| Code | Meaning |
| --- | --- |
| `not_confirmed` | Sent: LaunchServices took the target, and nothing confirms a window shows it |
| `not_macos` | The app runs on macOS only |
| `app_not_found` | LaunchServices knows no Metabrowser app |
| `app_not_installed` | The app LaunchServices names is not at an install location below, as a build left where it was built is not |
| `app_not_marked` | The app is not named Metabrowser or does not declare the marker below, being an older build or another app |
| `app_cannot_select_folder` | `--path` names a folder inside ROOT, and the app opens each folder in a window of its own; it is refused before LaunchServices is asked |
| `lookup_failed` | LaunchServices could not be asked, as when a sandbox denies its database |
| `open_failed` | `open` failed or did not return in time |

`reason` says the same in words.
`DELIVERY_EXIT_CODES` in `cli/present.py` maps each code to its status, so a caller can
tell “install or update the app” from “run this where LaunchServices answers” by the
status alone.

Every handoff, a file’s or a URL’s, first checks the bundle LaunchServices names:

- **Installed:** it is at `/Applications/Metabrowser.app` or
  `~/Applications/Metabrowser.app`, `~` being the home folder of your account, not
  `$HOME`. LaunchServices registers a bundle wherever it was opened, a build in a source
  checkout included, so a bundle anywhere else, or a link at an install location, is
  refused with `app_not_installed` and a message that names its path; install the
  Metabrowser app at one of the two, and open it once from there.
- **Named:** its `Info.plist` names it `Metabrowser`.
- **Marked:** its `Info.plist` declares `MetabrowserOpensURLs` true, which every build
  that takes what `--present` sends declares: an older build drops a URL while `open`
  still succeeds, and an app an override names must not be handed a file it would run.

Each identifier’s bundle is checked in turn, so a stray registration of the release
identifier does not hide an installed development build, and the first refusal is
reported only when no identifier’s bundle passes.
A developer testing a build where it was built sets
`METABROWSER_ALLOW_UNINSTALLED_APP=1`, which lifts the first check alone.
`APP_INSTALL_LOCATIONS` and the other constants in `cli/present.py` hold the locations,
the bundle identifiers, the name, and the marker.

A build that predates `--present` refuses it as an unknown option, a usage error.
`metab --present --version` checks for it without presenting anything, as the app checks
each `metab` it might run for the flags it needs
([Choosing a metab](macos-app.md#choosing-a-metab)).

In an agent’s sandbox, LaunchServices may not answer, or may refuse what `open` asks,
and `--present` reports `lookup_failed` or `open_failed`. Run it again outside the
sandbox with `--open-in app`, as `metab --present ROOT --open-in app`: under `auto`, the
command outside looks the app up again, and when no app takes the target it starts a
server there.
[Working with agents](working-with-agents.md#let-an-agent-reach-the-app-from-a-sandbox)
has the Claude Code and Codex settings, which match a command by its first words, so
write `metab --present` first, and says when such a setting is safe.
Such a setting also lets `--present` start a server outside the sandbox for any path the
agent names, unless `present_browser` is false
([Turning Browser Delivery Off](#turning-browser-delivery-off)).

### Opening in a Browser

Under `browser`, and under `auto` when no app takes the target, `--present` starts
`metab ROOT`, with its `--path`, as a server of its own: in a session of its own, with
its output in a log file in the temporary folder, so it outlives the command and the
terminal. It waits for the server’s `Serving <root> at <url>` line, and then for that
address to answer `GET /api/identity` as a server of the target’s root, and reports it.
The second wait is what says this server started: two servers started together can both
find the same port free and print it, and the second to bind exits.
The server opens the page in your browser once it answers, as `metab ROOT` in a terminal
does, and serves until it is stopped:

```json
{
  "delivered_to": "browser",
  "open_in": "auto",
  "open_in_source": "default",
  "bundle_id": null,
  "bundle_path": null,
  "url": "http://127.0.0.1:8411/view/",
  "pid": 41235,
  "log": "/tmp/metab-present-k2v9q1x8.log",
  "target": {"kind": "folder", "root": "/path/to/notes", "page": "/view/", "handoff": ["/path/to/notes"], "refusal": null},
  "confirmed": false,
  "code": "server_started",
  "reason": "a metab server for the target runs detached at http://127.0.0.1:8411/view/ ...",
  "fallback": {"code": "app_not_found", "reason": "LaunchServices knows no app ..."}
}
```

| Code | Meaning |
| --- | --- |
| `server_started` | The server printed `url`, which answers as a server of the target, and opens it in a browser once the page answers; nothing confirms a browser shows it |
| `server_starting` | The server runs, but has not printed its address, or its address has not answered as the target’s, in the time `--present` waits, as a first clone can take minutes; `url` is null, the server opens the page once it answers, and `log` will hold the address |
| `server_failed` | The server exited first, before or after it printed an address, or could not start; `reason` names its last line and `log` holds the rest, and the status is 1 |

`pid` is the server’s process ID: `kill PID` stops it.
`fallback`, under `auto`, is the code and reason that no app took the target.
`server_announce_timeout_s` in `cli/present.py` is how long `--present` waits, with the
measurement that set it.
Each `--present` starts a server of its own; to show another page under the same root,
open it on that server’s address rather than presenting again.

### Turning Browser Delivery Off

```yaml
config:
  # ... format, written_by, and upgrades, as above
  present_browser: false
```

`present_browser: false` in the `config` mapping of `config.yml` keeps `--present` from
starting a server for a browser: it opens a target in the app or nowhere, whatever
`open_in` says and wherever it was read.
No option of the command turns it back on, and `--present` refuses `--config-dir`, so it
holds for a command an agent runs outside its sandbox through a rule for
`metab --present`
([Working with agents](working-with-agents.md#let-an-agent-reach-the-app-from-a-sandbox)).
The configuration directory is still the environment’s to choose
([Storage Locations](#storage-locations)): `METABROWSER_CONFIG_DIR`, `XDG_CONFIG_HOME`,
and `HOME` name it, and a directory without `config.yml` allows a browser.
Unset, or `true`, a browser may be used.
`--present` reads it only when it would start a server, and a `config.yml` it cannot
read then is an `Error:` line, so a broken file starts nothing; a target for the app is
sent as before. `--dry-run` reports the decision, and `--doctor` the setting:

| Code | Meaning |
| --- | --- |
| `browser_off` | A browser would take the target, and `present_browser` is false, so nothing was sent and no server started; under `auto`, `fallback` says why no app took it, and the status is 4 |

## Recent Targets

Metabrowser keeps one list of what you opened lately, which the
[macOS app](macos-app.md#recent-items)’s File > Open Recent shows:

```shell
metab --recent                      # the list, most recently opened first
metab --recent --json               # the same, for a script or another shell
metab ~/src/project --recent-forget # remove one entry
metab --recent-clear                # empty the list
```

- **What is recorded:** every time `metab` serves, it records what it serves just before
  it prints `Serving`: a folder by its path with symbolic links resolved, or a
  repository by its address.
  `metab FILE` records the file’s folder, with the file as the entry’s `target`, where
  the open pointed, and a GitHub URL records its repository, whichever pull request,
  branch, or file it named.
  The data modes (`--api`, `--show`, `--walk`, `--diff`, `--check-api`, and
  `--no-serve`) record nothing.
- **Each entry’s mode:** `folder` for your own files as they are on disk, or `mirror`
  for Metabrowser’s cached copy of a repository.
  `--recent --json` also gives each entry’s `git`, true for a folder that held a `.git`
  entry, a checkout, when it was last opened, so a menu can draw its Git checkout mark
  without looking at the folder, and false for any other folder and for a mirror.
  A folder opened before this field existed lists it as false until it is opened again.
  No entry records which branch or commit was shown, so a folder reopens on its files as
  they are on disk.
- **Order and length:** opening something again moves its one entry to the front, and
  the oldest entry falls off a full list.
  `--recent --json` gives the list’s length as `limit`.
- **Folders that are gone** stay listed until you forget them or open them: the list
  never looks at a listed folder, since a look can raise a macOS privacy prompt or wait
  on a drive that is not there.
- **`--recent-add`** records `ROOT` without serving it, for a shell that shows something
  already open.
- **`METABROWSER_RECORD_RECENT=0`** keeps a `metab` from recording: it serves as usual
  and leaves the list alone, and `--recent-add` records nothing.
  Set it for a server nobody opened to read, such as a benchmark’s or a script’s.
  `--remote` sets it for the server it starts on the far host, so a remote serve enters
  no list on either machine.

The list is `recent-targets.yml` in the [configuration directory](#storage-locations),
readable only by you.
A list that is damaged is replaced the next time something is opened; one written by a
newer Metabrowser is left alone, and `--recent` says to upgrade.

## Remote Directories

```shell
metab --remote example-host --path /srv/shared-files
metab --remote example-host --path /srv/data --ssh-options '-i ~/.ssh/mykey'
metab --remote my-vm --gcp --zone europe-west1-b --project my-project --path /data
```

`metab` connects to the host over SSH, starts `metab` there on the remote directory, and
tunnels its port back, so the browser stays local and opens at a `localhost` address.
`ROOT` is not used; `--path` names the remote directory and is required.
Ctrl-C closes the tunnel and stops the remote server, and the remote server also stops
when the SSH connection drops.
The remote server is started with `--no-open`, so what crosses the tunnel is gzipped
([Compression](#compression)), whichever release either host runs.

The remote host needs:

- **`metab` installed,** the same Metabrowser version as here, on the remote `PATH` or
  in `~/.local/bin`, where `uv tool install` puts it.
  Without it, the command says that `metab` is not available there.
- **`python3`** on its `PATH`, which picks the remote port.
- **SSH access** from here, as plain `ssh` or `gcloud compute ssh` reaches it.

Options:

- **`--base-port`:** the first port tried, both locally and on the remote host; each
  side takes its first free port from there up, so several sessions can share a host.
- **`--ssh-options`:** extra flags for plain `ssh`, split as shell words.
  They are not passed to `gcloud`.
- **`--gcp`:** connect with `gcloud compute ssh` instead of `ssh`.
- **`--zone` and `--project`:** the Compute Engine zone and project for `--gcp`.
  `--project` defaults to `METABROWSER_GCP_PROJECT`.
- **`--no-open`:** leave the local browser closed.

The trust flags do not apply to `--remote`: the remote server runs with its host’s own
defaults and environment.

## Configuration and Environment Variables

### Storage Locations

| What | Default on macOS and Linux | Flag | Variable |
| --- | --- | --- | --- |
| Cache: mirrors and pull-request records | `~/.cache/metabrowser` | `--cache-dir DIR` | `METABROWSER_CACHE_DIR` |
| Configuration: `config.yml` | `~/.config/metabrowser` | `--config-dir DIR` | `METABROWSER_CONFIG_DIR` |

A flag takes precedence over its variable, and `--present` refuses `--config-dir`
([Turning Browser Delivery Off](#turning-browser-delivery-off)). Without either,
`XDG_CACHE_HOME` and `XDG_CONFIG_HOME` choose the base directories, with `/metabrowser`
appended. A variable must be a nonempty absolute path with no `..`; a flag may be
relative to the current directory.
The two directories may not overlap.

Serving a folder creates no cache and no `config.yml`; it creates the configuration
directory, owner-only, for the one file it writes there, the recent targets.
The first repository cloned creates the cache, owner-only, and writes `config.yml` if it
is missing. `config.yml` records the cache format it was written for.
Metabrowser keeps the keys and comments you add, and refuses keys that look like
credentials. If the file cannot be parsed, Metabrowser names it and exits without
replacing it: move it aside and start again.
A newer format asks you to upgrade Metabrowser.
A cache an older release wrote is migrated the first time a repository in it is opened:
each mirror’s directory is renamed to a readable name, and nothing is cloned again.
That first open writes to the cache, so it needs a cache you can write once; a read-only
copy is not migrated.
Stop running `metab` servers first: one of an older release cannot read its mirrors once
they are renamed. Deleting the cache directory, with no server running, removes every
mirror and record; the next run clones again.
[The repository cache](project/architecture/arch-repository-cache.md) describes the
layout, and the repair for each refusal that concerns it.

### Content Trust

Three switches set how far served content is trusted:

| Flag | Variable | Effect |
| --- | --- | --- |
| `--untrusted` | `METAB_UNTRUSTED=1` | The conservative profile: active content and mutations off |
| `--no-active-content` | `METAB_ACTIVE_CONTENT=0` | Markdown renders as inert markup, the page carries a strict Content-Security-Policy, and `/raw` runs no scripts |
| `--allow-edits` | `METAB_ALLOW_EDITS=1` | Publishes the mutations capability; no route writes yet |

By default active content is on and mutations are off.
A variable accepts `1`, `true`, `yes`, or `on`, and `0`, `false`, `no`, or `off`. A flag
beats the environment: `--untrusted` stays conservative whatever the variables say, and
only `--untrusted --allow-edits` lifts part of it.
Within the environment alone, `METAB_ACTIVE_CONTENT=1` and `METAB_ALLOW_EDITS=1`
override `METAB_UNTRUSTED=1`. The switches apply when serving and to `--api`, `--show`,
and `--check-api`, and a Git source is always untrusted.
The [content-trust model](project/architecture/arch-server-and-content.md) explains what
each protects against.

### Environment Variables

Every variable is read from the process environment, so export it in the shell that runs
`metab`. The [`.env` files](#env-files) below supply only two of them.

| Variable | What it sets |
| --- | --- |
| `METAB_UNTRUSTED`, `METAB_ACTIVE_CONTENT`, `METAB_ALLOW_EDITS` | [Content trust](#content-trust) |
| `METABROWSER_CACHE_DIR`, `METABROWSER_CONFIG_DIR` | [Storage locations](#storage-locations) |
| `METABROWSER_ALLOWED_HOSTS` | Comma-separated host names the server accepts besides the one it binds, for reaching it by another trusted name; see the [security policy](../SECURITY.md) |
| `METABROWSER_PLUGINS_DIRS` | Plugin directories, separated by `:`, loaded before any `--plugins-dir` |
| `METABROWSER_RECORD_RECENT` | `0` keeps a serve, and `--recent-add`, from recording a [recent target](#recent-targets) |
| `METABROWSER_ORIGIN_STORE` | `0` keeps a serve of a repository folder from keeping a store of its origin’s branches and tags, so nothing is fetched for it and the folder lists its own remote-tracking branches |
| `METABROWSER_LOG_LEVEL` | Log verbosity, as `--log-level`, which overrides it |
| `METABROWSER_REQUEST_LOG` | `verbose` logs every request with its arrival and completion times |
| `METABROWSER_SLOW_SERVER_MS` | The time, in milliseconds, past which a request is logged as slow, 2,000 by default |
| `METABROWSER_DEBUG` | `1` enables the `/_debug/tasks` and `/_debug/inventory` diagnostics |
| `METABROWSER_MAX_FIRST_CLONE_KB` | The size limit, in kilobytes, on a first clone from GitHub; a refused clone names the default |
| `METABROWSER_GCP_PROJECT` | The default `--project` for `--remote --gcp` |
| `METABROWSER_INVENTORY_PROVIDER` | The inventory engine; this build ships `python` alone, the default |
| `METABROWSER_TEXT_PREVIEW_BYTES`, `METABROWSER_TEXT_PREVIEW_MAX_BYTES`, `METABROWSER_HIGHLIGHT_MAX_BYTES` | Text loading and highlighting budgets, in bytes |
| `METABROWSER_INERT_RENDER_DEADLINE_MS` | How long one untrusted Markdown document may take to render, in milliseconds and at least 1, before its source is shown instead |
| `METABROWSER_BINARY_PREVIEW_BYTES`, `METABROWSER_BINARY_PREVIEW_MAX_BYTES`, `METABROWSER_BINARY_PREVIEW_MAX_CHUNK_BYTES` | Byte-view budgets, in bytes |
| `STRUCTURED_PARSE_MAX_BYTES`, `STRUCTURED_CACHE_SIZE` | JSON and YAML tree-view budgets: the largest file parsed, in bytes, and how many parses are kept |
| `METABROWSER_OPEN_IN` | Where `--present` opens a target, `auto`, `app`, or `browser`, as `--open-in`, which overrides it; see [choosing the app or a browser](#choosing-the-app-or-a-browser) |
| `METABROWSER_APP_BUNDLE_ID` | The app `--present` hands a target to, as `--app-bundle-id`, which overrides it |
| `METABROWSER_ALLOW_UNINSTALLED_APP` | `1` lets `--present` hand a target to an app outside the install locations, such as a development build |
| `METABROWSER_METAB` | Read by the [macOS app](macos-app.md), not by `metab`: the `metab` the app runs |

[Rendering large content](large-content-rendering.md) explains the rendering budgets and
what sets each one. Git and `gh` read their own environment, as
[installation](installation.md#git-and-github-setup) describes.

### `.env` Files

`metab` looks for `.env` and `.env.local` in the current directory and each directory
above it, and takes only `METABROWSER_LOG_LEVEL` and `METABROWSER_REQUEST_LOG` from
them; an exported value wins.
A repository you browse can hold its own `.env`, so a file cannot change trust, plugins,
hosts, budgets, or what runs; Metabrowser warns when it ignores one of its own names
there.

## Why the Data Modes Exist

Every route the browser uses is reachable from `metab` and pinned by a golden
transcript, so a change to a route’s answer shows up as a readable diff, and an agent or
a script gets the browser’s answer as structured output.
[CLI and functional UI parity](../AGENTS.md#cli-and-functional-ui-parity) states the
rule, and [working with agents](working-with-agents.md) shows the modes in use.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
