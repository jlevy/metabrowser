# Structured Diff Projection Bounds

This measurement sets the budgets of the rendered YAML and JSON diff
(`src/metabrowser/diff/structured_projection.py`): the byte bounds for strict JSON and
for the pure-Python parsers, the node and entry budgets, and the alignment work bound.
Each constant’s comment cites the figures it rests on.

```shell
uv run python explorations/structured-diff/measure.py [REPO]
```

The script collects every distinct (parent blob, commit blob) pair of a `.yaml`, `.yml`,
or `.json` file in the repository’s non-merge history, prints the pair-size
distribution, and projects each pair, reporting time and answer size by format.
It then projects synthetic pairs of nested mappings just inside each byte bound.

## Recorded Result

Four runs on 2026-11-18, Python 3.13 in a Linux container, over this repository (624
distinct pairs: 168 YAML, 456 JSON). Ranges are the lowest and highest of the runs.

| Case | Size | Time | Status |
| --- | ---: | ---: | --- |
| Real YAML pairs | p50 5 KiB, p90 18 KiB, largest 38 KiB | p50 13-15 ms, p90 40-42 ms, max 62-76 ms | all ready |
| Real JSON pairs | p50 15 KiB, p90 156 KiB | p50 0.3 ms, p90 1.8-2.5 ms, max 7-8 ms | 395 ready, 60 too large, 1 unsupported |
| Synthetic YAML | 48 KiB pair | 208-244 ms | ready |
| Synthetic JSONC | 47 KiB pair | 271-300 ms | ready |
| Synthetic strict JSON | 127 KiB pair | 4 ms | ready |

The largest real answer was 120 KiB. YAML and JSONC parse in pure Python at about 5 and
6 ms per KiB, so they share a 48 KiB bound that every real YAML pair fits, and keep the
slowest projection near the slowest Markdown projection’s 222-268 ms; strict JSON is
about 150 times cheaper and has a 128 KiB bound.
Projections run in the projection child process, not on the server’s interpreter.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
