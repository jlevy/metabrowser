# Plan: Pull-Request Review from a Mirror or an Existing Checkout

**Status:** Designed and tested, not started.
Nothing here exists in the code: no store mode, flag, record, route field, state, or
test. The design was proven by experiments on 2026-11-02 against a 1.2 GB private
repository and small local replicas; every number below is from those runs, and
[What the Experiments Established](#what-the-experiments-established) says which claims
were proven and which are inferred.
[Open Decisions for the User](#open-decisions-for-the-user) lists what the user settles
before step 1 starts, and [Delivery](#delivery) says what can ship in 0.12.x.

This plan extends the [Pulls tab plan](plan-2026-10-01-github-pulls-tab.md), which stays
the authority for the list, the tab, numbered routes, and the pages on a checkout, and
the [thin-mirror plan](plan-2026-09-23-v012-thin-mirror.md), which stays the authority
for the mirror, `gh`, and records.
It revises one decision of the Pulls tab plan,
[the alternates option](plan-2026-10-01-github-pulls-tab.md#local-checkouts), and one
invariant of
[Shared Repository Store](../../architecture/arch-repository-sources-and-provider-mirrors.md#shared-repository-store);
[The Rule This Changes](#the-rule-this-changes) names both.
Beads: `mb-cbak` (pull requests on a checkout), `mb-lnkl` and `mb-iw1v` (the list and
the tab), and `mb-dqvj` (shallow history), which this plan touches but does not start.

## Goal

Review a GitHub pull request in Metabrowser in two situations, with the same pages, the
same commands, and the same cache:

- **Fresh.** Nothing is on disk.
  `metab <pull-request URL>` clones the repository into Metabrowser’s read-only cache
  and serves the pull request from it, as 0.12 does.
- **Beside an existing checkout.** The reader already has the repository checked out,
  possibly large, possibly shallow, possibly as one of many linked worktrees.
  Metabrowser serves the pull request without copying the checkout’s objects into the
  cache and without writing anything into the checkout.

In the user’s words: it should “work seamlessly both fresh, using our cached read-only
metabrowser repo cache, as well as in an existing checked-out repo without duplicating
the checked-out local storage”, which “should be possible since the Git repo history is
usually immutable”.

### Non-Goals

- The pull-request list and the Pulls tab themselves, which the Pulls tab plan owns.
- Writing into the user’s checkout for any reason: no fetch, ref, index, worktree, or
  configuration write.
  The checkout is read.
- Deepening a shallow checkout’s history for the reader, which is `mb-dqvj`.
- Fork remotes, SSH transports, and GitHub Enterprise, as in the Pulls tab plan.
- Reclaiming disk from existing full mirrors automatically.
  A conversion exists ([Conversions](#conversions)) and is explicit.

## What the Experiments Established

All runs on 2026-11-02, Git 2.50.1, `gh` 2.98.0, macOS on a 10-core laptop with load
averages between 2 and 7, against a 1.2 GB private repository and its mirror in the
cache. Facts about the checkout, read with no write to it:

- It is shallow (`git rev-parse --is-shallow-repository`), with a boundary of 17 commits
  (`wc -l .git/shallow`).
- Its `HEAD` is thousands of commits behind `origin/main`, but its remote-tracking refs
  are kept fetched, so it holds the head and base of every recent pull request.
- It has 1,633 refs (`git for-each-ref | wc -l`), 210 linked worktrees
  (`ls .git/worktrees | wc -l`), 47 packs, 1.5 GB under `.git/objects`, and no
  partial-clone promisor packs.
- Its local configuration sets `core.hooksPath` and holds three hooks; it has no
  `objects/info/alternates`.

The cache’s full mirror of the same repository holds 1,240 MB of objects
(`du -sk repository.git/objects`) and took 185 s to clone.

| Question | Result |
| --- | --- |
| Cost of an **overlay store**: a bare store whose `objects/info/alternates` names the checkout’s objects, fetching only `refs/pull/<n>/head` and the base branch with `gh` as the credential helper | 0.7 to 1.2 s per pull request and **0 KB added** for five pull requests whose commits the checkout has (1075, 1074, 1073, 1071, 1081); **1.4 s and 92 KB** (15 loose objects) for one it lacks (1053, a merged pull request whose branch was deleted). The full mirror cost 185 s and 1,240 MB |
| A **complete overlay acquisition** as [Storage Modes](#storage-modes) proposes it: `ls-remote`, `init --bare`, configuration, alternates, the shallow boundary, 332 seeded refs, the mirror’s full fetch of every branch and tag, and one pull-request head | **5.2 s in all, 0 KB of objects**, 1.3 MB on disk for refs and records. A second refresh of every branch and tag with `--prune --atomic`: 1.3 s |
| Do Metabrowser’s reads work on it | `cat-file`, `ls-tree`, `log`, `merge-base` (25 to 38 ms), and `diff --numstat` (27 to 42 ms) all work. `merge-base(base, head)..head` matched GitHub’s **files, additions, and deletions exactly for all six pull requests**. The real `metab` CLI, pointed at a scratch application home whose store was replaced by the overlay, answered `/api/plugin/github/pull`, `/api/source/status`, `--show README.md`, `--show /pull/1074/files`, and the diff plugin’s comparison route; the comparison route’s 504,557-byte answer was **byte-identical** to the mirror’s, and `metab` fetched a seventh pull request (1079) into the overlay through its own job in 6.2 s |
| The **shallow boundary** without the checkout’s `shallow` file in the store | `git log` on the default branch dies after 6,302 commits with `fatal: cannot read commit object`; `fsck` reports a broken link from a boundary commit; `repack -a` dies with `fatal: bad tree object`. `rev-list --count` answered 10,321, the full history, because the store also reads the checkout’s stale `objects/info/commit-graph`, which names commits whose objects are gone; with `core.commitGraph=false` it dies instead |
| With the `shallow` file copied in | `log` walks 9,578 commits and stops, the same count the checkout’s own Git gives; `merge-base` and the comparisons are unchanged; a fetch into the shallow store works; `fsck --connectivity-only` reports only the stale commit-graph, and with `core.commitGraph=false` it passes in 0.56 s |
| Deepening into the store’s own objects, the checkout untouched | `--deepen=50`: 7.6 s, 7.6 MB. `--unshallow`: **7.5 s, 8.8 MB** (8,263 objects), after which the store walks the full 10,321 commits the mirror does, and `fsck` passes. The checkout’s `shallow` file, packs, and refs were unchanged after every run |
| A fetch’s **negotiation** with the checkout’s refs | By default Git runs `git --git-dir=<checkout> for-each-ref --format=%(objectname)` inside the checkout twice per fetch (negotiation and the connectivity check). With `core.alternateRefsCommand=true` and the store’s `refs/remotes/origin/*` seeded from the checkout’s remote-tracking refs (327 refs in 0.12 s), the same fetch costs the same 92 KB and 1.6 s and **runs nothing in the checkout**. With neither, the first fetch of a pull-request head cost **340 MB and 40 to 45 s**: the default branch’s whole history |
| **Fragility**, on a local replica: a pull request squash-merged upstream, its branch deleted, the checkout fetched with `--prune`, its reflogs expired, then `git gc --prune=now` | The pull request’s objects leave the checkout and the store’s `refs/pull/1/head` dangles. `cat-file`: `could not get object info`; the batch reader: `missing`; `log`: `fatal: bad object`; `ls-tree`: `fatal: not a tree object`; `merge-base`: `Not a valid commit name`; `fsck`: `invalid sha1 pointer`. The open pull request beside it, whose branch the checkout still has, was unaffected. **A plain fetch of the same `refs/pull/<n>/head` healed it**: Git saw the local object was missing, re-wanted it, and the origin sent the pull request’s own objects (5 on the replica). `--negotiation-tip` did the same; `--refetch` brought the whole repository |
| `git repack -a -d` in the checkout | No effect: reachable objects survive, and the store read them from the new pack |
| `git gc` in the store itself | Never runs (`gc.auto=0`); run by hand it passes `-l` to `repack`, so it neither copies the checkout’s objects in nor touches the checkout, whose object directory was byte-for-byte unchanged |
| The checkout **moved** | Every read: `error: unable to normalize alternate object path` then `fatal: missing object`. A fetch fails the same way. Rewriting `objects/info/alternates` to the new place restores every read |
| The checkout **deleted** | The same errors. With the alternates file removed, a fetch still fails, because the store’s own refs name objects it cannot read (`Could not read …`, `did not send all necessary objects`); recovery is a new acquisition |
| Cost of **detecting** a dangling pin on the real overlay | `cat-file --batch-check` of the pinned commit and its tree: 24 ms. A pull-request-scoped `rev-list --objects --missing=print head ^main`: 55 ms. `fsck --connectivity-only` over the store’s refs: 0.56 s with six refs, 3.2 s with 333 |
| **No persistent store**: `GIT_ALTERNATE_OBJECT_DIRECTORIES` per process | Works per process, fetch included; the next process without it answers `fatal: bad object` for the ref it wrote. Metabrowser scrubs this variable from every spawn (`git/process.py`, `_REPO_PINNING_GIT_VARS`) |
| **Reading the checkout directly** with `--git-dir` | Same speed, the checkout’s shallow boundary honored, but a commit the checkout lacks cannot be brought, and the checkout’s local configuration governs every read: on a replica whose configuration set `diff.external`, `git diff <tree> <tree>` under the isolated environment **ran the external command**, and `git status` ran `core.fsmonitor`. The same reads through an overlay store ran neither: the store’s own configuration governs, and the checkout’s is never read for an object |
| **Reverse direction**: a full mirror exists and a checkout appears | A clonefile copy of the mirror (0.09 s) given the alternates file and `git repack -a -d -l` went from 1,241 MB to **896 KB in 6.3 s**, keeping the 110 objects the checkout lacks; every read and comparison still worked, with the full 10,321-commit history |
| An overlay exists and the checkout is about to go | `git repack -a -d` in a store with the shallow file: **6.3 s and 346 MB** for the 204,345 objects its refs reach, after which the alternates file is removed and `fsck` passes in 0.45 s; `--unshallow` then completes it for the 8.8 MB above. Without the shallow file `repack -a` dies at the boundary |
| `git clone --reference <shallow checkout>` | Refuses: `reference repository … is shallow`. The manual alternates file is not checked, which is why the boundary must be copied by hand |

The scripts and raw outputs are kept outside the repository; the coordinator holds the
path.
A replica is a bare origin, a clone of it as the checkout with one linked worktree,
and an overlay store, built in seconds, so every destructive scenario above can become a
test fixture.

## Design

### One Store Shape, Two Ways to Fill It

A repository store stays what it is: one bare `repository.git` under
`repository-stores/<store-key>/`, with Metabrowser’s configuration, the origin’s
branches under `refs/remotes/origin/`, its tags, and `refs/pull/<n>/head` for each pull
request opened. The served pin, the batch readers, `pull_refs.py`, `update.py`, the
`RepositoryStoreTarget` and its `STORE_READ_POLICY`, the freshness window, the fetch
lock, and the pull-request records are unchanged.
The experiment ran the real `metab` on an overlay with no code change, and the
comparison route answered byte for byte what the mirror answers.

What changes is only how the store is filled:

| Mode | Objects | When |
| --- | --- | --- |
| `full` | Every object, fetched from the origin, as today | No checkout is known, or borrowing is impossible |
| `overlay` | `objects/info/alternates` names the checkout’s objects directory; the store holds only what the checkout lacks | A checkout of the repository is known when the store is created |

An overlay store is created by `acquire_into_staging`’s sibling in `cache/acquire.py`,
with the same staging entry, locks, validation, and publication:

1. `ls-remote --symref` of the origin’s HEAD, as now.
2. `init --bare --template=`, the store configuration, plus two keys:
   `core.commitGraph=false`, because the store would otherwise read the checkout’s
   `objects/info/commit-graph`, which can name commits whose objects are gone, and
   `core.alternateRefsCommand=true`, so no fetch runs Git inside the checkout.
3. `objects/info/alternates` holding the absolute path of the checkout’s objects
   directory, which for a linked worktree is the common directory’s.
4. The checkout’s `shallow` file copied in when it has one.
5. The store’s `refs/remotes/origin/*` and `refs/tags/*` created from the checkout’s
   remote-tracking refs and tags, read with one `for-each-ref` on the checkout under the
   store-read isolation (no user or system configuration, lazy fetch off, no prompt),
   which is how the experiment read them.
   These are the fetch’s negotiation tips; without them the first fetch costs the
   default branch’s whole history.
6. The mirror’s own fetch of every branch and tag with `mirror_fetch_args`, which brings
   only what the checkout lacks, then the same validation of HEAD and object format as a
   full clone.

The size check `check_first_clone` makes does not apply: the first fetch is bounded by
what the checkout lacks, which nothing reports in advance, so the acquisition deadline
is its bound.
The checkout’s object format must match the origin’s advertised one, or the
overlay is refused.

**Records.** `store.yml` gains an optional `lender` block beside `acquisition`: the
absolute path of the objects directory borrowed and the checkout’s root at creation, for
display. Absent means `full`; present means `overlay`. A store with the block and no
alternates file, or the reverse, is `damaged`. No version moves: no released version
wrote a store with the block, and a 0.12.0 store without it is a full store, which is
what absence means. `cache/contracts.py` and the conformance corpus gain the field, and
`check_artifact_contracts.py` checks it as it checks the rest.

**What the reader is told.** A store’s mode is visible wherever its location is:

- `metab` prints `borrowing objects from ~/src/repo` where it prints the clone’s
  progress today, and the mirror heading’s tooltip says
  `Mirror of <origin> at <commit>, stored in <location>, borrowing objects from <checkout>`.
- `/api/source/status` carries `borrows`, null for a full store, beside `location`,
  under the same exception that admitted `location`
  ([What a mirror’s page is called](../../architecture/arch-repository-sources-and-provider-mirrors.md#what-a-mirrors-page-is-called-and-where-it-says-it-is-kept)).
  The path is the user’s own checkout, so the leak argument there applies unchanged;
  `tests/test_serve_pin.py` extends its path-leak check to it.
- `/api/cache/stores` reports `mode` and, for an overlay, the lender’s
  [health](#failure-and-recovery).

### Finding the Checkout

Nothing about a checkout is recorded today, and scanning the disk is out.
Three ways, all cheap and deterministic, and no fourth:

| How | Cost | Command |
| --- | --- | --- |
| **The working directory.** `metab <url>` run from inside a checkout whose `origin` is the URL’s repository borrows it. The checkout is found as a served folder’s identity is found today: `discover_repository_context` walks up to `.git`, follows a linked worktree’s `gitdir:` file to the common directory, and reads `origin` from the configuration with bounded file reads and no Git process | Microseconds; no Git | `cd ~/src/repo && metab https://github.com/owner/repo/pull/123` |
| **Named.** `--checkout PATH` names it from anywhere. The path must resolve to a checkout whose `origin` is the URL’s repository, or the command refuses and says which repository it found | Same | `metab https://github.com/owner/repo/pull/123 --checkout ~/src/repo` |
| **Remembered.** Once a store borrows from a checkout, `objects/info/alternates` and the `lender` record are the memory. Every later `metab <url>` for that repository, from any directory, uses the overlay | Nothing | `metab https://github.com/owner/repo/pull/124` |

Precedence: a published store for the source wins, whatever its mode, so a URL never
silently changes storage; then `--checkout`; then the working directory.
`metab <url>` from inside a checkout when a full mirror already exists uses the mirror
and prints that it did, with the conversion command ([Conversions](#conversions)); item
4 of [Open Decisions](#open-decisions-for-the-user) is whether that should be automatic.

The Pulls tab plan’s rule “Nothing about the checkout is recorded: no path, no branch”
stays true for the shared records under `sources/<slug>/pulls/`, which a checkout and a
mirror share, and for the `unattached` source.
It is changed for a store: an overlay store records the one path Git itself records
beside it.

### Workflows

Exact commands, both scenarios, with what each does and costs as measured.

**A pull-request URL with nothing local.** Unchanged from 0.12:

```shell
metab https://github.com/owner/repo/pull/123
```

A full mirror is cloned (185 s and 1.2 GB for the measured repository), the pull
request’s record is read with `gh`, its head is fetched, and the page is served under
the forced untrusted profile.

**A pull-request URL when a checkout exists.** From inside it, or naming it:

```shell
cd ~/src/repo
metab https://github.com/owner/repo/pull/123
metab https://github.com/owner/repo/pull/123 --checkout ~/src/repo
```

An overlay store is created (5.2 s in all for the measured repository, no object
copied), the record is read, the head is fetched (about a second; kilobytes when the
checkout lacks it), and the same page is served the same way.
The checkout is not written.
`metab` says it is borrowing, and from where.

**A checkout in a linked worktree.** The same, from any worktree of the repository:

```shell
cd ~/src/repo-feature-x      # .git here is a file: gitdir: …/.git/worktrees/feature-x
metab https://github.com/owner/repo/pull/123
```

The borrowed directory is the common directory’s `objects`, which every worktree shares;
the store records that directory, not the worktree.

**Several pull requests.** After the Pulls tab plan’s step 2, any number is a page of
the same server, and each head is one fetch of about a second into the overlay:

```shell
metab https://github.com/owner/repo
# then /pull/123, /pull/124, … in the page, or:
metab https://github.com/owner/repo --api '/api/plugin/github/pull?number=124'
```

Until step 2 lands, each pull request is its own `metab <url>`, sharing one store.

**`metab <checkout>` and finding a pull request from there.** The Pulls tab plan’s steps
4 and 5: the folder server lists and opens pull requests from the shared records.
Its step 5 changes with this plan: when the commits are not in the checkout, the page no
longer offers a full clone but fetches them into an overlay store that borrows the very
checkout being served, which is the cheap case measured above.
The CLI form is the plan’s own:

```shell
metab ~/src/repo --api '/api/plugin/github/pull?number=123'
metab ~/src/repo --api '/api/plugin/github/pulls?state=open'
```

Files changed on the folder server reads the overlay store, never the checkout, so the
checkout’s configuration is not consulted for pull-request content; see [Trust](#trust).

### Storage Modes

Which mode applies, and the fallback:

| Situation | Mode | What the reader is told |
| --- | --- | --- |
| No checkout known | `full` | The clone’s size and progress, as now |
| A checkout known, origin matches, object format matches, objects readable, not a partial clone | `overlay` | `borrowing objects from <checkout>` |
| The checkout is **shallow** | `overlay`, with its boundary copied; history views stop where the checkout’s do, and status reports `shallow: true` | `history is shallow, as the checkout’s is`. Deepening is `mb-dqvj`; the measured `--unshallow` cost 7.5 s and 8.8 MB here but is unbounded in general, so it is not automatic in the first version (item 3 of the decisions) |
| The checkout is a **partial clone** (`remote.<name>.promisor` or `.promisor` packs) | `full` | `the checkout is a partial clone, which cannot be borrowed from; cloning` — an overlay would find objects missing at read time, exactly what `GIT_NO_LAZY_FETCH` exists to refuse |
| The checkout’s `origin` is another repository, or none | `full`, after `--checkout` refuses with the repository it found | The refusal names both repositories |
| The checkout’s object format differs from the origin’s | `full` | Named |
| The objects directory is unreadable, or owned by another user | `full` | `the checkout’s objects could not be read; cloning` |
| A full store already exists | `full` is kept | Named, with the conversion command |

Nothing ever converts a store or changes its mode without a command.

### Failure and Recovery

A commit is immutable; its presence on disk is not.
The realistic loss is precise: a pull request that was squash-merged, whose branch was
deleted upstream, whose remote-tracking ref the checkout then pruned, whose reflog entry
expired (30 days by default), and whose objects a later `gc` removed.
Every other object an overlay depends on is reachable from a ref the checkout keeps, and
ordinary `gc`, `repack`, and `fetch --prune` never remove those.
So the exposure is the pull requests the reader opened whose branches are gone from the
checkout, after a month, when the checkout collects garbage; and GitHub keeps
`refs/pull/<n>/head` after the branch is deleted, which is what the healing fetch relies
on.

| Event | What fails | Detected | Recovery | Page or command |
| --- | --- | --- | --- | --- |
| Objects pruned in the checkout (above) | Reads of that pin: the batch reader answers `missing`, `ls-tree` and `log` fail, `merge-base` fails | **At open**, `cat-file --batch-check` of the pinned commit and its root tree, 24 ms, before the server starts. **In a session**, the next read: every Git failure on a store is already typed (`GitObjectUnavailableError`, `object_unavailable`), never a traceback, pinned by `tests/test_plugin_content_reader.py` | The pull request’s refresh job runs its ordinary fetch of `refs/pull/<n>/head`, which brings the objects back (proven on the replica). The server starts it when the open check fails, and a page starts it as it starts a stale refresh | The page says `this pull request’s commits are no longer in the checkout; fetching them from GitHub`, then re-renders. If GitHub no longer serves them, `commits_unavailable`, with the conversation and reviews still shown from the record |
| The checkout is repacked | Nothing | — | — | — |
| The checkout’s history made shallower | As pruned | As pruned | As pruned | As pruned |
| The checkout moved or deleted | Every read of a borrowed object; a fetch too | **At open**, the alternates directory is stat’ed: `lender_missing` | `--checkout <new path>` rewrites `objects/info/alternates` and the record after checking `origin`; otherwise re-acquire as a full mirror, which is a new clone. A conversion before deleting the checkout avoids both ([Conversions](#conversions)) | `metab` refuses to serve and prints both commands; `/api/cache/stores` reports `lender_missing` with the recorded path; a running server answers `object_unavailable` for borrowed objects and the status route reports `lender_missing` on its next refresh |
| `gc` in the store | Never runs | — | — | — |

“No object Metabrowser showed is ever lost” is kept for a full store and relaxed for an
overlay to: **no object Metabrowser showed is lost while the checkout keeps it, and one
the checkout drops is fetched again from GitHub when GitHub still serves it.** A
dangling pin is a typed state, repaired by the job that would run anyway, and never a
blank page. That relaxation is item 1 of the decisions.

### The Rule This Changes

Two written rules say an overlay is not allowed:

- The Pulls tab plan,
  [Local Checkouts](plan-2026-10-01-github-pulls-tab.md#local-checkouts): “The
  alternates option … is left out at first: a `gc`, a repack, or a move of the user’s
  repository can remove objects the borrowing store depends on, which breaks the rule
  that no object Metabrowser showed is ever lost.”
- [Shared Repository Store](../../architecture/arch-repository-sources-and-provider-mirrors.md#shared-repository-store):
  “repository content is self-contained: every object is present, and nothing depends on
  alternates into a user-owned checkout or on the origin after acquisition”.

Both rest on the thin-mirror principle “No Git object is deleted in v1”, which is about
Metabrowser’s own store and stays true: an overlay store still never runs `gc`, `prune`,
or `repack`.

The user’s argument is that history is immutable.
The experiments say how far that holds: the objects are immutable and GitHub keeps every
pull-request head, so what is lost locally is always recoverable from the origin; but
presence in the checkout is a function of the checkout’s refs, reflogs, and `gc`, and
the squash-merge case above loses exactly the pull request’s own commits after a month.
A repack loses nothing.
A move loses everything until the path is fixed.

The rejection was right about the mechanism and wrong about the consequence.
The consequence is a typed state with a one-second repair, not a lost object, because
the ref that names the object is the origin’s and the origin keeps it.
The recommendation is to adopt the overlay for the checkout scenario, keep the full
mirror as the default when no checkout is known, and rewrite both rules as [Docs](#docs)
lists.
The cost of not adopting it is the one the user named: 185 s and 1.2 GB duplicated
for the measured repository, and more for larger ones, every time a reader wants a pull
request beside a checkout they already have.

### Trust

The same rules in both scenarios, and one new boundary.

- **Pull-request text is inert under both profiles.** Unchanged from the Pulls tab plan:
  the server allowlist and the page’s inert rebuild, with no branch on the profile, and
  the hostile corpus run under both.
- **A pull request’s code is served only as a pin, under the forced untrusted profile.**
  An overlay store is a `RepositoryStoreTarget` like a full one, read under
  `STORE_READ_POLICY` with `GIT_NO_LAZY_FETCH=1`, and served with the untrusted
  profile’s policy. On a trusted folder server (`metab <checkout>`), Files changed is the
  diff plugin’s text over the overlay, and View file of a pull-request blob is a link to
  the pin server, as the Pulls tab plan’s page on a checkout already has no pin.
  No blob of a pull request is ever served as a page under the trusted profile.
  A test asserts it over every route of a folder server with an overlay beside it.
- **The checkout’s configuration is never read for an object.** Reading a borrowed
  object is a file read of the checkout’s packs and loose objects; Git consults only the
  borrower’s configuration.
  The experiment’s replica set `diff.external`, `core.fsmonitor`, `core.hooksPath`, and
  `core.sshCommand` in the checkout: direct reads with `--git-dir=<checkout>` ran the
  external diff, while the same reads through the overlay ran nothing.
  This is why the overlay is preferred over reading the checkout directly even when the
  commits are present.
- **No Git runs inside the checkout after creation.** `core.alternateRefsCommand=true`
  makes Git’s own alternate-refs read a no-op, and the seeded refs replace it.
  The one Git process that reads the checkout is the `for-each-ref` at creation, under
  the store-read isolation; the Git tab makes the same read on every served checkout
  with less isolation, and `for-each-ref` runs no hook, opens no index, and uses no
  transport. The checkout’s local configuration is in effect for that one command, as it
  is for the Git tab’s. Replacing it with a file read of `packed-refs` and loose refs is
  possible and left for later; a checkout using reftable would then seed nothing and pay
  the first-fetch cost rather than fail.
- **Network and credentials** are the mirror’s: `origin_git_args` with `gh` as the only
  helper, `HOME=/dev/null` for curl, the stall bound, and the acquisition deadline.
  A fetch into an overlay sends the store’s refs as haves, which are the origin’s own
  tips; nothing about the checkout’s local branches leaves the machine, because they are
  not seeded.
- **Paths.** The lender’s path appears in exactly the places `location` does and nowhere
  else; it is display text, never read back from a request.
- **The alternates file is trusted input.** It is written by Metabrowser under the store
  lock and read by Git.
  A store whose alternates file names anything but the recorded lender is `damaged` and
  refused, so a cache that was tampered with cannot point reads at another directory.

### Fit with the Pulls Tab Plan

Reuse, not a parallel path:

- **Shared records and `unattached`.** The list and per-pull-request records under
  `sources/<slug>/pulls/` stay keyed by repository and shared by a checkout, a full
  mirror, and an overlay.
  A folder server that has written records and no store is the plan’s `unattached`
  source; creating an overlay later attaches a store to that same directory through
  `_attach_existing_source`, as acquiring a full mirror would.
- **One pull request per server, then any.** Nothing in `MirrorSession`, the companion,
  or the status route knows the mode, so the plan’s step 2 generalization applies to an
  overlay unchanged.
- **Step 5 changes.** “Files changed on a checkout when the commits are missing” no
  longer needs a full clone.
  The in-page fetch the plan left to item 4 of its decisions becomes an overlay
  acquisition inside the folder server, with the measured cost, and the record written
  without a store (`no_store`) is refreshed with a comparison as the plan already says.
  Acquisition inside a running folder server is still the new thing it names; the clone
  is not.
- **The page on a checkout** keeps the plan’s behavior: no pin, no Browse code; the
  working tree is not the pull request’s code.

### Conversions

Both directions, explicit, never automatic, each one command on a store under its lock
with the server stopped, since `repack` rewrites packs:

| Direction | Command | What it does | Measured |
| --- | --- | --- | --- |
| Full → overlay, a checkout appeared | `metab --api /api/cache/store-borrow --data '{"source": "...", "checkout": "~/src/repo"}'` | Checks the checkout as creation does, writes the alternates file and record, runs `git repack -a -d -l`, which drops every local object the checkout has | 1,241 MB → 896 KB in 6.3 s |
| Overlay → full, the checkout is going away | `metab --api /api/cache/store-dissociate --data '{"source": "..."}'` | `git repack -a -d` copies the reachable borrowed objects in, then removes the alternates file and the record. A shallow boundary stays until `mb-dqvj` deepens it | 346 MB in 6.3 s, then 8.8 MB to unshallow |

`git clone --reference` and `--dissociate` are not used: the reference form refuses a
shallow checkout, and the dissociate form is a repack anyway.
The CLI spellings above are placeholders for the route the step defines; the cache
routes are already `--api` surfaces, so they are inspectable and golden-pinned by
construction.

## Parity and Tests

Each new surface has a `metab` equivalent and a golden, per AGENTS.md, and each new
state is reached by a transcript.

| Surface | `metab` equivalent | Golden |
| --- | --- | --- |
| Overlay acquisition from the working directory, from `--checkout`, and remembered | `metab <url> --checkout <path> --api /api/source/status`, and the same from inside the checkout | A new tryscript over a `file://` origin, a clone of it as the checkout with a linked worktree, and the stand-in `gh`; pins `borrows`, `mode`, and that nothing under the checkout’s `.git` changed, byte for byte, with the directory read-only |
| `store.yml` with `lender`; `/api/cache/stores` with `mode` and lender health | `--api /api/cache/stores`, `--api /api/cache/source` | `cli-api-cache.tryscript.md` gains overlay rows, `lender_missing`, and the `damaged` mismatch |
| The refusals: partial clone, wrong origin, object format, unreadable objects, existing full store | `--checkout` on each | The same tryscript; each refusal’s text |
| A shallow checkout | `--api /api/source/status` showing `shallow: true`; `--api /api/git/log` stopping at the boundary | The tryscript, with a shallow clone as the checkout |
| A dangling pin: at open and in a session | `metab <url> --api /api/plugin/github/pull` after the fixture prunes the objects; a served-session test | An in-process transcript using the replica’s gc scenario: the typed state, the healing fetch, the page after it; and `commits_unavailable` when the stand-in origin lacks the ref |
| The pull request’s page, Files changed, View file on an overlay | `--show /pull/<n>/files`, the comparison route | `cli-github-pull.tryscript.md` run over an overlay fixture as well as a full one, with identical model lines |
| Conversions | The two cache routes | A tryscript that converts both ways and reads the same pull request before and after; `fsck --connectivity-only` passes after dissociation |
| Trust on a folder server with an overlay beside it | `metab <checkout> --api …` for every route | `tests/test_serve_pin.py`’s path-leak check extended to the lender path; a new test that no pull-request blob is served as a page under the trusted profile |

**Tests that guard the rules.**

- The checkout’s `.git` is byte-for-byte unchanged after creation, every fetch, a
  conversion, and a served session, and all of it passes with the directory read-only.
- No Git process runs with the checkout as its repository after creation: the fake `git`
  wrapper used by the process tests logs every `--git-dir` and `GIT_DIR`.
- The hostile-configuration replica (`diff.external`, `core.fsmonitor`,
  `core.hooksPath`, `core.sshCommand`) leaves no marker file after every route of a pin
  server and of a folder server with an overlay.
- A store whose alternates file disagrees with its record is refused.
- Rules from the v0.12 test review apply: standard output and error pinned separately,
  no source-text assertions, mutation checks on every guard.

**Measure before any bound is set.**

- The cost of the open check on a store with many `refs/pull/` heads, to decide whether
  only the pin or every pull-request head is checked at open.
- `fsck --connectivity-only` on an overlay with the mirror’s full ref set (3.2 s here
  with 333 refs) to decide whether a whole-store check ever runs on a request path.
  The recommendation is never: the pin check at open and typed reads in session.
- Seeding cost on a checkout with tens of thousands of refs, and the first-fetch cost
  when seeding yields nothing (a reftable checkout), to decide whether an overlay is
  refused there.
- The `--unshallow` cost on a depth-1 checkout of a large repository, before deepening
  is ever made automatic.
- Startup pairs on a plain folder and on a served pin, within 1.1x, since the lender
  check adds a stat to a pin’s open and nothing to a folder.

## Delivery

Each step is one pull request against `main`, implemented and reviewed by separate
agents, with `make verify` and green CI, merged before the next starts, updating
[Views, Models, and Routes](../../architecture/arch-views-models-routes.md) and
`CHANGELOG.md` in the same change.

| Step | Scope | Checkpoint a person can see | Needed for the user’s goal | Ships |
| --- | --- | --- | --- | --- |
| 1. Overlay acquisition | `acquire.py`’s overlay path, `--checkout` and the working directory, `lender` in `store.yml` and its contract, `borrows` and `mode` in the routes and the heading, the refusals, the shallow boundary | `cd <checkout> && metab <pull-request URL>` serves the pull request in seconds with no object copied, and says so | Yes | 0.12.x, after 0.12.0 is tagged; it adds a mode and touches no served behavior of a full store, which the regenerated transcripts show |
| 2. Lender health and healing | The open check, `lender_missing`, the dangling-pin state and the healing fetch, `--checkout` as repair, the replica fixture and its scenarios | Prune the fixture, open the pull request, watch it heal; move the checkout, see the refusal and fix it | Yes | 0.12.x, with step 1 or just after |
| 3. Conversions | The two cache routes and their repacks | Convert the measured mirror to an overlay and back | No; it is how an existing full mirror stops duplicating | After 0.12.x; small |
| 4. Overlay inside the folder server | The Pulls tab plan’s step 5 revised: acquisition from a running folder server into an overlay of that checkout | Open a checkout, open a pull request whose commits it lacks, read Files changed | No; it needs the Pulls tab stack | With that stack |
| 5. Deepening | `--unshallow` as a background job with a measured bound | A shallow overlay’s history completes itself | No | `mb-dqvj`, later |

Size: step 1 is the largest, about the size of the thin-mirror plan’s acquisition step,
since it is a second acquisition path through the same staging and publication, plus a
flag, a record field, two route fields, and a tryscript.
Step 2 is mostly tests and two typed states.
Steps 3 and 5 are each a route and a transcript.

**Backward compatibility requirements**, per
`tbd guidelines backward-compatibility-rules`:

- **Internal code:** DO NOT MAINTAIN. One acquisition module with two paths; no shim.
- **Server APIs:** DO NOT MAINTAIN. `borrows`, `mode`, and the new states are added
  everywhere in one commit; nothing reads the old shapes.
- **File formats:** N/A for migration.
  `lender` is optional in `store.yml`; absence is a full store, which is what every
  0.12.0 store is. No version moves and no second reader exists.
- **Library, plugin, persisted client state, database:** N/A.

## Docs

For a documentation agent, after step 1 and again after step 2:

- `docs/command-line.md`: the two scenarios under “Pull requests” with the exact
  commands above, `--checkout`, what `borrowing objects from` means, the shallow note,
  and `borrows` in the status envelope’s field list.
- `docs/project/architecture/arch-repository-sources-and-provider-mirrors.md`: the
  self-contained invariant under “Shared Repository Store” rewritten for two modes; the
  `lender` field in the cache record contracts table; the overlay’s acquisition in the
  acquisition state machine; `borrows` under “What a mirror’s page is called”.
- `docs/project/architecture/arch-views-models-routes.md`: parity rows for the new
  fields, states, and routes, with their goldens.
- `SECURITY.md`, Content Trust Model: the checkout as a read-only object source whose
  configuration is never consulted.
- `docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md`: already points here
  from “The alternates option” and decision 4; its step 5 text is rewritten when step 4
  above starts.
- `docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md`: a one-line note under
  Principles that “No Git object is deleted in v1” applies to Metabrowser’s own store
  and that this plan says what an overlay borrows.
- `docs/qa-v012-repository-library.md`: a part for the checkout scenario, including a
  linked worktree and a shallow clone.
- `CHANGELOG.md` for each step.
- `docs/project/README.md`: this plan in the active list, done with this document.

## Risks

- **The alternates file is a hard dependency.** A moved or deleted checkout stops every
  read until it is fixed, and a fetch cannot heal that case.
  The open check turns it into a refusal with the repair command rather than a failing
  page, and the conversion exists for a checkout about to go.
- **Git’s behavior with alternates is relied on in three places** that could change
  between versions: `everything_local` skipping a fetch whose tips are present, the
  healing re-want of a missing local object, and `repack -l`. Each has a test on the
  replica, so a Git upgrade that changes one fails a test rather than a reader.
  The acquisition Git floor already pins the versions admitted.
- **Reading the checkout’s refs at creation** runs one Git process in the checkout.
  It is the Git tab’s read, with its isolation, and it can become a file read.
- **A stale commit-graph in the checkout** would make history walks lie;
  `core.commitGraph=false` in the store prevents it, at a measured cost of nothing on
  merge-base and short logs.
  Long history views on a very large repository may be slower than on a full mirror,
  which the performance pairs in step 1 measure.
- **Two servers, one overlay.** A pin server and a folder server with an overlay can
  fetch into the same store; the fetch lock already serializes writers across processes.
- **Disk accounting.** `du` of an overlay understates what it depends on; the cache
  routes report the lender so a reader is not misled.

## Open Decisions for the User

1. **Relax the no-loss rule for an overlay.**
   - *Recommended:* yes, to “no object shown is lost while the checkout keeps it, and
     one it drops is fetched again from GitHub when GitHub still serves it”, with the
     typed state and healing fetch of [Failure and Recovery](#failure-and-recovery).
   - *Alternative:* keep the rule as written, which means no overlay and the duplicated
     clone the user asked to avoid.
   - *Affects:* whether this plan proceeds.
2. **How a checkout is found.**
   - *Recommended:* all three of [Finding the Checkout](#finding-the-checkout): the
     working directory, `--checkout`, and the remembered store; never a scan.
   - *Alternative:* `--checkout` only, which is explicit but not seamless; or a
     configuration list of checkout roots in `config.yml`, which is a fourth way and a
     record of paths to maintain.
   - *Affects:* whether `metab <url>` from inside a checkout borrows without being told.
3. **Shallow checkouts.**
   - *Recommended:* copy the boundary; history stops where the checkout’s does and
     status says so; deepening waits for `mb-dqvj`.
   - *Alternative:* `--unshallow` in the background after the first page, under the
     acquisition deadline: 7.5 s and 8.8 MB here, unbounded for a depth-1 clone.
   - *Affects:* whether a history view on an overlay can show more than the checkout.
4. **When a full mirror exists and a checkout appears.**
   - *Recommended:* keep the mirror and print the conversion command; the disk is the
     user’s to reclaim.
   - *Alternative:* convert automatically when `metab <url>` runs from inside a
     checkout.
   - *Affects:* whether a command ever changes a store’s mode on its own.
5. **Showing the checkout’s path.**
   - *Recommended:* `borrows` beside `location` in the status envelope and the heading
     tooltip, under the same exception.
   - *Alternative:* the cache routes only.
   - *Affects:* whether a page says where its objects come from.
6. **Negotiation.**
   - *Recommended:* seed the store’s refs from the checkout and set
     `core.alternateRefsCommand=true`, so no Git runs in the checkout after creation.
   - *Alternative:* Git’s default, two `for-each-ref` runs in the checkout per fetch,
     under the isolated environment.
   - *Affects:* one more read at creation versus a process in the checkout on every
     fetch; the bytes are the same.

## References

- [GitHub Pulls Tab for Mirrors and Local Checkouts](plan-2026-10-01-github-pulls-tab.md)
- [v0.12 Thin Mirror for Git and GitHub Browsing](plan-2026-09-23-v012-thin-mirror.md)
- [Repository Sources and Provider Mirrors](../../architecture/arch-repository-sources-and-provider-mirrors.md)
- [Views, Models, and Routes](../../architecture/arch-views-models-routes.md)
- Git: `gitrepository-layout` (`objects/info/alternates`, `shallow`), `git-fetch`
  (`--negotiation-tip`, `--refetch`, `--unshallow`), `git-repack` (`-l`), `git-config`
  (`core.alternateRefsCommand`, `core.commitGraph`)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
