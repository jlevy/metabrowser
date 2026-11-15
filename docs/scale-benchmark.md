# Scale Benchmark

**Status:** Built: `make benchmark` measures the Python inventory provider, and the
Python baseline below was recorded on 2026-11-15. Planned: results for another provider
once one is registered.

A few figures anyone can reproduce on their own machine, published as evidence for the
README’s claim about large trees.
They show how soon a large folder shows counts, how long the full scan takes while the
page is open, and how much memory the server holds.
This benchmark is not a release gate.
The [performance loop](../explorations/performance-loop/README.md) is the gate: it
compares a candidate build against the unchanged one on the same corpus and refuses a
regression.

## What It Measures

`make benchmark` runs [`devtools/bench_serving.py`](../devtools/bench_serving.py) once
at each size in `BENCHMARK_SIZES` (in the `Makefile`), on the harness’s default
synthetic corpus. `build_corpus` makes that corpus from a fixed seed, so a size always
produces the same tree, and builds it under `.bench/`, which Git ignores.
Each run starts `metab` on the corpus with a client polling the folder Overview’s rollup
(`phase_scan_with_client`), then starts it again to measure settled serving
(`phase_settled`), which adds to the run time but not to the table.
The cold scan, which no figure here comes from, is skipped.

The table reports three fields of the `scan_with_client` result:

- **First folder counts** (`first_count_s`): seconds from launching the server to the
  first rollup response with a nonzero `total_files`. It includes process startup.
- **Scan with a client attached** (`wall_s`): seconds from the same start until a rollup
  reports the index `done` or `truncated`.
- **Peak server RSS** (`diagnostics.process.peak_rss_kb`, shown in MiB): the highest
  resident memory the harness sampled with `ps`. It samples when the scan finishes and
  when it reads diagnostics, not continuously.

## Running It

```shell
make install
make benchmark
```

Each run’s full result is written to `.bench/benchmark-<provider>-<files>.json`. To
print the table again from saved results:

```shell
uv --config-file uv.toml run --frozen python -m devtools.bench_serving \
    --markdown .bench/benchmark-python-100000.json .bench/benchmark-python-300000.json
```

When another inventory provider is registered in `INVENTORY_PROVIDERS` (in
`devtools/bench_serving.py`), `make benchmark BENCHMARK_PROVIDER=<name>` runs the same
command with `--provider`, and its rows go beside the ones below.

## Results

The Python-provider baseline, recorded on 2026-11-15:

| Provider | Files | First folder counts (s) | Scan with a client attached (s) | Peak server RSS (MiB) |
| --- | ---: | ---: | ---: | ---: |
| python | 100,000 | 1.19 | 5.5 | 174 |
| python | 300,000 | 1.38 | 19.3 | 331 |

- **Build:** `metab 0.12.1.dev1037+19f4d5e4 (+1105 commits, c8ef5d9ed)`.
- **Machine:** Apple M1 Pro, 32 GB, macOS 26.5.2.
- **Load at the start:** 1.50, 1.83, 1.79 (1, 5, and 15 minutes, from `uptime`).
- **Time:** `make benchmark` took 1 minute 38 seconds in all.
  The 100,000-file run took about 26 seconds and the 300,000-file run about 72 seconds,
  each including building its corpus and the settled phase.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
