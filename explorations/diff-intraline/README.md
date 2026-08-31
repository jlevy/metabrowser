# Diff Intraline Bound Benchmark

This fixture measures the browser-local changed-run algorithm independently of DOM and
syntax work. It records input characters, edit distance when computation completes,
deterministic algorithm work, elapsed main-thread time, and Chrome’s retained-heap delta
for ordinary code, shifted unequal lines, minified long lines, unrelated text, and
similar and unrelated inputs at the standalone patch parser’s current 8 MiB boundary.

Serve the repository root and open the fixture in a real browser:

```shell
uv run python -m http.server 8412 --bind 127.0.0.1
```

Then visit `http://127.0.0.1:8412/explorations/diff-intraline/benchmark.html`. The page
publishes the same JSON as `window.diffIntralineBenchmarkResult` for repeatable
collection.

## Recorded Result

Five consecutive runs in Chrome 151 on macOS at a 1600 × 900 viewport produced these
maximums. Timing covers `refineChangedRun` only; each case constructs its strings before
the timer starts.

| Case | Maximum elapsed | Deterministic work | Result | Maximum positive retained-heap delta |
| --- | ---: | ---: | --- | ---: |
| Ordinary code | 1.2 ms | 1,483 | Refined | 0 B |
| Shifted unequal lines | 0.4 ms | 1,961 | Refined | 0 B |
| Minified similar long line | 2.3 ms | 49 | Refined | 0 B |
| Unrelated 200,000-character lines | 31.6 ms | 1,002,001 | Over budget | 0 B |
| 8 MiB patch-bound similar line | 20.5 ms | 49 | Refined | 9,470,076 B |
| 8 MiB patch-bound unrelated lines | 32.6 ms | 1,002,001 | Over budget | 0 B |

The result selects a 1,000,000-work-unit budget for each changed run.
It stops pathological edit-distance growth below the repository’s 200 ms interaction
budget, while similar text at the existing maximum patch shape still refines without a
separate input-size cutoff.
Crossing the work budget keeps the positional split rows, syntax tokens when available,
exact text, and ordinary whole-line background.

Chrome exposes `performance.memory.usedJSHeapSize`, not a peak-allocation counter, so
the last column is the best available retained-heap evidence and may read zero or
negative when garbage collection intervenes.
The maximum positive delta occurred while refining the similar 8 MiB case; neither
pathological fallback retained additional heap in these runs.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
