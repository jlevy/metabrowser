# Research: Fuzzy File Ranking

**Date:** 2026-07-31

**Status:** Phase 1 implemented and validated

## Summary

Quick File uses a dependency-free ordered-subsequence matcher over file basenames and
served-root-relative paths.
Ranking is a lexicographic comparison of named components, not a single opaque weight.
This makes close calls deterministic and lets maintainers change one preference without
unintentionally changing unrelated matches.

The machine-readable review surface is
[`tests/fixtures/file_fuzzy_ranking.json`](../../../tests/fixtures/file_fuzzy_ranking.json).
Its scenarios are both executable tests and examples for reviewing future tuning.

## Eligibility and Normalization

The query is trimmed and lowercased with JavaScript’s locale-independent
`String.prototype.toLowerCase`. Candidate paths use the same case normalization but
retain punctuation, diacritics, and `/` separators.
Phase 1 does not strip accents or apply Unicode canonical normalization because either
operation would require an explicit mapping back to original-string highlight ranges.

Every query character must match a distinct candidate character in order.
For queries without `/`, the matcher tries the basename first and falls back to the full
path only when the basename is ineligible.
Queries containing `/` match the full relative path so the slash constrains segment
order. When more than one alignment is possible, dynamic programming selects the
alignment that is best under the named components below.
For full-path matches, `path-segment` means the alignment does not skip an unmatched
slash between its first and last characters.

## Named Rank Components

The matcher exposes these fields with every result:

- `matchClass`: exact basename, basename prefix, contiguous basename, basename
  subsequence, path-segment match, or full-path subsequence
- `boundaryHits`: matched characters at the string start or after `/`, dash, underscore,
  dot, or whitespace, plus lower-to-upper camel-case transitions
- `contiguousChars`: the longest contiguous matched run
- `runCount`: number of contiguous matched runs
- `gapChars`: unmatched characters between runs
- `startOffset`: first matched position in the matched basename or path
- `candidateLength`: length of the matched basename or path
- `directoryDepth`: slash count in the relative path
- `normalizedPath`: lowercased path used for the penultimate tie-break
- `originalPath`: original path used for the total-order tie-break

The comparison order is the order above.
Lower values win for match class, run count, gaps, offsets, length, and depth.
Higher values win for boundary and contiguous counts.
Paths use deterministic UTF-16 code-unit comparison rather than locale-sensitive
collation.

## Match Ranges

Matched character positions are converted into half-open ranges over the original path.
Adjacent positions share one range.
Basename matches add the basename’s path offset, so the UI can highlight the same result
representation regardless of whether eligibility came from the basename or full path.

## Initial Policy Review

The fixture records obvious winners and close calls:

- exact and prefix basenames
- basename matches versus parent-directory-only matches
- dash, underscore, dot, slash, and camel-case boundaries
- contiguous versus gapped subsequences
- path queries and no-slash path fallback
- repeated characters, case, Unicode, total-order ties, and no-match behavior

The initial policy deliberately favors predictable navigation over typo correction.
It accepts only ordered subsequences and does not transpose characters or calculate edit
distance. Approximate matching can be evaluated separately if real queries show that
ordered subsequences are too restrictive.

## Tuning Checklist

For every ranking change:

1. Add or update a fixture scenario that demonstrates the close call.
2. Record the previous and new ordering and explain why the new winner is more useful.
3. Change either component calculation or component priority, not both in one step.
4. Run the full fixture suite and inspect every changed scenario.
5. Re-run Recent-sized and expanded-catalog measurements.
6. Keep normalized and original path tie-breakers so the order remains total.

## Implementation Review

The first executable pass found two fixture omissions on 2026-07-31. These were coverage
corrections, not ranking-policy changes:

- `app.js` against `app.jsx` and `application.js` changed from omitted to lower-ranked
  prefix and basename-subsequence matches because all six query characters occur in
  order.
- `rdr` against `render.js` changed from omitted to the middle result because its two
  `r` characters are distinct and surround `d`.
- `readme` against `read-me.md` changed from omitted to a lower-ranked
  separator-assisted basename subsequence.

Future changes belong below as dated before-and-after examples.

## Scorer Throughput

The public synthetic profile in `tests/dom/file_fuzzy_match_profile.js` measures the
pure scorer without DOM work or result sorting.
On an arm64 development machine running macOS 26.5.2 and Node 24.18.0, the median of
five Recent-sized runs over 2,000 paths was 19.46 ms, or 9.73 microseconds per
candidate. The median of three heavily expanded runs over 50,000 paths was 484.20 ms, or
9.68 microseconds per candidate.

The larger scan is inappropriate as one synchronous browser task.
Phase 1 should keep a small synchronous fast path and yield between bounded chunks for
larger catalogs, checking cancellation between chunks.
The evidence does not justify a Worker or secondary client index yet because chunking
can preserve input responsiveness without another state-transfer boundary.

## Search Runtime Validation

The repeatable profile in `tests/dom/search_controller_profile.js` measures the complete
local provider and controller path, including catalog snapshots, ranking, bounded
retention, chunk yields, cancellation, and result composition.
The provider publishes one completed batch, so `firstResultMs` is also completion
latency in Phase 1.

On the same arm64 development machine and Node 24.18.0, one validation run produced:

| Fixture | Candidates | First result | Queued-input delay | Yields | Results passed to UI |
| --- | ---: | ---: | ---: | ---: | ---: |
| Shallow | 50 | 0.81 ms | Not applicable | 0 | 50 |
| Recent-sized | 2,000 | 30.43 ms | 3.16 ms | 7 | 100 |
| Heavily expanded | 50,000 | 794.77 ms | 12.55 ms | 199 | 100 |

The queued timer ran before both large searches completed, showing that the
250-candidate chunks return control to the browser.
A superseded 5,000-candidate query was aborted and never published a completion.
The provider made zero fetch calls.
The palette DOM test independently verifies that it mounts no more than its configured
result limit.

A real-browser fixture contained 2,315 files from shallow, Recent-sized, and lazy deep
sources. The initial catalog exposed 2,053 observed files.
Recursive lazy loading raised that count to 2,314 while leaving the target beyond the
tree’s 200-row mount cap; loading the remaining nested source raised the catalog to all
2,315 fixture files.
The unmounted target matched in 57 ms and opened through normal preview navigation.
A broad query over the same catalog returned in 69 ms, while the input action returned
in 15 ms and the palette mounted exactly 100 rows.
A rapid broad-to-specific query published only the specific result.

The same browser pass confirmed one palette instance, focus transfer to the preview,
focus restoration on dismissal, editable slash handling, keyboard and pointer opening,
duplicate-basename display, and stale-file recovery with the query preserved.
The accessible tree exposed a labelled modal dialog, expanded combobox, listbox,
selected option, and polite status region.
Browser diagnostics contained no warnings or errors.
The local modules define no search endpoint, and the headless provider test fails on any
fetch call.

No ranking policy changed during validation.
Exact `index.js` duplicates placed `tests/index.js` before `src/components/index.js`
because the earlier comparison components tied and the shorter candidate won.
The path-aware query `src/index` selected only `src/components/index.js`, which is the
intended disambiguation behavior.

The 50,000-file completion time is visible enough that progressive result publication or
a Worker may become worthwhile for unusually large observed catalogs.
Current evidence does not justify either boundary: input delay remained below one frame
on this machine, normal Recent-sized searches completed in about 30 ms, and Phase 1
catalogs are partial.
Reconsider a Worker if representative target hardware exceeds the input-delay budget or
if later complete catalogs make 50,000-candidate scans routine.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
