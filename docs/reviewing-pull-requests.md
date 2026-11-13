# Reviewing Pull Requests

Metabrowser reviews GitHub pull requests from a repository URL, an existing checkout, or
a pull-request URL. The Pulls tab lists the repository’s pull requests; each page shows
the description, conversation, reviews, checks, and changes.
Records and Git objects are cached locally, so previously fetched data remains readable
offline while those objects are available.

To fetch new GitHub data, install a current GitHub CLI (`gh`) release and sign in.
Acquiring or refreshing Git objects also needs Git.
[Git and GitHub setup](installation.md#git-and-github-setup) gives the installation
commands and the sign-in check.
Local file browsing and cached PR metadata do not require `gh`.

## Open a Repository

Point `metab` at its GitHub URL or a checkout you already have:

```shell
metab https://github.com/owner/repo
metab ~/src/repo
metab ~/src/repo-worktree
metab ~/src/repo/src
```

A repository URL opens a managed copy in the cache, pinned to a commit.
A local path serves that folder, including its local changes.
The main checkout, a linked worktree, and a subdirectory can all show **Pulls** when
Metabrowser recognizes a github.com `origin` and can read the checkout’s `HEAD`. On a
fork, the list belongs to `origin`, usually the fork; the tab names the repository.
A folder without a recognized GitHub repository has no Pulls tab.

Choose **Pulls** beside Files and Commits.
It starts on **Open**; the filters are **Open**, **Closed**, and **All**. Closed
includes merged pull requests.
Small tallies show each filter’s total when the catalog knows it.
Switching back to Files or Pulls restores that tab’s last selection; switching to
Commits selects the newest commit.
The list shows the newest pull requests first, with their open, draft, merged, or closed
state. The status gives the repository’s total and name, with the number in bold.

Metabrowser caches a lightweight catalog of titles, authors, states, branches, and dates
in the background, publishing each page as it arrives and resuming unfinished work.
It initially displays up to 500 matching pull requests.
When more exist, **Showing last 500** appears below the total.
Scrolling toward the end loads the next window for the current filter.
**Fetch more** advances the list explicitly.
After initial Files work is idle, Metabrowser prepares lightweight PR headers and
descriptions in both managed repositories and existing checkouts.
The current filter warms first, visible rows take priority as you scroll, and
preparation continues through the cached catalog.
Small transport batches limit in-flight work without capping total coverage.
Busy preparation retries while demand remains; hiding the browser or losing the network
pauses the unfinished pass, and returning resumes it.
Validated descriptions persist locally across later batches and server restarts.
A changed summary can show its older description while new metadata is prepared.
A selected refresh takes priority.
Selecting a row shows its prepared description when available.
For a missing full record, the selected refresh still verifies a fresh description and
completes the record.
The background step never fetches comments, reviews, checks, or Git objects.
Diffs are generated from the Git objects in the cache.
Mounted content creates lazy author images; the browser controls when nearby images load
and caches their bytes.
Cached metadata remains readable when images cannot load.
After a metadata projection change, the next accepted catalog refresh enriches existing
rows through the same resumable background scan; cached rows and counts remain
available. A detail record whose metadata projection changed revalidates its
representations once on an accepted refresh; later refreshes reuse conditional responses
as usual. A failed refresh retains the displayed record.

Click a PR row to open the PR and toggle its changed files.
Right expands the tree, and Left collapses it.
The tree shows cached files immediately when available and automatically lists them when
needed. A list that GitHub takes a while to return is offered on the tree’s line as
**Show N files** rather than drawn by itself, and so are its later pages (**Show N more
files**) and a refresh that changes a list already shown, which floats over the tree’s
top, so the rows below never move while you are not interacting with the list.
Selecting a file opens **Changes** at that file.
Use J, K, or the up and down arrows to walk rows without changing which trees are
expanded. Enter opens the focused PR. Space expands or collapses its changed files in
place. Keyboard walks keep focus in the tree and replace one browser history entry, so
Back leaves the walk in one step.
The selected file follows the diff as you scroll; Back and Forward restore the selected
file and reading position.

A served folder can show Pulls and Conversation without a comparison store.
Opening **Changes** prepares a missing comparison automatically.
Metabrowser reuses a healthy cached store or creates one that borrows the checkout’s
objects and fetches what it lacks into the cache.
Git runs in the store and leaves the served folder and Commits tab on your checkout.
If preparation fails, **Changes** reports the reason and offers a retry.

Only **Changes** creates that store.
The first one fetches every branch and tag the checkout lacks, and once it exists each
later refresh of a PR fetches that PR into it, so reading Conversation never starts that
cost: a Conversation-only session runs no Git at all.
The trade-off is that the first **Changes** on a checkout without a store waits for it.
Once the checkout has a store, from an earlier **Changes** in this session or another,
Conversation can prepare the comparison of a PR record fetched within the last minute in
the background. That work fetches only the PR’s head and base, says nothing on
Conversation, and gives way to anything you ask for: opening **Changes** takes it over,
and any other refresh stops it.
See [Beside a Checkout](#beside-a-checkout) for the URL-based borrowing workflow.

## Keep Pulls Up to Date

Metabrowser watches the repository while Pulls or a PR page is visible.
New PRs, state changes, and edits to titles or other list metadata arrive in the
background. The list catches up when you return to it.

The connection status is below the Pulls tally.
Cached PRs remain readable during a disconnection, and Metabrowser retries when the
network returns. Use **Reload** to request a new check.
If the status asks you to install GitHub CLI, sign in, or check repository access,
follow its instructions and choose **Reload**. See
[Git and GitHub Setup](installation.md#git-and-github-setup).

## Native Stack Navigation

With the optional [gh-stack extension](installation.md#git-and-github-setup), a list row
shows a Layers icon and position, such as **5/23**, when native GitHub metadata names
its membership. The PR page uses the same position as a menu trigger.
Open it for the stack number and members ordered from stack top to base, with each
member’s title, ordinal, and PR number.
Titles come from the matching local catalog; a missing title falls back to the PR
number.
Press `N` for the next member toward the stack’s top and `P` for the previous one
toward its base; Shift makes no difference.
Help lists both shortcuts, and editors or open dialogs keep their normal keys.
Moving between members keeps the current PR tab selected and clears the previous PR’s
file selection.
Expanded trees retain their keyboard position; the current-file highlight
belongs to the PR being viewed.

Stack metadata refreshes as one shared repository snapshot, independently of PR details.
Missing tooling, unavailable APIs, or a partial snapshot do not prevent normal PR
reading and do not establish that a PR is unstacked.
Matching cached membership remains usable.
Metabrowser reads stack metadata; it does not create or change GitHub or local stacks.

## Review a Pull Request

```shell
metab https://github.com/owner/repo/pull/123
```

`metab` prints the address it serves and opens your browser there.
Press Ctrl-C in that terminal to stop it.

Without an existing store or `--checkout`, a repository or pull-request URL first clones
the whole repository into your cache, with progress on stderr.
A pull-request URL then reads that PR:

```text
cloning https://github.com/pallets/click into ~/.cache/metabrowser
cloned https://github.com/pallets/click in 4.9 s (5.3 MiB); starting the server
Serving https://github.com/pallets/click at http://127.0.0.1:8411/pull/3866
```

Later runs reuse that clone and say so
(`using the clone of … cached in ~/.cache/metabrowser, fetched 3 hours ago`).

GitHub URLs ending in `/pull/123/files` or `/pull/123/checks` open **Changes** or
**Checks** at the matching local address.
The `Serving` line prints the address.
A GitHub `/pull/123/commits` URL opens **Conversation**, where commit summaries appear
with the discussion.

## What the Page Shows

The header has the title, state, branches, labels, and dates.
PR numbers use dark text, usernames use bold normal text ink at the surface’s normal
size, and branch names use smaller ref chips, consistently with the Pulls list and Git
history. Hover or focus a copyable branch chip to reveal its copy control; it copies the
full branch name. The author’s small circular avatar appears beside the username when
available. Full metadata uses relative ages such as “2h ago”, “just now”, or “in 2h”;
condensed navigation keeps short ages.
An initially empty page shows gray pulsing loading blocks.
When switching from useful content, that content stays visible until the new description
or an actionable failure is ready.
The description can appear while comments, reviews, checks, and changes are still
loading; those sections show gray pulsing blocks after a moment, and nothing spins.
A visible PR opened from a row or a direct link fetches its record on the first visit.
A cached full page renders from disk at once and stays as it is while it refreshes in
the background: no spinner covers it, and only the line saying when it was fetched
breathes gently until the refresh lands.
A row’s changed-files tree does the same with its folder and file names, and the Pulls
list with its “Updated” line.
**View on GitHub** opens the pull request on github.com with a leading GitHub brand
icon. External GitHub links in conversation text carry a destination icon; an unknown
issue or PR state uses a neutral entity icon.
The page has three tabs.

- **Conversation** shows the description, followed by comments, reviews, and commit
  summaries. Commits that arrive after the page has painted are added after what it
  shows, so nothing you are reading moves; shown again with its commits known, as after
  another tab, the conversation follows GitHub’s order.
  A short commit ID opens the exact commit on GitHub.
  Cached timelines are readable offline.
  **Review comments** lists inline review comments with their files and diff hunks.
- **Changes** shows the comparison from the merge base to the head, split or unified.
  Markdown changes open in **Rendered** when Metabrowser can map the Git hunks to the
  document. **Source** keeps the exact patch and is used automatically for the files
  [Rendered Markdown in Changes](#rendered-markdown-in-changes) lists.
  The changed-files tree in Pulls navigates this comparison.
- **Checks** summarizes check runs and status contexts, with links to their details.
  Open or share it directly at `/pull/<n>/checks`.

The code controls depend on how the repository was opened:

| Opened with | Code controls |
| --- | --- |
| A repository or pull-request URL, with or without `--checkout` | **Browse code** opens the pinned code; if another branch or PR is pinned, it first switches to the selected PR’s head. A newer head is selected separately with **Switch to the head** when offered. A changed file offers **View file** at the head and **View at base** at the merge base where that side exists. |
| A checkout or subdirectory path | Files and Commits continue to show the local checkout. The PR page has no **Browse code**: the working files may differ from the PR commits. Once Changes are fetched, **View file** and **View at base** open each side from the cache. |

**View file** and **View at base** never move the server’s pin.
A side the page does not show opens on its own revision page, at that exact commit, in
your theme; the link keeps working after the pull request moves on, for its last 16
comparisons.
On a managed source pinned at the head, **View file** opens in the app’s own
viewer. **Browse code** returns to the PR head, or **Switch to the head** does so when
the page shows that offer.
A pin is shared by the pages of that server.

### Rendered Markdown in Changes

**Rendered** shows each changed block of a Markdown file as removed and added, with the
changed words marked.
A changed list item or quoted paragraph is shown alone, and long runs of unchanged
blocks fold. A file’s **Rendered** | **Source** chooser switches between the two.

Rendered shows what a change does to the document as it reads.
A change that does not show in the rendered document appears only in **Source**, and
Rendered does not mark it: a link or image destination or title, a link whose label now
points somewhere else, an image’s alt text, an HTML comment, attribute syntax such as
`{#name}`, a code fence’s language, or only whitespace and line wrapping.
A block that changed only in those ways reads as unchanged.
One whose destination, title, alt text, comment, attribute, or fence language changed is
never folded away with the unchanged blocks around it, but one whose only change is
whitespace or line wrapping can stay inside a fold.
An added code block’s fence text other than exactly one language name, such as `python`
or `mermaid`, likewise appears only in Source.

These files open in **Source**:

- files with raw HTML, including inline tags such as `<br>` and blocks such as
  `<details>` (HTML comments are allowed),
- task lists (`- [ ]` items) and footnotes,
- files past the rendered view’s limits, such as more than 48 KiB of Markdown across the
  two sides.

Rendered differs from the file’s own document view in two ways: math (`$…$`) and Mermaid
diagrams show as their source text, and code blocks are not highlighted.

## Beside a Checkout

If you already have the repository checked out, name that checkout once.
The managed mirror borrows its objects instead of copying them, reducing the time and
disk space needed when the checkout already holds most of the repository:

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

This flag chooses a managed, pinned view of the URL; `metab ~/src/repo` keeps serving
your working folder instead.
Both can review pull requests.

Only a checkout you name or have previously named lends.
A healthy existing store is reused, including an overlay with its remembered lender.
On a cache miss without a named lender, `metab <url>` clones a full mirror.
If the current directory is a checkout of that source, it prints the command that would
have borrowed instead; it never infers permission to borrow from that directory.
A directory you merely stand in can be made to look like a checkout of anything.

Three things are worth knowing:

- **A shallow checkout may not settle the comparison at once.** If its history stops
  before the pull request’s merge base, `metab` fetches more history into the mirror.
  Until that succeeds, and offline, **Changes** says the history is too shallow to know
  what the pull request changed, rather than show a guess.
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

A clone that fails stops the command with an `Error:` line and exit status 1. When
opening a PR URL, a pull request that cannot be read does not: `metab` serves the
default branch, exits 0 in the one-shot modes, and says why on the `Pull request:` line.
The page gives the reason and offers **Fetch** to retry the missing record.
Once the cause is fixed, use that action or run the command again.

| Name | What it means | What to do |
| --- | --- | --- |
| `gh_missing` | `gh` is not on `PATH` | Install `gh` |
| `gh_too_old` | `gh` is older than the version above | Upgrade `gh` |
| `not_logged_in` | `gh` is not signed in to github.com | Run `gh auth login` |
| `not_found_or_private` | It does not exist, or the account cannot read it; GitHub does not say which | Check the URL, and that `gh auth status` names an account with access |
| `too_large` | The first clone is over the limit | See [Large Repositories](#large-repositories) |
| `lender_missing` | The checkout this mirror borrows from has moved or gone, or can no longer lend: it borrows objects itself, its objects cannot be read, or it holds another repository now | Run the command again with `--checkout <new path>` |
| `network_unreachable`, `network_error` | GitHub could not be reached, by Git or by `gh` | See [Offline](#offline) |

The conversation can remain available when the comparison cannot be read:

| Name | What it means | What to do |
| --- | --- | --- |
| `no_store` | A served folder has a PR record but no store for its comparison | Open **Changes** to prepare the comparison |
| `base_uncertain` | Shallow history does not establish the merge base | **Refresh** with the network available to fetch more history |
| `commits_unavailable`, `object_unavailable` | A commit or object needed for the comparison is missing or unreadable | **Refresh** can try to recover missing objects; it may still fail if the origin no longer serves them |
| `object_corrupt` | Read bytes do not match their Git object ID | Repair the damaged cache or use a healthy lender, then **Refresh**; Metabrowser does not overwrite the checkout’s objects |
| `comparison_timeout` | Checking the comparison took too long | **Refresh** to try again |
| `comparison_too_large` | Checking or repairing the comparison exceeded a bound | Use **View on GitHub** if the local comparison remains unavailable |

Reattach a moved lender with `--checkout <new path>`, or name another healthy checkout
of the repository. An unreadable lender must be made readable or replaced before the
store can use it again.
Beside a served folder, comparison preparation reuses a healthy store or borrows from
the checkout. Partial clones and checkouts that borrow objects themselves cannot lend.
Metabrowser reports a borrowing refusal in **Changes** and never falls back to a full
clone. The URL-based `--checkout` command has its own
[documented fallback cases](command-line.md#beside-a-checkout).

A managed source whose cached pinned tree is missing can fail before the server starts.
It reports an error without a traceback or automatic replacement clone; the page’s
Refresh is unavailable until the source can open.
Repair the affected cache or lender before restarting.

If a changed-file refresh cannot admit the application cache, its error remains visible
and automatic retries pause in the current server.
The rejected refresh does not contact GitHub or write into the refused cache; correct
the reported cache problem before retrying.
A provider rate-limit hold remains in force without replacing a newer cache error with
an older outcome. Work admitted before the cache refusal can still finish in another
process.
[The source reference](project/architecture/arch-repository-sources-and-provider-mirrors.md#pull-requests-beside-a-checkout)
describes the recovery limits.

[The command-line guide](command-line.md#pull-requests) lists the record’s failure
names.

## Find a Pull Request With Quick Search

Press `/` or `T` to open Quick Search.
Type `#` to see recent PRs across all states.
Keep typing digits, such as `#30`, to complete PR numbers, with the exact number first.
Type `#` followed by words to match PR titles.
Ordinary text continues to match files and PR titles.
A result shows its title, number, and state.
Press Enter to open its Conversation tab.

The catalog grows in the background, and cached results are available offline.
Number completions cover the whole cached catalog.
Title searches check up to the 50,000 newest entries.

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

One server can review several pull requests through Pulls or `/pull/<n>`. Opening a PR
page does not switch the code being served.
A managed server has one pin, shared by its pages; use its code controls to switch it.
Run separate servers when you want different PR heads available for code browsing at
once. A served folder keeps its working files throughout.
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

The page shows when GitHub CLI fetched the record, for example
`Fetched 3 min ago via GitHub CLI`. A description preview reports when GitHub CLI
fetched the description while discussion and checks load.
A record is current for a minute, and for as long after that as the repository’s list of
pull requests, which Metabrowser rescans about once a minute while its Pulls tab or the
page is visible, says GitHub has not changed it: the page then says
`Checked just now · fetched 3 h ago via GitHub CLI`. That list does not track checks,
statuses, or mergeability, so while you have an open pull request’s page open, those are
read again on their own each minute: a check that starts, a re-run, or a conflict a
newer base commit made shows within about a minute.
The Pulls tab also asks Metabrowser to read, behind you and within hourly limits, the
pull requests you are likely to open next: the rows around the one you opened and the
top of the list, when they are missing or changed, and their changed files.
It stops while less than a quarter of your GitHub rate limit remains.
A managed PR URL refreshes a stale record when the server starts.
A visible stale PR page refreshes it too: at once when you clicked its row, after a
short pause when you reached it by a key or an address, and again each time it goes
stale while you keep it open, at most once a minute.
It keeps showing the plain age meanwhile, never a note that it may be out of date.
The page names a problem only when it cannot refresh: `Offline`,
`GitHub rate limit · next check at` a time, after which it tries again by itself, or the
last failure, with **Refresh**. It tries a failure again once a minute while you keep it
open, except one you must fix, such as GitHub CLI missing or signed out, which waits for
your **Refresh**. **Refresh** is available after a failed refresh or an unavailable
comparison, on a stale record whose automatic refresh did not run, and on **Changes**
even while the record is current, but not while GitHub’s rate limit holds the page, as
the Pulls tab’s **Reload** waits too.
The time the page names is when it asks again: not before GitHub’s reset, and not within
a minute of the attempt the limit refused.
A managed source’s row at the foot of the navigation pane separately reports when its
Git store was fetched and can refresh it.

A refresh does not select a newer comparison for you.
When the list of pull requests shows the head moved, **Changes** says
`New commits were pushed; updating.` over the diff it keeps.
When the PR head advances, the conversation and checks update while the displayed diff
stays on its original commits.
Choose **Show the newer changes** to move the diff.
On a managed source the code pin also stays put; **Switch to the head** or the footer’s
**Switch** moves it when offered.
A folder’s working files are never switched.

If a displayed comparison has missing objects, its explicit **Refresh** attempts to
recover the objects observed missing from that comparison.
A successful repair reloads the same comparison and preserves your reading position,
even when the PR’s head has advanced.
A failed repair leaves the displayed selection and cached record in place and reports
the reason. It does not automatically select the newer changes.
Reading a cached comparison starts no fetch, and automatic metadata refresh is not an
object-repair scan.

An old comparison link can remain readable after a server restart without being eligible
for network repair: repair needs a comparison associated with that PR in the running
session. Open the current PR comparison before retrying in that case.

## Offline

Cached records, lists, and comparisons remain readable while their required objects are
available. A borrowed store also needs its lender to remain readable.
A failed refresh reports its reason and retains the cached data; **Refresh** tries
again. A PR record, list page, or comparison whose data has not been fetched needs the
network.

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

A pull request’s text and diff are untrusted and inert, including beside a checkout:
nothing in them runs, and they cannot make the page load anything from another site.
Repository URLs use the untrusted profile.
Other files served from a local folder keep that folder’s content-trust settings;
reviewing a PR does not change them.
The [security policy](../SECURITY.md#content-trust-model) has the details.

## What It Does Not Do Yet

- **No inline comments on the diff.** They are listed under **Review comments** on the
  Conversation tab.
- **No writing to GitHub.** Comment, approve, and merge on GitHub through **View on
  GitHub**.
- **Only github.com.** A pull-request URL on any other host is read as a Git address and
  fails.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
