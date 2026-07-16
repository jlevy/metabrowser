# Scanning State and Recent Directories

Status: planned after v0.1.0.

Large served roots are useful before their initial scan is complete.
MetaBrowser should expose partial progress honestly, preserve directory recency, and
avoid presenting an incomplete subtree as empty.

## Goals

- Record directory modification times and aggregate ages during inventory walks.
- Represent pending, complete, and truncated directory scan states explicitly.
- Include both files and directories in recent-item results.
- Report indexed counts, limits, and completion state in API responses.
- Update Recent and tree views incrementally while scanning continues.

## Data Contract

Directory inventory records gain their real `mtime_ns` and a scan state.
Tree payloads distinguish an unscanned child list from a scanned empty directory.
Recent responses include stable item kind, path, modification time, size when
meaningful, the number of files indexed, and whether more results may appear.

Live events carry monotonic inventory progress and scoped directory changes.
Clients must tolerate duplicate events and reconnect from a fresh snapshot when a cursor
is no longer valid.

## Delivery Plan

1. Extend inventory and tree wire models with scan state and directory timestamps.
2. Add deterministic walker tests for partial, truncated, ignored, and symlinked trees.
3. Extend the recent endpoint and sort contract to include directories.
4. Add progress and incomplete-state UI without layout jumps.
5. Add incremental polling or event updates with bounded request frequency.
6. Validate on public synthetic large-tree fixtures and record performance budgets.

## Acceptance

- An incomplete directory is never rendered as definitively empty.
- Recent results remain deterministically ordered while new items arrive.
- Directory ages match filesystem metadata within documented platform precision.
- Truncation and index caps remain visible in the API and UI.
- The feature preserves fast first paint and bounded memory on large roots.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
