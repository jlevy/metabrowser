# Reviewing Pull Requests

Metabrowser reads GitHub pull requests from a repository URL, a pull-request URL, or a
checkout you already have.
The Pulls tab lists the repository’s pull requests, and each pull request’s page shows
its description, conversation, reviews, checks, and changes.
What it fetches is cached, so a pull request you have read stays readable offline.

![A pull request’s page on its Conversation tab, with its changed files in the Pulls list](../images/screenshot-pull-request.jpg)

Cloning needs Git, and reading pull requests from GitHub needs GitHub CLI (`gh`), signed
in; [installation](installation.md#git-and-github-setup) says how to set them up.
Cached pull requests stay readable without `gh`.

## Open a Repository or a Pull Request

```shell
metab https://github.com/owner/repo           # a repository
metab https://github.com/owner/repo/pull/123  # one pull request
metab ~/src/repo                              # a checkout, a linked worktree, or a folder in one
```

- **A repository or pull-request URL** clones the repository into your cache once and
  serves it pinned to one commit: a pull-request URL pins the pull request’s head.
  Later runs reuse the clone.
- **A local path** serves that folder as it is on disk, local changes included.
  It shows **Pulls** when its checkout’s `origin` is on github.com and its `HEAD` can be
  read. On a fork, the list belongs to `origin`, usually the fork, and the tab names the
  repository.

`metab` prints the address it serves and opens your browser there; Ctrl-C in that
terminal stops it. A first clone reports its progress on stderr:

```text
cloning https://github.com/pallets/click into ~/.cache/metabrowser
cloned https://github.com/pallets/click in 4.9 s (5.3 MiB); starting the server
Serving https://github.com/pallets/click at http://127.0.0.1:8411/pull/3866
```

A GitHub URL ending in `/pull/123/files` or `/pull/123/checks` opens that tab, and one
ending in `/pull/123/commits` opens the conversation, where the commits appear.
If you already have the repository checked out, `--checkout` lets the clone borrow its
objects instead of copying them; see
[beside a checkout](command-line.md#beside-a-checkout).

## The Pulls Tab

Choose **Pulls** beside Files and Commits, or press `P`. The list starts on **Open**;
**Closed** includes merged pull requests, and **All** shows both.
Each filter shows its total when the catalog knows it.

Rows are newest first, each with its open, draft, merged, or closed state.
Metabrowser fetches the repository’s list of pull requests in the background and shows
each page as it arrives; scroll toward the end to load more, and a spinner below the
last row says how many have been fetched so far.

Each row’s third line is its pull request’s brief change line, “21 A, 7 D, 15 M · +1,234
−567”: how many files it adds, deletes, modifies, and renames, and its lines added and
deleted, so walking the list shows the size of each change.
It sums the same list of changed files the row’s tree shows, as a stack’s heading sums
its pull requests’, and asks GitHub for nothing: the lists come from what the Pulls tab
already reads behind you for the rows in view and from trees you open, and a gray
placeholder holds the line’s place until one arrives.

Click a row’s title or number to open its pull request; its files stay as they were.
The change line carries the chevron for the files, which start collapsed: click it to
show or hide them under the row.
No row expands on its own.
Click a file to open **Changes** at that file.
Move between rows with `J` and `K` or the arrow keys, and Enter opens the focused pull
request. Right moves to the row’s change line, where Enter or Space shows or hides the
files, Right shows them or moves into them, Left hides them and then returns to the row,
and Up returns to the row.
The file list says **Listing changed files…** until GitHub answers.
Once the files show, a later page or an updated list does not move the rows you are
reading: it is offered as **Show N more files** or **Show the updated list of N files**.

To start over, click the folder’s name at the top of the navigation pane, or press `0`.
That is Home: the folder as a fresh load shows it, with every tab at its first, so
**Pulls** opens its list and a pull request you open from it opens on **Conversation**,
whichever tab you last read.

### Stacks

With the optional [gh-stack extension](installation.md#git-and-github-setup), the Pulls
tab groups the pull requests of each native GitHub stack under a **Stack #N** row, open
by default, top of the stack first; pull requests in no stack follow, and a stack’s row
opens and closes like a folder.
A member’s row shows its place before its number, such as **1/6 · #455 · octo**, and its
title on the line under it.
A pull request in two stacks sits under the first, and its place names the other stack
by its number, such as **3/4 · ⧉300 2/2**.

On the page, a stack button at the end of the author’s line shows the same position, and
a pull request in two stacks has a button for each, which names its stack, such as
**⧉300 2/2**. The button opens a menu of the stack’s members, from top to base.
On macOS, Control-N goes to the next member toward the top and Control-P to the previous
one toward the base; on Windows and Linux, where those keys are the browser’s, use the
menu. Without the extension, or when GitHub cannot answer, pull requests read as usual
and the list stays flat, unless stacks are cached.
Metabrowser reads stacks and never changes them.

## The Pull Request Page

The header gives the title and number; the author’s sentence, such as “octo wants to
merge 2 commits”, with any stack button at its end; the head and base branches on a line
of their own, head → base; the state and dates, with **View on GitHub**; and the labels,
each in the color GitHub gives it, with its description, if any, shown on hover.
The author’s GitHub avatar is beside the name, and a neutral person icon holds its place
where GitHub gave none, as on a commit’s page; a Pulls row shows none.
Its last row is the **Diff summary**, on every tab, collapsed: the files and lines
changed, such as “35 files changed · 2 A, 3 D, 30 M · +1,234 −3,423”, which opens into
the tree of changed files with rolled-up line counts, and a file there opens **Changes**
at that file.
While the comparison it counts is on its way, as when Conversation prepares
it in the background, the row holds a gray pulsing block after a moment; that block is
the only sign of the background work.
A cached page shows at once and refreshes in the background; the
[design system](design-system.md#the-pull-request-page) describes how it draws.

The page has three tabs:

- **Conversation** (`C`): the description, then comments, reviews, and commits in
  GitHub’s order, joined by a timeline line.
  Commits that arrive while you read are added after what is shown.
  A short commit ID opens that commit on GitHub.
  **Review comments** lists the inline review comments with their files and diff hunks.
- **Changes** (`G`): the diff from the merge base to the head, **Split** or **Unified**
  (`L` switches). Markdown files open as rendered changes, as the next section describes.
  The changed-file list on the Pulls tab moves through this diff, and the selected file
  follows the diff as you scroll.
- **Checks** (`E`): the check runs and commit statuses, with links to their details.

### Code Controls

| Opened with | Code controls |
| --- | --- |
| A repository or pull-request URL | **Browse code** opens the pinned code, first switching the pin to this pull request’s head when another commit is served. When the head has moved since, **Switch to the head** offers the new one. |
| A checkout or a folder in one | Files and Commits keep showing your checkout, which may differ from the pull request, so there is no **Browse code**. When the checkout’s `HEAD` is the pull request’s head, the page says so and offers **Browse the checkout**. |

In **Changes**, a changed file offers **View on branch**, which opens the file at the
pull request’s head in the main view, with the file tree, tabs, and ref selector around
it, as **Browse code** opens the whole tree.
Where it opens follows the table above:

- Opened with a repository or pull-request URL, it first switches the pin to the head
  when another commit is served, as Browse code does.
  The pin is the server’s, so every tab moves with it, and a tab whose pin another tab
  switched turns its links into the switch back.
- Beside a checkout, or a folder in one, it opens your working-tree copy of the file,
  only while the checkout’s `HEAD` is the pull request’s head and only for a file inside
  the served folder. That copy includes any changes you have not committed.

A deleted file, a symbolic link, and a submodule have no View on branch, and no file
does while Changes shows an earlier head than the pull request’s, which no branch holds
any more. If the pull request moves on after the page was drawn, View on branch and
Browse code switch nothing and say that the head has moved; reload to see the newer
changes.

### Rendered Markdown in Changes

**Rendered** shows each changed block of a Markdown file as removed and added, with the
changed words marked.
Long runs of unchanged blocks fold into one quiet line that opens them in place, and a
file’s **Rendered** | **Source** chooser switches between the two.

Rendered shows what a change does to the document as it reads, so a change that does not
show in the document appears only in **Source**: a link or image destination or title,
an image’s alt text, an HTML comment, attribute syntax such as `{#name}`, a code fence’s
language, or only whitespace and line wrapping.
A block whose destination, title, alt text, comment, attribute, or fence language
changed is never folded away.

These files open in **Source**:

- files with raw HTML other than comments, such as `<br>` or `<details>`
- files with task lists (`- [ ]`) or footnotes
- files too large for the rendered view

Rendered also shows math and Mermaid diagrams as their source text, and does not
highlight code blocks.

A Markdown file’s front matter shows as the Frontmatter disclosure the file’s Document
view shows above it.
It stays closed when the front matter did not change, and opens with each changed key’s
old value removed and new value added when it did.

### Rendered YAML and JSON in Changes

A changed `.yaml`, `.yml`, or `.json` file opens in **Rendered** as the tree its file
view draws.
An added or removed key or item is marked in the change gutter, and a changed
value shows its old row removed and its new row added.
Every mapping and list that holds a change is open; an unchanged one is closed with the
file view’s preview of it, and a click opens it.
The tree shows what the data says, so a change to a comment, quoting, indentation, or
the order of a mapping’s keys appears only in **Source**.

YAML that does not parse, YAML with anchors and aliases (`&name` and `*name`), and files
too large for the rendered view open in **Source**.

## Find a Pull Request with Quick Search

Press `/` or `T` to open Quick Search, and type `#` to see recent pull requests in every
state. Digits after it, such as `#30`, complete pull-request numbers with the exact
number first; words after it match titles.
Ordinary text matches files and pull-request titles together.
Each result shows its title, number, and state, and Enter opens its Conversation.

Search reads the cached catalog, so it works offline.
Number completion covers the whole catalog, and a title search reads only its newest
entries.

## Staying Current

The page says when GitHub CLI fetched what it shows, as in
`Fetched 3 min ago via GitHub CLI`, at the end of the author’s line; Refresh ends the
row of ages under it.
While the Pulls tab or a pull request’s page is visible, Metabrowser rescans the
repository’s list of pull requests, so new pull requests, state changes, and edits
arrive by themselves.
A record counts as current for 60 seconds after its fetch, the freshness window, and for
as long after that as the list says GitHub has not changed the pull request; the page
still reads `Fetched 3 h ago via GitHub CLI`, one time and never two, since a check that
found nothing changed makes what is shown no newer.
The list does not track checks, statuses, or mergeability, so an open pull request’s
page reads those again on their own once a window.

A visible page refreshes a record that has gone stale, and the Pulls tab also fetches,
behind you, the pull requests you are likely to open next, within hourly limits and
while enough of your GitHub rate limit remains.
The page names a problem only when it cannot refresh: `Offline`, a rate limit with the
time of its next check, or the last failure with **Refresh**. The page tries a failure
again once a window while it stays open, except one you must fix, such as GitHub CLI
missing or signed out, which waits for **Refresh**. The Pulls tab’s **Reload** asks for
a new check of the list.

A refresh never moves the diff you are reading.
When the head moves, the conversation and checks update, **Changes** says
`New commits were pushed; updating.` over the diff it keeps, and **Show the newer
changes** moves it. On a repository URL the served code stays put too, until **Switch to
the head**. The foot of the navigation pane says separately when the repository’s mirror
was fetched.

### Several Pull Requests at Once

One server opens any pull request of its repository, from the Pulls tab or at
`/pull/<n>`, without changing the code it serves.
To browse the code of several heads at once, run a server for each; servers of one
repository share one clone, so only the first one clones.
Each takes the first free port from `--port` up and prints it on its `Serving` line;
`--no-open` keeps the browser closed.

## Offline and Cached Reading

Pull requests, lists, and comparisons you have fetched stay readable offline, as long as
the Git objects they need are in the cache, and a mirror that borrows from a checkout
also needs that checkout.
A failed refresh keeps what was shown and says why.
A pull request, list page, or comparison never fetched needs the network.

### Private Repositories

They work through your `gh` login, and nothing else is needed.
`gh` is Git’s credential helper for `https://github.com` and for no other host, and
Metabrowser never reads or stores a token.
The clone and the records stay in your cache, and `metab` refuses a cache directory
other users can read.

### Large Repositories

A repository URL clones the whole repository, a second copy of its objects, unless you
name a checkout for it to borrow from.
Clones and records live in the cache directory that
[storage locations](command-line.md#storage-locations) names, and `du -sh` on it
measures them. No command removes a clone: to reclaim the space, stop every server and
delete the cache directory, and the next run clones again.

A first clone is refused before it starts when GitHub reports the repository over the
size limit. The refusal gives the repository’s size, the limit, and the deadline every
clone must meet. If your network is fast enough, set a larger limit in kilobytes:

```shell
METABROWSER_MAX_FIRST_CLONE_KB=<size> metab https://github.com/owner/repo/pull/123
```

To pay for a long clone ahead of time, run the same URL with `--no-serve`.

To discard everything cached of a repository’s pull requests, the list, records, changed
files, and refresh outcomes, while keeping its clone, run:

```shell
echo '{}' | metab https://github.com/owner/repo --api /api/plugin/github/cache-clear --data -
```

In a checkout, run it as `metab .` instead, since the address would clone the
repository. The cache-related failures below name this command.

## When Something Does Not Open

A clone that fails stops the command with an `Error:` line and exit status 1. A pull
request that cannot be read does not: `metab` serves the default branch, exits 0 in the
one-shot modes, and says why on its `pull_request` line.
The page says why too, and offers **Fetch** to try again once the cause is fixed.

| Name | What it means | What to do |
| --- | --- | --- |
| `gh_missing` | `gh` is not on `PATH` | Install `gh` |
| `gh_too_old` | This `gh` cannot report its active account | Upgrade `gh` |
| `not_logged_in` | `gh` is not signed in to github.com | Run `gh auth login --hostname github.com` |
| `not_found_or_private` | It does not exist, or the account cannot read it; GitHub does not say which | Check the URL, and that `gh auth status` names an account with access |
| `rate_limited` | GitHub’s rate limit, with its reset time when GitHub gives one | Wait; the page tries again after the reset |
| `network_error`, `network_unreachable`, `connection_interrupted`, `timed_out` | GitHub could not be reached, by `gh` or by Git | Restore the network, then **Refresh** |
| `too_large` | The first clone is over the size limit | See [large repositories](#large-repositories) |
| `lender_missing` | The checkout this clone borrows from has moved, gone, or can no longer lend | Run the command again with `--checkout <new path>` |
| `account_changed`, `head_mismatch` | The `gh` account changed, or the pull request kept moving, during the read | **Refresh** |
| `fetch_failed`, `git_failed` | Git failed | **Refresh**; for a clone, `--log-level debug` shows Git’s own message |
| `cache_unwritable` | The cache refused the write | Fix what the message names, or clear the repository’s cache |
| `newer_cache`, `unknown_cache` | A newer Metabrowser wrote the repository’s list, or its version cannot be read | Upgrade, or clear the repository’s cache |

A pull request’s conversation can stand while its **Changes** cannot.
The record names why in `unavailable.comparison`:

| Name | What it means | What to do |
| --- | --- | --- |
| `no_store` | A checkout has the record but no comparison yet | Open **Changes**, which prepares it |
| `base_uncertain` | The checkout’s shallow history does not settle the merge base, and Metabrowser does not guess | **Refresh** with the network, which fetches more history into the cache |
| `commits_unavailable`, `object_unavailable` | A commit or object the comparison needs is missing, as when the checkout lending objects has pruned it | **Refresh** tries to recover them from the origin |
| `object_corrupt` | An object does not match its ID | Repair the checkout or the cache, then **Refresh**; Metabrowser never writes to your checkout |
| `no_merge_base` | The base and head share no history | Read the diff on GitHub |
| `comparison_timeout`, `comparison_too_large` | Checking the comparison took too long or went past its bounds | **Refresh**, or read the diff on GitHub |

Every reason comes with a message that says more, and a rarer one, such as a failed TLS
security check or a proxy that requires authentication, is named in its message.
[GitHub pull requests](project/architecture/arch-github-pull-requests.md) describes how
records are prepared and how the cache refuses, and
[mirror acquisition and refresh](project/architecture/arch-mirror-acquisition-and-refresh.md)
the cases of borrowing from a checkout.

## From a Terminal or an Agent

Everything the page shows is available without a browser:

```shell
URL=https://github.com/owner/repo/pull/123
metab "$URL" --no-serve                                  # clone or reuse, and refresh the record
metab "$URL" --show /pull/123                            # kind, views, and counts
metab "$URL" --api '/api/plugin/github/pull?number=123'  # the whole record, with comparison_route
```

Issue the record’s `comparison_route` with `--api` to get the diff as data.
[The command-line guide](command-line.md#pull-requests) is the reference, with worked
examples, and [working with agents](working-with-agents.md) shows an agent handing you
the page.

## Trust

A pull request’s text and diff are untrusted and inert, beside a checkout too: nothing
in them runs, and they cannot make the page load anything from another site.
A description or comment that takes longer than a few seconds to render stays plain
text, under one line saying so; the same line says when the renderer is busy with other
texts or could not start, and reloading the page then tries again.
A repository URL is served under the untrusted profile.
Files of a local folder keep that folder’s
[content-trust](command-line.md#content-trust) settings; reviewing a pull request does
not change them.

## What It Does Not Do Yet

- **No comments on the diff.** Inline review comments are listed under **Review
  comments** on the Conversation tab.
- **No writing to GitHub.** Comment, approve, and merge on GitHub through **View on
  GitHub**.
- **Only github.com.** A pull-request URL on another host is read as a Git address and
  fails.
- **The pull request’s code beside a checkout that is elsewhere.** Files and Commits
  there show your checkout, which is the pull request’s code only while its `HEAD` is
  the pull request’s head.
  Opening the head whatever is checked out, as a read-only revision view in the same
  window, is planned in
  [Open Modes](project/architecture/arch-open-modes.md#pull-requests-in-a-repository-folder).

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
