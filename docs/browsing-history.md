# Browsing History

The Commits tab shows a repository’s history as a commit graph.
Each commit opens at its own address with its summary and its diff, and the same change
sets are available from a terminal with `--diff`.

![The Commits tab with a commit’s summary and diff](../images/screenshot-commits.jpg)

Reading history needs Git; [installation](installation.md#git-and-github-setup) says
which tools each feature needs.

## The Commits Tab

Choose **Commits** beside Files and Pulls, or press `H`. The tab appears when the served
folder is the root of a Git repository or of a linked worktree, and on any repository
opened by its URL. A folder inside a repository has no Commits tab, because history
covers files outside what that folder serves.

The row under the tabs, the same one Files has, names the branch, tag, or commit both
tabs show, and choosing another there changes both
([Branches and Tags of a Repository URL](#branches-and-tags-of-a-repository-url) and
[of a Local Checkout](#branches-and-tags-of-a-local-checkout)). The graph lists, newest
first in topological order:

- **For a folder’s working tree:** the commits reachable from `HEAD`, its upstream, and
  the trunk branches `main` and `master`, locally and on `origin`.
- **For a branch, tag, or commit chosen in that row, and for a repository URL:** the
  history of that commit.

Each row is the graph, the commit’s branch and tag chips, its subject, its author, and
its age. The header counts the commits and says when the first one was made.
More history loads as you scroll.
Hover a row to see a summary card with the commit’s change counts.

Switching to Commits selects the newest commit.
Click a row, or move with `J` and `K` or the arrow keys, to select another; Enter and
Space select the focused row.
The selected commit opens in the main pane, and the address becomes that commit’s page.

When you come back to Commits after `HEAD` has moved, as after a checkout or a commit,
the graph reloads. If branches move while you scroll an open list, the list says
**History changed since this list loaded.** and offers **Refresh**.

## A Commit’s Page

Every commit has an address, `/commit/<id>`, with its full 40- or 64-character ID. Share
or bookmark it to come back to that commit; a short ID or a branch name in the address
shows **This address needs the full commit ID.** instead.

The page begins with the commit’s summary, laid out as a pull request’s header is:

- the subject
- the author, with a person icon where a pull request shows the author’s avatar
- the short ID, its first seven characters, as GitHub shows them, with a copy control
  for the full ID, and the commit’s branches and tags
- “Committed” and the age
- the **Diff summary**, on every commit, one file or many: the files changed, counted by
  status, and the lines added and deleted; it starts collapsed and opens into the tree
  of changed files, where a file takes you to its diff
- the rest of the commit message, when there is more than a subject, as Markdown, as a
  pull request’s description is: wrapped lines join into paragraphs, `-` and `*` lines
  are lists, and indented or fenced code stays code; trailers such as `Signed-off-by:`
  follow as written, one per line

Below it is the diff against the commit’s first parent, one section per file with its
`+N` and `−N` counts.
Click a file’s bar to collapse it.
The diff draws **Split** or **Unified**; press `L` or use the layout control to switch,
and a pane too narrow for Split draws Unified until there is room.
**Diff** | **Excerpt** | **Full** chooses how much of the comparison to show.
Press `N` to switch between Diff and Excerpt.
See [Comparison View](reviewing-pull-requests.md#comparison-view).
A commit that changes more than one file has a **File type** menu ahead of the
comparison and layout choosers, the same menu as the Files tab’s, which counts the
commit’s changed files by group, family, and extension.
Choose types in it (`Y` opens it) to show only the changed files of those types; the
toolbar then says how many of the commit’s files it shows, with **Clear**. A renamed
file counts under its old type and its new one, the summary at the top still describes
the whole commit, and a file you jump to from it that the choice hides shows every type
again. Large files load as you reach them, and a commit that changes more files than the
page lists says that its diff is bounded.

On a repository opened by its URL, each file’s bar also offers **View file**, which
opens the file the commit made, at the commit, switching the served commit first when
the page shows another; a deleted file has none.

A repository URL serves a mirror of the repository (see
[the command line](command-line.md#serving-a-git-source)), which holds what its last
fetch brought. A commit address the mirror does not have yet starts a fetch when the
mirror is older than its freshness window, and the page opens the commit if the fetch
brings it. Otherwise the page says the commit is not in the mirror and offers **Retry**.

## Branches and Tags of a Repository URL

A repository opened by its URL is pinned to one commit, its default branch’s unless the
URL names another. The row directly below the Files and Commits tabs names the branch,
tag, pull request, or commit.
Click the branch or tag chip for its actions.
Click the separate down chevron beside it, or press `W`, to choose another revision.

The chooser lists every one of the mirror’s branches or tags.
The default branch is first, and the rest are newest first, by the date of each one’s
last commit, which its row shows as an age.
The filter box narrows either list by name.
Choosing one serves it and reloads the page on the same file or folder when the new
commit has it, or at the root when it does not.
Chosen on the Commits tab, it reloads the page on Commits, at the newest commit of the
new history. The switch lasts until the server stops.

The foot of the navigation pane says when the mirror was last fetched from its origin.
**Refresh**, the circular arrow at the top of the navigation pane, fetches it now and
then reads the files and history again, what is on screen first.
A branch or tag is shown as the mirror last fetched it, as github.com shows a branch:
when a fetch moves the served branch, the page follows it to the new commit by itself,
on the same file or folder when the new commit has it, or at the root when it does not.
A commit you opened by its ID stays put, also when it is a branch’s tip; when that
branch moves on, the foot offers its new commit with **Switch**.

## Branches and Tags of a Local Checkout

A folder that is a repository’s root opens on **Working tree**, the files on disk with
whatever you have edited, staged, or not yet added.
The row under the Files and Commits tabs says so, then names the branch the files are
on, as in “Working tree · main”, or the commit when `HEAD` is detached.
If you, or an agent, check out another branch in a terminal, the row names the new
branch within about a second, without a reload.
Click the branch’s chip for its actions.
Click the chevron in that row or press `W` to browse the other branches and tags.
The list has four tabs, and opens on the one that holds what the page shows.

- **Working tree** is the first tab, and the only one that shows your live files.
  It has one entry, which names the branch your files are on and the folder’s path.
  Choosing it shows the files on disk; it never checks anything out, so the branch is
  whichever one you have checked out.
  From a page that shows a branch or tag, clicking the tab itself, or pressing Enter or
  Space on it, does the same in one step.
  Arrow keys along the tabs only show each tab’s list, so they never leave the page you
  are on.
- **Branches** are the checkout’s own, with the one you have checked out first and
  marked “checked out”.
  **Tags** are its tags.
  **Remotes** are its remote-tracking branches, such as `origin/main`. Each list holds
  every one, newest first by its last commit.
- **The origin’s branches and tags are as Metabrowser last fetched them,** when the
  checkout’s `origin` is an `https` address.
  Metabrowser keeps a store of its own beside the checkout for them, which borrows the
  checkout’s objects and holds only what the checkout lacks, and fetches it in the
  background while the folder is served, so `origin/main` there is where the origin is,
  not where your own last `git fetch` left it.
  The origin’s default branch is first and marked “default”.
  A branch there is marked “yours differs” when your checkout’s own `origin/<branch>` is
  at another commit, which is a branch you have not fetched since it moved, or have
  pushed since Metabrowser last fetched, and “not in checkout” when you have never
  fetched it; hover over the row for your commit and which of the two was committed
  later. On a branch’s or tag’s page, the row at the foot of the navigation pane says
  when the origin was last fetched, and **Refresh** at the top of the navigation pane
  fetches it again; it fetches Metabrowser’s store, never your checkout.
  The working tree’s page has no such row.
  **Refresh** there reads your files and history again first, and then fetches the
  origin in the background, so Remotes and Tags are current the next time you look; an
  open list updates in place.
  A line under the list says when it was fetched, or why it was not: an origin that
  needs a password Metabrowser does not have is listed from your checkout instead, and
  nothing asks for one.
  Another remote’s branches, and a tag only your checkout has, are read from the
  checkout.
- Choosing a branch or tag shows its last commit, read from the repository’s Git
  objects. The row then names it alone, as in “main”, and the navigation header, still
  the folder’s name, names its full commit when you hover over it.
  This includes the checked-out branch: choosing it in Branches shows what is committed,
  without your uncommitted changes, so its row reads “main” where the working tree’s
  reads “Working tree · main”.
  The **Working tree** tab is the way back to them.
  A branch’s page follows its branch: when you commit to it, the page goes to the new
  commit by itself within a few seconds.
  A tag’s page follows its tag the same way, and a commit opened by its ID stays put.

Nothing is checked out, fetched, or written.
Your working tree, your index, and `HEAD` stay exactly as they are, so it is safe with
work in progress, and Git commands in a terminal are unaffected.

A branch or tag is shown the way a repository opened by its URL is.
It is read-only and runs under the untrusted profile, whatever the folder was opened
with, because another branch holds whatever a fetch brought: Markdown is rendered inert
and an HTML file shows only its source.
It has no Recent tab, live updates, ignored files, or Pulls tab; those belong to the
working tree, which gets the folder’s own profile back.

The choice is the server’s, so it holds for every tab until you choose **Working tree**
again or the server stops: Files shows the branch’s files and Commits its history,
whichever tab you chose it on.
`metab <folder>` starts on the working tree, and `metab <folder> --ref <name>` starts on
that branch or tag
([the command line](command-line.md#a-branch-or-tag-of-a-local-checkout)). A tab left on
the other one says so and offers **Reload page**.

A branch or tag you chose follows that branch or tag.
Metabrowser fetches nothing into a checkout, so your own branches, and another remote’s,
are only as new as your own Git commands left them; when you commit on the branch shown,
or your own `git fetch` moves `origin/main`, the page goes to the new commit by itself
within a few seconds, on the same file or folder when the new commit has it, or at the
root when it does not.
It reads the repository’s refs to find that out and fetches nothing into your checkout.
When you delete the branch shown, the page keeps its last commit, and the row at the
foot of the navigation pane says the branch no longer exists.
Where Metabrowser keeps a store of the origin, as above, a page shown on such a branch
also keeps that store fetched, quietly, about once a freshness window.
One of the origin’s branches follows the origin by itself, as a repository opened by its
URL does. A commit you opened by its ID stays that commit, even while it is the tip of
the branch you came from, and **Working tree** is always the files on disk.
The button follows the folder you opened: it is there when that folder is a repository’s
root, as the Commits tab is.

Showing a branch or tag needs a Git as recent as cloning does
([installation](installation.md#git-and-github-setup)), and in a partial clone, one made
with `git clone --filter`, a newer one still.
With an older one the list says which release it needs, and the working tree and its
Commits tab work as before.

## Diffs from a Terminal

`--diff` prints a change set of a local repository without a browser:

```shell
metab ./repo --diff main..feature      # from main to feature, directly
metab ./repo --diff main...feature     # from their merge base, as a pull request does
metab ./repo --diff <revision>         # one commit against its first parent
metab ./repo --diff changes.patch      # a .patch or .diff file under ROOT
```

The text report names the comparison, its two ends, the totals, and one line per file:

```text
comparison git:45fa118cac607080 (first_parent)
left  f11ba44cc886f0446daf7757727515e276d7a96c
right 60429cd1ba18245a840d3e7460a0f4777ce58544
files 1  +8 -7  (exact)
M    docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md  [+8 -7]
```

- **`--format json`** prints the whole change set as a
  [File Diff Format](project/architecture/file-diff-format/file-diff-format.md)
  document, the same data the page draws.
- **`--diff-patch PATH`** prints one changed file’s hunks.
- **`--diff-check`** rebuilds the target tree from the base tree and the change set, and
  compares the two tree hashes.
  It prints both and `apply: clean`, or `apply: MISMATCH` with exit status 1. It needs a
  comparison of two commits, not a patch file.

A spec that does not resolve, or a file name that is not in the comparison, prints a
`diff error:` line and exits with status 2.

`--diff` reads a local checkout only.
For a repository opened by its URL, or for any range from a script, issue the comparison
route that the page itself uses:

```shell
metab https://github.com/owner/repo --api '/api/plugin/diff/comparison?left=v1.0&right=origin/main'
metab ./repo --api '/api/plugin/diff/comparison?left=main&right=feature&base_policy=merge_base'
metab ./repo --api '/api/plugin/diff/comparison?revision=HEAD&types=.md,.py'  # only these types
metab ./repo --api '/api/plugin/diff/comparison?revision=HEAD&view=types'      # counts by type
```

In a mirror, a branch is named as its origin’s, `origin/<branch>`.

The history the tab draws is also data:

```shell
metab ./repo --api '/api/git/log?limit=20'           # the newest 20 commits
metab ./repo --api '/api/git/log?scope=all'          # every branch and tag
metab ./repo --api /api/git/refs                     # branches and tags
metab ./repo --show /commit/<revision>               # a commit's change set
metab ./repo --show /commit/<revision>/README.md     # one file in it
```

`--show` accepts any revision Git resolves, such as `HEAD~2` or a tag; the page’s
address takes a full commit ID. [The command-line guide](command-line.md) has every
option.

## What It Does Not Do Yet

- **Uncommitted changes:** the Commits tab shows commits only.
  Working-tree status and diffs are planned in the
  [Git status plan](project/specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md).
- **Ranges in the browser:** a page shows one commit against its first parent, or a pull
  request’s Changes. A range of commits is a terminal command.
- **A folder inside a repository:** it has no Commits tab and no branch button, which
  belong to a repository’s root.
  Opening such a folder at its repository’s root is planned in
  [Open Modes](project/architecture/arch-open-modes.md).
- **Pull requests on a branch of a local checkout:** the Pulls tab belongs to the
  working tree.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
