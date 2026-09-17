# Repository Cache Measurements

**Status:** Accepted on 2026-09-16 as the measured basis for the repository-library
contract freeze. The decisions are recorded where the implementation reads them: the
[repository-library plan](../../docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md#phase-0-decisions)
and
[Repository Sources and Provider Mirrors](../../docs/project/architecture/arch-repository-sources-and-provider-mirrors.md#measured-decisions).
The machine-checkable contracts are in `tests/fixtures/repository-cache/`, pinned by
`tests/test_repository_cache_contract_fixtures.py`.

The plan left the cache’s costliest choices to evidence: how to acquire a worktree-free
Git database, what a blobless store does on the v0.10 read routes, how readers and
fetches behave concurrently, and which filesystem and lock primitives the publication
state machines can rely on.
This exploration answers those questions once.
Nothing here runs in CI.

## Method

One development machine: Apple M1 Pro, 10 logical CPUs, 32 GiB, macOS 26.5.2 on APFS,
Python 3.14.7, Git 2.50.1 (Homebrew; Apple’s Xcode Git is also 2.50.1). Every result
file records its environment.
No older Git was available, so version floors come from upstream release notes and
documentation at each tag, cited in
`tests/fixtures/repository-cache/git-version-gates.json`, not from measurement.

Repositories:

- **Small:** `https://github.com/pallets/flask`, 26,353 objects, 12 MiB transferred for
  a full clone, 236 blobs at `HEAD`.
- **Medium:** `https://github.com/python/mypy`, 118,501 objects, 85 MiB transferred,
  1,927 blobs at `HEAD`.
- **Local origin:** a full bare copy of each served through `file://` with
  `uploadpack.allowFilter` and `uploadpack.allowAnySHA1InWant` enabled, so a filtered
  fetch behaves as a hosting provider’s does without network variance.

`measure.py` runs one suite at a time and writes `results/<suite>.json` with the scratch
and home directories replaced by placeholders.
Git runs with no system or global configuration, no prompts, and no inherited `GIT_*`
variables, so a developer’s credential helpers, filter drivers, or maintenance settings
cannot change a result.
Every clone lives under the `--scratch` directory.

```shell
uv --config-file uv.toml run --frozen python explorations/repository-cache/measure.py \
  --scratch "$TMPDIR/mb-repository-cache" --reps 3 acquire
```

| Suite | Question | Repetitions |
| --- | --- | --- |
| `environment` | Which features the installed Git reports | 1 |
| `url` | Which URL spellings reach the same smart-HTTP request | 1 |
| `platform` | Rename, link, and lock semantics; filesystem name limits | 1 |
| `catalog` | Scanning a flat directory of source records | 5 |
| `acquire` | Full versus blobless, backfill, and three layouts, over HTTPS and `file://` | 3, alternating order |
| `prefetch` | Subject prefetch, backfill coverage, and one-request convergence over HTTPS | 2, full and blobless back to back |
| `read` | The v0.10 route argument vectors on full, blobless, and backfilled stores | 5 warm, 1 cold |
| `precheck` | Whether the tree-only change set names every blob a diff route reads | 1 per comparison, 40 comparisons |
| `lazy` | Lazy fetch over HTTPS, against stalled and refused remotes, and in the batch protocol | 1 |
| `autogc` | Per-object lazy fetches over HTTPS with and without automatic maintenance | 2 |
| `concurrency` | Concurrent readers, reader pools, actor latency, cancellation, readers during maintenance | 3 to 10 |
| `fetches` | Same-ref job fetches into a blobless store, compare-and-swap publication, maintenance afterward, and the rejected alternate-staging design | 2 |
| `maintenance` | Automatic maintenance, gc of blobless stores, object retention | 1 to 3 |
| `gitlinks` | Gitlinks in a change set, want-list permission and rejection, and splitting a rejected request | 1, tiny repository |
| `mailmap` | Which store reads load a mailmap and which configuration stops them | 1, tiny repository |
| `umask` | File modes Git writes into a store under different umasks | 1, tiny repository |
| `storeconfig` | Which operations change a store’s configuration, fork sources, hook paths, and retention of a discarded job’s objects | 1, tiny repository |
| `lockdescriptors` | `flock` requests on a separate `open()` versus a `dup()` of a lease descriptor | 1 |

Timings are medians with the observed range.
Network runs moved by up to 2× between repetitions (mypy full clone: 8.8 s and 17.8 s in
consecutive `prefetch` repetitions), so only comparisons taken in the same repetition
carry weight, and no single run is interpreted alone.

`results/read.json` counted `missing` in whole-tree batch reads by substring, which also
matches blob bodies containing that text; its full-store rows therefore show a few
spurious misses (2 for flask, 29 for mypy).
The harness now parses frames.
The authoritative missing counts are the lazy-fetch-disabled rows, whose output has no
bodies, and the `rev-list --missing=print` counts in `results/prefetch.json`. In
`results/acquire.json` the `filter_ignored` field is unreliable because stderr is
truncated to its tail; object counts are the evidence there.

## Results

### Acquisition

Bare layout, median and range of three alternating runs:

| Origin | Full | Blobless | `git backfill` after blobless | Full on disk | Blobless on disk | After backfill |
| --- | --- | --- | --- | --- | --- | --- |
| flask, HTTPS | 2.83 s (2.30–4.28) | 1.75 s (1.57–1.90) | 2.85 s (2.60–2.98) | 13.3 MiB | 4.0 MiB | 14.4 MiB |
| mypy, HTTPS | 11.64 s (11.11–12.58) | 3.46 s (2.83–5.93) | 22.48 s (18.96–34.98) | 100.5 MiB | 15.9 MiB | 103.0 MiB |
| mypy, `file://` | 5.24 s (4.87–10.25) | 1.43 s (0.96–1.47) | 9.47 s (6.25–12.14) | 100.2 MiB | 15.7 MiB | 103.3 MiB |

A blobless clone transferred 3.5 MiB instead of 12.0 MiB for flask and 13.6 MiB instead
of 85 MiB for mypy.

Layout made no measurable difference to cost.
`clone --no-checkout` medians were 3.25 s (flask full) and 15.54 s (mypy full, range
11.60–15.64) against 2.83 s and 11.64 s bare, with overlapping ranges and on-disk sizes
within 1%. It differs in state instead: `core.bare=false` with an empty work tree,
reflogs written under `logs/`, one local branch plus remote-tracking refs, and a fetch
refspec.
`clone --bare` writes every remote branch under `refs/heads/`, no fetch refspec,
and no reflogs. `init --bare` followed by one explicit fetch took 4.21 s (flask) and
13.94 s (mypy) full, because it adds an `ls-remote --symref` round trip to learn the
remote `HEAD`.

Two surprises:

- **`git backfill` does nothing and exits 0 when `HEAD` is unborn.** In the
  `init --bare` layout, before `HEAD` named a fetched ref, backfill finished in 0.02 s,
  spawned no child, and fetched no object.
- **A `file://` origin that has not enabled `uploadpack.allowFilter` silently sends
  everything.** The store recorded `remote.origin.promisor=true` and
  `partialclonefilter=blob:none` but held all 118,501 objects; the only signal is one
  warning line on stderr.

### Blobless convergence over HTTPS

`results/prefetch.json`, two repetitions, each with a full and a blobless clone taken
back to back:

| Measurement | flask | mypy |
| --- | --- | --- |
| Full clone | 3.35 s, 4.01 s | 8.81 s, 17.75 s |
| Blobless clone | 2.06 s, 1.62 s | 3.10 s, 3.23 s |
| Blobs missing, reachable from `HEAD` / all refs | 9,271 / 9,302 | 52,289 / 53,607 |
| Subject prefetch: `HEAD` tree blobs in one request | 230 blobs, 0.93 s, 1.33 s, 4.8 MiB | 1,753 blobs, 2.63 s, 2.56 s, 20.0 MiB |
| `git backfill` | 3.06 s, 2.52 s | 21.76 s, 22.47 s |
| Still missing after backfill (all from non-`HEAD` refs) | 31 | 1,318 |
| Remainder in one request | 0.77 s, 0.71 s | 4.26 s, 3.02 s |
| Listing every missing object (`rev-list --missing=print`) | 0.36 s, 0.32 s | 1.75 s, 1.84 s |
| Every missing object in one request | 9,302 OIDs, 3.41 s, 2.87 s | 53,607 OIDs, 24.86 s, 16.23 s |

- **Backfill covers `HEAD` only.** Git 2.49 through 2.54 document no revision argument;
  2.55 adds one. Every other ref’s blobs remained missing.
- **One explicit object-ID request reaches every ref, which backfill does not.** Its
  time was comparable to backfill plus its remainder (mypy 16.2 s and 24.9 s against
  25.5 s and 26.0 s) and it needed no more space (101.5 MiB against 102.3 MiB after
  backfill alone), but there were only two runs and the one-request fetch always ran
  after backfill, so order effects are not excluded; coverage, not speed, is the
  evidence.
- **The default revision’s content is complete sooner blobless for mypy.** Blobless
  clone plus subject prefetch took 5.8–5.9 s against 8.8–17.8 s full.
  For flask the difference was small and variable: 3.0 s against 3.3 s and 4.0 s, a 1.1×
  and a 1.4× advantage across two pairs, which does not support a claim either way.
  Reaching every object took longer blobless: 4.8–5.8 s against 3.3–4.0 s (flask) and
  21.3–29.7 s against 8.8–17.8 s (mypy).

### Read routes on full, blobless, and backfilled stores

`results/read.json`, mypy, stores acquired from the local origin.
Warm columns are medians of five; the lazy column is one cold run on a fresh copy, so
its fetch count is exact and its time is a lower bound on a real network.

| Route argument vector (invocations) | Full | Blobless, lazy fetch disabled | Blobless, lazy fetch allowed | After backfill |
| --- | --- | --- | --- | --- |
| Inventory, `ls-tree -r -z` (1) | 11.7 ms | 11.0 ms | 9.9 ms, 0 fetches | 10.7 ms |
| Inventory with sizes, `ls-tree -r -z -l` (1) | 16.0 ms | 55.4 ms, sizes absent | **237 s, 1,753 fetches** | 17.9 ms |
| Path identity, `ls-tree -z <oid> -- <path>` (20) | 229 ms | 183 ms | 159 ms, 0 | 197 ms |
| History page, `log --max-count=250 --stdin` (1) | 91 ms | 82 ms | 82 ms, 0 | 91 ms |
| History count, `rev-list --count` (1) | 91 ms | 80 ms | 78 ms, 0 | 87 ms |
| Commit detail without line counts, `show --raw` (20) | 233 ms | 173 ms | 171 ms, 0 | 214 ms |
| Commit detail, `show --raw --numstat -M -C` (20) | 308 ms | 20 of 20 fail, 9.77 s | 1.04 s, 20 fetches | 280 ms |
| Comparison manifest, raw and numstat with `-M50 -C` (40) | 562 ms | 24 of 40 fail, 12.56 s | 1.76 s, 23 fetches | 557 ms |
| Deferred patches, `diff -M50 -C` (20) | 316 ms | 20 of 20 fail, 10.26 s | 1.27 s, 20 fetches | 347 ms |
| Revision content, `cat-file blob` (149) | 1.52 s | 149 of 149 fail, 1.45 s | 8.40 s, 149 fetches | 1.47 s |
| Whole `HEAD` tree through one `cat-file --batch` (1,927 blobs) | 59.3 ms | 60.2 ms, all missing | not run | 64.5 ms |

Refs, history count, tree listing, and path identity never read a blob.
The history page and `show --raw` read none of the commits’ blobs but do read one: a
bare store’s default mailmap is `HEAD:.mailmap`, and with lazy fetch disabled Git
printed `error: unable to read mailmap object at HEAD:.mailmap` and still exited 0 (see
[store reads and file modes](#store-reads-and-file-modes)). This table’s `git_defaults`
run did not detect that, because the harness counted only exit codes.
The diff routes read blobs for line counts and rename detection, and each route
invocation issued exactly one batched lazy fetch.
`cat-file` and size-bearing tree listings issued one fetch per object.
A route that fails with lazy fetch disabled takes 93 ms (flask) to 488 ms (mypy) per
invocation, far longer than the 10–15 ms it takes to succeed on a complete store.
flask showed the same shape: 230 fetches and 10.7 s for one `ls-tree -r -l` against the
local origin.

`results/precheck.json` tested a bounded alternative for the diff routes.
For 40 comparisons, 19 single commits per repository plus `HEAD~50..HEAD` with 168
(flask) and 404 (mypy) changed blobs, it listed the change set with
`diff --raw -z --no-abbrev --no-renames`, checked it with `cat-file --batch-check`, and
fetched exactly the missing blobs in one request.
All four route argument vectors then succeeded with lazy fetch disabled in 40 of 40
comparisons. Listing took 9–22 ms, checking 10–38 ms, and the local fetch 43–226 ms.
The first attempt omitted `--no-renames` and failed on flask’s wide comparison:
porcelain `git diff` enables rename detection by default, and inexact rename detection
reads blobs.

### Lazy fetch against real and failing remotes

`results/lazy.json`, a blobless flask store whose promisor is GitHub over HTTPS:

| Case | Result |
| --- | --- |
| `ls-tree -r -z -l`, 236 entries | 230 requests, 135.3 s, 0.59 s per blob |
| Commit detail, 10 commits | 10 requests, 7.27 s |
| Deferred patches, 10 comparisons | 10 requests, 8.56 s |
| Missing blob, remote accepts and never answers, Git defaults | Still waiting when the harness killed it at 20 s |
| Same, `http.lowSpeedLimit=1`, `http.lowSpeedTime=3` | Failed in 3.13 s |
| Same, remote port refused | Failed in 0.115 s |
| Same, `GIT_NO_LAZY_FETCH=1` or `git --no-lazy-fetch` | Failed in 8 ms, no request |
| Same, `-c remote.origin.promisor=false` | Still fetched, killed at 20 s |
| `cat-file --batch-command` with lazy fetch disabled | `<oid> missing` for `info` and for `contents`, then the next request answered normally |

`remote.origin.promisor=false` does not stop lazy fetch because the repository’s
`extensions.partialClone` still names the promisor remote.

`results/autogc.json` and `results/maintenance.json` record a failure that appears only
with Git’s default automatic maintenance and a real network:

| Case | Result |
| --- | --- |
| HTTPS, Git defaults | 2 of 2 failed at the 51st lazy fetch, after 50 of 236 entries (28.3 s, 27.4 s): `You are attempting to fetch …, which is in the commit graph file but not in the object database` |
| HTTPS, `maintenance.auto=false`, `gc.auto=0` | 2 of 2 succeeded: 230 fetches, no maintenance, 124.7 s and 124.2 s |
| HTTPS, `core.commitGraph=false`, maintenance left on | 2 of 2 succeeded: 230 fetches with 234 maintenance spawns, 129.0 s and 127.9 s |
| Local origin, Git defaults | 3 of 3 succeeded, with 242 maintenance spawns |

Every lazy fetch spawns a detached `git maintenance run --auto`. The failure appears
exactly when the 51st promisor pack exceeds the default `gc.autoPackLimit` of 50, needs
the commit graph, and needs a fetch slow enough to overlap the detached repack;
disabling either automatic maintenance or the commit graph removed it, and a local
origin was too fast to reproduce it.
The mechanism is inferred from those four conditions, not traced inside Git.

### Concurrency, pools, and cancellation

`results/concurrency.json`, mypy full store:

- **Two readers on different full object IDs** (1,927 and 1,335 blobs) finished in 0.063
  s concurrently against 0.116–0.122 s sequentially, byte-identical in 3 of 3.
- **Reader pool scaling** over the 1,927-blob tree: 31.3–31.7 k blobs/s with 1 reader,
  46.7–48.7 k with 2, 54.8–57.2 k with 4, and 45.0–46.4 k with 8.
- **Persistent `cat-file --batch-command --buffer` actor**, `info` plus `contents` per
  blob over 400 blobs: p50 0.033 ms, p95 0.100 ms, p99 0.187 ms alone; p50 0.039 and
  0.041 ms, p95 0.110 and 0.132 ms, p99 0.208 and 0.248 ms with two actors running.
- **Actor restart** to its first response: p50 9.3 ms, maximum 10.0 ms over 10 starts.
- **Cancelling a streaming batch reader** mid-stream: the process exited 0.69 ms (p50)
  after SIGTERM and 0.64 ms after SIGKILL, maximum 0.77 ms over 5 each.
- **Cancelling a mypy clone over HTTPS** 1.5 s in: SIGTERM exited in 4.4 ms (full) and
  5.6 ms (blobless) and Git removed the destination; SIGKILL exited in 1.9 ms and 0.9 ms
  and left the destination with a temporary pack.
- **Readers during maintenance:** four threads repeatedly listing a random historical
  tree and batch-reading 50 of its blobs completed 237 iterations across `repack -a -d`
  (1.23 s) and 220 across `gc --prune=now` (1.35 s) with no failure and no missing
  object. An actor started before maintenance found 200 of 200 objects afterward.

`results/fetches.json` measures the fetch-job design on a blobless flask store with its
default revision prefetched, from a local origin, two repetitions.
Each job fetched the origin’s new branches (60 and then 120 commits with 16 KiB blobs)
directly into the store under `refs/metabrowser/jobs/<job>/`, then published with one
`update-ref --stdin` transaction that compare-and-swapped the public refs and deleted
the job refs.
Four concurrent object-ID fetches of the new tips’ blobs followed, and then
`gc --prune=now`, `repack -a -d`, and `fsck --connectivity-only`.

| Measurement | One job | Four concurrent jobs |
| --- | --- | --- |
| Fetch failures | 0, 0 | 0, 0 |
| Publication outcomes | published | 1 published, 3 already published, twice |
| Job refs left | 0 | 0 |
| Bytes received | 8,520 and 17,480 | 34,356 and 70,002 |
| Packs after fetching, all promisor packs | 3 | 5 |
| `gc --prune=now`, then `repack -a -d` | both succeeded, one promisor pack, no bitmap | both succeeded, one promisor pack, no bitmap |
| Objects missing from all refs, before and after maintenance | 9,072 and 9,072 | 9,072 and 9,072 |

The four concurrent blob prefetches added only one pack, because the later fetches found
the objects already present; how often concurrent object fetches overlap is timing
dependent.

The same run tested the design the jobs replaced, staging each fetch in a separate
repository with the store as an alternate:

| Variant | Result, two of two runs |
| --- | --- |
| Filtered staging fetch, then import into the store | Import failed: `aborting due to possible repository corruption on the remote side` |
| Unfiltered staging fetch, then import | Import succeeded with a non-promisor pack; `gc --prune=now` and `repack -a -d` then failed: `Failed to write bitmap index. Packfile doesn't have full closure` |

A blobless store may receive objects only from its promisor remote.
When every pack is a promisor pack Git wrote no bitmap and reported nothing, so
`repack.writeBitmaps` needs no override.

### Gitlinks and rejected object requests

`results/gitlinks.json`, a tiny repository whose second commit changes four blobs, an
executable, a symbolic link, and a `160000` gitlink:

- The `--no-renames` change set had 11 blob-mode sides and 2 gitlink sides;
  `cat-file --batch-check` reported both gitlink commit IDs missing.
- A want list containing a gitlink failed with `not our ref` under protocol v0 and v2,
  whether or not the origin set `uploadpack.allowAnySHA1InWant`, and fetched nothing.
- A blob-only want list succeeded under protocol v2 without
  `uploadpack.allowAnySHA1InWant`; under v0 without it every blob was refused with
  `Server does not allow request for unadvertised object`.
- After fetching only the blob-mode entries, commit detail, the raw and numstat
  manifests, and patches all succeeded with lazy fetch disabled and wrote nothing to
  stderr; the gitlink appears as a submodule line.
- Splitting a 13-ID list — 11 blobs, the gitlink at position 4, and an ID absent from
  the origin — in halves down to single IDs took 13 requests (sizes 13, 7, 4, 2, 2, 1,
  1, 3, 6, 3, 3, 2, 1) and 0.87–1.00 s locally; it fetched all 11 blobs and rejected
  exactly the gitlink and the absent ID.

### Store reads and file modes

`results/mailmap.json`, a tiny repository with a `.mailmap` at `HEAD`, read from a
blobless store with lazy fetch disabled, from a copy with lazy fetch allowed, and from a
full store, with and without an inherited `mailmap.file`:

| Configuration | Mailmap blob reads | Error on stderr with exit 0 | `%aN` identity |
| --- | --- | --- | --- |
| Git defaults | history page, `show --raw`, and `%aN` | yes | mapped |
| `log.mailmap=false` | `%aN` only | yes, for `%aN` | mapped |
| `mailmap.blob=` | none | no | mapped by an inherited `mailmap.file` |
| `mailmap.blob=` and `mailmap.file=` | none | no | raw |
| All three keys | none | no | raw |

The `%an` and `%ae` placeholders the routes use were raw in every configuration, so
disabling the mailmap changes no current route output.
`log.mailmap=false` added nothing once the other two keys were set.

`results/umask.json`, the modes Git wrote while cloning a blobless store, fetching its
blobs, and running `gc`:

| Git child | Directories | Files | Entries with group or other bits |
| --- | --- | --- | --- |
| umask `022` | 7 at `0755` | 5 at `0444`, 5 at `0644` | 17 |
| umask `022`, `core.sharedRepository=0600` | 1 at `0700`, 6 at `0755` | 4 at `0400`, 1 at `0444`, 4 at `0600`, 1 at `0644` | 8 |
| umask `077` | 7 at `0700` | 5 at `0400`, 5 at `0600` | 0 |

### Maintenance and retention

`results/maintenance.json`, flask:

- A fetch with Git defaults spawned `git maintenance run --auto`; with the store
  configuration it spawned nothing.
- `gc` of a blobless store took 0.16 s, issued no lazy fetch, and kept the promisor pack
  (17,055 objects before and after).
- A fetched commit behind a private ref survived `gc` and `gc --prune=now`. With the ref
  deleted, or fetched without a ref, it survived the default `gc` (the two-week prune
  window) and was removed by `gc --prune=now`.
- Bare stores wrote no reflogs, so reflogs never retain an object in this layout.

Those retention results are for a full store.
A blobless store behaves differently; see
[store configuration, fork sources, and retention](#store-configuration-fork-sources-and-retention).

### Store configuration, fork sources, and retention

`results/storeconfig.json`, tiny repositories from a local origin, one run:

- **Configuration keys.** `init --bare` and the Metabrowser store configuration wrote
  `core.repositoryformatversion`, `core.filemode`, `core.bare`, `core.ignorecase`,
  `core.precomposeunicode`, `core.hookspath`, the maintenance, submodule, and bundle-URI
  keys, and `remote.origin.url`. The first filtered fetch added `remote.origin.promisor`
  and `remote.origin.partialclonefilter`.

- **Snapshot stability.** After that fetch, the SHA-256 of
  `git config --file <config> --list -z` was unchanged by a job fetch into private refs,
  an object-ID prefetch, an `update-ref --stdin` transaction, `gc --prune=now`,
  `repack -a -d`, and a store read.

- **Fork sources.**

| Fetch into a blobless store | Result |
| --- | --- |
| Fork by URL, with `--filter=blob:none` | Succeeded, and wrote `remote.<url>.promisor` and `remote.<url>.partialclonefilter` into the store’s configuration |
| Fork by URL, without the filter | Succeeded without changing configuration; the next `gc --prune=now` failed: `Packfile doesn't have full closure` |
| The same commit through the base repository’s `refs/pull/1/head` and `origin` | Succeeded; configuration unchanged; `gc --prune=now` and `repack -a -d` succeeded |

- **Hook paths.** A `reference-transaction` hook ran on `update-ref` only when
  `core.hooksPath` was unset and the hook was planted in the store’s `hooks/` directory.
  With `core.hooksPath` empty or `/dev/null` no hook ran, and a hook in the process’s
  working directory never ran.

- **Retention of a discarded job’s objects.** A job fetched a branch and, in the
  blobless store, prefetched its new blob; then its job ref was deleted.

| Store | After `gc --prune=now` | After `repack -a -d` | After `prune --expire=now` |
| --- | --- | --- | --- |
| Blobless | commit and blob present | commit and blob present | commit and blob present |
| Full | removed | removed | removed |

  Git never prunes promisor objects, so unreachable objects a blobless store fetched
  stay until an explicit compaction.

### Platform primitives

`results/platform.json` and `results/catalog.json`, APFS:

| Primitive | Result |
| --- | --- |
| `os.rename(dir, existing empty dir)` | **Replaced the empty directory** |
| `os.rename(dir, existing non-empty dir)` | `ENOTEMPTY` |
| `os.replace(file, existing file)` | Replaced |
| `os.link(file, existing file)` | `EEXIST` |
| `os.mkdir(existing)` | `EEXIST` |
| `renamex_np(dir, existing empty dir, RENAME_EXCL)` | `EEXIST` |
| `flock` exclusive, holder SIGKILLed | Second process blocked while held; acquired 2.8 ms after the kill |
| `flock` shared | Two holders coexisted; a third shared request succeeded; exclusive refused |
| `lockf`, then the same process closes an unrelated descriptor for the file | **The lock vanished**; another process acquired it |
| `flock` shared lease held; exclusive non-blocking request in the same process (`results/lockdescriptors.json`) | Through a separate `open()`: refused. Through a `dup()` of the lease descriptor: **granted, converting the lease**, after which another process could not take a shared lock |
| Names | `NAME_MAX` 255, `PATH_MAX` 1024; case-insensitive and Unicode-normalization-insensitive |
| Flat directory scan plus one record read per entry | 100: 1.9 ms; 1,000: 20.9 ms; 10,000: 262 ms |

`results/url.json`: Git’s smart-HTTP client requested the same `/info/refs` URL with and
without a trailing slash, and sent `%72`, `//`, and uppercase path segments verbatim.

## Not Measured

- Linux and Windows rename, lock, and case semantics, and network filesystems; CI runs
  only on `ubuntu-latest`.
- `renameat2` with `RENAME_NOREPLACE`.
- A stall bound on initial acquisition, where the server may send nothing while it
  counts and compresses objects.
- SSH acquisition, prompting, and stall behavior; no SSH credentials were used.
- Git older than 2.50.1, distribution builds with backported fixes, and Git for Windows
  version strings; the lazy-fetch guard in older releases was read from source, not run.
- Convergence requests larger than 53,607 object IDs, and repositories larger than mypy.
- Crash during `gc` or `repack`.
- Browser-side costs of tree indexes and immutable directory listings.

## Disposition

Keep `measure.py`, the results, and this document together as the reproducible record.
The decisions live in the plan and architecture document linked above; change a decision
there, with a new measurement recorded here, rather than editing these results.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
