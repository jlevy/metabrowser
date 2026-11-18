# Open Modes

**Status:** Designed and partly built.
The owner settled the model on 2026-11-18, and [Decisions](#decisions) records each
answer. Built on `main`: mirror mode, and a folder served as the exact path named, with
history only when that path is a repository’s root.
Not built: resolving a path to its repository’s root, a repository folder’s revision
views, the mode indicator, and the File menu described here.
[Implementation Status](#implementation-status) names the pull request or bead for each
part. Two points are recommendations that await the owner, and each is marked where it
appears.

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
- **Root:** what one server serves, and what one app window or tab group belongs to: a
  folder, or a repository’s address.
  It is called the **open root** where it must be told apart from the path the reader
  named.
- **Mode:** how a root is open: plain folder, repository folder, or mirror.
  Nothing done in a page changes it.
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
  tags, and objects.
- **Mirror:** Metabrowser’s own bare, cached copy of a repository, kept current from its
  origin.
- **Working directory:** only its operating-system sense, the directory a process runs
  in.

### Standard Terms

**A recommendation, for the owner to confirm.** The owner asked on 2026-11-18 that these
words follow what Git, the Codex app, and Claude’s desktop app use, and suggested
“working directory” for the live files and “worktree” for Git’s worktrees.

| Source | The live files | A second checkout of one repository |
| --- | --- | --- |
| Git’s glossary (`git help glossary`, Git 2.50.1) | *Working tree*: the checked-out files, which are the `HEAD` commit’s contents and any uncommitted changes | *Worktree*: a working tree with its repository metadata. `git help worktree` calls the first the *main worktree* and each added one a *linked worktree* |
| Git’s messages | `git status` reports “working tree clean”; the Git 2.10 release notes record that it used to say “working directory” |  |
| [Claude Code’s worktrees guide](https://code.claude.com/docs/en/worktrees) and [desktop guide](https://code.claude.com/docs/en/desktop) | The *main checkout*, or the *project folder*. A worktree is described as a separate working directory, the phrase these guides otherwise use for the directory a session or command runs in | *Worktree*, a Git worktree |
| [The Codex app’s worktrees guide](https://developers.openai.com/codex/app/worktrees) | The *local checkout*, shortened to *Local* | *Worktree*, a Git worktree |

All three use “worktree” only for Git’s worktrees.
For the live files, only Git has a defined term, “working tree”.
The desktop tools name the place instead, a checkout or a project folder.
This repository’s documents already say “working tree” for the files and “working
directory” for the directory a process runs in, and one tooltip in the page says
“working tree” (`builtin_plugins/markdown/link-enhancer.js`).

The recommendation:

1. **“Working tree” names the live files**, in these documents and as the label of the
   ref chooser’s row for them.
   It is the term Git defines and prints, and it leaves “working directory” with its
   operating-system meaning.
   A plain folder shows no such label, since it has one view.
2. **“Worktree” is only ever Git’s**, and prose writes “linked worktree” or “main
   worktree” in full, never “worktree” as a short form of “working tree”.
3. **A linked worktree is a repository folder like any other.** It opens as its own
   root, the worktree’s top-level directory, with its own working tree and `HEAD`. Its
   branches and tags are the repository’s, so a branch checked out in another worktree
   is a revision here. Where the difference matters, a document says “linked worktree”;
   otherwise “checkout” covers both.

The owner’s alternative, “working directory” for the live files, reads more plainly to
someone who does not use Git, and sits further from “worktree” on the page.
It would change the chooser’s label and the sentences that use the term, and it would
share a phrase with the directory a command runs in.

## Resolving a Target to a Root

A URL opens a mirror, and its root is the repository’s address, whatever branch, pull
request, or file the URL selects inside it.
[The command-line guide](../../command-line.md#what-root-names) says how an argument is
told apart as a URL or a path.

A path opens a folder, by these steps:

1. Resolve symbolic links.
   A file starts from the folder that holds it.
2. Find the nearest enclosing Git repository by asking Git:
   `git rev-parse --show-toplevel`. A `.git` entry in an ancestor is only the cheap test
   of whether to ask.
3. Open the repository’s working-tree root when every [guard](#the-guards) holds.
4. Otherwise open the folder named, or for a file the folder that holds it.
5. Show the page at the folder or file the reader named, under whichever root was
   opened.

A root that is the working-tree root of a repository is a **repository folder**. Any
other folder root is a **plain folder**: a folder in no repository, or one served
exactly, below a repository’s root.

### The Guards

The repository’s root is opened only when all of these hold:

| Guard | Why |
| --- | --- |
| Git answers with a root that contains the path and can be read | Git’s own checks decide what a repository is, including its refusal of a repository another user owns. A `.git` that Git refuses names no root |
| The root is not the home folder or a volume’s root, unless the reader named that folder itself | A dotfiles repository at the home folder would turn every open into the home folder: a walk and a watch of all of it, and on macOS a privacy prompt for each protected location |
| The repository does not ignore the path (`git check-ignore`) | A repository does not count an ignored path as its own, so its root is not what the reader named. This also stops the usual dotfiles layout, which ignores everything |
| The server binds loopback only: no `--host` naming another address, and no `--remote` | `metab ./docs --host 0.0.0.0` inside a private repository would serve the whole repository to the network |
| `--exact-root` was not given | The reader asked for the folder named and nothing above it |

A guard that fails opens the path named, as step 4 says, and never an error.
The `Serving` line and the page name the root that was opened, so a root above the path
the reader named is never silent.
`--exact-root` is also how to open one part of a large repository without walking and
watching the rest.

### Which Commands Resolve

Serving, `metab TARGET --present`, and the macOS app resolve a path this way.
The data modes, `--api`, `--show`, `--walk`, `--diff`, and `--check-api`, read `ROOT`
exactly as given, so a script’s answer never depends on what encloses its argument.

One resolver in `metab` answers for every caller, and a shell never implements the rule
a second time. The app starts each server on a root that is already resolved, with
`--exact-root`, and that includes the servers a restore starts, so a saved root is never
resolved again.
A fixture of resolution cases, replayed by Python and by the app’s tests,
holds the two together.

### Edge Cases

Git’s answers below are Git 2.50.1’s, checked on 2026-11-18.

| Case | What Git answers | What opens |
| --- | --- | --- |
| A nested repository, or a submodule | The nearest one; a submodule is its own root | The nearest repository |
| A linked worktree | The worktree’s own root. Its `HEAD` is its own, and its refs and objects are in the repository’s common directory | The worktree, as a repository folder |
| A bare repository, or a path inside `.git` | “this operation must be run in a work tree” | A plain folder |
| A `.git` Git refuses, such as an empty directory by that name or a repository another user owns, or a root the reader cannot read | A failure | A plain folder at the path named |
| A symbolic link into a repository | The physical root | Links are resolved first, then the repository is found |
| The home folder is a repository | The home folder | The path named. `git check-ignore -q` exits 0 for an ignored path and 1 for a tracked one |
| A shallow clone | Its root | A repository folder. Revisions work, and history stops at the boundary |
| A partial clone | Its root | A repository folder. A revision’s missing object is `object_unavailable` and is never fetched |
| A dirty index, or a detached `HEAD` | Its root | A repository folder. A revision view reads neither the index nor the working tree |
| No commit yet | Its root | A repository folder with no revision to choose |

## The Three Modes

|  | Plain folder | Repository folder | Mirror |
| --- | --- | --- | --- |
| Opened by | A path for which no repository’s root is opened | A path in a Git repository, of any host or none | A URL |
| Root | The folder | The repository’s working-tree root | The repository’s address |
| Views | The working tree | The working tree, and revisions | Revisions |
| Commits, diffs, and the ref chooser | No | Yes | Yes |
| Pulls and the GitHub toggle | No | When `origin` is on github.com | When the origin is on github.com |
| Refresh from the origin | None | Never into the checkout | A background fetch into the store |
| `kind` in `GET /api/identity` | `folder` | `folder` | `mirror` |

- **Repository folder mode needs only Git.** Any repository gets its root opened,
  Commits, and the chooser.
  GitHub’s features are a separate layer over a repository on github.com.
- **A folder and a mirror of one repository are two roots.** A reader picks one by what
  they open: the path shows their checkout, and the URL shows the mirror, even while the
  checkout’s window is open.
- **A mirror has no working tree.** Its store is bare, so there is nothing checked out
  that could hold a change, and every view of it is a revision.
- **A repository folder is a mirror and more.** It views every branch and tag the way a
  mirror does, as a revision, the checked-out branch included, and it also has the true
  working tree, where the folder-only features live.
- **The two folder modes are one recorded mode.** Records and `kind` say `folder` or
  `mirror`. Whether a folder is a repository’s root is Git’s answer about the folder,
  asked when it opens and again as [Git Reading and History](arch-git.md) describes.

## Views

A server shows one view at a time: the working tree, or one revision.

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
- **A revision is read from Git objects alone.** A mirror reads its store.
  A repository folder reads its checkout’s own Git directory in place, or Metabrowser’s
  cache for that directory; either way nothing is checked out, and
  [a revision never writes the checkout](#showing-a-revision-never-writes-the-checkout).
- **The checked-out branch, chosen as a ref, is a revision.** It shows the branch’s last
  commit. The working tree is a separate choice, and it is what a folder opens on.
- **The page says which view it shows.** The chooser reads “Working tree” or names the
  ref, and a revision’s name carries `@<ref>`, as a mirror’s does.
- **A tab names its view.** A page left on one view is refused, not answered from the
  other, once the server shows another
  ([the pin guard](arch-source-sessions-and-pins.md#switching-the-pin-and-the-pin-guard)).

### Pull Requests in Folder Mode

Pulls and the GitHub toggle stay when a repository folder shows a revision: the
repository comes from the root, and the branch or commit from the view.

**View on branch** and **Browse code** go to the pull request’s head as a revision view,
as they do on a mirror.
Opening the reader’s own working-tree copy of the file is a separate action with its own
label, since the working tree can differ from the head and renders under the folder’s
profile.

## What Is Never Written

In no mode does Metabrowser write a user’s Git directory: no index, ref, or object.
It writes a working tree only when the reader edits a file in it, which no route does
today.

- It runs no `checkout`, `switch`, `reset`, `stash`, `fetch`, `gc`, or `repack` in a
  checkout, takes no lock there, and writes nothing under its Git directory.
- Showing a revision of a repository folder reads objects and refs and nothing else.
- A mirror writes only its own store.
  One that borrows a checkout’s objects reads that checkout’s object files through
  `objects/info/alternates` and runs no Git in it
  ([The Lending Checkout](arch-mirror-acquisition-and-refresh.md#the-lending-checkout)).
- An edit, when editing is built, writes the one file the reader edits, in the
  working-tree view and under `--allow-edits`.

What Metabrowser writes is in its own directories, the repository cache and the
configuration directory
([Cache and Configuration Directories](arch-repository-cache.md#cache-and-configuration-directories)).

Two reads on `main` fall short of this rule, because Git itself writes during them:
[Known Gaps in the Read-Only Rule](arch-git.md#known-gaps-in-the-read-only-rule).

## Security Requirements

Each requirement below closes a hole the design review of 2026-11-18 found, and each
names the test that must hold it before its part ships.

### Opening a Path Never Widens a Server Unasked

A root above the path the reader named exposes more files, walks and watches more of the
disk, and runs Git under the configuration of a repository the reader did not name
directly.

- **Git decides, through the process boundary.** Discovery is `git rev-parse` run by
  `git/process.py`. No walk for a `.git` marker makes a root, because a planted `.git`
  is the attack that
  [Finding the Checkout](../specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md#finding-the-checkout)
  records: one under any directory can name any repository as its `origin`.
- **Every guard is checked before the root is taken**, and a server bound beyond
  loopback serves exactly the path named.
- **The root is always said.** The `Serving` line and the page name the resolved root.
- **A plain folder’s start gains no Git process.** Resolution asks Git only when an
  ancestor holds a `.git` entry, and the cost on the open path is measured before the
  resolver ships.
- **What the guards do not close.** A repository that passes Git’s ownership check has
  its configuration honored by the reads its Commits tab makes, as it has whenever its
  root is opened directly.
  Opening a path at its repository’s root extends that to a path opened anywhere beneath
  one, which is one more reason the root is always said.
- **Test:** the shared fixture of resolution cases, with each guard’s case and each row
  of [Edge Cases](#edge-cases).

### Showing a Revision Never Writes the Checkout

After the chooser lists refs, shows several revisions with their commits and diffs, and
returns to the working tree, every file under the checkout, its Git directory included,
is byte for byte what it was.

- **The hole.** The store policies that read a revision isolate the reader’s global and
  system Git configuration, and take attributes from the empty tree.
  They do not isolate the checkout’s own configuration.
  A textconv driver selected by `.git/info/attributes` or a local `core.attributesFile`
  runs during a diff, and with `cachetextconv` Git writes `refs/notes/textconv/<driver>`
  into the checkout. Reproduced with Git 2.50.1 on 2026-11-18. An in-tree
  `.gitattributes` selects nothing under those policies, and `ls-tree` and `cat-file`
  run no driver.
- **The rule.** A diff of a checkout’s revision passes `--no-textconv --no-ext-diff`,
  and every read sets `GIT_NO_LAZY_FETCH=1`, so a partial clone’s missing object is
  `object_unavailable` and is never fetched into the checkout.
  A mirror’s store names no driver, so the same options change nothing there.
- **The fallback.** A store with no origin whose `alternates` names the checkout’s
  objects reads them with no Git process in the checkout, as an overlay does, and
  satisfies the requirement by construction.
- **Test:** `tests/test_checkout_revisions.py`, with a fixture that has a dirty index,
  uncommitted and untracked files, and a local configuration naming a driver that would
  leave a marker file.
  It asserts no marker and an unchanged checkout across a revision’s files, its commit
  pages, and its Commits tab.

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
- **Test:** with the process’s block trusted, every route asked for a revision answers
  with no active content.
  [The pull-request review plan](../specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md#trust)
  lists this test as planned.

## What Keys on the Root

Three records name what is open.
Each keys on the mode and the root, never on the view and never on the path the reader
named. The first two are not on `main` yet
([Implementation Status](#implementation-status)).

| Record | Key | Holds |
| --- | --- | --- |
| A recent target, in `recent-targets.yml` | `mode`, which is `folder` or `mirror`, and `root` | When it was last opened. A folder’s root is its open root, and a mirror’s is its credential-free address |
| `SessionRoot`, the app’s key for one server and its windows | A folder’s path, or a repository’s URL | Nothing else: a page can switch its view while the server runs, so a key that held the view would stop naming the session |
| A saved tab, in the app’s `session.json` | Its root | The page the tab showed |

- **No record holds a view.** A recent folder reopens on its working tree, and a mirror
  on its default branch until recent targets record what a mirror was opened at.
- **The path the reader named is not a key.** It may be kept beside one, as where to
  land when the root reopens.
- **A restore is not an open.** Restoring a session starts servers and reorders nothing
  in the recent list.
- **In the app, a file joins the most specific open folder that contains it, never one
  above its repository’s root.** With no such folder open, it opens its own root.
  So a file inside a repository is never shown by the window of a folder that merely
  encloses the repository.

## The File Menu

- **Open Folder…** opens a folder or a file in a folder mode, resolved as
  [above](#resolving-a-target-to-a-root).
  A drop, Finder’s Open With, and `open -a` do the same.
- **Open URL…** opens a mirror, always.
  A folder never stands in, under its own trust profile, for the repository a URL names.
  When a checkout of that repository is known, the dialog offers two more choices:
  **borrow from the checkout**, which opens the mirror with `--checkout` and downloads
  none of the objects the checkout already has, and **open the checkout instead**, which
  opens that folder. A checkout is known when an open folder window is one; recent
  folders join when an entry records its repository.
  If the repository already has a window, the window switches to the branch or pull
  request the URL selects, and it never shows another revision silently.
- **Open Recent** lists the recent targets and reopens each in the mode it records.

## The Indicator and the GitHub Toggle

These are two controls, and neither stands in for the other.

**The mode indicator** shows how the root is open.

- **Where:** with the root’s name, in the page’s navigation heading and in the app’s
  window title.
- **A mirror:** the GitHub mark with a small cloud over it.
  If that pair does not read at the size it is drawn, the cloud alone.
  The GitHub mark alone would repeat the toggle’s glyph.
- **A mirror of a repository that is not on github.com:** the cloud alone, since it has
  no mark to show.
- **A folder:** a folder icon.
- **What it reads:** `kind` in `GET /api/identity`, the route the app’s window title
  already reads, so the page and the app cannot disagree.
- **It shows the mode and not the view.** A repository folder keeps the folder icon
  while it shows a revision.
  The chooser beside the name and the `@<ref>` in the name say which view is shown.

**A recommendation, for the owner to confirm:** a plain folder and a repository folder
show the same folder icon.
The indicator answers one question, whether the root is the reader’s own folder or
Metabrowser’s cached copy, and both folder modes give one answer.
A repository folder already looks different where it matters: it has the ref chooser
under its name and the Commits tab, and a plain folder has neither.
A third glyph, such as a folder with a branch badge, would carry the legibility risk the
cloud over the GitHub mark has, and the heading would need Git’s answer before its first
paint, where one icon for each `kind` needs none.

**The GitHub toggle** is a separate control and appears only for a repository on
github.com, in a repository folder and in a mirror.
It stays on a revision view, and its link names the ref or commit being viewed.

## Decisions

The owner’s, given in chat on 2026-11-18 except where another date is shown.

| Subject | Decision |
| --- | --- |
| The modes | Three: a plain folder, with no repository and every Git feature off; a repository folder; and a mirror |
| Finding the root | Walk up to the nearest enclosing repository. A folder in no repository opens as itself. A file in no repository opens its enclosing folder |
| The working copy | Mirror mode never has working-copy changes. Folder mode views every other branch the way a mirror would, from the checkout’s own `.git` or Metabrowser’s cache for that directory, and also has the true working tree, where the folder-only features live |
| Which repositories | Repository folder mode applies to any Git repository. Pulls and the GitHub toggle appear only for github.com |
| The guards | No walk-up for an ignored path. Never up to the home folder or a volume’s root. Not when bound beyond loopback. `--exact-root` opts out. The data modes (`--api`, `--show`, `--walk`, `--diff`, `--check-api`) keep the exact path; only serving, `--present`, and the app resolve |
| GitHub features on a revision | Pulls and the GitHub toggle stay on a revision view. The toggle links to the ref or commit being viewed |
| Open URL… | It opens the mirror, always. When a checkout is known it offers “borrow from the checkout” and “open the checkout instead”. It switches an open repository window to the URL’s branch or pull request and never silently shows another revision |
| View on branch and Browse code | In folder mode they go to the pull request’s head as a revision view. Opening the working-tree copy is a separate, labelled action |
| The indicator | It sits with the root’s name in the navigation heading and the app’s title. If the cloud over the GitHub mark does not read, fall back to the cloud alone. Folder mode uses a folder icon |
| The GitHub toggle | A separate control from the mode indicator, shown only for github.com repositories |
| Files in the app | A file joins the most specific open folder that contains it, but never one above its repository’s root |
| A revision’s trust | A revision renders inert. First decided on 2026-11-09 and confirmed |
| Recent targets | The list holds recent targets, keyed as `SessionRoot` is. A restore is not an open. The file lives in the configuration directory, as YAML with an `mfNN` format string. It is reached through `metab` only, with no route |

The owner’s words for the working tree were “the true working directory”;
[Standard Terms](#standard-terms) says why this document writes “working tree”.

Not decided:

- **The two recommendations above:** the [standard terms](#standard-terms), and whether
  a plain folder and a repository folder look different.
- **Links that select a branch, and a branch beside the working tree in one server.**
  The design is one view for the whole server, and a `/view/` address names no revision.
  Changing that is the next design step under `mb-itzy`.
- **Pulls on a folder served exactly, below a repository’s root.** Such a folder has
  Pulls today when its repository’s `origin` is on github.com.
  The model’s plain folder has every Git feature off.
- **`--remote`.** The owner’s answer names binding beyond loopback.
  The design also keeps a `--remote` server on the path named.
- **A command line for a checkout’s revision.** The parity rule needs one for the routes
  a repository folder’s revision adds.
  `metab PATH --ref NAME` is proposed.

The request this design answers is bead `mb-itzy`, recorded on 2026-11-07: Files should
make both a live working tree and read-only cached branch snapshots accessible.
Its rules are older: on 2026-09-16 the repository-sources design made a user’s checkout
the authority for its own files, barred Metabrowser from fetching into, switching, or
writing it, and made every view of a branch, tag, or commit an immutable revision
(commit `1a5188eec`).

## Implementation Status

A pull request that builds a part updates its row.

| Part | State | Where |
| --- | --- | --- |
| Mirror mode: stores, pinned revisions, refresh, and the ref chooser | Built | [Source Sessions and Pins](arch-source-sessions-and-pins.md), [Mirror Acquisition and Refresh](arch-mirror-acquisition-and-refresh.md) |
| A folder served as the path named, and a file’s folder | Built; resolution replaces it | `run_serve` in `cli/serve.py`; the app’s `OpenTarget` |
| History only at a repository’s root | Built; stays as the gate for a folder served exactly | [The Exact-Root Gate](arch-git.md#discovery-and-the-exact-root-gate) |
| Resolving a path to its repository’s root, the guards, `--exact-root`, and the root in the `Serving` line | Not built, and no bead yet | The resolver is to be the one [#540](https://github.com/jlevy/metabrowser/pull/540) adds for `--present` |
| `metab TARGET --present` | Not on `main` | [#540](https://github.com/jlevy/metabrowser/pull/540), `mb-d9tu` |
| GitHub links opened in the app, and `SessionRoot` | Not on `main` | [#539](https://github.com/jlevy/metabrowser/pull/539), `mb-87j0` |
| A repository folder’s revision views and its chooser, with the two revision requirements above | In progress on `claude/checkout-ref-selector`, with no pull request yet | `mb-8ob8` |
| Pulls and the toggle on a folder’s revision; View on branch and Browse code to the head as a revision | Not built | Follows `mb-8ob8` |
| Recent targets and File > Open Recent | Not on `main` | [#546](https://github.com/jlevy/metabrowser/pull/546), `mb-40k4` |
| File > Open URL… | In progress | `mb-m4mg` |
| The GitHub toggle | Not on `main` | [#552](https://github.com/jlevy/metabrowser/pull/552), `mb-zp7y` |
| The mode indicator | Not built | `mb-wup3` |
| One mode vocabulary across `IdentityKind` in `root_identity.py`, the recent-targets store, and the app, held by a test | Not built, and no bead yet |  |
| The two [known gaps in the read-only rule](arch-git.md#known-gaps-in-the-read-only-rule) on a served checkout | Present on `main`, and no bead yet |  |
| Links that select a branch | Not decided | `mb-itzy` |

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
