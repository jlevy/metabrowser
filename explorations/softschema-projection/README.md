# SoftSchema Folder Table Projection

On the pinned GitHub Universe knowledge base, a second SQLite connection could read the
first 25 people after 351 ms.
The eager folder-table implementation took 16.45 s to produce the same projected rows in
memory. Both implementations finished with 4,971 records in 18 contracts.
The complete SQLite build still took 14.72 s.

The [Universe route benchmark](actual-routes.md) measures the current preview through
the real table handlers, including restart, a one-file edit, and backlink updates.

## Measurements

One comparison per corpus ran on macOS arm64 under CPython 3.14.7 with SoftSchema’s
C-first YAML parser.
Each strategy ran in a fresh process, eager first.
The operating system’s file cache was warm.
Timings exclude interpreter startup, imports, fixture generation, HTTP and browser
rendering.

| Corpus and strategy | First page | Source opens / bytes through first page | Full committed build | SQLite size | Peak process RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Universe, eager | 16.454 s | 4,992 / 15,814,717 | 17.478 s | 46.55 MiB | 584.12 MiB |
| Universe, projection | 0.351 s | 43 / 180,746 | 14.722 s | 1.80 MiB | 90.31 MiB |
| Flat mixed tree, eager | 0.915 s | 1,025 / 50,418,817 | 3.715 s | 106.65 MiB | 446.23 MiB |
| Flat mixed tree, projection | 0.044 s | 26 / 27,545 | 0.363 s | 0.22 MiB | 61.73 MiB |

The Universe path-and-stat inventory took 162 ms and opened no content.
Reading its 18 schemas brought elapsed time to 263 ms.
After completing the index, opening a fresh read-only connection and querying the page
took 0.40 ms. Selecting its first person read one 5,297-byte source and validated the
full record in 2.65 ms.
The eager implementation already held that record in memory.

The generated flat tree has 1,024 records, split equally between JSON objects and
Markdown documents with 96 KiB bodies.
The projection read 1.08 MB through the completed build, compared with 50.42 MB for
eager scanning. Universe contains smaller Markdown bodies and many standalone YAML
records. Its two complete builds read 15.22 MB and 15.81 MB. Prioritizing the requested
folder accounted for most of the improvement in Universe’s first-page time.

The [Universe measurements](universe.json) and [flat-tree measurements](flat.json)
include cumulative times, source byte counts and equivalence digests.
RSS uses the process high-water mark from `getrusage`, including interpreter, SQLite,
serialization and result verification.
The program converts macOS bytes or Linux KiB to MiB. Source counters measure bytes
supplied by file reads, independently of OS cache hits.

## What the Comparison Exercises

The [benchmark](compare.py) calls SoftSchema’s Python collection reader and validator,
and Metabrowser’s row-key and label functions.
The eager path runs the complete scan, groups its records, builds its ID lookup and
derives each table schema before selecting the page.
It serializes the full snapshot into a SQLite row to measure durable build cost.
First-page timing ends before this write.

The projection inventories candidate names and stamps, reads all candidate schemas, then
processes files in the requested folder first in path order.
For ordinary LF frontmatter it reads 2 KiB blocks through the closing fence; other
spellings go through the full reader.
For JSON and standalone YAML it reads the entire source.
SQLite stores source path, contract, opaque row key, ID, display label and validation
state. An index on contract and path supports the page query, and a second index covers
IDs.

The writer commits once it can fill a **preliminary folder-scoped page**. A second
read-only connection queries the first 25 rows in path order.
Once all rows are indexed, the benchmark confirms that the final query returns the same
page. The comparison checks digests of every projected row, the ordered page, and the
selected record’s payload, host metadata, body and validation execution.

The prototype assumes an unchanged, trusted corpus.
It captures the cost of a narrow projection and one selected read.
Production filesystem safety, generation isolation under concurrent changes, arbitrary
global sorting and filtering, full cell rendering, duplicate-ID handling and reference
navigation require separate evidence.
This run provides one observation per strategy with no estimate of run-to-run
variability.

## Reproduce

Use a Metabrowser checkout containing this exploration.
Its folder-table code in the recorded trial was at
`29085095e1c212c129cf1f562a7d7fbf3def08ed`. The benchmark calls private SoftSchema
discovery, reader and binding functions from `e6ee08f330faed45bf4fd0b49709a5dfd28a9e12`;
it requires that checkout on `PYTHONPATH` ahead of the released package.
The [SoftSchema collection change](https://github.com/jlevy/softschema/pull/78) contains
the pinned implementation.

Set `SOFTSCHEMA_CHECKOUT` to that source checkout, `UNIVERSE_CHECKOUT` to a clone of
[GitHub Universe](https://github.com/jlevy/universe2026-md), and `BENCH_SCRATCH` to an
existing writable directory outside the repository and corpus.
From the Metabrowser checkout, prepare a fresh corpus directory under scratch:

```shell
mkdir "$BENCH_SCRATCH/universe"
git -C "$UNIVERSE_CHECKOUT" archive a82367923bee34147da575dbd0cef17b5bc285a8 kb |
  tar -x -C "$BENCH_SCRATCH/universe"
export PYTHONPATH="$SOFTSCHEMA_CHECKOUT/packages/python/src:$PWD/src"
```

The recorded corpus matched all 5,001 Git blobs in that revision’s `kb` tree.
Run both strategies on Universe’s People folder and on the generated corpus:

```shell
uv --config-file uv.toml run --frozen --extra yaml-accelerator python \
  explorations/softschema-projection/compare.py --scratch "$BENCH_SCRATCH" \
  --root "$BENCH_SCRATCH/universe/kb" --table paraverse.conference:Person/v2 --prefix people/

uv --config-file uv.toml run --frozen --extra yaml-accelerator python \
  explorations/softschema-projection/compare.py --scratch "$BENCH_SCRATCH"
```

Each command prints aggregate JSON after the equivalence checks pass, and removes its
generated files and databases.
For another corpus, supply its root, contract and optional folder prefix.
The benchmark requires at least 25 matching records and a tree within the full scan’s
limits. The generated case accepts `--synthetic-rows` and `--body-bytes`.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
