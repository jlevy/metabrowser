# Universe collection refresh through the table routes

On 2026-11-26, the first eligible table refresh after a one-profile edit in a scratch
copy of Universe took 1.255 s. The scanner read the contents of just the edited file.
It still walked the full collection and the plugin rebuilt the in-memory projection and
replaced its SQLite snapshot.

## Timings

One run used Metabrowser `2908509` and the local SoftSchema Python package at `e6ee08f`.
A Starlette TestClient called the production collection, rows, and record handlers in
process. Each overview waited for a ready index.
Times include the handler and JSON response but exclude server startup and browser
rendering. The cold request started with an empty plugin cache on a warm filesystem.

| Root collection overview | Elapsed | Scanner content reads | Generation |
| --- | ---: | ---: | --- |
| First build | 18.794 s | 4,992 | First |
| Immediate repeat in the same process | 0.017 s | 0 | Same |
| Refresh after the polling interval, no changes | 0.576 s | 0 | Same |
| Refresh after editing one profile | 1.255 s | 1 | New |
| Fresh process after the edit, same cache | 1.382 s | 0 | Same as edited |

All three scans in the original process walked 4,992 candidate files.
The scan reported one changed path, zero additions, and zero removals after the edit.
All generations returned 4,971 valid records, 18 tables, 18 schemas, and zero problems.
The read counter covers SoftSchema’s content reader.
Folder discovery samples and filesystem metadata calls are outside that counter.

## Where the edit spent time

- The scan took 570 ms, including 159 ms walking the tree and 48 ms checking bindings
  across 4,971 records.
  An unchanged binding can reuse its verdict.
- Serializing the full snapshot took 150 ms.
  Writing it to SQLite took 361 ms.
- Grouping all records took 23 ms, rebuilding the ID lookup took 7.5 ms, and inferring
  fields and reference targets across all 18 tables took 26 ms.
- After publication, a one-row Profile page took 1.3 ms and the full detail request took
  1.6 ms. Fetching the affected Person details and their filtered incoming rows took
  0.9–2.1 ms per request.

On process restart, reading and decoding the saved snapshot took 895 ms and the reuse
scan took 392 ms. These figures describe single requests with timing wrappers around the
named operations.

After the second generation, the preview SQLite file occupied 97,443,840 bytes.
Its single live snapshot contained 48,583,958 UTF-8 bytes.
Of 23,790 database pages, 11,916 were on the freelist and available for reuse.
The separate eager prototype’s cold-only database occupied 48,816,128 bytes with zero
free pages. The preview’s `INSERT OR REPLACE` rewrites one large row.
The file size includes pages freed when SQLite replaced the first generation.
The staged prototype stores projected rows in a different format.

## Reproduction

Use an extracted Universe knowledge base, the two revisions above, and a Metabrowser
development environment that can import the SoftSchema overlay.
Create a fresh directory on the scratch volume, clone the corpus into it, and point the
service at that copy.
On macOS, with `CORPUS`, `SCRATCH`, and `SOFTSCHEMA` set to the source folder, existing
scratch parent, and SoftSchema checkout, run the following commands from the Metabrowser
checkout.

```sh
set -eu
bench=$(mktemp -d "$SCRATCH/actual-routes.XXXXXX")
cp -cRp "$CORPUS" "$bench/kb"
export METABROWSER_CACHE_DIR="$bench/cache"
export PYTHONPATH="$SOFTSCHEMA/packages/python/src:$PWD/src"
uv run --no-sync metab "$bench/kb" --no-open
```

Keep the server running through the one-file edit.
The [route test](../../tests/test_softschema_table_source.py) shows the TestClient
setup, request parameters, and backlink filter encoding.

1. Request `/api/plugin/softschema/collection?path=&wait=1` until ready and record time
   to ready, generation, all table counts, and summary.
   Repeat immediately, then again after the plugin’s refresh interval.
2. Request `/api/plugin/table/rows` for the Profile table with a one-row limit and
   columns `id`, `headline`, and `person`. Use its returned key at
   `/api/plugin/table/record` and identify the source file from `source_path`. Choose a
   second Person with one incoming profile.
   Record the two Person details’ incoming counts and the corresponding filtered Profile
   row keys.
3. In the copied profile only, change the headline and point `person` at the second
   Person. After the refresh interval, repeat the overview, row, detail, and incoming
   queries. The generation changed and the Profile key held.
   Both row and detail returned the edited headline and new reference.
   The old Person’s incoming count fell from one to zero and the new Person’s rose from
   one to two. The filtered incoming rows confirmed the move.
   Every table count and summary field held.
4. Stop and restart the process with the same cache and same absolute corpus path.
   Request the overview with `wait=1` to measure disk-cache reopen.
5. To separate scan reads from the route timings, count calls to
   `softschema.collection._read` and time `scan_collection`. Time the plugin’s `_group`,
   `_locations`, and `_schema` calls for the projection.
   Query `PRAGMA page_count`, `PRAGMA page_size`, and `PRAGMA freelist_count` on the
   plugin database to compare live and reusable space.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
