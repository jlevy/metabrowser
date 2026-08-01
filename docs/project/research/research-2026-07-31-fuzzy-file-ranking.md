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
order.

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

No ranking changes were needed before the first implementation.
Future changes belong below as dated before-and-after examples.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
