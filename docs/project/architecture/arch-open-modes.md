# Open Modes

**Status:** Designed and partly built.
The owner settled the model on 2026-11-18: [Decisions](#decisions) lists each answer,
and [Not Decided](#not-decided) what is still open.
Built on `main`: mirror mode; a folder served as the exact path named, with history only
when that path is a repository’s root; a repository folder’s revision views with their
chooser and `--ref`; recent targets kept by `metab`, behind File > Open Recent; and File
\> Open URL…, without its offer of a known checkout.
The mode indicator is built too, as three marks, one for each kind of root
([The Indicator and View on GitHub](#the-indicator-and-view-on-github)). Not built:
resolving a path to its repository’s root, Pulls and the toggle on a folder’s revision,
and Open URL…’s offer of a checkout.
[Implementation Status](#implementation-status) names the pull request or bead for each
part.

Whatever a reader opens, a folder, a file, or a URL, Metabrowser serves a **root** in
one of three **modes**: a plain folder, a repository folder, or a mirror.
The mode says whose files the pages show, the reader’s own as they are on disk or
Metabrowser’s cached copy of a repository, and so what can change under the reader and
what the content is trusted to do.

This document holds the model: the words, how a target resolves to a root, what each
mode and view can do, what is never written, and what must hold for the model to be
safe. The mechanisms are in the documents it links: how a view is held and switched in
[Source Sessions and Pins](arch-source-sessions-and-pins.md), how Git is run in
[Git Reading and History](arch-git.md), and how a mirror is filled in
[Mirror Acquisition and Refresh](arch-mirror-acquisition-and-refresh.md).

## Vocabulary

- **Target:** what the reader names to open: a folder, a file, or a URL.
- **Root:** what one server serves, and what the app windows that show it belong to: a
  folder, or a repository’s address.
  It is called the **open root** where it must be told apart from the path the reader
  named.
- **Mode:** how a root is open: plain folder, repository folder, or mirror.
  Nothing done in a page changes it.
- **Folder mode:** the two folder modes together, which a recent target’s `mode` writes
  as one value, `folder`; its `git` and the `kind` of `GET /api/identity` tell them
  apart.
- **View:** what the server shows now: a folder’s working tree, or one revision.
  A repository folder can change its view while it stays open, and its mode stays.
- **Working tree:** the files of a folder as they are on disk now, with whatever is
  modified, untracked, or ignored.
- **Revision:** one commit’s tree, read from Git objects and named by the branch, tag,
  pull request, or commit ID it was resolved from.
  It never changes.
- **Checkout:** a repository’s working tree together with its Git directory, which is
  what the root of a repository folder is.
- **Linked worktree:** a further checkout of one repository, made by `git worktree add`,
  with its own working tree, `HEAD`, and index, and the repository’s shared branches,
  tags, and objects. It opens as a repository folder of its own.
- **Mirror:** a repository opened by its address and read from a
  [store](arch-repository-cache.md#repository-stores), Metabrowser’s own bare copy of it
  in the cache, kept current from its origin.
- **Working directory:** only its operating-system sense, the directory a process runs
  in.

### Standard Terms

The owner decided on 2026-11-18 that these words follow Git’s, and that “worktree” names
only a proper Git worktree.

- **The live files are the “working tree”**, the term `git help glossary` defines and
  `git status` prints.
  “Working directory” keeps its operating-system meaning.
- **Prose writes “linked worktree” or “main worktree” in full**, never “worktree” as a
  short form of “working tree”.

The owner’s first statement of the model called the working tree “the true working
directory”.

## Resolving a Target to a Root

**Not built.** Today a path opens the folder named, and a file the folder that holds it.

A URL opens a mirror, and its root is the repository’s address, whatever branch, pull
request, or file the URL selects inside it.
[The command-line guide](../../command-line.md#what-root-names) says how an argument is
told apart as a URL or a path.

A path opens a folder, by these steps:

1. Resolve symbolic links.
   The walk starts from a folder: the folder named, or the folder that holds the file
   named.
2. Find the nearest enclosing Git repository by asking Git:
   `git rev-parse --show-toplevel`. A `.git` entry in an ancestor is only the cheap test
   of whether to ask.
3. Open the root Git reports when every [guard](#the-guards) holds.
4. Otherwise open the folder named, or for a file the folder that holds it.
5. Show the page at the folder or file the reader named, under whichever root was
   opened.

A root that is the working-tree root of a repository is a **repository folder**. Any
other folder root is a **plain folder**: a folder in no repository, or one served
exactly, below a repository’s root.

### The Guards

The root Git reports is opened only when all of these hold:

| Guard | Why |
| --- | --- |
| Git answers with a root that contains the path and can be read | Git’s own checks decide what a repository is, including its refusal of a repository another user owns. A `.git` that Git refuses names no root |
| That root holds the `.git` entry naming the Git directory Git used: `<root>/.git`, followed if it is a file, is what `git rev-parse --absolute-git-dir` answers | A repository’s own configuration can place its working tree anywhere. With `core.worktree = ../..` in the `.git/config` of an unpacked archive, Git reports the folder above the unpacked archive as the root, and every other guard passes. An ordinary checkout, a nested repository, a linked worktree, and a submodule each hold their own `.git` |
| The root is not the home folder, unless the reader named the home folder itself. The design adds a volume’s root, which the owner was not asked about | A dotfiles repository at the home folder would turn every open into the home folder: a walk and a watch of all of it, and on macOS a privacy prompt for each protected location. A repository at a volume’s root would do the same to the volume |
| The repository does not ignore the path the reader named: `git check-ignore -q` exits 1 for it, a file’s own path where a file was named | A repository does not count an ignored path as its own, so its root is not what the reader named. Any other answer opens the path named: exit 0, which is ignored, and a failure such as exit 128. This also stops the usual dotfiles layout, which ignores everything |
| The server binds loopback only, with no `--host` naming another address | `metab ./docs --host 0.0.0.0` inside a private repository would serve the whole repository to the network |
| `--exact-root` was not given | The reader asked for the folder named and nothing above it |

A guard that fails opens the path named, as step 4 says, and never an error.
The `Serving` line and the page name the root that was opened, so a root above the path
the reader named is never silent.
`--exact-root` is also how to open one part of a large repository without walking and
watching the rest.

### Which Commands Resolve

Only serving, `metab TARGET --present`, and the macOS app resolve a path this way.
Every other mode reads `ROOT` exactly as given, so a script’s answer never depends on
what encloses its argument.

One resolver in `metab` answers for every caller, and a shell never implements the rule
a second time.

- **Asking without serving.** `metab TARGET --present --dry-run --format json` answers
  the open root, whether that root is a repository’s, and the place the reader named,
  and a golden pins its answers.
  `--recent-add` records the root the same resolver answers: today both ask
  `resolve_local_open` in `cli/common.py`, whose body the resolver replaces.
- **The app asks, and then serves exactly.** It starts each server on a root that is
  already resolved, with `--exact-root`, and that includes the servers a restore starts,
  so a saved root is never resolved again.
- **One fixture of resolution cases**, replayed by Python and by the app’s tests, holds
  the two together.

### Edge Cases

Git’s answers below are Git 2.50.1’s, run in scratch repositories on 2026-11-18. The row
for another user’s repository used `GIT_TEST_ASSUME_DIFFERENT_OWNER`, Git’s own switch
for that check, and not a second account.

| Case | What Git answers | What opens |
| --- | --- | --- |
| A nested repository, or a submodule | The nearest one; a submodule is its own root | The nearest repository |
| A linked worktree | The worktree’s own root. Its `HEAD` is its own, and its refs and objects are in the repository’s common directory | The worktree, as a repository folder |
| A bare repository, or a path inside `.git` | “this operation must be run in a work tree” | A plain folder |
| A `.git` Git refuses, such as an empty directory by that name, a repository another user owns, or a Git directory the reader cannot read; or a root the reader cannot read | A failure, or for an unreadable root an answer the first guard refuses | A plain folder at the path named |
| A `.git` whose configuration places its working tree elsewhere (`core.worktree`) | The configured directory, which holds no `.git` naming that Git directory | The path named |
| A symbolic link into a repository | The physical root | Links are resolved first, then the repository is found |
| The home folder is a repository | The home folder | The path named |
| An ignored file in a tracked folder | `check-ignore -q` exits 0 for the file and 1 for its folder | The file’s folder, as a plain folder |
| A path the repository does not ignore, tracked or not | `check-ignore -q` exits 1 | The repository’s root |
| A shallow clone | Its root | A repository folder. Revisions work, and history stops at the boundary |
| A partial clone | Its root | A repository folder. A revision’s missing object is `object_unavailable` and is never fetched |
| A sparse partial clone, and a path that only an ignore file outside the sparse checkout would ignore | Under the resolver’s policy `check-ignore -q` exits 1 and fetches nothing | The repository’s root |
| A dirty index, or a detached `HEAD` | Its root | A repository folder. A revision view reads neither the index nor the working tree |
| No commit yet | Its root | A repository folder with no revision to choose |

## The Three Modes

|  | Plain folder | Repository folder | Mirror |
| --- | --- | --- | --- |
| Opened by | A path for which no repository’s root is opened | A path in a Git repository, of any host or none | A URL |
| Root | The folder | The repository’s working-tree root | The repository’s address |
| Views | The working tree | The working tree, and revisions | Revisions |
| Commits, diffs, and the ref chooser | No | Yes | Yes |
| Pulls and View on GitHub | No, with one case [not decided](#not-decided) | When `origin` is on github.com | When the origin is on github.com |
| Refresh from the origin | None | Never into the checkout; a background fetch into [Metabrowser’s store beside it](#origin-branches-in-a-repository-folder), which lists the origin’s branches and tags and which a served origin branch follows | A background fetch into the store, which a served branch follows |
| `kind` in `GET /api/identity` | `folder` | `folder` | `mirror` |

- **Repository folder mode needs only Git.** Any repository gets its root opened,
  Commits, and the chooser.
  GitHub’s features are a separate layer over a repository on github.com.
- **A folder and a mirror of one repository are two roots.** A reader picks one by what
  they open: the path shows their checkout, and the URL shows the mirror, even while the
  checkout’s window is open.
- **A cloud mirror serves revisions from a bare store.** A branch or tag view follows
  the remote ref as fetches move it.
  A view opened by commit ID stays pinned to that revision.
  [Following a Branch](arch-mirror-acquisition-and-refresh.md#following-a-branch)
  describes which views follow and how the page updates.
- **A repository folder is a mirror and more.** It views every branch and tag the way a
  mirror does, as a revision, the checked-out branch included, and it also has the true
  working tree, where the folder-only features live.
- **The two folder modes are one recorded mode.** `IdentityKind` in `root_identity.py`
  holds the values records and `kind` use, and one test, tracked as `mb-ajxe`, is to
  hold every copy of them to it.
  Whether a folder is a repository’s root is Git’s answer about the folder, asked when
  it opens and again as [Git Reading and History](arch-git.md) describes.

## Views

**Built**, in a repository folder as in a mirror
([Revisions of a Checkout](arch-source-sessions-and-pins.md#revisions-of-a-checkout) is
the mechanism), except Pulls and the toggle on a folder’s revision
([Pull Requests in a Repository Folder](#pull-requests-in-a-repository-folder)).

A server shows one view at a time: the working tree, or one revision.
A link that selects a branch, and a branch shown beside the working tree in one server,
are deferred.

|  | The working tree | A revision |
| --- | --- | --- |
| What it is | The files on disk, live | One commit’s tree, read from Git objects, immutable |
| Found in | A plain folder and a repository folder | A repository folder and a mirror, identical in both |
| Navigation, the index, size and type rollups | Yes | Yes |
| Live updates, the Recent tab, activity, and ignore state | Yes | No |
| Git status and local modifications, when built | In a repository folder | No |
| Editing, when built | Where `--allow-edits` permits | Never |
| Commits, diffs, and the ref chooser | In a repository folder | Yes |
| Trust | The profile the folder was opened with | Untrusted, always |

- **Capabilities follow the view.** `SourceCapabilities` declares them, and a route that
  needs an absent one answers `unsupported_for_subject`
  ([Capabilities](arch-source-sessions-and-pins.md#capabilities)).
- **Trust follows the view.** A revision renders inert, with no highlighted fences and
  no HTML preview, whatever profile its folder was opened with.
  The working tree is what the reader checked out and works in; another branch or tag is
  whatever a fetch brought, which the reader may never have looked at.
  [Content Trust Model](arch-server-and-content.md#content-trust-model) defines the
  profiles.
- **A revision is read from Git objects alone, and nothing is checked out.** A mirror
  reads its store. In a repository folder, the checkout’s own branches, tags, and commits
  are read from its Git directory in place, or from Metabrowser’s cache for that
  directory, and
  [never write the checkout](#showing-a-revision-never-writes-the-checkout).
  Its origin’s branches and tags are read from
  [the store Metabrowser keeps beside the checkout](#origin-branches-in-a-repository-folder).
  A pull request’s head is read from the store that
  [borrows from the checkout](arch-mirror-acquisition-and-refresh.md#the-lending-checkout),
  as its Changes are, because the head is usually not among the checkout’s objects and
  nothing is fetched into the checkout.
- **The checked-out branch, chosen as a ref, is a revision.** It shows the branch’s last
  commit. The working tree is a separate choice, and it is what a folder opens on.
- **The Files row names its source.** “Working tree” names the checkout’s live files and
  the branch its `HEAD` is on.
  A detached `HEAD` shows the short commit ID. When Git changes `HEAD` outside the app,
  the page’s file watch prompts a fresh read of the checkout and updates the label in
  place. A revision row names the chosen ref.
  The [ref selector’s source tooltip](../../design-system.md#the-ref-selector) reports
  the resolved working-tree directory and the age of the last `HEAD` observation.
  A cloud-backed view reports the remote repository and the last successful sync.
- **Files and Commits share the served view.** The chooser heads both tabs.
  Files shows the served files, and Commits reads their Git history.
  Pulls keeps its repository scope.
  [Revisions of a Checkout](arch-source-sessions-and-pins.md#revisions-of-a-checkout)
  describes which history each view reads.
- **A tab names its view.** A page left on one view is refused, not answered from the
  other, once the server shows another
  ([the pin guard](arch-source-sessions-and-pins.md#switching-the-pin-and-the-pin-guard)).

### Pull Requests in a Repository Folder

**Not built.** Today a checkout’s pull-request pages are pages of the folder, which
keeps showing its working tree
([Beside a Checkout](arch-github-pull-requests.md#beside-a-checkout)).

Pulls and View on GitHub stay when a repository folder shows a revision: the repository
comes from the root, and the commit from the view.

**View on branch** and **Browse code** go to the pull request’s head as a revision view,
as they do on a mirror.
Opening the reader’s own working-tree copy of the file is a separate action with its own
label, since the working tree can differ from the head and renders under the folder’s
profile.

### Origin Branches in a Repository Folder

**Built** (bead `mb-ay84`), in `checkout_store.py`. The owner set the rule on
2026-11-22: a repository folder shows its origin’s branches and tags as Metabrowser last
fetched them into a store of its own beside the checkout, kept current as a mirror’s
store is, while the checkout is never fetched into.
It carries out “in local mode, … the cache layers are still the same as mirror mode”
(the owner, 2026-11-19): a folder’s revisions are a mirror’s, and the working tree and
local branches are what it adds.
Fetching into Metabrowser’s own store is safe to repeat, so how often is a matter of
cost alone
([Metabrowser’s Own Stores](../specs/active/plan-2026-11-22-pull-request-update-cadence.md#metabrowsers-own-stores)).

- **The store** is the cache’s store for the address the checkout’s `origin` remote
  names, the one `metab <URL> --checkout <folder>` would make: an overlay with the
  served checkout as its lender
  ([The Lending Checkout](arch-mirror-acquisition-and-refresh.md#the-lending-checkout)),
  so it holds only the objects the checkout lacks, or the full store of that address
  when the cache already has one.
  `checkout_origin` in `cache/lender.py` reads the address from the checkout’s
  configuration file, in the command line’s grammar, and `acquire_checkout_store`
  acquires with `allow_clone_fallback=False`, so a checkout that cannot lend is refused
  and never cloned in full unasked.
- **Which checkouts keep one:** a checkout whose `origin` is an `https` address the
  grammar accepts, on github.com or not.
  A checkout with no `origin`, or one whose origin is a path or a `file://` address,
  keeps no store and is served exactly as before: its remote-tracking branches are
  already that repository’s, a file read away, and the listing’s `origin` is null.
  An origin reached another way, SSH on a host no provider reduces to HTTPS, or an
  `http://` or `git://` address, is one Metabrowser cannot fetch, and the chooser says
  so (`transport_unsupported`); a server never tries it.
  With `METABROWSER_ORIGIN_STORE=0` (`ORIGIN_STORE_ENV` in `checkout_store.py`) no
  application keeps a store for any checkout, a server’s or a one-shot command’s alike:
  `lifespan_checkout_store` reads it, so a transcript answers what a served page does,
  and the GitHub plugin’s prefetch attaches none for its lists
  (`attach_store_for_lists`). The one exception is a reader’s comparison of a pull
  request, which still makes the store and fetches it from the origin
  (`_acquire_comparison` in the GitHub plugin’s `checkout.py`). The test suite sets it,
  and a test of the store unsets it.
- **When it is fetched:** from the moment the folder is served, by the rules of every
  store Metabrowser keeps
  ([Refresh Cadence](arch-mirror-acquisition-and-refresh.md#refresh-cadence)). A server
  reads the origin and the store the cache has in the background as it starts, acquires
  a store it lacks, and then runs the idle timer, so with no page visible the store is
  at most `STORE_IDLE_REFRESH_S` old.
  A visible page asks as a mirror’s does: an open chooser sends its own ask once, with
  the first list that reads the store, Remotes or Tags, and not for the checkout’s own
  branches, `POST /api/source/refresh` with `{"for": "page"}`, which fetches a store
  older than `FRESHNESS_WINDOW_S`, and a page on one of the origin’s branches has that
  branch probed every `STORE_PROBE_S`. A one-shot `--show` or `--api` reads the store
  the cache has, at the request that needs it, and reaches the network only through an
  explicit `POST /api/source/refresh`, which makes the store when there is none.
- **The session** is a `MirrorSession` over that store, made once the store exists.
  `mirror_refresh.py` splits what belongs to the store, its fetch, its turn, its probe
  and hold rules, its idle timer, and its last outcome (`StoreSession`), from what
  belongs to the pin (`MirrorSession`), and a session is told which served revisions are
  its store’s (`owns`). So while the working tree or one of the checkout’s own revisions
  is served, a folder’s session fetches and reports and follows nothing.
- **One store, one turn:** the GitHub plugin fetches pull requests’ heads into the same
  store. Core owns the acquisition and the store’s turn (`store_turn`), and the plugin
  takes both from core (`_acquire_comparison` and `_CheckoutPulls.turn` in
  `builtin_plugins/github/checkout.py`), so the folder’s fetch and a pull request’s
  queue at one `StoreTurn` and neither reports the other as a refresh running elsewhere.
- **The chooser:** `GET /api/source/refs` answers `origin`, the store’s state
  (`OriginStore`): `ready` with the last fetch’s time and outcome, `acquiring` while the
  first fetch runs, or `absent` with a reason code and a sentence.
  Once it is ready, the list of remote-tracking branches has the origin’s branches from
  the store, each named `origin/<branch>` as the checkout names it, and the list of tags
  the origin’s tags from it; any ref only the checkout has, another remote’s branch or a
  local tag, is still read from the checkout.
  The checkout’s own `refs/remotes/origin/*` is not a second list.
  The checkout’s own branches are read from the checkout, as before.
- **Where the reader’s own `origin/<branch>` differs:** a row of the origin’s branches
  carries `checkout` when the checkout’s own remote-tracking branch is not at the row’s
  commit: that ref’s commit and its date, or nulls when the checkout has no such ref
  (`_own_difference` in `checkout_revisions.py`, bead `mb-h7mv`). So a branch the reader
  has not fetched since it moved, or has pushed since Metabrowser’s last fetch, is
  visible, and the chooser marks the row “yours differs” or “not in checkout”.
  The row says that the two differ and not which is ahead or by how many commits: that
  takes a walk of the history between the two for every branch that differs, a Git
  process apiece whose cost the number of refs does not bound, where the checkout’s ref
  was already read by the listing’s one `for-each-ref`. Both commits’ dates are in the
  row, and the tooltip says which is the later.
- **Showing an origin branch** serves a revision read from the store
  (`StoreMirror.open_selection`), inert as every revision is, and it follows the branch
  when a fetch moves it, as a mirror’s does
  ([Following a Branch](arch-mirror-acquisition-and-refresh.md#following-a-branch)). The
  pin route reads a selection from the store when it names a full ref of one of the
  origin’s branches, or a tag the store holds, and a commit ID while a revision of the
  store is served (`CheckoutRevisions._of_origin`). A short name, as `--ref` gives one,
  is read in a checkout’s order with the origin’s taken from the store: the checkout’s
  own branch of that name, then a tag the store holds, then a tag only the checkout has,
  then `origin/<branch>` as the store has it.
  The pin route’s answer says which was read in `read_from`, `origin` or `checkout`, and
  `--ref` says so on standard error.
  A switch opens the store first, which adopts a cached one with no network, so
  `metab PATH --ref origin/topic` reads the store once the cache has it and the checkout
  until then. The status of such a pin has the store’s freshness, `refreshable` and
  `follows`, and is still a folder’s, named and placed as the folder is.
- **The origin’s default branch** appears among the primary branches in Remotes and is
  marked `default`, as a mirror’s is, from the store’s record of it.
- **The freshness row** on a revision’s page shows progress, source issues, and actions,
  with the reload offer handled by the ref selector (`describe` with `checkout` in
  `static/source-freshness.js`). The Refresh tooltip reads the store’s last fetch time
  from the status. A checkout’s own branch follows the local ref
  ([Revisions of a Checkout](arch-source-sessions-and-pins.md#revisions-of-a-checkout)).
  A page that shows nothing of the store, the working tree’s or one of the checkout’s
  own revisions, has a store grown old fetched by its own ask, `{"for": "page"}`: once
  each time it is shown, and on one of the checkout’s own branches each time that page
  asks while it is visible.
  That fetch is quiet: nothing on the page can change when it ends.
  The row says “Refreshing…” for the reader’s own Refresh, and on a page of one of the
  origin’s branches, which a fetch can move.
- **Refresh:** `POST /api/source/refresh` on a folder that keeps a store fetches the
  store, whatever the folder shows, and the listing reads the checkout’s refs again each
  time it is asked for.
- **Without a store,** because the origin is refused, the reader is offline, or the
  first fetch has not ended, the chooser lists the checkout’s refs as before and says
  why. An origin that needs credentials the provider’s helper lacks is
  `not_found_or_private`: the origin is shown as not fetched, with that reason.
  Nothing prompts, since the acquisition policy gives Git no terminal and no askpass
  program. Where the provider says what to do about it, as GitHub’s does for `gh`, the
  reason’s sentence ends with that.
  A server tries a failed acquisition again unasked `STORE_IDLE_REFRESH_S` after it
  ended, and then twice as long after each failure in a row, up to
  `ACQUISITION_RETRY_CAP_S`, also when it was the checkout that could not lend, since a
  partial clone can be made whole; the chooser keeps the reason while it tries.
  An acquisition that ran out its deadline (`timed_out`) downloaded for all of it and
  kept nothing, so it is not tried again unasked at all (`_NOT_RETRIED_UNASKED` in
  `checkout_store.py`, with the measurement).
  A page’s own ask is held to the same waits, and a reader’s Refresh to none.
- **Never written:** `tests/test_checkout_store.py` compares every entry under the
  checkout’s `.git`, and its working tree, before and after the store is made, an origin
  branch served and read, a probe, a reader’s fetch, and the idle fetch.
  An entry’s modification time is compared too: every fetch into a store that borrows
  keeps the pack it receives (`OVERLAY_FETCH_CONFIG` in `cache/lender.py`), because Git
  would otherwise mark an object the checkout already holds as written again, in the
  checkout.

The first acquisition was measured on 2026-11-22; the numbers are in
`checkout_store.py`, beside the acquisition.

The defaults this was built on, recorded 2026-11-22 with the implementation:

- The folder’s store is fetched from the moment the folder is served, not only once the
  reader opens the chooser or Pulls.
  It keeps the owner’s “whenever possible, not out of date”; a server opened on a folder
  therefore reaches its origin’s host without being asked.
- An origin that needs credentials the store cannot use is shown as not fetched, with
  the reason, and nothing prompts.
- A checkout whose origin is not a network remote, or that has no origin, keeps its
  earlier behavior.

## What Is Never Written

In no mode does Metabrowser write a user’s Git directory: no index, ref, or object.
It writes a working tree only when the reader edits a file in it, which no route does
today.

- It runs no `checkout`, `switch`, `reset`, `stash`, `fetch`, `gc`, or `repack` in a
  checkout, takes no lock there, and writes nothing under its Git directory.
- Resolving a path, and showing a revision of a repository folder, only read.
- A mirror writes only its own store.
  One that borrows a checkout’s objects reads that checkout’s object files through
  `objects/info/alternates` and runs no Git in it
  ([The Lending Checkout](arch-mirror-acquisition-and-refresh.md#the-lending-checkout)).
- A repository folder’s store of its origin is such a store.
  Its origin is read from the checkout’s configuration file, and every fetch and probe
  runs with the store as its Git directory
  ([Origin Branches in a Repository Folder](#origin-branches-in-a-repository-folder)).
- An edit, when editing is built, writes the one file the reader edits, in the
  working-tree view and under `--allow-edits`.

What Metabrowser writes is in its own directories, the repository cache and the
configuration directory
([Cache and Configuration Directories](arch-repository-cache.md#cache-and-configuration-directories)).

Two reads on `main` fall short of this rule, because Git itself writes during them:
[Known Gaps in the Read-Only Rule](arch-git.md#known-gaps-in-the-read-only-rule).

## Security Requirements

The first part below is not built; the two about a revision are, with their tests.
Each requirement states its hole, its rule, and the test that holds it, or must before
its part ships.

### Opening a Path Never Widens a Server Unasked

A root above the path the reader named exposes more files, walks and watches more of the
disk, carries the folder’s trust profile across the whole repository, and runs Git under
the configuration of a repository the reader did not name directly.
The resolver adds `check-ignore`, which reads the index, to the Git that already runs in
a folder below a repository’s root.

- **Git decides, through the process boundary, and its answer is checked.** Discovery is
  `git rev-parse` run by `git/process.py`, never a walk for a `.git` marker.
  A planted `.git` is the attack that
  [Finding the Checkout](../specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md#finding-the-checkout)
  records: one under any directory can name any repository as its `origin`.
- **The root holds its own `.git`.** Asking Git does not close that attack alone,
  because a planted repository’s `core.worktree` makes Git report a root above it, which
  contains the path, can be read, and passes Git’s ownership check, since the reader
  owns what they unpacked.
  So a root is taken only when `<root>/.git`, followed if it is a file, is the Git
  directory `git rev-parse --absolute-git-dir` answers.
  With Git 2.50.1 that keeps an ordinary subfolder, a nested repository, a linked
  worktree, and a submodule, and refuses the planted case.
- **The resolver has its own Git policy.** Its commands run with
  `-c core.fsmonitor=false`, with optional locks off, and with `GIT_NO_LAZY_FETCH=1`, so
  resolving runs no program the repository’s configuration names, starts no daemon,
  fetches nothing, and writes nothing under the Git directory.
  `git check-ignore` reads the index, and Git’s file-system monitor settings apply to
  that read. With Git 2.50.1 and `core.fsmonitor` naming a program, `check-ignore -q` ran
  the program, which `rev-parse --show-toplevel` did not; with `core.fsmonitor=true` it
  started Git’s `fsmonitor--daemon` and created its files under `.git`. Under the policy
  it ran nothing, changed nothing under `.git`, and gave the same exit code.
  `check-ignore --no-index` avoids the index too, but it reports a tracked file that
  matches a pattern as ignored, which contradicts the guard’s reason.
  `check-ignore` also reads an ignore file from the index when sparse checkout keeps it
  off disk, and in a partial clone it fetched that file’s blob from the origin; with
  `GIT_NO_LAZY_FETCH=1` it fetched nothing and exited 1. So an ignore file that is
  neither on disk nor in the object store is not consulted, and a path only such a file
  would ignore opens the repository’s root.
- **Every guard is checked before the root is taken**, and a server bound beyond
  loopback serves exactly the path named.
- **The root is always said.** The `Serving` line and the page name the resolved root.
- **A plain folder’s start gains no Git process.** Resolution asks Git only when an
  ancestor holds a `.git` entry.
  Its cost is measured before the resolver ships, on `metab`’s open path and on the
  app’s, where every file opened asks for its repository’s root, a file an open window
  already holds included.
- **What the guards do not close.** A repository that passes them has its configuration
  honored by the reads its Commits tab makes, as it has whenever its root is opened
  directly, and its whole working tree is served under the profile the reader gave the
  path. Opening a path at its repository’s root extends both to a path opened anywhere
  beneath one, which is one more reason the root is always said.
  A repository whose configuration places its working tree elsewhere names no root, so a
  path inside one opens as a plain folder.
- **Test:** the shared fixture of resolution cases.
  It holds each guard’s case, each row of [Edge Cases](#edge-cases), the sparse partial
  clone among them, and a hostile configuration whose `core.fsmonitor` would leave a
  marker file, and it asserts no marker and an unchanged Git directory across
  resolution.

### Showing a Revision Never Writes the Checkout

After the chooser lists refs, shows several revisions with their commits and diffs, and
returns to the working tree, nothing has changed in three places: the working tree, the
Git directory, and the repository’s common directory
(`git rev-parse --git-dir --git-common-dir`). The three differ for a linked worktree,
whose shared refs are in the main repository’s Git directory, and for a submodule, whose
Git directory is under its superproject’s.

- **The hole.** The store policies that read a revision isolate the reader’s global and
  system Git configuration, and take attributes from the empty tree.
  They do not isolate the checkout’s own configuration.
  A textconv driver selected by `.git/info/attributes` or a local `core.attributesFile`
  runs during a diff, and with `cachetextconv` Git writes `refs/notes/textconv/<driver>`
  into the common directory.
  Reproduced with Git 2.50.1 on 2026-11-18, in a linked worktree too, where the
  worktree’s own directories stayed unchanged.
  An in-tree `.gitattributes` selects nothing under those policies, and `ls-tree` and
  `cat-file` run no driver.
- **The rule.** A diff of a checkout’s revision passes `--no-textconv --no-ext-diff`,
  and every read sets `GIT_NO_LAZY_FETCH=1`, so a partial clone’s missing object is
  `object_unavailable` and is never fetched into the checkout.
  A mirror’s store names no driver, so the same options change nothing there.
  That variable is all that keeps a partial clone from fetching, so a checkout’s
  revisions are read only with a Git the acquisition floor admits, and an older one is
  refused by name while the working tree is still served.
  A partial clone’s are read only with a Git that also reads a missing object as missing
  rather than ending (`PARTIAL_CLONE_GIT_MINIMUM` in `checkout_revisions.py`).
- **The fallback.** A store with no origin whose `alternates` names the checkout’s
  objects reads them with no Git process in the checkout, as an
  [overlay](arch-mirror-acquisition-and-refresh.md#the-lending-checkout) does, and
  satisfies the requirement by construction.
- **A second program.** `log.showSignature` in the checkout’s configuration makes `log`
  and `show` verify signatures, which runs the program `gpg.program`, `gpg.ssh.program`,
  or `gpg.x509.program` names.
  Every command therefore sets `log.showSignature=false`, in a folder’s own Commits tab
  too. That tab’s diffs still run a driver the folder’s configuration names, which is one
  of the
  [known gaps in the read-only rule](arch-git.md#known-gaps-in-the-read-only-rule).
- **A submodule’s own diff.** A superproject’s `diff.submodule=diff` diffs a moved
  submodule in a child Git that runs the submodule’s drivers, so every read at a store
  target sets `diff.submodule=short`.
- **Held where Git starts.** `spawn_git_process` refuses a store read that lacks the
  options it needs, the argument shapes known to start a configured program, and under
  the read policies any command outside those store reads use and any write, so a read
  added later cannot omit them.
- **Test:** `tests/test_checkout_revisions.py`, with a fixture that has a dirty index,
  uncommitted and untracked files, a signed commit, and a local configuration naming a
  driver and a signature program that would each leave a marker file.
  It runs as an ordinary checkout, as a linked worktree, and as a submodule served as
  the root, and asserts no marker and the three places unchanged across a revision’s
  files, its commit pages, its comparisons, and its Commits tab.
  A blobless clone answers `object_unavailable` there and gains no pack.

### A Revision Is Never Trusted

No response built from a revision carries active content, on any route, whatever profile
the folder was opened with and whatever view the server holds when the response is
finished.

- **The hole.** The trust profile is one block per process, and the route that renders a
  revision’s Markdown reads it after awaiting the blob.
  One server that holds a trusted working tree and untrusted revisions could switch
  between the two during that wait and render a revision under the folder’s profile.
  This is read from the code and was not reproduced.
  The page’s own inert rebuild and its policy still apply, so the requirement is the
  server’s half of a rule held twice.
- **The rule.** The profile comes from the subject the request resolved, never from
  process state read after a wait: in `git/content_routes.py`, in the page policy
  `server.py` writes, and in `/raw`. A revision is untrusted by construction.
- **Test:** `tests/test_checkout_revisions.py`: with the process’s block trusted, every
  route asked for a revision answers with no active content, and `/raw` answers as a pin
  when the revision arrived after the request did.

## What Keys on the Root

Three records name what is open.
Each keys on the mode and the root, never on the view and never on the path the reader
named.

| Record | Key | Holds |
| --- | --- | --- |
| A recent target, in the list `metab` keeps | Its recorded mode and its root | When it was last opened. A folder’s root is its open root, and a mirror’s is its credential-free address |
| `SessionRoot`, the app’s key for one server and its windows | A folder’s path, or a repository’s URL | Nothing else: a page can switch its view while the server runs, so a key that held the view would stop naming the session |
| A saved window, in the app’s `session.json` | Its root | The page the window showed |

- **No record holds a view.** A recent folder reopens on its working tree, and a mirror
  on its default branch until recent targets record what a mirror was opened at.
- **The path the reader named is not a key.** It may be kept beside one, as where to
  land when the root reopens: a recent target keeps it as its `target`
  ([Recent Targets](arch-recent-targets.md#the-entry)).
- **Recent targets are `metab`’s.** The list is kept in the configuration directory and
  reached through `metab` alone, with no route, so every shell reads one list.
  The owner also chose its file’s format, which
  [Recent Targets](arch-recent-targets.md#the-store) states.
- **A restore is not an open.** Restoring a session starts servers and reorders nothing
  in the recent list.
- **In the app, a file joins the most specific open folder that contains it, never one
  above its repository’s root.** With no such folder open, it opens its own root.
  So a file inside a repository is never shown by the window of a folder that merely
  encloses the repository.

## The File Menu

**Partly built.** Today the menu has Open Folder…, for folders and files; Open URL…,
which opens a mirror and offers no checkout yet (`mb-bkk2`); and an Open Recent that
lists the recent targets `metab` keeps
([Recent Targets](arch-recent-targets.md#the-macos-app)): folders, and repositories
opened by URL, a GitHub link sent to the app or a URL entered in Open URL… among them
([#539](https://github.com/jlevy/metabrowser/pull/539)).

- **Open Folder…** opens a folder or a file in folder mode, resolved as
  [above](#resolving-a-target-to-a-root).
  A drop, Finder’s Open With, and `open -a` do the same.
- **Open URL…** opens a mirror, always.
  A folder never stands in, under its own trust profile, for the repository a URL names.
  When a checkout of that repository is known, the dialog offers two more choices:
  **borrow from the checkout**, which opens the mirror with `--checkout` and downloads
  none of the objects the checkout already has, and **open the checkout instead**, which
  opens that folder. A checkout is known when an open folder window is one; recent
  folders join when an entry records its repository.
  A repository has one mirror, served from the repository itself, never from the URL
  that first opened it, by the owner’s word on 2026-11-19. If the mirror already has a
  window, that window and its server open the URL: the mirror refreshes, a pull request
  or a commit opens at its page, and a branch, folder, or file switches the window to
  the revision the URL selects, so it never shows another revision silently
  (`POST /api/source/link`). A link sent to the app does the same.
  If it has none, the mirror opens in a window of its own, as every folder does, also
  while a window shows a checkout of the same repository, by the owner’s word on
  2026-11-24, which replaced a tab of the checkout’s window
  ([GitHub Links](arch-macos-app.md#github-links)).
- **Open Recent** lists the recent targets `metab` keeps, repositories opened by URL
  among them, and reopens each in the mode it records.

## The Indicator and View on GitHub

These are two controls, and neither stands in for the other.

**The mode indicator** shows how the root is open, as one of three marks.
It is built, by the owner’s word on 2026-11-20 that each kind of root has an icon of its
own, and [Source Kinds](../../design-system-icons.md#source-kinds) is where they are
defined and where each is drawn.

- **A mirror:** a cloud.
  The GitHub mark with a small cloud over it, which this section first designed, would
  have carried the legibility risk of two glyphs at the size drawn, and the GitHub mark
  alone would repeat View on GitHub’s glyph.
- **A repository folder:** a folder with Git’s branch, the `git` kind.
  A folder that holds a `.git` entry, which is the test the Commits tab is drawn by, so
  the mark is known at the first paint without asking Git.
- **A plain folder:** a folder with a dot, the `folder` kind.
- **Where:** with the root’s name: in the page’s navigation heading, and in the macOS
  app’s menus that list roots, the title’s folder chooser and path menu, File > Open
  Recent, and the Dock menu.
- **What it reads:** `kind` in `GET /api/identity`, the route the app’s window title
  already reads, so the page and the app cannot disagree.
  Its `kind_tip` is the sentence the mark carries as its tooltip, “Cloud mirror of
  owner/repo”, “Local Git checkout (GitHub: owner/repo)”, or “Local folder”.
- **It shows the mode and not the view.** A repository folder keeps its mark while it
  shows a revision. The chooser in the Files toolbar and the `@<ref>` in the name say
  which view is shown.
- **A checkout’s mark differs from the ordinary folder’s.** The owner asked on
  2026-11-20 that a root’s icon never read as the folder icon of an ordinary subfolder,
  so the plain folder’s mark is not the folder outline, and the app’s title menu draws
  the outline for the folders above the root.

**View on GitHub** is a separate control, the button in a page header’s upper right
([View on GitHub](../../design-system.md#view-on-github)), and appears only for a
repository on github.com, in a repository folder and in a mirror.
It stays on a revision view, and its link names the commit being viewed.

## Decisions

The owner’s, given in chat.
The table says what the owner decided, and the section linked states the rule once, with
the design that carries it out.

| Decision | Date | Stated in |
| --- | --- | --- |
| Three modes: a plain folder, a repository folder, and a mirror | 2026-11-18 | [The Three Modes](#the-three-modes) |
| Terms follow Git’s, and “worktree” names only a proper Git worktree | 2026-11-18 | [Standard Terms](#standard-terms) |
| A path opens its nearest enclosing repository; in no repository, a folder opens as itself and a file opens its folder | 2026-11-18 | [Resolving a Target to a Root](#resolving-a-target-to-a-root) |
| Walk-up is guarded: not for an ignored path, not up to the home folder, not when bound beyond loopback, and `--exact-root` opts out | 2026-11-18 | [The Guards](#the-guards) |
| Only serving, `--present`, and the app resolve; the data modes keep the exact path | 2026-11-18 | [Which Commands Resolve](#which-commands-resolve) |
| Mirror mode never has working-copy changes; a repository folder views every other branch as a mirror would and also has the true working tree | 2026-11-18 | [The Three Modes](#the-three-modes), [Views](#views) |
| Repository folder mode is for any Git repository; Pulls and View on GitHub are for github.com only | 2026-11-18 | [The Three Modes](#the-three-modes) |
| One view for each server for now; links that select a branch are deferred under `mb-itzy` | 2026-11-18 | [Views](#views) |
| A revision renders inert | 2026-11-09, confirmed 2026-11-18 | [Views](#views) |
| A repository folder shows its origin’s branches and tags from Metabrowser’s own store beside the checkout, fetched as often as is useful; the checkout is never fetched into | 2026-11-22 | [Origin Branches in a Repository Folder](#origin-branches-in-a-repository-folder) |
| That store is fetched from the moment the folder is served; an origin whose credentials it lacks is shown as not fetched, with the reason, and nothing prompts; a checkout with no origin, or a local one, keeps no store | 2026-11-22, as defaults with `mb-ay84` | [Origin Branches in a Repository Folder](#origin-branches-in-a-repository-folder) |
| Pulls and View on GitHub stay on a revision view, and it links to the commit viewed | 2026-11-18 | [Pull Requests in a Repository Folder](#pull-requests-in-a-repository-folder) |
| View on branch and Browse code go to the pull request’s head as a revision view; the working-tree copy is a separate, labelled action | 2026-11-18 | [Pull Requests in a Repository Folder](#pull-requests-in-a-repository-folder) |
| Open URL… opens the mirror, always, offers a known checkout, and never silently shows another revision | 2026-11-18 | [The File Menu](#the-file-menu) |
| Every folder and mirror opens in a window of its own, and no app window takes tabs, replacing 2026-11-18’s mirror window as a tab of an open checkout’s | 2026-11-24 | [The File Menu](#the-file-menu) |
| The indicator sits with the root’s name; the cloud alone is the fallback; folder mode uses a folder icon | 2026-11-18 | [The Indicator and View on GitHub](#the-indicator-and-view-on-github) |
| Each kind of root has an icon of its own, a cloud mirror, a local Git checkout, and a local folder, drawn the same in the page and the macOS app, and none reads as an ordinary folder’s icon | 2026-11-20 | [The Indicator and View on GitHub](#the-indicator-and-view-on-github), [Source Kinds](../../design-system-icons.md#source-kinds) |
| The GitHub control is separate from the indicator, for github.com repositories only | 2026-11-18 | [The Indicator and View on GitHub](#the-indicator-and-view-on-github) |
| One View on GitHub button in the upper right of every page github.com has a page for, which the app opens in a native popover and whose menu copies the link or opens it in the browser, in place of the Metabrowser and GitHub toggle and the pull request’s View on GitHub link | 2026-11-18 | [View on GitHub](../../design-system.md#view-on-github) |
| A file joins the most specific open folder that contains it, never one above its repository’s root | 2026-11-18 | [What Keys on the Root](#what-keys-on-the-root) |
| Recent targets: keyed as `SessionRoot` is, kept in the configuration directory, reached through `metab` only; a restore is not an open | 2026-11-18 | [What Keys on the Root](#what-keys-on-the-root) |

The request this design answers is bead `mb-itzy`, recorded on 2026-11-07: Files should
make both a live working tree and read-only cached branch snapshots accessible.
Its rules are older: on 2026-09-16 the repository-sources design made a user’s checkout
the authority for its own files, barred Metabrowser from fetching into, switching, or
writing it, and made every view of a branch, tag, or commit an immutable revision
(commit `1a5188eec`).

### Not Decided

Each of these waits for the owner.

- **Pulls on a folder served exactly, below a repository’s root.** Such a folder has
  Pulls today when its repository’s `origin` is on github.com.
  The model’s plain folder has every Git feature off.
- **Whether a `--remote` server resolves its path.** `--remote HOST` starts `metab` on
  the host for the directory `--path` names and tunnels it to localhost, so that server
  binds loopback and the loopback guard says nothing about it.
  The reader cannot see what encloses a path on another host, and the far server runs
  under that host’s own trust defaults.
  Until this is answered the design keeps a `--remote` server on the path named.
- **Walk-up and trust.** The trust profile belongs to the root, so a root above the path
  named carries the reader’s profile across the whole repository.
  A reader who passes `--untrusted` has said the content may be hostile, and opening the
  repository above it runs Git under that repository’s configuration.
  The question is whether `--untrusted` is a guard, so that such an open serves the path
  named.

## Implementation Status

A pull request that builds a part updates its row.

| Part | State | Where |
| --- | --- | --- |
| Mirror mode: stores, pinned revisions, refresh, and the ref chooser | Built | [Source Sessions and Pins](arch-source-sessions-and-pins.md), [Mirror Acquisition and Refresh](arch-mirror-acquisition-and-refresh.md) |
| A folder served as the path named, and a file’s folder | Built; resolution replaces it | `run_serve` in `cli/serve.py`; the app’s `OpenTarget` |
| History only at a repository’s root | Built; stays as the gate for a folder served exactly | [The Exact-Root Gate](arch-git.md#discovery-and-the-exact-root-gate) |
| The resolver: a path to its repository’s root, the guards, `--exact-root`, and the root in the `Serving` line | Not built | `mb-2wfk` |
| `metab TARGET --present`, whose dry run answers a resolution | Partly built: `--present` and its dry run, on the path named; answering a resolution waits on the resolver | [#540](https://github.com/jlevy/metabrowser/pull/540), `mb-d9tu`; `mb-2wfk` |
| GitHub links opened in the app, and `SessionRoot` | Built: one mirror per repository, which opens every link into it in its running server | [#539](https://github.com/jlevy/metabrowser/pull/539), `mb-87j0`; `mb-30xb` |
| A repository folder’s revision views, its chooser, and their command line, with the two revision requirements above | Built | [Revisions of a Checkout](arch-source-sessions-and-pins.md#revisions-of-a-checkout); [#559](https://github.com/jlevy/metabrowser/pull/559), `mb-8ob8` |
| Pulls on a folder’s revision; View on branch and Browse code to the head as a revision | Not built | Follows `mb-8ob8` |
| A repository folder’s origin branches and tags from Metabrowser’s store beside it, each marked where the reader’s own `origin/<branch>` differs | Built | [Origin Branches in a Repository Folder](#origin-branches-in-a-repository-folder), `mb-ay84`, `mb-h7mv` |
| Recent targets kept by `metab`, behind File > Open Recent | Built; a mirror’s `target` waits for `ProviderUrlReducer.web_url` (`mb-8bds`), and the resolved root for the resolver | [Recent Targets](arch-recent-targets.md), `mb-40k4` |
| File > Open URL… | Built, without the offer of a known checkout, which waits for a way to tell that an open folder is a checkout of the URL’s repository | [#560](https://github.com/jlevy/metabrowser/pull/560), `mb-m4mg`; the offer is `mb-bkk2` |
| View on GitHub on files, folders, pull requests, and commits | Built; the app’s native popover is its own | `mb-4wqh` |
| The mode indicator: three marks, the page’s nav heading and the app’s menus | Built | `mb-4s2y`; the page’s `kind` and `kind_tip` in `/api/identity`, the app’s `RootMark` |
| One mode vocabulary across `IdentityKind`, the recent-targets store, and the app, held by a test; the shared resolution fixture | Not built | `mb-ajxe` |
| The two [known gaps in the read-only rule](arch-git.md#known-gaps-in-the-read-only-rule) on a served checkout | Open | `mb-z849` |
| Links that select a branch, and a branch beside the working tree in one server | Deferred | `mb-itzy` |

## References

- [Source Sessions and Pins](arch-source-sessions-and-pins.md)
- [Git Reading and History](arch-git.md)
- [Mirror Acquisition and Refresh](arch-mirror-acquisition-and-refresh.md)
- [Repository Cache](arch-repository-cache.md)
- [Server and Content](arch-server-and-content.md)
- [GitHub Pull Requests](arch-github-pull-requests.md)
- [macOS App](arch-macos-app.md)
- [The pull-request review plan](../specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md)
- [The View on branch plan](../specs/active/plan-2026-11-17-view-on-branch.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
