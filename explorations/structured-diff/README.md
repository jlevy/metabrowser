# Structured Diff Projection Bounds

This measurement sets the budgets of the rendered YAML and JSON diff
(`src/metabrowser/diff/structured_projection.py`): the byte bounds for strict JSON,
YAML, and JSONC, the nodes a YAML side may compose to, the node and entry budgets of the
merge, and its alignment and pairing work.
Each constant’s comment cites the figures it rests on; the values themselves live there.

```shell
uv --config-file uv.toml run --frozen python explorations/structured-diff/measure.py [REPO]
```

The script collects every distinct (parent blob, commit blob) pair of a `.yaml`, `.yml`,
or `.json` file in the repository’s non-merge history, prints the pair-size
distribution, and projects each pair, reporting time, entries, and answer size by
format. An answer counts as `ready` only when it encodes as the route’s `JSONResponse`
encodes it. It then projects synthetic pairs of nested mappings just inside each byte
bound, and the shapes each work budget is measured on: the densest text each pure-Python
parser reads at its bound, lists of values drawn from ten (review A1 of #557), a long
list nested deep (review C3), and the node, entry, alignment, and pairing cases.

## Recorded Results

### Review Run

One run on 2026-11-18 on an Apple M1 Pro (10 cores), macOS, Python 3.14.7, over this
repository with the review’s changes (638 distinct pairs: 169 YAML, 469 JSON; pair size
p50 9.4 KiB, p90 124 KiB, largest 978 KiB). Other work shared the machine, and the load
average was 70 to 100 throughout, so every time here is inflated by an amount this run
cannot separate. The byte-bound cases are the median of five projections; the other
synthetic cases are the lowest and highest of three.

| Case | Size | Time | Status |
| --- | ---: | ---: | --- |
| Real YAML pairs | largest 38 KiB | p50 23 ms, p90 90 ms, max 222 ms | 169 ready |
| Real JSON pairs | 60 past the byte bound | p50 0.7 ms, p90 4.4 ms, max 11 ms | 408 ready, 60 too large, 1 unsupported |
| Nested mappings, YAML, inside its byte bound | 48 KiB pair | 213 ms | ready |
| Nested mappings, JSONC, inside its byte bound | 8 KiB pair | 51 ms | ready |
| Nested mappings, strict JSON, inside its byte bound | 127 KiB pair | 13 ms | ready |
| YAML flow list of one-digit integers, 4,000 items | 23 KiB pair | 211-379 ms | ready |
| YAML block list of one-digit integers, 4,000 items | 31 KiB pair | 487-878 ms | ready |
| YAML flow list just past the node bound | 29 KiB pair | 103-172 ms | too large |
| YAML block list just past the node bound | 39 KiB pair | 107-264 ms | too large |
| JSONC list of one-digit integers inside its byte bound | 8 KiB pair | 276-1,485 ms | ready |
| Lists of 1,000 drawn from ten values (A1) | 6 KiB pair | 103-119 ms | ready |
| Lists of 2,000 drawn from ten values (A1) | 12 KiB pair | 110-117 ms | too large |
| 1,000 bits, the first and last flipped | 6 KiB pair | 3-5 ms | ready |
| A list of 19,900 nested 15 deep (C3) | 117 KiB pair | 38-39 ms | ready |
| A list of 19,900 nested 60 deep (C3) | 117 KiB pair | 37-38 ms | too large |
| Two lists of 19,999, one item changed | 117 KiB pair | 57-62 ms | too large |
| A list of 10,000, one item changed | 115 KiB pair | 34-55 ms | too large |
| 4,000 items, nothing shared | 49 KiB pair | 132-251 ms | too large |
| 100 mappings of 40 keys, half of each changed | 101 KiB pair | 35-66 ms | too large |
| One list of 15,000 against 8,000 lists of one (E1) | 108 KiB pair | 137-140 ms | too large |

The real answers that encode are p90 11 KiB and at most 15 KiB for YAML, and p90 34 KiB
and at most 119 KiB for JSON. They draw p50 19, p90 90, and at most 223 entries for
YAML, and p50 16, p90 121, p99 681, and at most 940 for JSON. Every refused synthetic
case is inside its byte bound, so a work budget refused it, and the time is what the
projection spent before it stopped.
The E1 row was measured after review E’s fix, the lowest and highest of five at a load
average of 37 to 40; with the fix backed out, the same pair took 9.7 s.

Pure-Python parsing costs follow the nodes, not the bytes.
A list of one-digit integers costs several times what nested mappings of the same size
cost, so the YAML node bound and the JSONC byte bound are set on that shape.
The constants’ comments give the figures that set them.
Strict JSON, parsed in C, is about forty times cheaper per byte than YAML here.
Projections run in the projection child process: a page’s prefetch waits for it to
start, and a reader’s own request before it is ready runs in a thread, bounded by the
same budgets.

### First Run

Four runs on 2026-11-18, Python 3.13 in a Linux container, over this repository before
the review (624 distinct pairs: 168 YAML, 456 JSON). Ranges are the lowest and highest
of the runs. The JSONC row predates the JSONC byte bound.

| Case | Size | Time | Status |
| --- | ---: | ---: | --- |
| Real YAML pairs | p50 5 KiB, p90 18 KiB, largest 38 KiB | p50 13-15 ms, p90 40-42 ms, max 62-76 ms | all ready |
| Real JSON pairs | p50 15 KiB, p90 156 KiB | p50 0.3 ms, p90 1.8-2.5 ms, max 7-8 ms | 395 ready, 60 too large, 1 unsupported |
| Synthetic YAML | 48 KiB pair | 208-244 ms | ready |
| Synthetic JSONC | 47 KiB pair | 271-300 ms | ready |
| Synthetic strict JSON | 127 KiB pair | 4 ms | ready |

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
