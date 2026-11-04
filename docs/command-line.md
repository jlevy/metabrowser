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
effect of serving them, `--show`, `--api`, or `--check-api`; ssh stays closed.
`metab <source>` serves the commit its URL selects, or its default branch’s, pinned;
`--show`, `--api`, and `--check-api` inspect that pin in-process without binding a port.
Acquired content always runs under the untrusted profile.
A bare filesystem path is never treated as a clone origin.

Two rules decide between the readings, in this order:

1. An argument that starts with `scheme://` is always a source, whatever exists on disk.
   No path needs that spelling — the system reads `https://host/x` as the path
   `https:/host/x` — so a pasted URL opens the same thing in every working directory,
   and a local folder cannot stand in, under the local trust profile, for the repository
   a URL names. Write the path with one slash, or as `./https://host/x`, to serve such a
   folder.
2. Any other argument that names an existing path is that path.
   A folder called `file:notes`, `a::b`, `me@host:dir`, or `https:x` is served, a file
   is opened, and a symbolic link is followed, as for any other name.
   Only an argument that names nothing on disk is read as an scp-like address or refused
   as a malformed URL or remote-helper syntax.
   This covers an scp-like address: `git@github.com:o/r` names the folder `r` inside
   `git@github.com:o` when the working directory has one, and the GitHub repository only
   when it does not. Write `https://github.com/o/r` to open the repository whatever the
   directory holds.

A path that exists but that the process may not read is a usage error
(`Path 'x' is not readable.`, exit status 2), not a tree that serves as empty.
An empty argument is refused as `invalid ROOT (empty)`; write `.` for the current
directory.

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
| `--no-serve` | Acquire a `file://` or `https://` Git source into the cache without starting a server |
| `--remote HOST` | Serve a remote directory over an SSH tunnel |
| `--plugins`, `--plugin NAME`, `--doctor` | Inspect installed plugins |

Most modes are read-only.
`--no-serve` writes a cache entry for a Git source.
`--api` writes only when the route it names writes, which today means
`/api/kpress/export` and, in the cache, the refresh routes.

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
`--untrusted` (`METAB_UNTRUSTED=1`) is the conservative content-trust profile: it turns
active content off and keeps mutations off.
`--no-active-content` (`METAB_ACTIVE_CONTENT=0`) is the individual switch for active
content. With it off, Markdown renders as an allowlist of inert markup, the page carries
a strict Content-Security-Policy, and `/raw` omits `allow-scripts` from its sandbox; the
[security policy](../SECURITY.md) has the details.
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

### Serving a Git source

```shell
metab file:///path/to/origin.git
metab file:///path/to/origin.git --path docs/guide.md --no-open
```

Serving a `file://` source acquires it, or reuses the cached store, and serves the
commit its default branch names in the store: the commit it named at the last fetch.
The banner prints the source and a `Revision:` line with the full commit and the branch;
the navigation heading shows the repository’s name, then the branch and short commit,
and hovering it shows the full commit and where the mirror is kept; see
[What a mirror’s page is called](#what-a-mirrors-page-is-called).
`--path` takes a path within that commit, spelled as `--show` accepts it (`docs`,
`docs/`, `./docs`, or a `GitPath` wire), and the banner prints a directory’s address
with a trailing slash.
If the pin cannot be opened again when the server starts, the command prints the same
error as `--show` and exits 1. Every page reads from the store, so the origin can be
gone and the pinned revision still serves.
Before the banner, stderr says whether the source was cloned just now or found in the
cache; see [What a clone prints](#what-a-clone-prints).

The store is a mirror that refreshes in the background.
When the server starts on a mirror last fetched more than a minute ago it runs one
`git fetch` from the origin, and a page asks for one when it opens or becomes visible on
a stale mirror; nothing a page shows waits for either.
The foot of the navigation pane says when the mirror was last fetched; click it to
refresh now. A refresh never moves the page under a reader: when it moves the pinned
branch, the row offers the commit the branch now names, and **Switch** serves that
commit and reloads the view.
To serve another branch or tag, open the button under the navigation header that names
the served ref. It lists the mirror’s branches, the default first, or its tags, newest
first, and the filter box narrows either list by name; the list reads the mirror alone,
so it shows what the last fetch brought.
Choosing one serves it and reloads the view on the same file or folder when the new
revision has it, or at the root when it does not.
A switch lasts until the server stops; the next `metab file://…` serves the default
branch again, as its banner says.
A branch or tag deleted upstream leaves the mirror, but no commit does, so an older pin
stays readable after a force-push.
If the origin is gone the row says the refresh failed and the pin keeps serving.
A `/commit/<id>` address for a commit the mirror does not have is fetched for only when
the mirror is older than the one-minute freshness window: the page says it is fetching,
then opens the commit, says the commit was not found when the fetch ran without bringing
it, or says it was not fetched, with the reason, when the fetch could not run.
On a mirror fetched inside the window nothing is fetched, because a link in a served
page can lead to any such address; the page says the commit is not in the mirror as
fetched. Either way **Retry** fetches.

A served pin always runs under the untrusted profile: `--untrusted` is implied, the
`METAB_*` enables are ignored, and `--allow-edits` is an error.
HTML files offer only their source.
`/api/cache/…` answers `unsupported_for_subject` on a served pin, so nothing about other
cached sources is served beside it; inspect the cache with
`metab <url> --api /api/cache/…` instead.

`/api/source/status` reports the pinned commit and ref and the mirror’s freshness.
`POST /api/source/refresh` starts a refresh, or joins the running one, and answers at
once.
With the body `{"for": "commit"}` it is the fetch a missing commit waits for, which
starts a fetch of the mirror only outside the freshness window and otherwise answers
`fresh`; adding `"retry": true` always fetches.
Its answer’s `pull_refresh` says how the attended pull request’s refresh was answered,
`too_many` when the queue had no room for it, or null when none was asked for.
`POST /api/source/pin` switches the served commit to a branch, a tag, or a commit ID in
the mirror, with a JSON body such as `{"ref": "feature"}` or `{"oid": "3f2a9c1"}`. In a
server, one the mirror lacks answers `202` with `selection_pending` and fetches once;
asked again after that fetch, it switches or answers `404`. `--api` never fetches for it
and answers `404` at once.
A pin request may also name the page’s address, as in
`{"ref": "feature", "view": "/view/…"}`; the answer’s `view_href` is then that address
when the new revision has the entry, or `/view/` when it does not.
The address is checked before anything switches: it must be percent-encoded ASCII, as a
page’s own pathname is, and a query or fragment is dropped.
`/api/source/refs?kind=branch` (or `kind=tag`) lists what the selector offers, with `q`
for a case-insensitive name fragment and `limit` for the page size (default 100, at most
1000); `total` and `truncated` say how many matched.
Each is a POST with a JSON body behind the same-origin guard, so a link inside a served
page cannot start one.
The same routes work in-process:

```shell
echo '{}' > refresh.json
echo '{"ref": "feature"}' > pin.json
metab file:///path/to/origin.git --api /api/source/status
metab file:///path/to/origin.git --api "/api/source/refs?kind=tag"
metab file:///path/to/origin.git --api /api/source/refresh --data refresh.json
metab file:///path/to/origin.git --api /api/source/pin --data pin.json
```

The refresh command waits for the fetch it asked for, prints the status after it under
`after:`, and exits 1 when the refresh failed, or when it had not finished within one
Git deadline, in which case leaving stops it; it exits 0 when the fetch ran, or when
another process was already refreshing the mirror.
After URL selection resolves, ordinary reads and cache-only GETs do not fetch or
implicitly repair Git objects.
CLI startup can acquire a source and obtain missing PR metadata or required Git head/ref
data, even when the source store already exists.
Explicit source and GitHub refresh actions can also fetch in a one-shot command.
A pin switch through `--api` lasts for that one command, because each command is its own
server; the next one serves the default branch again.

## Acquiring a Git source: `--no-serve`

`--no-serve` acquires or reuses an `https://` or `file://` source in the repository
cache under `METABROWSER_CACHE_DIR` (default `~/.cache/metabrowser`) and prints the
source slug, store identity, and revision without binding a port or opening a browser.
A healthy published store is reused, including an overlay with its remembered lender.
On a cache miss, `--checkout` can name a lender; acquisition without a selected lender
creates a full store.
Borrowing follows the same checkout admission and missing-object rules as serving.
SSH transport is not supported.

```shell
metab file:///path/to/origin.git --no-serve
metab file:///path/to/origin.git --api /api/cache/layout
metab file:///path/to/origin.git --show README
metab file:///path/to/origin.git --api /api/tree
```

### What a clone prints

A first clone of a large repository runs for minutes, so every mode that clones says on
stderr where the clone goes, how far it has got, and when it is done:

```text
cloning https://github.com/owner/repo into ~/.cache/metabrowser
cloning https://github.com/owner/repo: receiving objects: 45%, 334.0 MiB at 9.5 MiB/s (40 s)
cloned https://github.com/owner/repo in 104 s (742.0 MiB); starting the server
```

- The first line names the cache directory of `METABROWSER_CACHE_DIR`, with your home
  directory as `~`. It is the directory that holds every clone, and the one to measure
  or move aside.
- On a terminal the middle line is one status line, redrawn in place: the phase, then
  Git’s own progress as it arrives, with the elapsed time counting once a second.
  Anywhere else it is a whole line at most every ten seconds, so a log stays short, and
  a clone that finishes sooner prints only the first and last lines.
- The last line gives the time the clone took, the size received unless the repository
  is too small for Git to report one, and, in serve mode, that the server starts next.

The numbers are read from `git fetch --progress` and printed in Metabrowser’s own words.
No text Git or the origin wrote reaches the terminal: a line of Git’s output that is not
exactly a progress record is dropped.
`--log-level debug` still shows Git’s own message when a clone fails, with every
character that is not printable written as its escape, such as `\x1b`, and on a line of
its own after the status line.
A line that cannot be written at once, to a stopped terminal or a pipe nobody reads, is
dropped rather than waited for, and a stderr that has been closed does not change the
exit status.

When the source is already cloned, serve mode and `--no-serve` say so in one line,
`using the clone of <url> cached in ~/.cache/metabrowser, fetched 3 hours ago`, and
start no clone. `--show`, `--api`, and `--check-api` print nothing for a cache hit: a
script runs them many times against one clone, and `/api/source/status` reports the last
fetch as data.

All of this is stderr, and stdout carries what it carried before.

### What a mirror’s page is called

A page served from a mirror is headed by the repository’s name, as a checkout of it
would be called: the last segment of the origin’s address without `.git`, so `squares`
for `https://github.com/jlevy/squares` and for `file:///srv/squares.git`. The ref and
the short commit follow it, with a control that copies the full commit, and the main
heading reads `squares / README.md`.

The page also says where the mirror is kept.
When the pane has room, the main heading ends with a note,
`mirror in ~/.cache/metabrowser/repository-stores/…`; the tooltip on the name, on the
note, and on the navigation heading gives the origin, the full commit, and the whole
path. That directory is a bare Git repository: nothing is checked out, and each page is
read from a Git object at the pinned commit, so no folder holds these files.
`git -C <location> log --all` works there.

The same three facts are data in `/api/source/status`, and `--api` prints them as the
route answered them:

```shell
metab https://github.com/owner/repo --api /api/source/status
```

- `name` is the repository’s name.
  A GitHub repository’s is lowercase, as its canonical address is.
- `origin` is the address the mirror was cloned from, as you gave it.
  A `file://` address under your home directory is shown with `~`:
  `file://~/git/squares.git`.
- `location` is the mirror’s bare repository, with your home directory as `~` when
  `METABROWSER_CACHE_DIR` is under it, and absolute when it is not.
- `borrows` is the checkout the mirror borrows objects from, as
  [Beside a checkout](#beside-a-checkout) describes, and `null` for a mirror that holds
  its own.
- `shallow` is `true` when the mirror’s history stops at a shallow boundary, and `false`
  otherwise.

`location` is the only place a route’s answer names a path in the cache, and `borrows`,
beside it, the only one that names a checkout.
File content, listings, errors, and every other envelope name neither.
`name`, `origin`, `location`, and `borrows` are `null` for a folder.

### GitHub URLs

A GitHub URL copied from the browser opens the repository it names, pinned where it
points:

```shell
metab https://github.com/owner/repo
metab https://github.com/owner/repo --no-serve
metab 'https://github.com/owner/repo/blob/release/v1/docs/guide.md#L10-L20' --no-serve
metab https://github.com/owner/repo/tree/v1.0 --api /api/tree
metab https://github.com/owner/repo/commit/1a2b3c4 --show README.md
```

Every spelling of one repository — `.git`, a trailing slash, `www.`, any letter case,
`git@github.com:owner/repo.git`, and `raw.githubusercontent.com` file URLs — is one
source, `https://github.com/owner/repo`, and one store.
A `/tree/` or `/blob/` URL may name a branch whose name contains `/`; the mirror decides
where the ref ends, preferring a branch, then a tag, then a commit ID. Ref names match
exactly, including letter case, and `HEAD` names the default branch.
`--no-serve` prints what the URL selected after the identity lines (`selection`, `pin`,
`path`, `lines` for a `#L10`, `#L10-L20`, or `#L10C5-L20C8` anchor, and `tab` for a pull
request’s `/files`), and `--show` and `--api` print the same lines on stderr and pin
that commit. A `/pull/<n>` URL pins the pull request’s head; see
[Pull requests](#pull-requests).
Query parameters other than `?plain=1` are dropped.
Any other github.com page, `http://`, and GitHub’s own top-level pages are refused with
a message that names the shape and offers the repository URL.

With no mode flag the source is served, and the browser opens at the file or folder the
URL names, with a `#L10-L20` anchor kept in the address and those lines highlighted.
`--no-serve`, `--show`, and `--api` read the mirror as it is: a ref or commit that is
not in it is reported as `ref_not_found` or `commit_not_found` rather than fetched, and
a path that is not at the pinned commit is `path_not_found`. Each exits with status 1,
but the acquisition before it succeeded, so the source stays published.
A server instead serves the default branch, fetches once in the background, and switches
to the selection if that fetch brings it, and a page opened meanwhile goes there;
`/api/source/status` reports `selection_state` as `pending`, then `found` or
`not_found`, or `fetch_failed` when the fetch could not run, and `superseded` after a
pin switch. A mirror the same command just cloned is not fetched again, so there the
selection is `ref_not_found` at once.
`--api /api/source/refresh --data <file with {}>` is the one-shot command that waits for
its selection’s fetch.

Public repositories are cloned anonymously.
When `gh` is installed, it is Git’s credential helper for `https://github.com` and for
nothing else, so a private repository opens once `gh auth login` has signed in an
account that can read it; Metabrowser never reads or stores a token.
No other credential source applies: your Git credential helpers are cleared, and Git
runs with `HOME=/dev/null`, so curl does not read `~/.netrc`. With `gh` installed, a
first clone is also refused before it starts when GitHub reports the repository over a
size limit, which the refusal states, set so a slow network still finishes within the
900-second acquisition deadline.
On a faster network, export `METABROWSER_MAX_FIRST_CLONE_KB` with a larger number of
kilobytes to go past it; the deadline still applies.
[Large repositories](reviewing-pull-requests.md#large-repositories) gives a measured
cost and what a mirror stores.
A first clone reports where it goes and how far it has got; see
[What a clone prints](#what-a-clone-prints).

### Pull requests

This is the reference for the commands; for the workflow in a browser, see
[Reviewing pull requests](reviewing-pull-requests.md).

`metab https://github.com/owner/repo` and `metab ~/src/repo` both offer Pulls.
A local checkout is identified by its github.com `origin` and readable `HEAD`; linked
worktrees and served subdirectories work too.
The local path keeps serving the working folder.
Its **Fetch changes** action acquires a comparison store only when requested, without
writing to the checkout or falling back to a full clone if borrowing is refused.
The URL-based [`--checkout` option](#beside-a-checkout) instead serves a managed pin and
retains the fallback cases documented below.

With the optional [gh-stack extension](installation.md#git-and-github-setup), native
stack membership is shared by the Pulls list and opened PRs.
Stack metadata is separate from PR details and refreshed as one shared repository
snapshot, not once per row.
These routes read the cached snapshot or explicitly refresh it (`stack-refresh.json`
contains `{}` or `{"retry": true}`):

```shell
metab https://github.com/owner/repo --api /api/plugin/github/stacks
metab https://github.com/owner/repo --api /api/plugin/github/stacks-refresh --data stack-refresh.json
```

The refresh body accepts only an optional boolean `retry`. A known provider rate reset
still holds a retry.
Failed optional work retains cached membership and leaves the PR catalog and details
usable.

A pull-request URL pins the pull request’s head commit and reads its data:

```shell
metab https://github.com/owner/repo/pull/123 --no-serve
metab https://github.com/owner/repo/pull/123 --show /pull/123
metab https://github.com/owner/repo/pull/123 --show /pull/123/files
metab https://github.com/owner/repo/pull/123 --show README.md
metab https://github.com/owner/repo/pull/123 --api '/api/plugin/github/pull?number=123'
metab https://github.com/owner/repo/pull/123 --api '/api/plugin/github/pull-markdown?number=123&part=body'
```

The first `--show` or `--api` of a pull request reads it with `gh api` (the description,
conversation, reviews, review comments, check runs, and statuses), fetches its commits
through GitHub’s `refs/pull/<n>/head`, a fork’s included, and caches the record.
Later ones answer from that cache without running `gh` or reaching the network, so they
work offline. `--no-serve` refreshes the record, sending the ETags it holds so an
unchanged part costs GitHub nothing against the rate limit.
A one-shot `--api /api/plugin/github/pull-refresh` with
`--data <file with {"number": 123, "retry": true}>` also refreshes it, waits, prints the
record under `after:`, and exits 1 when the refresh failed.
The `pull` and `pull-markdown` routes and the `pull-refresh` body all require the
number. `"retry": true` is a reader’s own request: without it, a number with no record
answers `not_cached`, one refreshed inside its window answers `not_due`, and neither
starts anything.

A `/pull/<n>/commits/<id>` URL pins that commit, which can be a fork’s, and a server
opens at the top of the repository.
A `/pull/<n>/files` URL selects the same pull request as `/pull/<n>` and adds
`tab: files` to the selection lines, and a server opens at `/pull/<n>/files`, as its
`Serving` line prints.
The tab says only where a server opens: `--show` and `--api` answer the path or route
they are given, so `--show /pull/<n>/files` is the way to ask for Files changed without
a browser. A `/pull/<n>/commits` URL is the same as `/pull/<n>`, because the page has no
Commits tab. Other pull-request pages, such as `/pull/<n>/checks`, and a repository’s
`/pulls` list are refused.
A URL selects one pull request, and `--show` and `--api` answer for any number:
`--show /pull/<other>` reports what the cache holds of it and fetches nothing, `absent`
with the reason `not_cached` when that is nothing, and a folder with no GitHub
repository answers the reason `not_github`.

`--show /pull/<n>` reports the page’s kind and a summary of its record, after the
selection lines that `--show` and `--api` print on stderr:

```console
$ metab https://github.com/pallets/click/pull/3866 --show /pull/3866
selection: pull_request
pin: b90faad1788bc030bb3320938f07c9189f42d7d0 (pull request 3866 head)
pull_request: 3866 (merged; fetched 2026-11-02T21:49:31Z by gh:your-login)
show: /pull/3866
route: /pull/3866
kind: pull-request
views: pull-request (default)
model: pull envelope; state=current pull_state=merged fetched_at=2026-11-02T21:49:31Z reader=gh:your-login issue_comments=6 reviews=1 review_comments=0 check_runs=11 statuses=1 tab=conversation
```

`/api/plugin/github/pull?number=<n>` reports the record with a state: `current` within a
minute of its fetch, `stale` after, or `absent` with a reason.
Its `comparison_route` is Files changed, the merge base of the base branch and the head
to the head, as GitHub shows it; issue it with `--api` to get the diff.
`--diff` does not open an `https://` source, so this route is the way to read one.
`--format json` prints the envelope alone, for a tool such as `jq`:

```shell
URL=https://github.com/owner/repo/pull/123
ROUTE=$(metab "$URL" --api '/api/plugin/github/pull?number=123' --format json |
  jq -r .comparison_route)
metab "$URL" --api "$ROUTE" --format json |
  jq -r '.manifest.files[] | "\(.kind) \(.new.path // .old.path) +\(.additions) -\(.deletions)"'
```

The answer is a
[File Diff Format](project/architecture/file-diff-format/file-diff-format.md) document:
`manifest.files` lists the changed files, and `patches`, keyed by each file’s `id`,
holds its hunks.

`--show <path>` reports a file at the head without printing it.
To read the file, run Git in the mirror, using `pin` and `location` from
`/api/source/status`, and expand a leading `~` in `location` yourself:

```shell
git -C <location> show <pin>:README.md
```

`metab <pull-request URL>` without `--no-serve` serves the head and keeps the record
fresh beside the mirror: a stale one is refreshed when serving starts and when a stale
page becomes visible, and `POST /api/plugin/github/pull-refresh` (a JSON object body
naming `number`) refreshes it on request and returns at once, with `pending` while no
record exists yet. A newer head is offered as the source’s `latest` rather than switched
to. The server pins that pull request’s head on the port its `Serving` line reports, and
opens any other of the repository’s at `/pull/<n>` without moving the pin; several run
side by side from one cache, one process for each.

A repository’s pull-request catalog is available from any URL of it:

```shell
echo '{"state": "open", "target": 500}' > refresh.json
metab https://github.com/owner/repo --api /api/plugin/github/pulls-refresh --data refresh.json
metab https://github.com/owner/repo --api '/api/plugin/github/pulls?state=open&limit=100'
```

The first command starts or joins a resumable metadata job and waits for its outcome; it
exits 1 if the job fails.
The job prioritizes the newest 500 matching pull requests, then continues through all
repository metadata.
The second command reads a cached window, offline too, with no `gh` and no Git.
`state` is `open` by default, `closed` (including merged), or `all`. `limit` is 0 to
1,000, and `after` is the last PR number from the preceding window.
`next_after` names another cached window, not a remote page.

`total` is GitHub’s exact count for the selected filter, `repository_total` its count
for all pull requests, and `count_at` says when those counts were read.
`fetched` counts cached matching rows; `catalog_fetched` counts all cached rows.
`complete` becomes true when the background catalog reaches the end.
Displaying another 500 rows does not cap or restart that catalog.
A refresh reads metadata changed since its last checkpoint;
`{"state": "open", "retry": true}` requests that check even while the cache is fresh,
subject to a reported rate-limit reset.
Descriptions, comments, reviews, checks, and comparison objects are separate per-PR
reads.

Fetching new pull-request data needs GitHub CLI (`gh`), signed in to github.com.
Use a current maintained release and verify the active account with
`gh auth status --active --hostname github.com`; see
[Git and GitHub setup](installation.md#git-and-github-setup).
Cached PR metadata remains readable without `gh`. A pull request that cannot be read
does not fail the command, so a script reads the `pull_request` line or the route’s
`state` rather than the exit status.
With a record cached, the pin stays at the record’s head and the `pull_request` line
adds why the refresh failed.
Without one, `/pull/<n>` pins the default branch and `/pull/<n>/commits/<id>` pins that
commit if the mirror has it, and the `pull_request` line says why:

| Name | Meaning |
| --- | --- |
| `gh_missing` | `gh` is not on `PATH` |
| `gh_too_old` | This `gh` cannot report its active account; update GitHub CLI |
| `not_logged_in` | `gh` is not signed in to github.com |
| `rate_limited` | GitHub’s rate limit, with the time it resets when GitHub gives one |
| `not_found_or_private` | The pull request does not exist, or the account cannot read it |
| `network_error` | `gh` could not reach GitHub |
| `account_changed` | The active `gh` account changed during the read |
| `head_mismatch` | The pull request kept moving during the read |
| `gh_failed` | An answer from `gh` could not be read |
| `fetch_failed`, `git_failed` | Git failed |
| `record_too_large` | The record is over the size a record may have |
| `cache_unwritable` | The record could not be written to the cache |

Check runs or statuses GitHub refuses, and a comparison whose base cannot be fetched,
are listed in the record’s `unavailable`, and the rest of the record stands.

`--api /api/cache/…` on a `file://` URL acquires as a side effect, then issues the route
against an empty throwaway directory so cache inspection cannot expose origin objects
through `/api/tree`. `--show` and other `--api` routes on that URL acquire or reuse the
store, pin the default revision, and inspect the pin in-process.
Nothing binds a port.
`--show` accepts a display path (`README`) or a `GitPath` wire.
`--check-api` runs the navigation scenario on the pin, where Recent’s
`unsupported_for_subject` is the expected answer.
`--walk` refuses a Git source: the walker reads a filesystem, and
`--api '/api/tree?depth=N'` lists a pinned tree.
ssh URLs stay closed.
A second `--no-serve` of the same `file://` source reuses the published store and says
so on stderr. That cache hit reads only the application home: it runs no Git, does not
need the origin, and works against a home the current user cannot write.
Spellings that normalize to the same address, such as `FILE://localhost/path/` and
`file:///path`, are one source.

Inspect cache state from any local root after an acquire: the cache routes resolve
`METABROWSER_CACHE_DIR` independently of the served directory.

```shell
metab ./notes --api /api/cache/sources
```

### Beside a checkout

If you already have the repository checked out, name that checkout once and the mirror
borrows its objects instead of copying them:

```shell
metab https://github.com/owner/repo/pull/123 --checkout ~/src/repo
metab https://github.com/owner/repo/pull/124    # remembered from then on, from anywhere
```

`--checkout` works with serving, `--api`, `--show`, `--check-api`, and `--no-serve`, on
a Git source. The path is a checkout’s root, a linked worktree of it, or a bare clone.
The mirror’s Git objects come from that checkout through `objects/info/alternates`, and
what it lacks, such as a pull request whose branch it never fetched, is fetched into the
mirror. That is usually kilobytes, and more when the checkout is behind: on a shallow
checkout of a 1.2 GB repository, one branch pushed since the checkout’s last fetch cost
43 MB and 15 s, and the same command minutes later cost 1 MB and 5 s, the checkout
having fetched it (measured 2026-11-02).

Everything else is the mirror you would otherwise have: the same pages, the same
pull-request records, and a page served under the same untrusted profile.
`metab` says so on stderr, `borrowing objects from ~/src/repo`, and `borrows` in
`/api/source/status` and the heading’s tooltip name it.

**Nothing writes to the checkout, and no Git runs in it.** Its refs, remotes, and
configuration are files read with a bound on each, and its hooks, `core.fsmonitor`,
`core.sshCommand`, and diff drivers are not consulted.
The mirror’s refs are still only what the origin sent: a branch or tag that exists only
in your checkout is not served.

**Only a checkout you name lends.** Run `metab <url>` inside a checkout of that
repository with no mirror yet and it clones a full mirror, as it does anywhere else, and
prints once what would have borrowed instead:

```text
this directory is a checkout of https://github.com/owner/repo; to borrow its objects instead of cloning: metab https://github.com/owner/repo --checkout ~/src/repo
```

A directory you merely stand in can be made to look like a checkout of anything, and Git
does not verify what it reads from one, so that decision is yours.

What can happen when you name one:

| Situation | What `metab` does |
| --- | --- |
| No remote of the checkout is the URL’s repository | Refuses, and names the repositories its remotes point at, with any credentials in their URLs left out. Any remote counts, compared without regard to case, so a fork with the repository as `upstream` lends; a remote spelled as a path, as `git clone /x/origin.git` records it, is the `file://` source of that path |
| The path is no checkout at all | Refuses, whether or not a mirror of the repository is already in the cache |
| The checkout is a partial clone, or has its own `objects/info/alternates` | Says why and clones a full mirror: the first would find objects missing when they are read, and the second would follow a chain nothing recorded |
| Its object format differs from the origin’s, its objects cannot be read, or another user owns them | Says why and clones a full mirror |
| A full mirror of the repository is already in the cache | Keeps it, says so, and borrows nothing. This release has no command that converts one; to borrow instead, delete the mirror from the cache and run the command again |
| The mirror already borrows from another checkout that can still lend | Keeps borrowing from that one, and says so |
| `--api /api/cache/...` | Says that the flag is not applied to a cache route, which reads records and no object, and answers the route |

**A shallow checkout** lends too, and `shallow` is `true`: history views stop where the
checkout’s do, and `metab` says `history is shallow, as the checkout’s is`. On a shallow
history `git merge-base` can name a commit that is not the real merge base, with no
error, which would show the base branch’s own changes as the pull request’s. So a merge
base there is used only when it is provably right.
When it is not, the pull request’s refresh fetches more history into the mirror, never
the checkout, in up to five growing rounds; a depth-limited CI checkout is where this
most often happens. Meanwhile, and offline, the record’s `unavailable.comparison` is
`base_uncertain`, `comparison_route` is `null`, and the page shows no Files changed
rather than a guess.

A commit the comparison needs that the checkout no longer holds, an ancestor it has
collected, is `commits_unavailable` in the record’s `unavailable.comparison`, never
`no_merge_base`, which is Git’s own answer that two commits share no history.
A commit at the shallow boundary is shown with its message and author, and its diff is
refused as `parent_unavailable`, since Git would otherwise diff it against nothing.

**If the checkout moves or is deleted,** nothing borrowed can be read, and `metab`
refuses rather than serve a failing page:

```text
Error: the checkout this mirror borrows objects from is gone: ~/src/repo (lender_missing), and this mirror of https://github.com/owner/repo cannot be served without it. If it moved, or another checkout of the repository should lend instead, name it: metab https://github.com/owner/repo --checkout <new path>
```

The same refusal, with its own reason, answers a checkout that can no longer lend: one
that has grown an `objects/info/alternates` of its own, whose objects can no longer be
read, or whose directory now holds another repository.
The checks that admitted it run again on every open that uses it, and before every fetch
into the mirror.
Naming the new place, or another checkout of the repository, repairs it,
after the same checks, with no network; a repair that stopped before its record was
written is finished by the same command.
`--api /api/cache/stores` still answers, with `mode` (`full` or `overlay`) and `lender`
(`present` or `lender_missing`) for each store, and no path.
A refresh in a server that is already running reports `lender_missing` as its outcome.
A store whose alternates file disagrees with its record is refused as `damaged`.

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
  publishes nothing. A source that is itself a partial clone missing objects says so;
  clone it fully first.
  An https origin names why, in parentheses: `not_found_or_private`,
  `network_unreachable`, `connection_interrupted`, `tls_failed`, `timed_out`,
  `server_error`, `rate_limited`, `proxy_auth_required`, or `too_large`.
  `not_found_or_private` means the origin did not show the repository: it does not
  exist, or it is private and the request, anonymous or with the account `gh` answered
  with, could not read it.
  The origin does not say which, so neither does the message.
  `timed_out` means the origin gave no answer to its first request within 30 seconds, or
  a transfer moved less than 1000 bytes per second for 30 seconds; a clone that keeps
  making progress is never stopped for taking long, only at the 900-second acquisition
  deadline.
- **A repository whose branch or tag names differ only in letter case** (`Feature` and
  `feature`) is refused as `ref_case_collision` on a case-insensitive filesystem, such
  as macOS’s default, which cannot hold both.
  A served mirror whose origin gains such a twin later reports the same outcome for its
  refresh and keeps every ref where it was.
- **An acquisition that is interrupted**, by Ctrl-C, by the terminal hanging up, or by
  `SIGTERM`, stops Git and every helper it started, and leaves nothing visible, because
  the source is published last, after its store.
  A hangup exits with status 129 and `SIGTERM` with 143; under `nohup`, a hangup is
  ignored as it asks. While the source is served, a hangup stops the server as Ctrl-C
  does, killing a running refresh’s Git first, and exits 129. The next acquisition
  removes the abandoned staging entry, fetches again, and reuses a store that was
  already published. Nothing deletes a published store.

Refusals that concern the application home say how to repair it:

| Message begins | Repair |
| --- | --- |
| `METABROWSER_CACHE_DIR is set but empty`, `METABROWSER_CACHE_DIR must be an absolute path` | Unset it, or set it to an absolute path |
| `The Metabrowser application home is accessible to other users` | Run `chmod 700` on it, or use another `METABROWSER_CACHE_DIR` |
| `An entry in the Metabrowser application home cannot be verified` | Restore the current user’s write permission, or use another `METABROWSER_CACHE_DIR` |
| `This Metabrowser application home uses format` | Upgrade Metabrowser, or use another `METABROWSER_CACHE_DIR` |

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

# Repository cache state in METABROWSER_CACHE_DIR (default ~/.cache/metabrowser), which is
# reported as absent rather than created when it does not exist.
metab ./notes --api /api/cache/layout
metab ./notes --api '/api/cache/sources?limit=20'

# Only the envelope, as JSON or YAML, for a tool to parse.
metab ./notes --api /api/git/refs --format json
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

With `--format json` or `--format yaml`, stdout is the envelope alone, so it parses.
A body that is not JSON is one string, and a refresh that waits prints only the status
it ended with, the answer the output above would print under `after:`.

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

## Storage locations

On macOS and Linux, cached repositories live in `~/.cache/metabrowser` and user
configuration in `~/.config/metabrowser/config.yml`. Use `--cache-dir DIR` or
`METABROWSER_CACHE_DIR` for an exact cache location, and `--config-dir DIR` or
`METABROWSER_CONFIG_DIR` for an exact configuration location.
Flags take precedence over environment variables.
Otherwise `XDG_CACHE_HOME` and `XDG_CONFIG_HOME` select the corresponding base
directories, with `/metabrowser` appended.

Environment overrides must be nonempty absolute paths without `..` components.
CLI paths may be relative to the current directory.
Ordinary folder browsing does not create these directories.
Cache creation preserves existing configuration.
Version 0.12 does not read `METABROWSER_HOME` or migrate `~/.metabrowser`.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
