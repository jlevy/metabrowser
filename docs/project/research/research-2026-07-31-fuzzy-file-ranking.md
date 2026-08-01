# Research: Fuzzy File Ranking

**Date:** 2026-07-31

**Status:** Phase 1 spike contract

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
five Recent-sized runs over 2,000 paths was 18.44 ms, or 9.22 microseconds per
candidate. The median of three heavily expanded runs over 50,000 paths was 456.93 ms, or
9.14 microseconds per candidate.

The larger scan is inappropriate as one synchronous browser task.
Phase 1 should keep a small synchronous fast path and yield between bounded chunks for
larger catalogs, checking cancellation between chunks.
The evidence does not justify a Worker or secondary client index yet because chunking
can preserve input responsiveness without another state-transfer boundary.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
