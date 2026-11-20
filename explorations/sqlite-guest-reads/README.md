# Reading Another Application’s SQLite Database

**Status:** Recorded on 2026-11-20 as the measured basis for the access rules in
[Tabular Data Browsing and Live SQLite](../../docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md#reading-another-applications-database).
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
paths in it.
Each case stages its databases in a fresh folder under `--scratch`; an owner
runs in its own process, and the reader opens a fresh connection per read.
Run it as an unprivileged user, since a superuser ignores the folder and file
permissions several cases depend on; the script refuses to run as root.

```shell
uv --config-file uv.toml run --frozen python explorations/sqlite-guest-reads/measure.py \
  --scratch "$TMPDIR/mb-sqlite-guest" access contention budget values encoding generation
```

| Suite | Question |
| --- | --- |
| `access` | What `mode=ro` and `immutable=1` read in each sidecar state, and what they leave |
| `contention` | How many of a rollback-journal owner’s commits fail while a viewer reads |
| `budget` | What a progress-handler budget sees, and what each kind of page costs in opcodes |
| `values` | Peak memory to preview one 200 MiB value, each query in a fresh process |
| `encoding` | Values JSON or Python’s defaults cannot carry, keyset paging, untrusted schemas |
| `generation` | Whether a restarted write-ahead log repeats its size, and whether its header changes |

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
| `-wal` with frames, no `-shm`, writable folder | 105 rows; **creates `-shm`** | 100 rows |
| Same, read-only folder | `SQLITE_CANTOPEN` | 100 rows |
| Rollback journal, hot `-journal` from a killed writer | `SQLITE_READONLY_ROLLBACK`; journal untouched | **14,585 of 20,000 rows half-updated** |

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
- **A held read starves the checkpoint.** With a reader inside one read transaction,
  `wal_checkpoint(TRUNCATE)` reported busy after 300 commits and the log held 3,712,152
  bytes; once the transaction ended, the same checkpoint truncated it to zero.
- **A write-ahead-log commit leaves the main file untouched**: its size, modification
  time, and bytes stayed the same while `-wal` grew from 4,152 to 8,272 bytes.

### Contention

A rollback-journal database of 200,000 rows; the owner commits one row per transaction
with `busy_timeout=0` for four seconds while the viewer reads four times a second.
These counts depend on timing and vary between runs; their shape does not.

| Viewer | Back-to-back commits: owner `SQLITE_BUSY` of attempts | One commit per 50 ms: owner `SQLITE_BUSY` | Viewer reads rejected, back to back / per 50 ms |
| --- | --- | --- | --- |
| None | 0 of 4,573 | 0 | — |
| `mode=ro`, 100-row key-ordered page | 9 of 4,593 | 0 | 3 of 11 / 0 of 16 |
| `mode=ro`, `count(*)` | 197 of 4,877 | 1 | 2 of 11 / 0 of 16 |
| `mode=ro`, page sorted by an unindexed column | 1,371 of 5,386 | 2 | 2 of 12 / 0 of 15 |
| Validated `immutable=1`, key-ordered page | 0 | 0 | 14 of 16 / 2 of 16 |
| Validated `immutable=1`, unindexed sort | 0 | 0 | 16 of 16 / 14 of 16 |

A validated read takes no lock, so it never fails a commit, but it succeeds only when
the read is shorter than the gap between commits.

### Budget

- `SELECT count(*)` over 1,500,000 rows runs 9 opcodes.
  With a progress handler every 1,000 opcodes, as `pull_catalog` sets, the handler was
  never called and the full count returned.
- `SELECT count(*) FROM (SELECT 1 FROM big LIMIT 1000001)` runs 7,000,021 opcodes, and
  the same budget stopped it on the handler’s first call.
- `Connection.interrupt()` from another thread ended a thread running `count(*)` in a
  loop.

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
| Baseline (`SELECT id`) | 18 |
| `substr(v, 1, 100), length(v)` on text | 219 |
| `substr(b, 1, 16), length(b)` on a blob | 221 |
| `length(v)` on text | 219 |
| `length(b)` on a blob | 18 |
| `octet_length(v)` on text | 18 |
| `typeof(v)` | 18 |
| `Connection.blobopen`, then read 100 bytes of the text | 18 |

### Encoding

- `13390000000000001` survives Python’s JSON but parses in a browser as
  `13390000000000000`.
- `json.dumps(..., allow_nan=False)` refuses an infinite real.
- Text holding the bytes `ff 41` raises `Could not decode to UTF-8` under Python’s
  default text factory.
- Keyset paging over an indexed column holding nulls, integers, reals, text, and blobs,
  under every declared type and `COLLATE NOCASE`: the row-value predicate
  `(s, id) > (?, ?)` stops at the first null cursor; with a separate branch for a null
  cursor, `(s IS NULL AND id > ?) OR s IS NOT NULL`, the pages match one
  `ORDER BY s, id` exactly.
  The row-value form keeps the index seek (1,222 opcodes above), where an
  affinity-stripping `+s` form costs a scan.
- `Connection.deserialize` of a committed write-ahead-log database (header bytes 18 and
  19 are `02 02`) fails with `SQLITE_CANTOPEN` on first use; with the two bytes set to
  `01 01` it reads, as `pull_catalog._refuse_newer_in_copy` already does.
- `trusted_schema` defaults to on in this build, which compiles in FTS3, FTS4, FTS5,
  R-Tree, Geopoly, and `dbstat`. With `trusted_schema=OFF`, a view using `MATCH` is
  refused, but the FTS5 table and its shadow tables `f_data` and `f_config` read
  directly. Python exposes `SQLITE_DBCONFIG_DEFENSIVE`.

### Generation

Across 200 commit-and-checkpoint cycles, the restarted log took only two sizes, while
the checkpoint sequence and salts in its header (bytes 12 to 24) were different every
cycle.

## What the Plan Takes From This

The plan’s access table keys on the write-ahead log’s size and the resolved path, not on
which sidecars exist; a rollback-journal database is read lock-free first; counts are
capped subqueries under a wall-clock deadline; sorts that would scan are refused past a
measured size; values are sized with `octet_length` and previewed through `blobopen`;
cells and keys use encodings these failures require; and the generation token includes
the log header.
[SQLite Source](../../docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md#the-sqlite-source)
states each rule.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
