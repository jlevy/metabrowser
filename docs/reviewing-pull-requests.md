# Reviewing Pull Requests

Metabrowser opens a GitHub pull request from its URL and shows it as a local page: the
description, conversation, reviews, checks, the diff, and the code at its head.
Once a pull request has been read, its pages come from a local mirror and a cached
record rather than from GitHub, so they open without waiting for the network, and
offline.

## Review a Pull Request

```shell
metab https://github.com/owner/repo/pull/123
```

`metab` prints the address it serves and opens your browser there.
Press Ctrl-C in that terminal to stop it.

You need:

- [`gh`](https://cli.github.com/) 2.81.0 or newer, signed in with `gh auth login`.
- A recent Git. `metab` refuses one below its security floor and names the versions it
  accepts.

The first pull request of a repository clones the whole repository into your cache, with
progress on stderr, then reads the pull request:

```text
cloning https://github.com/pallets/click into ~/.cache/metabrowser
cloned https://github.com/pallets/click in 4.9 s (5.3 MiB); starting the server
Serving https://github.com/pallets/click at http://127.0.0.1:8411/pull/3866
```

Later runs reuse that clone and say so
(`using the clone of … cached in ~/.cache/metabrowser, fetched 3 hours ago`).

A `/pull/123/files` URL copied from GitHub opens on **Files changed**, and the `Serving`
line prints that address, `http://127.0.0.1:8411/pull/123/files`. A `/pull/123/commits`
URL opens on Conversation, because the page has no Commits tab.

## What the Page Shows

The header has the title, state, branches, labels, and dates, and two links:

- **View on GitHub** opens the pull request on github.com.
- **Browse code** opens the repository at the head.
  The navigation pane beside the page already holds its Files and Git tabs.

Below the header are two tabs:

- **Conversation:** the description, then comments and reviews in time order.
  **Review comments** lists each inline review comment with its file and diff hunk, and
  **Checks** summarizes check runs and statuses, with links to their details.
- **Files changed:** the diff GitHub shows, from the merge base to the head, split or
  unified. Each file has **View file**, the file at the head, and **View at base**, the
  file at the merge base.

**View at base** moves the server to the merge-base commit, so the pull-request page
then says `This page's code is …, not the pull request's head …` and offers **Switch to
the head**, which moves it back.

## Beside a Checkout

If you already have the repository checked out, name that checkout once.
The mirror borrows its objects instead of copying them, so a pull request opens in
seconds and costs little, however large the repository is:

```shell
metab https://github.com/owner/repo/pull/123 --checkout ~/src/repo
metab https://github.com/owner/repo/pull/124    # remembered from then on
```

As a guide, a 1.2 GB repository that took 185 s and 1.2 GB as a full mirror took 5 s and
about 1 MB, and 43 MB when a branch had been pushed since the checkout’s last fetch
(measured 2026-11-02, under load, with `gh` adding its own seconds for the pull
request’s data).

Name any worktree of the repository; every worktree shares the same objects.

`metab` prints `borrowing objects from ~/src/repo`, and the heading’s tooltip says the
same. The pages, the commands, and the untrusted profile are the ones you would get from
a full mirror, and nothing is ever written to your checkout.

Only a checkout you name lends.
Run inside a checkout without the flag, `metab <url>` clones a full mirror and prints
the command that would have borrowed instead, because a directory you merely stand in
can be made to look like a checkout of anything.

Three things are worth knowing:

- **A shallow checkout may not settle Files changed at once.** If its history stops
  before the pull request’s merge base, `metab` fetches more history into the mirror.
  Until that succeeds, and offline, **Files changed** says the history is too shallow to
  know what the pull request changed, rather than show a guess.
- **If you move or delete the checkout,** `metab` refuses with `lender_missing`, prints
  the recorded path, and tells you to run the command again with
  `--checkout <new path>`.
- **A mirror that is already there stays.** Naming a checkout does not convert a full
  mirror, and this release has no command that does.
  To borrow instead, delete the mirror as [Large Repositories](#large-repositories)
  describes, and run the command again.

[The command-line guide](command-line.md#beside-a-checkout) has every case.

## Private Repositories

They work through your `gh` login, and nothing else is needed.
`gh` is Git’s credential helper for `https://github.com` and for no other host, and
Metabrowser never reads or stores a token.
The mirror and the record stay in your cache, and `metab` refuses a cache directory
other users can read.

## When a Pull Request Does Not Open

A clone that fails stops the command with an `Error:` line and exit status 1. A pull
request that cannot be read does not: `metab` serves the default branch, exits 0 in the
one-shot modes, and says why on the `Pull request:` line.
The page says `This pull request has not been fetched yet.`, gives the reason, and
offers **Fetch**. Once the cause is fixed, run the command again.

| Name | What it means | What to do |
| --- | --- | --- |
| `gh_missing` | `gh` is not on `PATH` | Install `gh` |
| `gh_too_old` | `gh` is older than the version above | Upgrade `gh` |
| `not_logged_in` | `gh` is not signed in to github.com | Run `gh auth login` |
| `not_found_or_private` | It does not exist, or the account cannot read it; GitHub does not say which | Check the URL, and that `gh auth status` names an account with access |
| `too_large` | The first clone is over the limit | See [Large Repositories](#large-repositories) |
| `lender_missing` | The checkout this mirror borrows from has moved or gone, or can no longer lend: it borrows objects itself, its objects cannot be read, or it holds another repository now | Run the command again with `--checkout <new path>` |
| `network_unreachable`, `network_error` | GitHub could not be reached, by Git or by `gh` | See [Offline](#offline) |

[The command-line guide](command-line.md#pull-requests) lists every name.

## Large Repositories

A **mirror** is a full bare clone of the repository, so it is a second copy of the
repository’s objects, unless you [name a checkout](#beside-a-checkout) for it to borrow
them from. Mirrors are kept in `~/.cache/metabrowser/repository-stores`, and each pull
request’s record is a JSON file under `~/.cache/metabrowser/sources`. See
[storage locations](command-line.md#storage-locations) to move them.
A mirror’s size is about the repository’s: measure the whole cache with
`du -sh ~/.cache/metabrowser`. Nothing deletes a mirror and no `metab` command removes
one, so to reclaim the space, stop any servers and delete that directory.
The next run clones again.

A first clone is refused before it starts when GitHub reports the repository over a size
limit. The refusal gives the repository’s size, the limit, and the deadline every clone
must meet. If your network can finish in time, go past the limit by naming a size in
kilobytes (`gh api repos/owner/repo --jq .size` reports the repository’s):

```shell
METABROWSER_MAX_FIRST_CLONE_KB=<size> metab https://github.com/owner/repo/pull/123
```

As a guide to the cost, a 1.2 GB private repository cloned in 185 s on a home connection
(measured 2026-11-02). To pay it ahead of time, run the same URL with `--no-serve`,
which clones and reads the pull request and starts no server.

## Several Pull Requests at Once

Run one `metab` for each pull request whose code you want at its head.
A server has one pin, and it opens any other pull request of the repository at
`/pull/<n>` without moving it: one it has not read offers **Fetch**, and **Browse code**
switches the pin to that pull request’s head.
Each server takes the first free port from 8411 up and reports it on its `Serving` line:

```text
Serving https://github.com/pallets/click at http://127.0.0.1:8412/pull/3866
```

Choose a port yourself with `--port`, and keep the browser closed with `--no-open`.

Servers of one repository share one mirror, so only the first clones.
A further pull request took about 8 s to reach its `Serving` line on the 1.2 GB
repository above and about 7 s on `pallets/click`, and one already cached about 2 s on
`pallets/click` (measured 2026-11-02).

## Staying Current

The page shows how old the record is and which account read it
(`Fetched 3 min ago by your-login`). A record is current for a minute and then stale,
when the page adds `may be out of date`. A stale record refreshes when the server starts
and when a stale page becomes visible, and a stale page offers **Refresh**. The row at
the foot of the navigation pane says when the mirror was last fetched; click it to
refresh now.

A refresh never moves the page under you.
When a pull request’s head moves, the conversation and checks update in place, while the
diff and the code stay as they were.
The page says `This page's code is …, not the pull request's head …` with **Switch to
the head**, Files changed offers **Show the newer changes**, and the row at the foot of
the navigation pane offers **Switch**.

## Offline

A cached pull request opens with no network: the page, Files changed, and the code all
read from the cache.
The status line adds `The last refresh failed:` and the reason, the row at the foot of
the navigation pane reads `Refresh failed · fetched …`, and **Refresh** tries again.
A pull request or repository you have not opened before needs the network.

## From a Terminal or an Agent

Everything the page shows is available without a browser, a port, or a server left
running:

```shell
URL=https://github.com/owner/repo/pull/123

metab "$URL" --no-serve                      # clone or reuse, and refresh the record
metab "$URL" --show /pull/123                # kind, views, and counts
metab "$URL" --show /pull/123/files          # the same, with the comparison route
metab "$URL" --show README.md                # one file at the head
metab "$URL" --api '/api/plugin/github/pull?number=123'   # the whole record, and comparison_route
```

Issue the record’s `comparison_route` with `--api` to get the diff as data.
[The command-line guide](command-line.md#pull-requests) is the reference, with worked
examples.

## Trust

A pull request’s code and text are untrusted and inert, whatever the repository: nothing
in them runs, and they cannot make the page load anything from another site.
The [security policy](../SECURITY.md#content-trust-model) has the details.

## What It Does Not Do Yet

- **No list of a repository’s pull requests, and no Pulls tab.** Open each one by its
  URL.
- **No pull requests from a served checkout.** `metab <checkout>` serves none.
  Use the pull request’s URL with [`--checkout`](#beside-a-checkout) instead.
- **No inline comments on the diff.** They are listed under **Review comments** on the
  Conversation tab.
- **No writing to GitHub.** Comment, approve, and merge on GitHub through **View on
  GitHub**.
- **Only github.com.** A pull-request URL on any other host is read as a Git address and
  fails.

[The Pulls tab plan](project/specs/active/plan-2026-10-01-github-pulls-tab.md) designs
the list and pull requests on a checkout.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
