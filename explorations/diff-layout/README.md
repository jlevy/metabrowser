# Diff Layout Bound Benchmark

This fixture measures unified and split reprojection at the server’s
`GIT_COMMIT_MAX_FILES` bound.
It duplicates the smallest representative ready patch from the File Diff Format
conformance corpus, mounts all files through the production renderer, alternates layouts
six times, and forces layout before recording each sample.
Syntax enhancement remains plain and queued so the result isolates layout reprojection.

Serve the repository root and open the fixture in a real browser:

```shell
uv run python -m http.server 8412 --bind 127.0.0.1
```

Then visit `http://127.0.0.1:8412/explorations/diff-layout/benchmark.html`. The page
prints browser, viewport, file count, mounted element count, mount time, and each
unified or split switch time.

## Recorded Result

Measured on 2026-08-25 in Chrome 151 at 1600×900 with 1,000 ready files and 33,008
mounted elements.
The unbatched renderer handled six alternating switches with a 147.4 ms
median and a 223.7 ms maximum blocking task.
Its samples were 223.7, 161.4, 140.3, 113.4, 147.4, and 111.1 ms.

Reprojecting 100 files per task reduced the two repeated runs to these ranges:

| Metric | Run 1 | Run 2 |
| --- | ---: | ---: |
| Mount | 35.1 ms | 24.0 ms |
| Median blocking switch | 21.3 ms | 18.9 ms |
| Maximum blocking switch | 140.3 ms | 133.7 ms |
| Slowest complete projection | 700.1 ms | 757.3 ms |

The cold first split includes style and layout for the retained unified DOM and remained
below the 200 ms interaction budget.
Later batches yield to the browser while the generation check ensures a newer layout
choice wins.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
