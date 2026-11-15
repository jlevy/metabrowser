# Scale Benchmark

**Status:** Built: `make benchmark` measures the Python inventory provider.
Planned: the recorded Python baseline below, and results for another provider once one
is registered.

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

The Python-provider baseline is planned: it is run on an otherwise idle machine and
recorded here with the date, the `metab --version` output, the provider, the machine’s
chip and memory, the load average from `uptime` at the start, and how long each size
took.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
