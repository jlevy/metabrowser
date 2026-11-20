# Reading Another Application’s SQLite Database

**Status:** Recorded on 2026-11-20 as the measured basis for the access rules in
[Tabular Data Browsing and Live SQLite](../../docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md#reading-another-applications-database),
and rerun for the plan’s second and third reviews.
Nothing here runs in CI. The plan’s nondestructive access tests grow from these cases.

A viewer pointed at a browser’s history or an application’s state database is a guest.
This exploration answers, once, what each way of opening such a database reads, what it
leaves beside the file, what it costs the owner, and which values and queries a bounded
reader must handle differently.

## Method

One Linux container: x86_64, 4 logical CPUs, 15 GiB, ext4, Python 3.13.18 with SQLite
3.53.1, the library the repository’s Python environment loads.
Every result file records its environment.

`measure.py` runs one suite at a time and writes `results/<suite>.json` with no machine
paths in it. Each case stages its databases in a fresh folder under `--scratch`, one
folder per access mode where a case compares modes; an owner runs in its own process,
and the reader opens a fresh connection per read.
Run it as an unprivileged user, since a superuser ignores the folder and file
permissions several cases depend on; the script refuses to run as root.

```shell
uv --config-file uv.toml run --frozen python explorations/sqlite-guest-reads/measure.py \
  --scratch "$TMPDIR/mb-sqlite-guest" access contention budget values encoding generation process
```

| Suite | Question |
| --- | --- |
| `access` | What `mode=ro` and `immutable=1` read in each sidecar state, what they leave, and what drops a reader’s locks |
| `contention` | How many of a rollback-journal owner’s commits fail while a viewer reads, under each read policy |
| `budget` | What a progress-handler budget and an interrupt see, and what each kind of page costs in opcodes |
| `values` | Peak memory to preview one 200 MiB value, each query in a fresh process |
| `encoding` | Values JSON or Python’s defaults cannot carry, keyset paging, authorizers, untrusted schemas |
| `generation` | Whether a restarted write-ahead log repeats its size, and whether its header changes |
| `process` | What a killed reader process leaves the owner, whether the race check’s held handle keeps its locks, and what a worker costs to start and to ask |

## Results

### Access

Each database holds 100 committed rows in its main file; an owner adds five more through
the write-ahead log where a case says so.

| Case | `mode=ro` | `immutable=1` |
| --- | --- | --- |
| Write-ahead log, owner not running, writable folder | 100 rows; **creates `-wal` and `-shm` and leaves them** | 100 rows; creates nothing |
| Same, read-only folder | `SQLITE_READONLY_DIRECTORY` | 100 rows |
| Owner running, five commits in `-wal` | 105 rows; creates nothing | 100 rows: **five commits missing** |
| Owner running, its new table not yet checkpointed | Reads | `no such table` |
| Owner killed, `-wal` (20,632 bytes) and `-shm` left, writable folder | 105 rows; **rewrites `-shm`** | 100 rows |
| Same, folder and files read-only | 105 rows | 100 rows |
| `-wal` with frames, no `-shm`, writable folder | 105 rows; **creates `-shm`** | 100 rows; creates nothing |
| Same, read-only folder | `SQLITE_CANTOPEN` | 100 rows |
| Rollback journal, hot `-journal` from a killed writer | `SQLITE_READONLY_ROLLBACK`; journal untouched | **14,585 of 20,000 rows half-updated** |
| `journal_mode=PERSIST`, no transaction open | 100 rows | — |

The idle `PERSIST` journal held 8,720 bytes with its header zeroed, which SQLite does
not treat as hot.

**A checkpoint killed part-way.** A database of 400,000 rows, every row rewritten in
`-wal` by an owner that then died; a second process ran `wal_checkpoint(TRUNCATE)` and
was killed after each of nine delays from 5 to 100 ms, and `-shm` was removed, as a copy
or a sync folder delivers the pair.

| Killed after | Main file alone, `immutable=1` | Private copy of the main file and `-wal`, `mode=ro` | Private copy through a second hard link, which has no log beside it |
| --- | --- | --- | --- |
| 5, 10, 15 ms | 400,000 rows, none rewritten (the old state); `quick_check` ok | 400,000 rewritten; ok | The old state; ok |
| 20, 25, 30, 40 ms | **`database disk image is malformed`** | 400,000 rewritten; ok | **Malformed**, though the copy’s validation passed |
| 60, 100 ms | 400,000 rewritten (checkpoint finished); ok | 400,000 rewritten; ok | 400,000 rewritten; ok |

No read wrote beside the original files.
Which delays tear the file depends on the machine; that a torn file exists does not.

**A closed handle drops the reader’s locks.** The reader, in this process, is inside one
`mode=ro` read transaction; the owner, with no busy timeout, is in another.
Then a file handle opens and closes the database or its `-shm`, 100 bytes read:

| Handle opened and closed by | Rollback journal: owner commits | Write-ahead log: owner’s `wal_checkpoint(RESTART)`, then 2,000 new rows | Reader’s next read |
| --- | --- | --- | --- |
| No one | `SQLITE_BUSY` | Busy; log not restarted | 2,000 rows, `integrity_check` ok |
| Another process | `SQLITE_BUSY` | Busy; log not restarted | 2,000 rows, ok |
| The reader’s own process | **Commits during the read** | **Restarts the log and overwrites it** | **`database disk image is malformed`** |

POSIX record locks belong to a process and a file, so closing any handle on the file
releases every lock the process holds on it
([How To Corrupt](https://sqlite.org/howtocorrupt.html), section 2.2).

Races and links:

- **Owner exits between the stat and the open.** The stat saw `-wal` and `-shm`; the
  owner then closed, checkpointed, and removed both; `mode=ro` recreated them and left
  them.
- **Reader closes last.** With a `mode=ro` reader open when the owner closed, `-wal`
  (12,392 bytes of uncheckpointed commits) and `-shm` stayed after the reader closed.
  Without the reader, the owner removed both.
- **Symlink in another folder.** No sidecar sits beside the link.
  Through it, `mode=ro` read 101 rows and `immutable=1` read 100.
- **Second hard link to a live database.** `mode=ro` through `hard.db` created
  `hard.db-wal` and `hard.db-shm` and read 100 rows, silently missing the commit in
  `app.db-wal`. (Review A on the plan’s pull request saw `SQLITE_IOERR_SHORT_READ` here;
  either outcome is wrong, and which one occurs depends on timing.)
- **Second hard link to a database with a hot journal.** Through `app.db`, `mode=ro`
  refused with `SQLITE_READONLY_ROLLBACK`. Through `hard.db`, both `mode=ro` and
  `immutable=1` read 14,585 of 20,000 rows half-updated with no error, and the lock-free
  read’s validation passed, since no journal sits beside `hard.db`.
- **A held read starves the checkpoint.** With a reader inside one read transaction,
  `wal_checkpoint(TRUNCATE)` reported busy after 300 commits and the log held 3,712,152
  bytes; once the transaction ended, the same checkpoint truncated it to zero.
- **A write-ahead-log commit leaves the main file untouched**: its size, modification
  time, and bytes stayed the same while `-wal` grew from 4,152 to 8,272 bytes.

### Contention

A rollback-journal database of 200,000 rows; the owner commits one row per transaction
with `busy_timeout=0` for four seconds, at three paces, while the viewer reads with a
random pause of 150 to 350 ms between reads (a fixed seed), so its reads do not lock
into phase with the owner.
Each cell is the owner’s refused commits (`SQLITE_BUSY`) of its attempts, then what the
viewer’s reads ended as.
These counts depend on timing and vary between runs; their shape does not.

| Viewer | Back-to-back commits | One commit per 5 ms | One commit per 50 ms |
| --- | --- | --- | --- |
| None | 0 of 4,429 | 0 of 618 | 0 of 77 |
| `mode=ro`, 100-row key-ordered page | 1 of 4,746; 14 of 15 reads refused | 0 of 611 | 0 of 78 |
| `mode=ro`, `count(*)` | 1 of 4,736; all 15 reads refused | 4 of 626 | 0 of 77 |
| `mode=ro`, capped count | 59 of 4,864 | 10 of 615 | 3 of 78 |
| `mode=ro`, page sorted by an unindexed column | 284 of 4,862 | 27 of 613 | 2 of 78 |
| Validated `immutable=1`, key-ordered page | 0; 3 of 15 reads valid | 0; 14 of 15 valid | 0; 15 of 15 valid |
| Validated `immutable=1`, unindexed sort | 0; 0 of 14 valid | 0; 0 of 14 valid | 0; 10 of 14 valid |
| Review A’s policy: a journal means `mode=ro`; else validate, retry once, then `mode=ro`; page and capped count | 131 of 5,078 | 14 of 618 | 0; 14 of 15 valid |
| Review B’s policy: wait out a journal or a failed validation of the page and capped count together for 250 ms, then lock for the key-ordered page alone | 2 of 4,646; 6 of 9 reads writer busy | 0 of 619; 7 of 9 locked page only | 0; 15 of 15 valid |
| Review B’s policy, unindexed sort and capped count | 0 of 4,717; 7 of 9 writer busy | 0 of 619; 6 of 9 locked page only | 0; 14 of 14 valid |
| The plan’s policy: never lock; wait out the page alone for 250 ms, then validate the capped count once with no wait, else send an estimate | **0** of 4,759; 15 of 15 pages valid, every count an estimate | **0** of 632; 15 of 15 pages valid, every count an estimate | **0** of 77; 15 of 15 pages valid, 11 counts exact |
| The plan’s policy, unindexed sort | 0 of 4,900; 1 of 9 valid, 8 writer busy | 0 of 615; 1 of 9 valid, 8 writer busy | 0 of 75; 14 of 14 valid, 12 counts exact |

A validated read takes no lock, so it never fails a commit, but it succeeds only when
the read is shorter than the gap between commits.
Against a back-to-back writer a lock is rarely granted at all, so the locking rows’
refusals there swing widely between runs.
Review B’s policy failed validation whenever the capped count, about 25 ms, outlasted
the gap between commits, and so locked on most reads at 5 ms.
Validated apart, the key-ordered page was valid on every read at every pace, and the
plan’s policy, which never locks, refused no commit.
A sort that scans outlasts the gap as the count does, which is one reason the plan
refuses it past a measured size.

### Budget

- `SELECT count(*)` over 1,500,000 rows runs 9 opcodes.
  With a progress handler every 1,000 opcodes, as `pull_catalog` sets, the handler was
  never called and the full count returned.
- `SELECT count(*) FROM (SELECT 1 FROM big LIMIT 1000001)` runs 7,000,021 opcodes, and
  the same budget stopped it on the handler’s first call.
- Median of five runs over the same 1,500,000 rows: `count(*)` 3.1 ms, the capped count
  25.4 ms, `max(rowid)` under 0.01 ms.
  A capped count holds a lock longer than the count it bounds.
- `Connection.interrupt()` from another thread, 10 ms into one `count(*)` over
  20,000,000 rows that takes 43 ms uninterrupted, stopped it after 10.3 ms.

Opcodes for one 100-row page over 200,000 rows:

| Page | Opcodes |
| --- | --- |
| Key order, first page | 707 |
| Key order, continuation (`id > ?`) | 710 |
| Indexed column, first page | 808 |
| Indexed column, continuation (`(c, id) > (?, ?)`) | 1,222 |
| Unindexed column, first page | 1,404,609 |
| Unindexed column, continuation | 1,904,247 |
| Key order filtered by `LIKE '%…%'` | 800,023 |

### Values

One row holding a 200 MiB text and a 200 MiB blob; peak resident memory of a fresh
process running one query:

| Query | Peak MiB |
| --- | --- |
| Baseline (`SELECT id`) | 20 |
| `substr(v, 1, 100), length(v)` on text | 221 |
| `substr(b, 1, 16), length(b)` on a blob | 223 |
| `length(v)` on text | 221 |
| `length(CAST(v AS BLOB))` on text | 221 |
| `length(b)` on a blob | 20 |
| `octet_length(v)` on text | 20 |
| `typeof(v)` | 20 |
| `Connection.blobopen`, then read 100 bytes of the text | 20 |

### Encoding

- `13390000000000001` survives Python’s JSON but parses in a browser as
  `13390000000000000`.
- `json.dumps(..., allow_nan=False)` refuses an infinite real.
- Text holding the bytes `ff 41` raises `Could not decode to UTF-8` under Python’s
  default text factory.
- **Keyset paging** over an indexed column holding nulls, integers, reals, text, and
  blobs, under every declared type and `COLLATE NOCASE`, 500 rows in pages of 7:
  - The row-value predicate `(s, id) > (?, ?)` stops at the first null cursor.
    Descending, `(s, id) < (?, ?)` returns 473 of 500 rows: nulls sort last, and a
    comparison with null is unknown.
  - Review A’s one predicate for a null cursor,
    `(s IS NULL AND id > ?) OR s IS NOT NULL`, matches one `ORDER BY s, id`.
  - Paging each region with its own query (the nulls by key, the rest by row value,
    continuing from one region into the next) matches one `ORDER BY` in both directions.
- **Opcodes for one 100-row page** over 200,000 rows whose indexed column is null in
  every other row, the cursor deep in the nulls or the values:

| Page | Opcodes |
| --- | --- |
| Ascending, one predicate over both regions | 525,925 |
| Ascending, the null region alone (`s IS NULL AND id > ?`) | 617 |
| Ascending, first non-null page | 511 |
| Ascending, non-null continuation | 918 |
| Descending, one predicate over both regions (`… OR s IS NULL`) | 500,926 |
| Descending, non-null continuation | 1,016 |
| Descending, the null region alone (`s IS NULL AND id < ?`) | 617 |

- `Connection.deserialize` of a committed write-ahead-log database (header bytes 18 and
  19 are `02 02`) fails with `SQLITE_CANTOPEN` on first use; with the two bytes set to
  `01 01` it reads, as `pull_catalog._refuse_newer_in_copy` already does.
- `trusted_schema` defaults to on in this build, which compiles in FTS3, FTS4, FTS5,
  R-Tree, Geopoly, and `dbstat`. With `trusted_schema=OFF`, a view using `MATCH` is
  refused, but the FTS5 table and its shadow tables `f_data` and `f_config` read
  directly. Python exposes `SQLITE_DBCONFIG_DEFENSIVE`.
- **Views under an authorizer**, with `trusted_schema=OFF`. A view selecting
  `upper(name)` and `strftime('%Y', at, 'unixepoch')`, and one selecting
  `fts3_tokenizer('simple')`:

| Authorizer | `upper` view | `fts3_tokenizer` view | `upper` called directly |
| --- | --- | --- | --- |
| None | Reads | `unsafe use of fts3_tokenizer()` | Reads |
| Only the adapter’s own functions | `not authorized to use function: upper` | Refused | Refused |
| The adapter’s functions, and any function inside a view | Reads | `unsafe use of fts3_tokenizer()` | Refused |

`trusted_schema=OFF` does not stop a view’s built-in functions; it refuses those not
marked innocuous, which is what makes admitting the rest safe.

- **One value past the length limit.** `SQLITE_LIMIT_LENGTH` at 1,000,000 bytes, one
  3,000,000-byte text among three rows: `WHERE v LIKE '%needle%'` and `ORDER BY v, id`
  each fail the whole statement with `string or blob too big`. Adding
  `octet_length(v) <= 1000000` to the search returns both matches, and
  `CASE WHEN octet_length(v) <= 1000000 THEN v END` reads every row with the large value
  as null.
- **Storage encoding.** In a `PRAGMA encoding='UTF-16le'` database, `blobopen` on
  `héllo wörld` returned `68 00 e9 00 6c 00 6c 00`, and `octet_length` counted 22 bytes
  for 11 characters. In UTF-8, a preview cut after two bytes of `aé` decodes with a
  replacement character unless the incomplete trailing sequence is dropped first.

### Generation

Across 200 commit-and-checkpoint cycles, the restarted log took only two sizes, while
the checkpoint sequence and salts in its header (bytes 12 to 24) were different every
cycle. The main file’s change counter took only two values across the same cycles, so in
write-ahead-log mode it does not mark a commit.

### Process

What
[Decision 13](../../docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md#decision-13-where-sqlite-connections-run)’s
reader processes rest on.

- **The race check’s handle.** A reader opens `-shm` before connecting and enters a read
  transaction; the owner, with no busy timeout, runs `wal_checkpoint(RESTART)` and
  writes 2,000 more rows.
  With the handle held until after the connection closed, the restart stayed busy and
  the reader read its 2,000 rows, `integrity_check` ok.
  With the handle closed while connected, the restart went through and the reader read
  `database disk image is malformed`.
- **A reader process killed with SIGKILL**, and what the owner then did:

| State when killed | Owner while the reader lived | Owner after the kill |
| --- | --- | --- |
| Write-ahead log, reader inside a read | Commits; `wal_checkpoint(TRUNCATE)` busy | Commits; `wal_checkpoint(TRUNCATE)` returns `(0, 0, 0)`; closing removes `-wal` and `-shm` |
| Rollback journal, reader holding its shared lock | Commit refused, `SQLITE_BUSY` | Commits |
| Rebuilding a crashed owner’s wal-index (a 189 MB log; the rebuild takes 49 ms), killed at 20, 40, 60, 80, and 95% of that time | — | Reopens, reads all 1,600,000 rows rewritten, writes, `quick_check` ok, every time |

- **What a worker costs** for a 100-row page through a fresh connection per request:
  medians of five starts and of 50 round trips after each start.

| Start method | Start to first answer | Page round trip | Exits when its pipe closes |
| --- | --- | --- | --- |
| In process | — | 52 µs | — |
| `spawn` | 47.5 ms | 154 µs | Yes |
| `forkserver` | 3.1 ms | 175 µs | Yes |
| `fork` | 2.3 ms | 180 µs | **No**: it inherits the parent’s end of the pipe |

The spawned worker imports only the standard library and this script.

## What the Plan Takes From This

The plan’s access table keys on the write-ahead log’s size, a live journal, the link
count, and the resolved path, not on which sidecars exist.
Every SQLite connection runs in a spawned reader process that opens nothing else while
it is connected. A log with no `-shm`, or a file with a second name, is read through a
validated private copy.
A rollback-journal database is never locked: its page is validated, waiting out the
owner, and its count is validated apart or replaced by an estimate.
Counts are capped subqueries under a wall-clock deadline and an interrupt, and never run
under a lock.
Sorts that would scan are refused past a measured size, and a sorted column
pages its null and non-null regions by their own seeks.
Values are sized with `octet_length`, guarded by it in every expression, and previewed
through `blobopen` in the database’s encoding.
The authorizer admits built-in functions inside views; cells and keys use encodings
these failures require; and the generation token includes the log header.
[SQLite Source](../../docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md#the-sqlite-source)
states each rule.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
