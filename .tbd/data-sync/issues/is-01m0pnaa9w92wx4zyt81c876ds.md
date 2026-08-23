---
type: is
id: is-01m0pnaa9w92wx4zyt81c876ds
title: Launcher overhead was charged to the build being measured
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0pn7vkfkd7tfzt7r331jkp8
created_at: 2026-08-23T06:35:50.971Z
updated_at: 2026-08-23T07:24:19.701Z
---
WHAT HAPPENED. The baseline is an installed console script (`metab`). The candidate runs through `uv run --frozen --project ...`, which resolves and checks the environment before the server starts -- roughly half a second. Both were timed from process spawn, so that half second landed in the candidate's `serving`, `first_row` and `index_done`.

WHAT IT MADE THE NUMBERS SAY. The candidate appeared SLOWER to first row -- 0.907s against 0.787s -- while actually reaching first row in 2ms against the baseline's 4ms once server start is subtracted. A reader stopping at the top line would have concluded the perf work made startup worse.

THE GENERAL SHAPE. Comparing two builds launched by different mechanisms measures the launchers as much as the builds. The overhead is a constant, which makes it harmless for a large difference and decisive for a small one -- exactly backwards from what intuition suggests, because the small differences are where the interesting regressions live.

THE FIX, in preference order. Launch both the same way -- install the candidate into its own venv and invoke its console script directly, so neither carries a resolver. Failing that, report every timing relative to the moment the server accepted its first connection, and never report a raw spawn-to-event number. The current harness records `serving` and so the correction is possible after the fact, but it prints the uncorrected numbers first, which is what misled.

## Notes

FIXED in #73. Two changes. Timings are measured from the first accepted connection rather than from process spawn, so start-up is never charged to the code under test -- spawn_to_serving is reported separately. And the documented workflow builds the candidate to a wheel and installs it into its own venv, so both sides are console scripts and neither carries a resolver the other does not. That is how the numbers in mb-j7xx were taken.
