# Feature: Scanning State and Recent Directories

**Date:** 2026-07-16 (last updated 2026-07-17)

**Author:** Metabrowser maintainers

**Status:** Draft

## Overview

Large served roots are useful before their initial scan is complete.
Metabrowser should expose partial progress honestly, preserve directory recency, and
avoid presenting an incomplete subtree as empty.

## Goals

- Record directory modification times and aggregate ages during inventory walks
- Represent pending, complete, and truncated directory scan states explicitly
- Include files and directories in recent-item results
- Report indexed counts, limits, and completion state in API responses
- Update Recent and tree views incrementally while scanning continues

## Non-Goals

- Blocking first paint until a complete root scan finishes
- Treating an inventory cap as a successful complete scan
- Adding an unbounded background traversal or request-path filesystem walk
- Guaranteeing metadata precision beyond the underlying platform

## Background

The inventory and tree APIs are intentionally bounded so very large roots remain
responsive. Without explicit scan state, a client cannot distinguish a directory that is
empty from one whose children are still pending or truncated.
Recent results also need directory metadata to represent newly active folders rather
than files alone.

## Design

### Approach

Extend inventory records and wire payloads with directory timestamps and explicit scan
state. Deliver monotonic progress and scoped changes through the existing live-event
channel so clients can update incrementally without polling the complete root.

### Components

- The inventory walker records real directory `mtime_ns` values and pending, complete,
  or truncated scan state
- Tree responses distinguish an unscanned child list from a scanned empty directory
- Recent responses include stable item kind, path, modification time, size when
  meaningful, indexed counts, and incomplete-result state
- Browser tree and Recent views render progress without layout jumps or false empty
  states

### API Changes

Directory inventory and tree records gain modification time and scan state.
Recent results gain item kind and inventory completeness metadata.
Live events carry monotonic inventory progress and scoped directory changes.

Clients tolerate duplicate events and reconnect from a fresh snapshot when a cursor is
no longer valid. Payloads remain bounded and never imply that capped or pending results
are exhaustive.

## Implementation Plan

### Phase 1: Explicit Scan State

- [ ] Extend inventory and tree wire models with scan state and directory timestamps
- [ ] Add deterministic walker tests for partial, truncated, ignored, and symlinked
  trees
- [ ] Extend the recent endpoint and sort contract to include directories
- [ ] Add progress and incomplete-state UI without layout jumps
- [ ] Add incremental event updates with bounded request frequency
- [ ] Validate public synthetic large-tree fixtures and record performance budgets

## Testing Strategy

- Use deterministic walker fixtures for pending, complete, capped, ignored, and
  symlinked directory states
- Test duplicate events, cursor resets, incremental progress, and stable Recent ordering
- Verify directory metadata within documented platform precision
- Measure first paint, server work, payload size, and browser updates on synthetic large
  roots

## Rollout Plan

Add wire fields in a backward-compatible form and teach the browser to prefer explicit
state when present. Keep first paint and direct navigation independent of full inventory
completion. Make incomplete indicators visible before expanding Recent to include
directories.

## Open Questions

- Which progress counters are stable enough to expose as public API?
- Should aggregate directory age reflect direct metadata or the newest indexed
  descendant?
- What event cursor retention is sufficient before clients must reload a snapshot?

## Acceptance Criteria

- An incomplete directory is never rendered as definitively empty
- Recent results remain deterministically ordered while new items arrive
- Directory ages match filesystem metadata within documented platform precision
- Truncation and index caps remain visible in the API and UI
- The feature preserves fast first paint and bounded memory on large roots

## References

- [Core architecture](../../../architecture.md)
- [Quick file finder and search providers](plan-2026-07-17-scalable-file-search.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
