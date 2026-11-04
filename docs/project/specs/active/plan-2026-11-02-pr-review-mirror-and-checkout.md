# Plan: Pull-Request Review from a Mirror or an Existing Checkout

**Status:** Overlay acquisition, bounded explicit recovery, and checkout-backed PR
comparisons are implemented in [#283](https://github.com/jlevy/metabrowser/pull/283) and
[#288](https://github.com/jlevy/metabrowser/pull/288) and are present on
[`main` at da87bb13](https://github.com/jlevy/metabrowser/commit/da87bb13c4434324af576b554711278139621b6b),
recorded on 2026-11-04. [Delivery](#delivery) maps the implemented scope; the
[alpha plan’s landing status](plan-2026-09-22-v012-alpha-testing.md#landing-status)
records current integration and release evidence.
Conversions and broader deepening remain future work.

The design was proven by experiments on 2026-11-02 against a 1.2 GB private repository
and small local replicas, reviewed the same day with the verdict *sound with changes*,
and revised. [Independent Review](#independent-review) preserves those findings and
[What the Experiments Established](#what-the-experiments-established) distinguishes
proofs from inferences.
[Open Decisions for the User](#open-decisions-for-the-user) records the original
decisions.

This plan extends the [Pulls tab plan](plan-2026-10-01-github-pulls-tab.md) and the
[thin-mirror plan](plan-2026-09-23-v012-thin-mirror.md).
It revised the original
[alternates decision](plan-2026-10-01-github-pulls-tab.md#local-checkouts), a Files
changed case, and the store invariant; [The Rule This Changes](#the-rule-this-changes)
records that design change.
Current runtime contracts are in
[Repository Sources and Provider Mirrors](../../architecture/arch-repository-sources-and-provider-mirrors.md)
and [Views, Models, and Routes](../../architecture/arch-views-models-routes.md).

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
- Deepening a shallow checkout’s history for the reader, which is `mb-dqvj`. Deepening
  the *store* when a merge base cannot be trusted is in scope.
- Fork remotes as a list source, SSH transports, and GitHub Enterprise, as in the Pulls
  tab plan. A fork checkout may still lend its objects.
- Reclaiming disk from existing full mirrors automatically.
  The planned conversion ([Conversions](#conversions)) is explicit and is not
  implemented.

## What the Experiments Established

All runs on 2026-11-02, Git 2.50.1, `gh` 2.98.0, macOS on a 10-core laptop, against a
1.2 GB private repository and its mirror in the cache.
The first set ran at load averages between 2 and 7; the runs after the review ran at
load averages between 25 and 62, which inflates their wall times, and each is marked.
Facts about the checkout, read with no write to it:

- It is shallow (`git rev-parse --is-shallow-repository`), with a boundary of 17 commits
  (`wc -l .git/shallow`).
- Its `HEAD` is thousands of commits behind `origin/main`, but its remote-tracking refs
  are kept fetched, so it holds the head and base of every recent pull request.
  Seventy of those remote-tracking refs name branches the origin no longer has
  (`git ls-remote --heads` against `for-each-ref refs/remotes/origin/`).
- It has 1,633 refs (`git for-each-ref | wc -l`), 210 linked worktrees
  (`ls .git/worktrees | wc -l`), 47 packs, 1.5 GB under `.git/objects`, no partial-clone
  promisor packs, and a stale `objects/info/commit-graph`.
- Its local configuration sets `core.hooksPath` and holds three hooks; it has no
  `objects/info/alternates`.

The cache’s full mirror of the same repository holds 1,240 MB of objects
(`du -sk repository.git/objects`) and took 185 s to clone.

### Before the Review

| Question | Result |
| --- | --- |
| Cost of an **overlay store**: a bare store whose `objects/info/alternates` names the checkout’s objects, fetching only `refs/pull/<n>/head` and the base branch with `gh` as the credential helper | 0.7 to 1.2 s per pull request and **kilobytes**, none for five pull requests whose commits the checkout has (1075, 1074, 1073, 1071, 1081); **1.4 s and 92 KB** (15 loose objects) for one it lacks (1053, a merged pull request whose branch was deleted). The full mirror cost 185 s and 1,240 MB |
| Do Metabrowser’s reads work on it | `cat-file`, `ls-tree`, `log`, `merge-base` (25 to 38 ms), and `diff --numstat` (27 to 42 ms) all work. `merge-base(base, head)..head` matched GitHub’s **files, additions, and deletions exactly for all six pull requests**. The real `metab` CLI, pointed at a scratch application home whose store was replaced by the overlay, answered `/api/plugin/github/pull`, `/api/source/status`, `--show README.md`, `--show /pull/1074/files`, and the diff plugin’s comparison route; the comparison route’s 504,557-byte answer was **byte-identical** to the mirror’s, and `metab` fetched a seventh pull request (1079) into the overlay through its own job in 6.2 s. The reviewer reproduced the byte-identical comparison and the pull route (identical but for timestamps) |
| The **shallow boundary** without the checkout’s `shallow` file in the store | `git log` on the default branch dies after 6,302 commits with `fatal: cannot read commit object`; `fsck` reports a broken link from a boundary commit; `repack -a` dies with `fatal: bad tree object`. `rev-list --count` answered 10,321, the full history, because the store also reads the checkout’s stale commit-graph, which names commits whose objects are gone; with `core.commitGraph=false` it dies instead |
| With the boundary in the store | `log` walks 9,578 commits and stops, the same count the checkout’s own Git gives; `merge-base` and the comparisons are unchanged; a fetch into the shallow store works; `fsck --connectivity-only` with `core.commitGraph=false` passes in 0.56 s |
| Deepening into the store’s own objects, the checkout untouched | `--deepen=50`: 7.6 s, 7.6 MB. `--unshallow`: **7.5 s, 8.8 MB** (8,263 objects), after which the store walks the full 10,321 commits the mirror does, and `fsck` passes |
| A fetch’s **negotiation** | By default Git runs `git --git-dir=<checkout> for-each-ref --format=%(objectname)` inside the checkout twice per fetch. With `core.alternateRefsCommand=true` and no other source of tips, the first fetch of a pull-request head cost **340 MB and 40 to 45 s**: the default branch’s whole history |
| **Fragility**, on a local replica: a pull request squash-merged upstream, its branch deleted, the checkout fetched with `--prune`, then `git gc` | `fetch --prune` deletes the remote-tracking ref **and its reflog**; the objects become unreachable at once, a plain `gc` moves them to a cruft pack, and `gc` after `gc.pruneExpire` (two weeks by default) or `--prune=now` removes them. The store’s `refs/pull/1/head` then dangles: `cat-file` says `could not get object info`, the batch reader `missing`, `log` `fatal: bad object`, `ls-tree` `fatal: not a tree object`, `merge-base` `Not a valid commit name`. A plain fetch of the same ref healed it when it was the store’s only dangling ref |
| `git repack -a -d` in the checkout; a concurrent repack while reads run | No effect: reachable objects survive; the reviewer’s 672 reads during churn had 0 failures |
| `git gc` in the store itself | Never runs (`gc.auto=0`); run by hand it passes `-l` to `repack`, so it neither copies the checkout’s objects in nor touches the checkout |
| The checkout **moved** or **deleted** | Every read: `error: unable to normalize alternate object path` then `fatal: missing object`; a fetch fails too; with the alternates file removed, a fetch still fails because the store’s refs name objects it cannot read. Rewriting the alternates file restores every read; otherwise recovery is a new acquisition |
| **No persistent store**: `GIT_ALTERNATE_OBJECT_DIRECTORIES` per process | Works per process; the next process without it answers `fatal: bad object`. Metabrowser scrubs this variable from every spawn (`git/process.py`, `_REPO_PINNING_GIT_VARS`) |
| **Reading the checkout directly** with `--git-dir` | Same speed, but a commit the checkout lacks cannot be brought, and the checkout’s local configuration governs every read: on a replica whose configuration set `diff.external`, `git diff <tree> <tree>` under the isolated environment **ran the external command**, and `git status` ran `core.fsmonitor`. Through an overlay store neither ran. Metabrowser’s diff commands (`diff/adapters/git.py`, `git/detail.py`) pass neither `--no-ext-diff` nor `--no-textconv`, so this holds for them as written |
| **Reverse direction**: a full mirror exists and a checkout appears | A clonefile copy of the mirror (0.09 s) given the alternates file and `git repack -a -d -l` went from 1,241 MB to **896 KB in 6.3 s**, keeping the 110 objects the checkout lacks |
| An overlay exists and the checkout is about to go | `git repack -a -d` in a store with a shallow boundary: **6.3 s and 346 MB** for the 204,345 objects its refs reach, then the alternates file is removed and `fsck` passes; `--unshallow` completes it for the 8.8 MB above. Without a boundary `repack -a` dies |
| `git clone --reference <shallow checkout>` | Refuses: `reference repository … is shallow`. A manual alternates file is not checked |

### After the Review

The reviewer’s replicas and the revised recipe of [Design](#design):

| Question | Result |
| --- | --- |
| A copied boundary makes **`merge-base` silently wrong** (reviewer, r2): a merge-heavy history cloned at `--depth 3` | The overlay answered A1 where the origin answers A4, and Files changed listed the base branch’s own change beside the pull request’s. The **certainty check** of [Merge Base on a Shallow Store](#merge-base-on-a-shallow-store) flagged it as `uncertain`; one `--deepen=2` round into the store (its own objects; the checkout untouched) made it `certain` at A4 with the correct Files changed. A `--depth 1` linear clone whose merge base is cut: empty answer, `uncertain`, certain after two rounds. The reviewer’s crafted boundary below the merge base: `certain` and correct; the same boundary placed above it: empty answer, `uncertain`. On the real repository all seven fetched pull requests were `certain` in 0.10 to 0.21 s each |
| A **live boundary**: the store’s `shallow` is a symbolic link to the checkout’s | Git reads it; a plain fetch leaves the link; when the checkout deepened the store answered the deeper merge base at once, and when it unshallowed the store stopped being shallow. **Corrected while building step 1:** the store’s own `--deepen` through the link does not replace the link. Git’s lockfile follows it, so on Git 2.50.1 the link stayed and the *checkout’s* `shallow` got a new inode and new contents. An earlier run saw the link vanish only because the checkout was by then unshallowed, and Git unlinks the file for that. The recipe below, a copy before the first round, is therefore what keeps the checkout unwritten, and `tests/test_checkout_overlay.py` pins it |
| Asking GitHub for the merge base instead (`GET repos/<o>/<r>/compare/<base>...<head>`, `merge_base_commit`) | Agreed with the local answer for all seven pull requests; `per_page=1` responses of 26 KB to 536 KB in 0.9 to 1.7 s, since the endpoint embeds every changed file with its patch and has no field selection |
| **Seeded refs** (reviewer, r1 and r4): the checkout’s remote-tracking refs created in the store | Served 70 branches and tags the origin no longer has, and a planted checkout’s `release-2.0` and `v9.9` at the attacker’s commit, until a `--prune` refresh. **Not seeding** and passing the checkout’s tips as `--negotiation-tip` instead, read from `packed-refs` and loose ref files with no Git process in the checkout: the store’s refs after acquisition were the origin’s 262 and nothing else, the planted refs never existed, and a pull-request head the checkout lacks still cost 92 KB (130 haves, 57 acknowledgements). The full acquisition fetch ran at load 36 in 13.3 s with 0 KB of objects; a first fetch pays a connectivity walk over every object its refs reach (327,834 objects, 6.7 s at load 62), and a later fetch’s walk stops at the store’s own refs (0.06 s) |
| **Content addressing on read** (new, replica): an object’s bytes replaced in the checkout under its genuine name, loose and packed, and a forged commit | Git **does not verify hashes on read**: `cat-file --batch` (Metabrowser’s batch reader), `show`, `diff`, and `log` served the forged bytes with no error, a fetch’s connectivity check passed, and only `fsck` reported `hash-path mismatch`; `merge-base` reported `hash mismatch` for the forged commit. Hashing the streamed blob (`sha1("blob <size>\0" + bytes)`) detects the forgery |
| **One dangling non-pull ref wedges every fetch** (reviewer, r3) | `fatal: bad object refs/remotes/origin/feat … did not send all necessary objects` from the healing fetch and from the refresh that would prune it. A **sweep** under the store lock, one `cat-file --batch-check` over every ref and `update-ref -d` of the dangling ones, took 0.12 s on the replica and 0.25 s on a store with the real checkout’s 1,632 refs; the healing fetch and the refresh then succeeded. Negotiation tips are recomputed before each fetch for the same reason: a tip the checkout has since lost makes Git refuse with `the object … does not exist` |
| **Force-push** (reviewer, r5): the shown head replaced upstream, then dropped by the checkout | Fetching the ref alone brought the new head and left the shown commit missing. **Fetching the pinned ID first** (`fetch_commit`) restored the shown commit, and the ref fetch then moved the ref to the new head with the shown commit still readable. When the origin had dropped the old commit too: `upload-pack: not our ref`, a typed `commits_unavailable`, and the ref fetch still brought the current head to offer |
| A lender with its own `objects/info/alternates`; a fork layout; a FIFO | Git follows a lender’s alternates onward (reviewer, r4 d), so such a lender is refused. Tips are read from `refs/remotes/<name>/` of whichever remote matches, and `discover_repository_context` reads only `origin` today. `_read_bounded_text` on a FIFO named `commondir` blocked until killed at 3 s |
| Discovery on the real checkout (reviewer, r8) | The root, a linked worktree, and a subdirectory resolve in 10 to 16 ms; the vendored submodule resolves to its own repository |

### While Building Step 1

The production code on the measured repository, on 2026-11-02 at load averages of 11 to
18, in caches of their own, with `gh` reading each pull request:

| Question | Result |
| --- | --- |
| Four pull requests, by `--checkout` on the checkout and again on a linked worktree | Acquisition 5.4 s, and each `metab <url> --no-serve` 12 to 14 s for the first and 6 to 8 s after it, most of it `gh`: a full mirror’s copy opened the same four in 6 to 7 s each. The store was **1.06 MB**: 266 loose refs at 4 KB each and no object. Files, additions, and deletions matched `gh pr view` for all four, and each comparison’s answer was **byte-identical** to the full mirror’s |
| The operating system refusing every write under the checkout (`sandbox-exec`, `deny file-write*`), including one real `--deepen=2` | Every command above succeeded, the deepening in 2.9 s for 1 MB, leaving the store’s boundary a file of its own and no `shallow.lock` beside the checkout’s. This proves it where a checksum cannot: the checkout was in active use and its `config` changed during a run, from elsewhere |
| A branch pushed between the checkout’s last fetch and an acquisition | The store took **43 MB in 15 s** (21,619 objects, 1,012 commits, a year of history), then the page opened as usual. When every tip is present Git’s `everything_local` skips negotiation and nothing comes. When one is not, the origin walks its history, and a shallow client’s haves stop at its boundary, so what it sends can go back past it. This is the worst measured cost of a first fetch and is bounded only by what the checkout appears to lack, as [Storage Modes](#storage-modes) says. The next acquisition, after the checkout fetched, cost 1 MB again |
| What the sweep is for, in the production refresh | The raw fetch of r3 wedges on any dangling ref, but `update_store` prunes and retries, and a fetch that wants the ref’s object brings it, so a dangling branch heals without the sweep. A dangling `refs/pull/<n>/head` does not, since no refspec of a refresh names it: the refresh and its retry both die. A pull request’s fetch wedges on any dangling ref. The sweep runs before both, as designed |
| `--deepen` through the symbolic link, on a replica | See the correction in [After the Review](#after-the-review): it replaces the checkout’s file, so the store replaces the link first |
| Tips at many refs | Over 40,000 remote-tracking refs the file read took 37 ms and the filter of 4,096 took 64 ms. A fetch ran in 1.4 s with no tips, 1.5 s with 4,096, and 1.8 s with 14,000, and 16,384 failed to start with `Argument list too long` at an `ARG_MAX` of 1 MiB. The measured repository has 327 tips, read in 9 ms |

### Found by the Review of Step 1

Three independent reviews of the step 1 pull request (senior, security, and correctness,
2026-11-02) found these, each fixed in that pull request and recorded here because it
changes what the plan says; the reviews and their dispositions are on the pull request
itself.

| Question | Result |
| --- | --- |
| **A boundary commit’s own diff** (correctness, High) | Git grafts a commit at the boundary into a root, so `<commit>^` does not resolve and the diff adapter compared it against the empty tree, showing a whole tree as added with no warning: on the merge-heavy depth-3 replica, A5 read `+a5` where the truth is one changed line. The same held for a served shallow checkout, and for `git show`, so `/api/git/commit/<id>` counted a whole tree too. **Fixed in one place:** `recorded_parents` reads the parents from the object itself, which the graft never touches; the comparison answers `parent_unavailable`, the commit detail reports its `stats` as unknown, and a real root commit is unchanged. `/api/git/log` keeps Git’s cut graph, which the status route labels shallow |
| **A refresh re-downloads the gap** (senior, High; the bot too) | With the checkout’s tips alone as `--negotiation-tip`, Git offered none of the store’s own refs, so the origin sent again everything the checkout lacked, on every refresh in which those refs moved: on a replica with `transfer.unpackLimit=1`, a branch of 24 commits the checkout never fetched, moved by one commit, cost 75, 78, and 81 objects per refresh. **Fixed:** the commits the swept store’s refs name are tips too, after the checkout’s; the same refresh then costs the one commit’s 3 objects, which `test_a_refresh_brings_only_what_the_store_lacks_and_not_the_gap_again` pins |
| **The lender’s checks ran only with `--checkout`** (security, Medium) | A remembered open and a running server stat’ed the directory and nothing else, so a lender that grew an `objects/info/alternates` after creation had Git follow the chain to a directory nothing recorded. **Fixed:** the cheap local checks run on every open that uses the record and before every fetch, the full check with the remote match at open; the answer is `lender_missing` with the reason, repaired the same way |
| **An unreadable lender was swept** (correctness, Medium) | A present but unreadable lender answered `missing` for every borrowed object, and the sweep deleted every ref, with the fetch failing in the same pass. **Fixed:** the lender’s own remote-tracking tips are read through the store before the sweep; a lender that names some and lends none is refused and the refs stay |
| **A missing ancestor read as `no_merge_base`** (correctness, Medium) | `merge-base` exits 128 when it cannot read a commit on the walk, and that was mapped to “the base and head share no history”. **Fixed:** `commits_unavailable`, the plan’s name, for that case in step 1; healing stays step 2 |
| **A half-written repair** (correctness, Medium; the bot too) | A repair that stopped between the alternates file and the record left a store `damaged` that `--checkout` could not repair. **Fixed:** `--checkout` naming the checkout the alternates file already names finishes the repair, and a repair takes the fetch lock before the store lock, as every fetch does |
| **A served pull head the sweep removed** (senior, Medium) | The refresh swept a dangling `refs/pull/<n>/head`, no refspec of a refresh restores it, and the status then read the ref as gone from the origin, which keeps every pull-request head. **Fixed:** a swept ref is unobserved (`ref_on_origin: null`) until a fetch names it again |
| **The boundary read before Git only** (correctness, Medium; the bot too) | The empty-boundary returns trusted the read taken before Git ran. **Fixed:** read again on every return; a boundary that differs makes the answer uncertain |
| **A stale owned boundary** (correctness, Low) | Once the store owned its boundary, a checkout that deepened or unshallowed left the store shallow. **Fixed:** before a fetch, a boundary the store owns is dropped when the checkout has no shallow file; a missing parent then stops a walk with an error, never a cut |
| **A path-spelled remote** (senior, Medium) | `git clone /x/origin.git` records that spelling, which classified as a local path and never matched a `file://` source. **Fixed:** a path remote is the `file://` source of its resolved path, absolute or relative to the checkout; a lookalike directory and an https source still match nothing |

The follow-up review of the fixes found three more, each fixed in the same pull request:

| Question | Result |
| --- | --- |
| **No common history on Git before 2.45** (High) | A merge-base walk that meets a commit it cannot read exits 1 there, Git’s answer for unrelated histories, where 2.45 and later fail, so the admitted 2.43.7 recorded `no_merge_base` for a collected ancestor. **Fixed:** a store with no boundary believes that answer, and a merge base that is neither tip, only after `rev-list --count` over the same walk, which fails on an unreadable commit on every Git |
| **A partly unreadable lender was swept** (Medium) | The probe of the lender’s tips passed when one loose object or one pack was unreadable and the rest read, and had nothing to probe on a lender whose refs no file holds, as reftable keeps them, so a live `refs/pull/<n>/head` or the default branch was deleted. **Fixed:** a ref is swept only when no loose file of its object exists, whatever its mode, and every file of the lender’s pack directory reads; otherwise `lender_missing` and the refs stay |
| **A repair the disk refused** (Medium) | A permission error while rewriting the alternates file printed a traceback. **Fixed:** an `Error:` line naming the reason; the record is written last, so the store is unchanged or refused as `damaged`, and the same command finishes it |

The scripts and raw outputs of all three sets are kept outside the repository; the
coordinator holds the paths.

A replica is a bare origin, a clone of it as the checkout, and an overlay store, built
in seconds, so every scenario above can become a test fixture.

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

What changes is how the store is filled:

| Mode | Objects | When |
| --- | --- | --- |
| `full` | Every object, fetched from the origin, as today | No checkout is named, or borrowing is refused |
| `overlay` | `objects/info/alternates` names the checkout’s objects directory; the store holds only what the checkout lacks | The reader named a checkout of the repository, or is serving one |

An overlay store is created by `acquire_into_staging`’s sibling in `cache/acquire.py`,
with the same staging entry, locks, validation, and publication:

1. `ls-remote --symref` of the origin’s HEAD, as now.
2. The lender is checked before anything is written ([Storage Modes](#storage-modes) has
   the refusals): it is a Git directory, its `objects` directory is readable, it has no
   `objects/info/alternates` of its own, it is not a partial clone, its object format is
   the origin’s, and a remote of it has the URL’s identity.
3. `init --bare --template=`, the store configuration, plus two keys:
   `core.commitGraph=false`, because the store would otherwise read the checkout’s
   `objects/info/commit-graph`, which can name commits whose objects are gone, and
   `core.alternateRefsCommand=true`, so no fetch runs Git inside the checkout.
4. `objects/info/alternates` holding the absolute path of the checkout’s objects
   directory, which for a linked worktree is the common directory’s.
5. `shallow` as a **symbolic link** to the checkout’s `shallow` file, never a copy, so
   the store’s boundary is the checkout’s current one; where the checkout is not shallow
   the link dangles and Git treats the store as not shallow.
   The boundary is untrusted input and is used only as a cut of the graph; what it may
   and may not affect is in
   [Merge Base on a Shallow Store](#merge-base-on-a-shallow-store).
6. **No ref is seeded.** The mirror’s own fetch of every branch and tag with
   `mirror_fetch_args` runs with the checkout’s remote-tracking tips as
   `--negotiation-tip=<oid>` arguments, so the origin sends only what the checkout
   lacks. The tips are read from the lender’s `packed-refs` and loose files under
   `refs/remotes/<name>/`, with bounded reads and no Git process in the checkout,
   filtered through the store’s own `cat-file --batch-check` to commits it can read, and
   recomputed before every fetch.
   The store’s refs are therefore only ever what the origin sent, as a full mirror’s
   are.
7. The same validation of HEAD and object format as a full clone.

The size check `check_first_clone` makes does not apply: the first fetch is bounded by
what the checkout lacks, which nothing reports in advance, so the acquisition deadline
is its bound. A first fetch also pays one connectivity walk over every object its refs
reach (6.7 s at load 62 for the measured repository), since the store has no refs of its
own yet; every later fetch stops at them.

**Records.** `store.yml` gains an optional `lender` block beside `acquisition`: the
absolute path of the objects directory borrowed, the checkout’s root at creation, and
the remote’s name, for display and for the tips.
Absent means `full`; present means `overlay`. A store with the block and no alternates
file, or the reverse, or an alternates file naming anything but the recorded directory,
is `damaged` and refused.
No version moves: no released version wrote a store with the block, and a 0.12.0 store
without it is a full store, which is what absence means.
`cache/contracts.py` and the conformance corpus gain the field, and
`check_artifact_contracts.py` checks it as it checks the rest.

**What the reader is told.** A store’s mode is visible wherever its location is:

- `metab` prints `borrowing objects from ~/src/repo` where it prints the clone’s
  progress today, and the mirror heading’s tooltip says
  `Mirror of <origin> at <commit>, stored in <location>, borrowing objects from <checkout>`.
- `/api/source/status` carries `borrows`, null for a full store, beside `location`,
  under the same exception that admitted `location`
  ([What a mirror’s page is called](../../architecture/arch-repository-sources-and-provider-mirrors.md#what-a-mirrors-page-is-called-and-where-it-says-it-is-kept)),
  and `shallow`, true when the store has a boundary.
  The path is the user’s own checkout, so the leak argument there applies unchanged;
  `tests/test_serve_pin.py` extends its path-leak check to it.
- `/api/cache/stores` reports `mode` and, for an overlay, the lender’s
  [health](#failure-and-recovery).

### Finding the Checkout

Nothing about a checkout is recorded today, and scanning the disk is out.
The review changed this section: the reviewed design borrowed from whichever checkout
enclosed the working directory, and the reviewer’s r4 showed that the nearest `.git`
wins, that a planted `.git` under any directory the reader stands in can name the
repository’s URL as its `origin`, and that a `.git` *file* pointing elsewhere is
followed too. With [content addressing not enforced on read](#trust), such a lender can
serve any bytes under genuine names.
So the rule is now:

**A store borrows only from a checkout the reader named or is serving.** Two ways, and a
memory:

| How | Command | What happens |
| --- | --- | --- |
| **Named.** `--checkout PATH` names it from anywhere. The path, or a worktree of it, must be a checkout with a remote whose identity is the URL’s, or the command refuses and says which repositories it found | `metab https://github.com/owner/repo/pull/123 --checkout ~/src/repo` | The checkout is checked, the overlay is created, and the lender is recorded |
| **Served.** `metab <checkout>` serves it trusted; a pull request opened from there whose commits need fetching creates the overlay of that same checkout (Pulls tab plan step 5, as revised here) | `metab ~/src/repo` | The same, from the folder server |
| **Remembered.** Once a store borrows from a checkout, `objects/info/alternates` and the `lender` record are the memory. Every later `metab <url>` for that repository, from any directory, uses it | `metab https://github.com/owner/repo/pull/124` | Nothing is checked beyond the lender’s [health](#failure-and-recovery) |

The working directory borrows nothing by itself.
When `metab <url>` runs inside a checkout of the URL’s repository and no store exists,
it clones a full mirror as it does today and prints, once, the `--checkout` command that
would borrow instead: the reader decides, and nothing is remembered that the reader did
not name. Item 2 of [Open Decisions](#open-decisions-for-the-user) records the
alternative and what it would cost.

Precedence: a published store for the source wins, whatever its mode, so a URL never
silently changes storage; then `--checkout`. `metab <url> --checkout` when a full mirror
already exists uses the mirror and prints the conversion command
([Conversions](#conversions)), as item 4 of the decisions settled.

**Which remote.** `discover_repository_context` reads only `origin` today.
The check reads every `remote.<name>.url` and accepts the checkout when any remote’s
identity is the URL’s, compared through the plugin’s grammar and therefore
case-insensitively; the tips come from that remote’s namespace alone,
`refs/remotes/<name>/`, so a fork checkout with the repository as `upstream` lends its
objects, and a fork’s own branches are never negotiation tips.
Which remote names the repository for the *list* is still the Pulls tab plan’s decision
1; this only decides whose objects are borrowed.

The Pulls tab plan’s rule “Nothing about the checkout is recorded: no path, no branch”
stays true for the shared records under `sources/<slug>/pulls/`, which a checkout and a
mirror share, and for the `unattached` source.
It is changed for a store: an overlay store records the one path Git itself records
beside it, and the remote’s name.

### Workflows

Exact commands, both scenarios, with what each does and costs as measured.

**A pull-request URL with nothing local.** Unchanged from 0.12:

```shell
metab https://github.com/owner/repo/pull/123
```

A full mirror is cloned (185 s and 1.2 GB for the measured repository), the pull
request’s record is read with `gh`, its head is fetched, and the page is served under
the forced untrusted profile.

**A pull-request URL when a checkout exists.** Name it once:

```shell
metab https://github.com/owner/repo/pull/123 --checkout ~/src/repo
metab https://github.com/owner/repo/pull/124          # remembered from then on
```

An overlay store is created with no object copied (5 s on a quiet machine with the
earlier recipe, 24 s at load 36 with this one, for the measured repository), the record
is read, the head is fetched (about a second; kilobytes when the checkout lacks it), and
the same page is served the same way.
The checkout is not written.
`metab` says it is borrowing, and from where.
Run from inside the checkout without `--checkout`, `metab <url>` clones a full mirror
and prints the command above.

**A checkout in a linked worktree.** Name any worktree of the repository:

```shell
metab https://github.com/owner/repo/pull/123 --checkout ~/src/repo-feature-x
# .git there is a file: gitdir: …/.git/worktrees/feature-x
```

The borrowed directory is the common directory’s `objects`, which every worktree shares;
the store records that directory, not the worktree.

**Several pull requests.** Any numbered PR is a page of the same server.
Explicit metadata refresh and comparison acquisition are independent of list discovery:

```shell
metab https://github.com/owner/repo --checkout ~/src/repo
# then /pull/123, /pull/124, … in the page, or:
metab https://github.com/owner/repo --api '/api/plugin/github/pull?number=124'
```

A cache-only GET may report an absent record; it does not fetch a PR merely because its
number is addressed.
The browser starts the appropriate background action.

**`metab <checkout>` and finding a pull request from there.** The Pulls tab plan’s steps
4 and 5: the folder server lists and opens pull requests from the shared records.
Its step 5 changes with this plan
([Fit with the Pulls Tab Plan](#fit-with-the-pulls-tab-plan)): Files changed is read
from a store opened or acquired by explicit **Fetch changes**, borrowing the served
checkout without writing to it.
Opening Files alone does not acquire a store, and a borrowing refusal does not fall back
to a full clone. The CLI form is the plan’s own:

```shell
metab ~/src/repo --api '/api/plugin/github/pull?number=123'
metab ~/src/repo --api '/api/plugin/github/pulls?state=open'
```

### Storage Modes

For URL acquisition with `--checkout`, the following mode/fallback rules apply.
The folder server’s **Fetch changes** path is borrowing-only when no healthy managed
store exists; it reports refusal instead of cloning when lending is ineligible:

| Situation | Mode | What the reader is told |
| --- | --- | --- |
| No checkout named | `full` | The clone’s size and progress, as now |
| A named checkout whose remote matches, object format matches, objects readable, no alternates of its own, not a partial clone | `overlay` | `borrowing objects from <checkout>` |
| The checkout is **shallow** | `overlay`, with the live boundary; history views stop where the checkout’s do, status reports `shallow: true`, and every comparison runs the certainty check of [Merge Base on a Shallow Store](#merge-base-on-a-shallow-store) | `history is shallow, as the checkout’s is`. A depth-limited clone, such as a `--depth 50` CI checkout, is the case where a merge base is most often uncertain |
| The checkout is a **partial clone** (`extensions.partialClone`, `remote.<name>.promisor`, or `.promisor` packs) | `full` | `the checkout is a partial clone, which cannot be borrowed from; cloning` — an overlay would find objects missing at read time, exactly what `GIT_NO_LAZY_FETCH` exists to refuse |
| The checkout has its own `objects/info/alternates` | `full` | `the checkout borrows objects itself; cloning` — Git would follow the chain to a directory nothing recorded |
| No remote of the checkout has the URL’s identity | Refused | The refusal names the repositories the remotes point at |
| The checkout’s object format differs from the origin’s | `full` | Named |
| The objects directory is unreadable, or owned by another user | `full` | `the checkout’s objects could not be read; cloning` |
| A full store already exists | `full` is kept | Named. The conversion command is printed once step 3 makes one; until then the line says there is none |

Nothing ever converts a store or changes its mode without a command.

### Merge Base on a Shallow Store

A shallow boundary cuts edges out of the commit graph.
`git merge-base` on the cut graph can answer a commit that is a common ancestor there
but not the best one in the full graph, with no error: the reviewer’s r2 produced A1
where the truth is A4, and Files changed then showed the base branch’s own change as the
pull request’s. `pull_refs.comparison_endpoints` catches only an empty answer today.
A wrong diff shown as right is not acceptable, so the merge base is established by
construction:

**The check.** Let *M* be the local answer.
*M* is certain when every boundary commit reachable from the base or the head is
reachable from *M*: in Git, `rev-list <base> <head> ^<M>` names no commit in the store’s
`shallow` file. Why that suffices: take any common ancestor *X* in the full graph and
walk a full-graph path from a tip toward it on the cut graph; either the path stays
visible, so *X* is a common ancestor on the cut graph and cannot be a proper descendant
of *M* there, or it meets a boundary commit *B* first, and *B* is reachable from *M*, so
*X*, an ancestor of *B*, is an ancestor of *M*. If *X* were a full-graph descendant of
*M*, a path from *X* down to *M* would either stay visible, contradicting *M* being best
on the cut graph, or meet a boundary *B* reachable from *X* and hence from the tips, so
*M* reaches *B* while *B* reaches *M*, a cycle.
So no full-graph common ancestor is a proper descendant of *M*. The argument uses only
that the cut graph is a subgraph of the full one, which holds for any boundary file, a
crafted one included, as long as the objects are genuine; a boundary can only make an
answer uncertain, never certain and wrong.
An empty answer on a shallow store is uncertain, not `no_merge_base`. The check costs
one `rev-list` of the commits since the merge base, 0.10 to 0.21 s on the measured
repository, where all seven pull requests were certain.

**When uncertain.** The store deepens itself from the origin, `fetch --deepen=<n>` of
the base branch and the pull-request head, into its own objects, the checkout untouched,
and checks again, for a bounded number of rounds; the reviewer’s r2 needed one round of
two commits, its depth-1 case two.
Before the first round the symbolic link is replaced by a copy, under the fetch lock, so
the store owns its boundary from then on: with the link in place, Git’s lockfile would
follow it and replace the checkout’s file.
A dangling link is removed for the same reason.
A store-owned boundary can only be a subset of what the checkout later has, which keeps
the cut-graph argument sound.
The whole `--unshallow` of the measured repository cost 8.8 MB, which bounds the rounds
there; a `--depth 1` clone of a large repository is where the rounds would cost most,
and the acquisition deadline bounds them.

**Offline, or still uncertain.** The comparison is `base_uncertain`, a typed state
beside `no_merge_base`: Files changed is not shown, and the page says that the
checkout’s history is too shallow to know what this pull request changed, with the
deepening offered when the network returns.
A guess is never shown.

**Asking GitHub instead.** `GET repos/<o>/<r>/compare/<base>...<head>` carries
`merge_base_commit`, agreed with the local answer for all seven pull requests, and the
record job already talks to `gh`. It is not adopted as the primary: it answers only
online, the response embeds every changed file with its patch and has no field selection
(26 KB to 536 KB here, bounded only by `GH_API_MAX_BYTES`), and it would make a Git fact
depend on the API. Item 3 of the decisions rejected it.

**Verifying counts** against GitHub’s `changed_files`, `additions`, and `deletions`
would have caught r2 but is not a proof: equal counts do not imply the same merge base.
The record does not keep those three fields, so this would change its schema, and step 1
leaves it out: the check above is the guard.

### Failure and Recovery

A commit is immutable; its presence on disk is not.
The realistic loss is precise: a pull request that was squash-merged, whose branch was
deleted upstream, whose remote-tracking ref the checkout then pruned, deleting the ref’s
reflog with it, so that the objects were unreachable at once; a plain `gc` then moves
them to a cruft pack, and `gc` removes them after `gc.pruneExpire`, two weeks by
default. Every other object an overlay depends on is reachable from a ref the checkout
keeps, and ordinary `gc`, `repack`, and `fetch --prune` never remove those.
So the exposure is the pull requests the reader opened whose branches are gone from the
checkout, after two weeks, when the checkout collects garbage; a force-pushed head the
reader saw is the same case.
GitHub keeps `refs/pull/<n>/head` after the branch is deleted and serves a replaced head
by ID while it still holds it, which is what the healing relies on.

| Event | What fails | Detected | Recovery | Page or command |
| --- | --- | --- | --- | --- |
| Objects pruned in the checkout (above) | Reads of that pin: the batch reader answers `missing`, `ls-tree` and `log` fail, `merge-base` fails | **At open**, `cat-file --batch-check` of the pinned commit and its root tree, 24 ms, before the server starts. **In a session**, the next read: every Git failure on a store is already typed (`GitObjectUnavailableError`, `object_unavailable`), never a traceback, pinned by `tests/test_plugin_content_reader.py` | The **healing job**, in order: the sweep below; `fetch_commit` of the pinned ID, so the commit that was shown comes back even after a force-push; then the ordinary fetch of `refs/pull/<n>/head`. Proven on the reviewer’s r3 and r5 | `this pull request’s commits are no longer in the checkout; fetching them from GitHub`, then re-render. If GitHub no longer serves the shown commit: `commits_unavailable`, with the conversation and reviews from the record and the current head offered |
| A dangling ref of any kind in the store, a pruned branch the origin had deleted | Every fetch, the healing one and the refresh that would prune it: `bad object … did not send all necessary objects`; `for-each-ref` and `log --all` fail | The **sweep**: before any fetch into an overlay, under the store lock, one `cat-file --batch-check` over every ref, and `update-ref -d` of each dangling one. 0.25 s at 1,632 refs | A refresh restores any swept ref the origin still has | None; it is a step of every fetch |
| The checkout is repacked | Nothing | — | — | — |
| The checkout’s history made shallower | As pruned | As pruned | As pruned | As pruned |
| The checkout moved or deleted, or can no longer lend: it grew an `objects/info/alternates` of its own, its objects stopped being the reader’s to read, or its directory holds another repository | Every read of a borrowed object; a fetch too; a chain of alternates would read a directory nothing recorded | **At open**, the checks that admitted the lender run again (the stat, the alternates refusal, the ownership and readability checks, then the remote match): `lender_missing` with the reason, in step 1. **Before every fetch**, the cheap local checks again, and the lender’s own remote-tracking tips are read through the store: a lender that names some and lends none is unreadable, and nothing is swept; nor is a ref whose object the lender may still hold (a loose file of it, or a pack it cannot read), which covers a lender with no ref files | `--checkout <new path>` rewrites `objects/info/alternates` and the record after checking the remote, under the fetch lock and the store lock, and finishes a repair that stopped before its record; otherwise re-acquire as a full mirror, which is a new clone. A conversion before deleting the checkout avoids both ([Conversions](#conversions)) | `metab` refuses to serve and prints both commands with the recorded path; `/api/cache/stores` reports `lender_missing`; a running server answers `object_unavailable` for borrowed objects and the status route reports `lender_missing` on its next refresh |
| An ancestor the checkout collected, which the store never held | `merge-base` cannot read a commit on its walk | The record’s `unavailable.comparison` is `commits_unavailable`, in step 1; `no_merge_base` is only Git’s own answer that two commits share no history | The healing job, step 2 | The page says a commit of the pull request’s history is not readable here |
| A served `refs/pull/<n>/head` the sweep removed | Nothing it reads; the ref is gone until a fetch names it | The refresh reports what it swept | The companion’s pull fetch brings the ref and its objects back | The status route reports the ref as unobserved (`ref_on_origin: null`), never as removed by the origin, which keeps every pull-request head |
| `gc` in the store | Never runs | — | — | — |

“No object Metabrowser showed is ever lost” is kept for a full store and relaxed for an
overlay to: **no object Metabrowser showed is lost while the checkout keeps it or GitHub
still serves that commit.** A dangling pin is a typed state, repaired by the healing
job, and never a blank page.
That relaxation is item 1 of the decisions, which the owner accepted.

### The Rule This Changes

Three written rules say an overlay is not allowed or read the checkout instead:

- The Pulls tab plan,
  [Local Checkouts](plan-2026-10-01-github-pulls-tab.md#local-checkouts): “The
  alternates option … is left out at first: a `gc`, a repack, or a move of the user’s
  repository can remove objects the borrowing store depends on, which breaks the rule
  that no object Metabrowser showed is ever lost.”
- The same section’s Files changed case: “The commits are in the checkout.
  The page checks for the base and head commits with a read-only Git command and shows
  the diff through the existing comparison route”, which reads the checkout directly.
- [Shared Repository Store](../../architecture/arch-repository-sources-and-provider-mirrors.md#shared-repository-store):
  “repository content is self-contained: every object is present, and nothing depends on
  alternates into a user-owned checkout or on the origin after acquisition”.

All three rest on the thin-mirror principle “No Git object is deleted in v1”, which is
about Metabrowser’s own store and stays true: an overlay store still never runs `gc`,
`prune`, or `repack`.

The user’s argument is that history is immutable.
The experiments say how far that holds: the objects are immutable and GitHub keeps every
pull-request head, so what is lost locally is recoverable from the origin while the
origin holds it; but presence in the checkout is a function of the checkout’s refs and
`gc`, and the squash-merge and force-push cases lose exactly the pull request’s own
commits after two weeks.
A repack loses nothing.
A move loses everything until the path is fixed.
And immutability of objects is not verified on read, so borrowing trusts the checkout’s
bytes as a served folder is trusted.

The rejection was right about the mechanism and wrong about the consequence.
The consequence is a typed state with a one-second repair, not a lost object, because
the ref that names the object is the origin’s and the origin keeps it.
The recommendation is to adopt the overlay for a checkout the reader names or serves,
keep the full mirror as the default otherwise, read a checkout’s objects only through an
overlay, and rewrite the three rules as [Docs](#docs) lists.
The cost of not adopting it is the one the user named: 185 s and 1.2 GB duplicated for
the measured repository, and more for larger ones, every time a reader wants a pull
request beside a checkout they already have.

### Trust

The same rules in both scenarios, and one boundary the review sharpened.

- **A lender is trusted as a served folder is.** Git does not verify an object’s hash
  when it reads it: a forged loose object, a rewritten pack entry, and a forged commit
  in a replica checkout were served by `cat-file --batch`, `show`, `diff`, and `log`
  with no error, and only `fsck` noticed.
  So “content addressing makes borrowing safe” is false on read: the checkout’s bytes
  are trusted, and whoever can write the checkout can decide what a pull request’s files
  look like. That is already true of `metab <checkout>`, whose Git tab reads the same
  objects, and it is why a store borrows only from a checkout the reader named or is
  serving, never from one found by walking up from the working directory, which the
  reviewer showed is attacker-choosable.
  The refs and the boundary are not what makes borrowing safe either: the store’s refs
  are only what the origin sent, and the boundary can make a merge base uncertain but
  never certain and wrong.
- **Blob verification, as defense in depth.** The batch reader can hash every blob it
  streams from an overlay, `sha1("blob <size>\0" + bytes)` against the name, and answer
  `object_corrupt` on a mismatch, which turns a damaged or dishonest checkout into a
  typed state for file views at the cost of one hash per read.
  Diffs are composed by Git and cannot be verified this way.
  It is item 6 of the decisions, measured in step 2.
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
- **The checkout’s configuration is never read.** Reading a borrowed object is a file
  read of the checkout’s packs and loose objects; Git consults only the borrower’s
  configuration. The replica set `diff.external`, `core.fsmonitor`, `core.hooksPath`, and
  `core.sshCommand`: direct reads with `--git-dir=<checkout>` ran the external diff,
  while the same reads through the overlay ran nothing.
  Metabrowser’s own diff commands pass neither `--no-ext-diff` nor `--no-textconv`, so
  reading a checkout directly would honor its drivers; this is why Files changed on a
  folder server reads the overlay too.
- **No Git runs inside the checkout, ever.** `core.alternateRefsCommand=true` makes
  Git’s alternate-refs read a no-op, the negotiation tips come from files, and the
  remote’s identity comes from the configuration file as `discover_repository_context`
  reads it. The one new file read, `packed-refs` and `refs/remotes/<name>/`, is bounded
  as the existing ones are, and every such read first checks that the path is a regular
  file, so a FIFO in a planted `.git` cannot block it; that check is added to
  `_read_bounded_text` for the reads it makes today as well.
  A checkout using reftable yields no tips and pays the first-fetch cost rather than
  fail.
- **Network and credentials** are the mirror’s: `origin_git_args` with `gh` as the only
  helper, `HOME=/dev/null` for curl, the stall bound, and the acquisition deadline.
  A fetch into an overlay sends the checkout’s remote-tracking tips as haves, which name
  commits of the origin; a tip the origin does not have is ignored by the server, and
  one the store cannot read is filtered out before the fetch.
  Nothing about the checkout’s local branches leaves the machine.
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
- **Step 5 is decided one way.** Files changed on a folder server reads an overlay store
  of the served checkout, in both of the plan’s cases: when the commits are in the
  checkout the overlay already has them and the fetch brings nothing; when they are
  missing, the fetch brings kilobytes.
  The plan’s direct read of the checkout is withdrawn, because it would honor the
  checkout’s diff drivers and could not bring missing commits, and its full clone is
  withdrawn, because it is no longer needed.
  The plan’s rules hold: the network is used only when the reader opens a pull request’s
  Files changed, nothing is written to the checkout, and the folder server serves the
  checkout trusted while the diff is text.
  Acquisition inside a running folder server is still the new thing the plan names; the
  clone is not. The plan’s decision 4 and its Files changed case point here.
- **The page on a checkout** keeps the plan’s behavior: no pin, no Browse code; the
  working tree is not the pull request’s code.

### Conversions

Both directions, explicit, never automatic, each one command on a store under its lock
with the server stopped, since `repack` rewrites packs:

| Direction | Command | What it does | Measured |
| --- | --- | --- | --- |
| Full → overlay, a checkout is named | `metab --api /api/cache/store-borrow --data borrow.json`, the file holding `{"source": "...", "checkout": "~/src/repo"}` | Checks the checkout as creation does, writes the alternates file, the link, and the record, runs `git repack -a -d -l`, which drops every local object the checkout has | 1,241 MB → 896 KB in 6.3 s |
| Overlay → full, the checkout is going away | `metab --api /api/cache/store-dissociate --data dissociate.json`, the file holding `{"source": "..."}` | Replaces the link by a copy, `git repack -a -d` copies the reachable borrowed objects in, then removes the alternates file and the record. A shallow boundary stays until `mb-dqvj` deepens it | 346 MB in 6.3 s, then 8.8 MB to unshallow |

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
| Overlay acquisition from `--checkout`, and remembered | `metab <url> --checkout <path> --api /api/source/status`, then without the flag | A new tryscript over a `file://` origin, a clone of it as the checkout with a linked worktree, and the stand-in `gh`; pins `borrows`, `mode`, `shallow`, that the store’s refs are the origin’s and only those, and that nothing under the checkout’s `.git` changed, byte for byte, with the directory read-only |
| `metab <url>` inside a checkout without `--checkout` | `--api /api/source/status` from inside the fixture checkout | The same tryscript: a full store, and the printed `--checkout` suggestion |
| `store.yml` with `lender`; `/api/cache/stores` with `mode` and lender health | `--api /api/cache/stores`, `--api /api/cache/source` | `cli-api-cache.tryscript.md` gains overlay rows, `lender_missing`, and the `damaged` mismatch |
| The refusals: partial clone, own alternates, no matching remote, object format, unreadable objects, existing full store | `--checkout` on each | The same tryscript; each refusal’s text |
| A fork checkout: tips from the matching remote’s namespace | `--checkout` on a fixture with `origin` a fork and `upstream` the repository | The tryscript; the fake `git` wrapper logs the `--negotiation-tip` arguments |
| A shallow checkout: `certain`, `uncertain` then deepened, `base_uncertain` offline, an empty answer | `--api '/api/plugin/github/pull?number=<n>'` and the comparison route on the reviewer’s r2 graph at depth 3 and depth 1 | An in-process transcript over those fixtures: the state per round and the diff after; the mutation check breaks the `rev-list` filter and sees the wrong merge base served |
| The sweep | A fixture store with a dangling branch ref, then `--api /api/source/refresh` | The in-process transcript: the swept names, then the refresh’s success |
| A dangling pin: at open and in a session, after a prune and after a force-push | `metab <url> --api '/api/plugin/github/pull?number=<n>'` after the fixture prunes the objects; a served-session test | An in-process transcript using the replica scenarios: the typed state, the by-ID fetch, the ref fetch, the page after; and `commits_unavailable` when the stand-in origin lacks the commit |
| The pull request’s page, Files changed, View file on an overlay | `--show /pull/<n>/files`, the comparison route | `cli-github-pull.tryscript.md` run over an overlay fixture as well as a full one, with identical model lines |
| Conversions | The two cache routes | A tryscript that converts both ways and reads the same pull request before and after; `fsck --connectivity-only` passes after dissociation |
| Trust on a folder server with an overlay beside it | `metab <checkout> --api …` for every route | `tests/test_serve_pin.py`’s path-leak check extended to the lender path; a new test that no pull-request blob is served as a page under the trusted profile |
| Blob verification | `--show` of a file whose object the fixture forged | An in-process transcript: `object_corrupt`, with the mutation check removing the hash |

**Tests that guard the rules.**

- The checkout’s `.git` is byte-for-byte unchanged after creation, every fetch, a
  conversion, and a served session, and all of it passes with the directory read-only.
- No Git process runs with the checkout as its repository, at creation or after: the
  fake `git` wrapper used by the process tests logs every `--git-dir` and `GIT_DIR`.
- The hostile-configuration replica (`diff.external`, `core.fsmonitor`,
  `core.hooksPath`, `core.sshCommand`) leaves no marker file after every route of a pin
  server and of a folder server with an overlay.
- A store whose alternates file disagrees with its record is refused.
- A planted checkout under the working directory is never borrowed from without
  `--checkout`.
- A FIFO in the place of `commondir`, `HEAD`, `packed-refs`, or a loose ref does not
  block discovery or the tips.
- Rules from the v0.12 test review apply: standard output and error pinned separately,
  no source-text assertions, mutation checks on every guard.

**Measure before any bound is set.**

- The first fetch’s connectivity walk on checkouts larger than the measured one, to
  decide whether it needs its own progress line; 6.7 s at load 62 here.
- The deepening rounds: how many and how large on depth-limited clones of large
  repositories, to set the round bound and whether deepening runs in the open path or
  only as a job.
- The cost of the open check on a store with many `refs/pull/` heads, to decide whether
  only the pin or every pull-request head is checked at open.
- The sweep and the tips on a checkout with tens of thousands of refs (0.25 s and 0.6 s
  at 1,632 here).
- Blob verification: the hash per streamed blob against the batch reader’s budget.
- Startup pairs on a plain folder and on a served pin, within 1.1x, since the lender
  check adds a stat to a pin’s open and nothing to a folder.

## Delivery

The implemented scopes below are present on
[`main` at da87bb13](https://github.com/jlevy/metabrowser/commit/da87bb13c4434324af576b554711278139621b6b).
The
[postlanding integration review](https://github.com/jlevy/metabrowser/pull/297#pullrequestreview-5770654024)
records their current source and acceptance evidence.
Conversions and broader deepening remain future work; merging the implemented subset
does not complete those steps or publish a release.

| Step | Implemented scope or remaining work | Owning evidence |
| --- | --- | --- |
| 1. Overlay acquisition | Explicit URL borrowing, lender admission, shallow certainty, safe ref sweep, and typed refusal | [#283](https://github.com/jlevy/metabrowser/pull/283) |
| 2. Healing and verification | Explicit retry of observed missing/corrupt objects; complete bounded blob verification; partial windows keep their limits; immutable displayed pairs remain selected | [#283](https://github.com/jlevy/metabrowser/pull/283), [#288](https://github.com/jlevy/metabrowser/pull/288) |
| 3. Conversions | Full-store/overlay repack routes are not implemented | [Conversions](#conversions), future work |
| 4. Overlay inside the folder server | Recognized main/linked/subdirectory checkouts read shared metadata; Fetch changes acquires explicitly without changing the folder root or its checkout | [#288](https://github.com/jlevy/metabrowser/pull/288) |
| 5. Broader deepening | Unshallowing as an independent measured background feature remains outside the bounded certainty recovery path | `mb-dqvj`, future work |

Repair can still be unavailable: the origin may no longer serve an old object, missing
ancestry may prevent negotiation, or a missing pinned root tree may prevent startup
before a page can offer repair.
No full clone, full-store scan, or checkout write is implied by recovery.

### Original delivery estimate

The following table records the 2026-11-02 design estimate.
Its shipping order, automatic-healing wording, and cost estimates are historical, not
current promises. The implementation table above and current architecture define the
accepted behavior.

| Step | Scope | Checkpoint a person can see | Needed for the user’s goal | Ships |
| --- | --- | --- | --- | --- |
| 1. Overlay acquisition | `acquire.py`’s overlay path from `--checkout` only; the lender check and every refusal, with `lender_missing` and its text at open, and the same checks again on every later open and before every fetch; the remote match across all remotes, a path-spelled remote included; tips from files and the store’s own refs as `--negotiation-tip`, with the FIFO guard; the live boundary, dropped once the checkout has none; the sweep before every fetch, only when the lender lends; the certainty check, deepening, `base_uncertain`, and `commits_unavailable` for an unreadable ancestor in `pull_refs.py`; a boundary commit’s diff refused as `parent_unavailable`; `lender` in `store.yml` and its contract; `borrows`, `shallow`, and `mode` in the routes and the heading; the printed suggestion inside a checkout | `metab <pull-request URL> --checkout <path>` serves the pull request in seconds with no object copied and says so; the reviewer’s r2 and r4 fixtures answer `uncertain` and serve no planted ref | Yes | 0.12.x, after 0.12.0 is tagged; it adds a mode and touches no served behavior of a full store but one documented fix, a boundary commit’s diff, which the regenerated transcripts show |
| 2. Healing and verification | The healing job (sweep, by ID, then the ref), `commits_unavailable` when GitHub no longer serves a shown commit, blob verification, the replica fixtures and their scenarios. `--checkout` as repair moved into step 1, because the refusal prints it and a printed command must work; so did `commits_unavailable` for an ancestor the checkout collected, because `no_merge_base` was a false statement there | Prune the fixture, open the pull request, watch it heal; force-push and watch the shown commit come back; move the checkout, see the refusal and fix it | Yes | 0.12.x, with step 1 or just after |
| 3. Conversions | The two cache routes and their repacks | Convert the measured mirror to an overlay and back | No; it is how an existing full mirror stops duplicating | After 0.12.x; small |
| 4. Overlay inside the folder server | The Pulls tab plan’s step 5 as decided here: acquisition from a running folder server into an overlay of that checkout | Open a checkout, open a pull request, read Files changed from the overlay | No; it needs the Pulls tab stack | With that stack |
| 5. Deepening | `--unshallow` as a background job with a measured bound, beyond what uncertainty needs | A shallow overlay’s history completes itself | No | `mb-dqvj`, later |

Size: step 1 is the largest, larger than the thin-mirror plan’s acquisition step: a
second acquisition path through the same staging and publication, a file reader for
refs, a sweep, a certainty check with a deepening loop and two typed states, a flag, a
record field, three route fields, and three tryscripts.
Step 2 is mostly tests, the job’s ordering, and one hash.
Steps 3 and 5 are each a route and a transcript.

**Backward compatibility requirements**, per
`tbd guidelines backward-compatibility-rules`:

- **Internal code:** DO NOT MAINTAIN. One acquisition module with two paths; no shim.
- **Server APIs:** DO NOT MAINTAIN. `borrows`, `shallow`, `mode`, and the new states are
  added everywhere in one commit; nothing reads the old shapes.
- **File formats:** N/A for migration.
  `lender` is optional in `store.yml`; absence is a full store, which is what every
  0.12.0 store is. No version moves and no second reader exists.
- **Library, plugin, persisted client state, database:** N/A.

## Docs

For a documentation agent, after step 1 and again after step 2:

- `docs/command-line.md`: the two scenarios under “Pull requests” with the exact
  commands above, `--checkout`, what `borrowing objects from` means, the shallow note
  with `base_uncertain`, the printed suggestion, and `borrows` and `shallow` in the
  status envelope’s field list.
- `docs/project/architecture/arch-repository-sources-and-provider-mirrors.md`: the
  self-contained invariant under “Shared Repository Store” rewritten for two modes; the
  `lender` field in the cache record contracts table; the overlay’s acquisition, the
  sweep, and the healing order in the acquisition and refresh state machines; `borrows`
  and `shallow` under “What a mirror’s page is called”; the merge-base certainty rule
  under “Pull-request records”; a note under “Read path and performance” that the diff
  commands pass neither `--no-ext-diff` nor `--no-textconv`, and what that means for a
  served checkout.
- `docs/project/architecture/arch-views-models-routes.md`: parity rows for the new
  fields, states, and routes, with their goldens.
- `SECURITY.md`, Content Trust Model: a named checkout as a read-only object source
  whose configuration is never consulted and whose bytes are trusted as a served
  folder’s are, with blob verification once it exists.
- `docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md`: already points here
  from “The alternates option”, the Files changed case, and decision 4; its step 5 text
  is rewritten when step 4 above starts.
- `docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md`: a one-line note under
  Principles that “No Git object is deleted in v1” applies to Metabrowser’s own store
  and that this plan says what an overlay borrows.
- `docs/qa-v012-repository-library.md`: a part for the checkout scenario, including a
  linked worktree, a shallow clone, and a pruned pull request.
- `CHANGELOG.md` for each step.
- `docs/project/README.md`: this plan in the active list, done with this document.

## Risks

- **The alternates file is a hard dependency.** A moved or deleted checkout stops every
  read until it is fixed, and a fetch cannot heal that case.
  The open check turns it into a refusal with the repair command rather than a failing
  page. Conversion before removing a lender remains a planned feature, not a recovery
  command available today.
- **Git’s behavior with alternates is relied on in four places** that could change
  between versions: `everything_local` skipping a fetch whose tips are present, the
  re-want of a missing local object, `repack -l`, and the lockfile rename over a
  symbolic link. Each has a test on the replica, so a Git upgrade that changes one fails
  a test rather than a reader.
  The acquisition Git floor already pins the versions admitted.
- **The checkout’s bytes are trusted.** Git verifies nothing on read.
  The named-checkout rule and blob verification bound it; diffs remain Git’s word.
- **A stale commit-graph in the checkout** would make history walks lie;
  `core.commitGraph=false` in the store prevents it, at a measured cost of nothing on
  merge-base and short logs.
  Long history views on a very large repository may be slower than on a full mirror,
  which the performance pairs in step 1 measure.
- **Deepening is network work in the comparison path.** It runs as a job the comparison
  starts, bounded in rounds and by the acquisition deadline, and `base_uncertain` is
  what the reader sees meanwhile and offline.
- **Two servers, one overlay.** A pin server and a folder server with an overlay can
  fetch into the same store; the fetch lock already serializes writers across processes,
  and the sweep runs under it.
- **Disk accounting.** `du` of an overlay understates what it depends on; the cache
  routes report the lender so a reader is not misled.

## Independent Review

Reviewed 2026-11-02 (`mb-shwd`), verdict **sound with changes**, with replica scripts r0
to r8 that the revisions were proven against.
What the reviewer checked and found solid stands unchanged: content addressing as the
basis of borrowing (narrowed by the read-verification finding below),
`core.commitGraph=false`, `core.alternateRefsCommand=true`, that no `refs/replace`,
grafts, or lender configuration are read through alternates, and a concurrent repack in
the lender during reads.

| # | Finding | Disposition | Evidence |
| --- | --- | --- | --- |
| 1 | **Blocker.** A copied shallow boundary makes `merge-base` silently wrong, not empty (r2); after the owner deepens the checkout the stale copy stays wrong; depth-N clones are the unsafe case; offline must not guess | Fixed by construction: the certainty check, deepening the store when uncertain, `base_uncertain` offline; the boundary is a live link, replaced by a store-owned copy only when the store deepens; depth-limited clones named as the unsafe case. Asking GitHub was evaluated and kept as an option, not the primary | r2 flagged and resolved in one round; depth-1 in two; seven real pull requests certain; GitHub’s merge base agreed for all seven; link follows the checkout’s deepening and unshallowing |
| 2 | **Blocker.** Seeded refs are published as the origin’s (r1: 70 phantoms; r4: a planted branch and tag at the attacker’s commit, remembered from any directory); a lender found from the working directory is attacker-choosable; the lender’s `shallow` is hostile input | Fixed: no seeding; tips from files as `--negotiation-tip`, recomputed per fetch; borrowing only from a named or served checkout; the boundary used only as a cut, which cannot make a wrong answer certain. Read-verification tested and found absent in Git, so the trust model says the checkout’s bytes are trusted and blob verification is added | Store refs equal the origin’s, phantoms 0, planted refs absent; a lacking head still 92 KB with 130 haves; forged loose, packed, and commit objects served by every read, caught only by `fsck` |
| 3 | **High.** One dangling non-pull ref wedges every fetch, including the refresh that would prune it (r3) | Fixed: the sweep before every fetch, under the store lock | r3: heal and refresh fail without it, succeed after; 0.25 s at 1,632 refs |
| 4 | **High.** After a force-push, healing by ref cannot restore the shown commit (r5) | Fixed: fetch the pinned ID first, then the ref; `commits_unavailable` when the origin lacks it; the relaxed rule narrowed to “or GitHub still serves that commit” | r5: shown commit restored, ref moved; origin without it: `not our ref`, current head offered |
| 5 | **Medium.** The loss window is two weeks (`gc.pruneExpire`), not 30 days; `fetch --prune` deletes the reflog with the ref; a cruft pack holds the objects meanwhile | Fixed in the text and the exposure estimate | r3 and the reviewer’s run |
| 6 | **Medium.** Files changed on a folder server contradicted the Pulls tab plan’s direct read of the checkout; the diff commands pass neither `--no-ext-diff` nor `--no-textconv` | Decided: the overlay, in both plans; the flag facts recorded with the file names | The earlier `diff.external` replica; the plan’s Files changed case now points here |
| 7 | **Medium.** Step 1 shipped without the lender check, so a moved checkout answered `object_unavailable` with no message | Fixed: the stat and the refusal text are in step 1 | — |
| 8 | **Medium.** Discovery matched `origin` only, so a fork checkout fell to a full clone | Fixed: any remote whose identity is the URL’s, case-insensitively; tips from that remote’s namespace | Fork replica: tips from `refs/remotes/upstream/`; `discover_repository_context` reads only `origin` today |
| 9a | **Low.** “0 KB” holds only when the checkout is current | Fixed: “kilobytes” | — |
| 9b | **Low.** `lender_missing` with the working directory a valid checkout of the same origin should repair the path itself | Not adopted: the working directory is attacker-choosable by the same argument as finding 2, so the repair is `--checkout <new path>`, and the refusal prints it with the recorded path | — |
| 9c | **Low.** Refuse a lender with its own `objects/info/alternates` | Fixed | r4 d: Git follows the chain |
| 9d | **Low.** `_read_bounded_text` blocks on a FIFO, and discovery would run on an arbitrary working directory | Fixed: the working directory no longer borrows; every bounded read checks for a regular file first, for the existing reads too | A FIFO as `commondir` blocked discovery until killed at 3 s |
| 9e | **Low.** `extensions.partialClone` belongs in the partial-clone refusal | Fixed | — |

What could not be fixed, and is stated instead: Git trusts a lender’s bytes on read, so
only the named-checkout rule and blob verification bound a dishonest checkout, and a
forged diff is still Git’s word; a crafted boundary can truncate the history a page
shows, which the page labels as shallow; the first fetch’s connectivity walk is
unbounded in the checkout’s size.

## Open Decisions for the User

None is open: the owner decided all six on 2026-11-02, each as recommended here when the
plan was reviewed. The rejected alternatives are kept so a later reader can see what was
weighed.

1. **The no-loss rule is relaxed for an overlay.** No object shown is lost while the
   checkout keeps it or GitHub still serves that commit, with the typed states and the
   healing job of [Failure and Recovery](#failure-and-recovery).
   - *Rejected:* keep the rule as written, which means no overlay and the duplicated
     clone the user asked to avoid.
2. **Only a checkout the reader names with `--checkout` or serves with
   `metab <checkout>` may lend**, remembered from then on.
   Inside a checkout, `metab <url>` clones and prints the flag once.
   The working directory never borrows silently.
   - *Rejected:* also the enclosing checkout of the working directory.
     The reviewer showed that any directory the reader stands in can be made to pass as
     a checkout, and Git does not verify what it reads.
3. **An uncertain merge base deepens from the origin** into the store, bounded in rounds
   and by the acquisition deadline, as a job.
   It reads `base_uncertain` meanwhile and offline.
   - *Rejected:* GitHub’s compare endpoint, which is online-only and heavy; and
     `base_uncertain` only, never resolved.
4. **An existing full mirror is kept** and the conversion command printed, with no
   automatic conversion.
   The disk is the user’s to reclaim.
   - *Rejected:* convert when `--checkout` is given.
5. **`borrows` is shown beside `location`** in the status envelope and the heading
   tooltip, under the same exception.
   - *Rejected:* the cache routes only.
6. **Blob verification comes in step 2**, once the hash per streamed blob is measured
   against the batch reader’s budget.
   - *Rejected:* trust the named checkout as the Git tab does.

## References

- [GitHub Pulls Tab for Mirrors and Local Checkouts](plan-2026-10-01-github-pulls-tab.md)
- [v0.12 Thin Mirror for Git and GitHub Browsing](plan-2026-09-23-v012-thin-mirror.md)
- [Repository Sources and Provider Mirrors](../../architecture/arch-repository-sources-and-provider-mirrors.md)
- [Views, Models, and Routes](../../architecture/arch-views-models-routes.md)
- Git: `gitrepository-layout` (`objects/info/alternates`, `shallow`), `git-fetch`
  (`--negotiation-tip`, `--deepen`, `--unshallow`), `git-repack` (`-l`), `git-config`
  (`core.alternateRefsCommand`, `core.commitGraph`, `gc.pruneExpire`), `git-fsck`

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
