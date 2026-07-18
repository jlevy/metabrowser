# Feature: Git Diff View

**Date:** 2026-07-18 (last updated 2026-07-18)

**Author:** Metabrowser maintainers

**Status:** Draft

## Overview

Metabrowser should show what has changed in the repository that contains the served
root. The first slice adds a Changes tab to the left navigation that lists every file
changed relative to `HEAD`, including untracked additions, and renders a fast, clear
per-file diff with the current file and the `HEAD` original one click away.
The primary use is reviewing edits that coding agents make to local files.

Later slices add staged and unstaged comparisons, commit history browsing, and a
multi-file review surface, all through one comparison API. This plan turns the
[diff viewer research brief](../../research/research-2026-07-17-web-diff-viewer-architecture.md)
into a staged implementation contract; the brief remains the rationale and evidence.

## Goals

- List all uncommitted changes (`HEAD` to working tree plus untracked files) with
  per-file status, staged/unstaged provenance, and honest totals
- Render a selectable, accessible per-file diff quickly: a small manifest first, then
  lazy per-file patches
- Give each changed file one-click access to its diff, its current rendered views, and
  its `HEAD` original
- Make partiality explicit everywhere: binary, too large, deferred, timed out,
  unsupported, and stale are distinct states, never empty responses
- Keep Git logic behind the plugin boundary in a built-in read-only plugin that uses
  only public platform capabilities
- Guarantee read-only operation: no index writes, no hooks, no fsmonitor, no external
  diff or textconv execution
- Reach staged, unstaged, commit, and two-revision comparisons and bounded history
  browsing without changing the comparison API shape
- Keep the wire format renderer-agnostic so a vendored renderer library can be adopted
  later without a server change

## Non-Goals

- Mutations: stage, unstage, discard, apply, or commit (research phase 5)
- Hosted review providers, comments, or synced viewed state
- Jujutsu support in the first slices (a later adapter to the same representation)
- A native Rust backend before the research brief’s benchmark gate is met
- Bundling a third-party diff renderer in the first slice
- Multiple repositories under one served root (the first slice serves the single
  repository that contains the served root)

## Background

The research brief recommends a layered architecture: comparison intent, resolved
comparison, change-set manifest, lazy semantic file patches, then separable enrichments
and render state. It also identifies six platform gaps, each now tracked as a platform
bead: plugin sub-router mounts, the SDK data plane, plugin event subscription, a bounded
subprocess runner, a repo-scoped surface, and a plugin cache API.

Current shell facts that shape this plan: the left pane has exactly two nav tabs (Files
and Recent) rendered by core; plugin views bind to single-file kinds and the preview
pane mounts one file at a time; `fetchPluginData` is GET-only; there is no bundler and
no runtime npm dependency, but `highlight.js` is already vendored; `MtimeCache` and the
event bus exist in core but are not plugin API; core runs no subprocesses today beyond
platform detection. Built-in plugins may declare Python data hooks, so a built-in plugin
can own server routes without new packaging.

Agent-generated change sets make bounded acquisition a first-slice requirement rather
than a scale nicety: a single lockfile rewrite or generated bundle can dwarf the rest of
the change set, and the changes list must not wait for it.

## Design

### Approach

Ship a built-in read-only `diff` plugin plus a small core platform slice.
The plugin resolves a comparison intent into an immutable resolved comparison, returns a
lightweight change-set manifest, and serves semantic per-file patches and side contents
lazily. The adapter runs the system `git` executable with hardened defaults behind an
interface that a native helper could implement later.
The browser side adds a Changes navigation surface and a custom design-token diff
renderer; adopting a renderer library is deferred to a scored spike.

### Decisions and Alternatives

#### Placement: Built-In Plugin Behind Public Capabilities

**Chosen:** a built-in `diff` plugin (manifest, data hooks, SDK) plus core platform
work, following the precedent of the `agent_log` and `structured` built-ins.

- A core implementation (routes in `server.py`, UI in `app.js`) would ship fastest but
  would bake Git schemas into core against the stated boundary, would bypass the
  platform gaps instead of closing them, and would be expensive to extract later.
- A separately installed `metabrowser-diff` package keeps core leanest but delays the
  primary use case behind packaging and makes every platform surface public-stable on
  day one. The built-in can graduate to an installed package later because it uses only
  public capabilities.

#### Backend: System Git Subprocess

**Chosen:** the installed `git` executable through a bounded async runner, using
`status --porcelain=v2 -z`, NUL-delimited raw/numstat output, per-file patches, and
`cat-file` for contents.

- Pure Python Git libraries duplicate Git semantics and add synchronous CPU or native
  dependencies; rejected by the research brief.
- A Rust helper (`gix`, `imara-diff`) is the measured successor only after profiling
  shows subprocess startup, discovery, or line diffing is the bottleneck; the adapter
  interface and contract tests must keep that door open.

#### Transport: Manifest First, Lazy Per-File Patches

**Chosen:** a small manifest response before any line diffing, then per-file semantic
patches and side contents on demand, with explicit availability states and bounded
prefetch of the first visible files.

- A one-shot repository-wide patch (the Difit model) is simpler but makes the slowest
  file gate the whole view, has no partiality semantics, and transfers work the user may
  never open. Lazy DOM mounting alone would not fix acquisition cost.
- Patches are produced server-side as semantic line groups (JSON), not parsed from
  unified text in the browser; a raw patch export remains available for download and
  diagnostics.

#### Renderer: Custom Token-Based Renderer, Library Spike Deferred

**Chosen:** a small strict-TypeScript renderer owned by the plugin: unified view first,
plain selectable text, design tokens, explicit special states.
Enrichment (vendored `highlight.js`, intraline spans) arrives in a later phase without
changing the patch format.

- `@pierre/diffs` is the strongest library candidate but is an ESM-only multi-megabyte
  dependency graph that requires the repository’s first bundling pipeline; it enters
  only through the phase 3 scored spike (bundle size, CSP and worker behavior from
  plugin static assets, dependency count, benchmarked rendering), with
  `@git-diff-view/core` as the named fallback.
- CodeMirror Merge and Monaco are editor-grade single-file components; they become
  relevant only if diff editing ever follows the editor contract.

#### Surface: Changes Nav Tab Plus Preview Pane, Review Surface Later

**Chosen:** a third left-nav tab listing changed files; selecting an entry shows that
file’s diff in the preview pane, with actions for the current file’s normal views and
the `HEAD` original.
The mount comes from the repo-scoped surface platform work: a manifest-declared
navigation surface with the standard render and dispose contract.

- A full-pane, single-scroll review surface (GitHub style) is the richer target and
  arrives in phase 3; starting there would front-load virtualization and layout work the
  per-file flow does not need.
- Decorating the existing Files tree with change badges is complementary, requires a
  core decoration API, and stays an open question to settle before the surface is
  considered stable.
- Anchoring on synthetic marker files is rejected outright.

### Components

- Core platform slice (existing platform beads): the bounded async subprocess runner,
  plugin sub-router mounts with honest status codes, SDK request bodies and response
  access, and the repo-scoped navigation surface.
  Event subscription and the shared cache helper formalize in phase 2; until then the
  surface may consume the public `/api/events` stream directly and keep a plugin-local
  bounded cache.
- Plugin server side: repository discovery (including `.git`-file worktrees and a clear
  `safe.directory` policy), Git version feature detection, the comparison service
  (intent resolution, deterministic comparison IDs, generation tokens, bounded LRU),
  manifest and patch builders, untracked-addition synthesis, and content retrieval.
- Plugin browser side: the Changes panel (badge count, status list, provenance badges,
  empty/non-repo/unavailable states), the diff renderer module, preview-pane
  integration, and event-driven staleness with an explicit refresh affordance.

### API Changes

New plugin routes, requiring sub-router support:

```text
POST /api/plugin/diff/comparisons
GET  /api/plugin/diff/comparisons/{comparison_id}
GET  /api/plugin/diff/comparisons/{comparison_id}/files/{file_id}/patch
GET  /api/plugin/diff/comparisons/{comparison_id}/files/{file_id}/content/{side}
```

Creation resolves an intent (`mode` of `uncommitted`, later `staged`, `unstaged`,
`commit`, `range`; whitespace, rename, context, and limit options) and returns the
resolved comparison plus the manifest.
Comparison IDs are self-describing and idempotent, so any `GET` can rebuild an evicted
comparison; `stale` is the only lifecycle state clients must handle.
File IDs are opaque; raw path bytes travel base64-encoded with a separate display
string. Patch and content responses carry ETags derived from content identities and
options, honor conditional requests, and never return ambiguous empty bodies.
Untracked files appear as additions from an empty side after ignore, safe-path, and size
checks. Every Git invocation is argument-array only, with sanitized environment,
`--no-optional-locks`, disabled hooks, fsmonitor, external diff, and textconv, plus
time, output, and concurrency caps and cancellation on client disconnect.

## Implementation Plan

### Phase 0: Platform Slice and Fixtures

- [ ] Land the bounded subprocess runner, sub-router mounts, SDK request bodies and
  typed response access, and the repo-scoped navigation surface from the platform beads
- [ ] Build golden fixture repositories covering the phase 1 state matrix: modified,
  added, deleted, renamed, mode change, binary, untracked, partial staging, unborn
  branch, detached `HEAD`, linked worktree, non-UTF-8 path, CRLF, missing final newline,
  and one pathological generated file
- [ ] Add adapter contract tests and record baseline command, parse, transfer, and
  render costs on those fixtures; set budgets from the baseline

### Phase 1: Uncommitted Changes and Per-File Diffs

- [ ] Implement repository discovery, version detection, and the hardened Git adapter
  (porcelain v2 status, raw/numstat manifest, per-file patch, `cat-file` content,
  untracked synthesis, caps and cancellation)
- [ ] Implement the comparison service: resolved comparisons, deterministic IDs,
  generation tokens, bounded LRU, ETags
- [ ] Mount the comparison, patch, and content routes with security and
  conditional-request tests
- [ ] Build the Changes panel: change count badge, status list with staged/unstaged
  provenance and additions/deletions when cheaply available, and explicit empty,
  non-repository, and unavailable states
- [ ] Build the per-file unified diff renderer as a strict-TypeScript module: selectable
  text, line numbers, hunk headers, design tokens, and explicit binary, too-large,
  renamed, and mode-change presentations with load-more caps
- [ ] Wire one-click actions: open diff, open the current file’s normal views, view the
  `HEAD` original
- [ ] Mark active comparisons stale from filesystem events and offer refresh without
  yanking content mid-read
- [ ] Verify recorded budgets: the manifest returns without computing any file patch,
  and one oversized file cannot block the changes list or freeze scrolling

### Phase 2: Comparison Modes and History

- [ ] Add a comparison bar with Staged, Unstaged, All uncommitted, Commit, and Two
  revisions presets, always showing the resolved endpoints
- [ ] Add a bounded history panel (first-parent `git log` with paging caps) and
  commit-versus-parent diffs with explicit root and merge policy
- [ ] Serve side contents at any resolved revision so the original of any comparison is
  viewable
- [ ] Add split view, whitespace toggle, bounded context expansion, intraline word
  spans, and `highlight.js` enrichment that renders plain text first
- [ ] Formalize plugin event subscription and adopt the shared cache helper, replacing
  the direct stream and plugin-local cache

### Phase 3: Review Surface and Renderer Decision Gate

- [ ] Build the full-pane review surface: one scroll owner, sticky file headers,
  keyboard navigation, local viewed state, and adaptive mounting tiers with
  virtualization only above measured thresholds
- [ ] Run the pinned renderer spike (`@pierre/diffs` stable and `CodeView`;
  `@git-diff-view/core` fallback) scored on bundle size, CSP and worker behavior,
  dependency count, and benchmark results; adopt it or recommit to the custom renderer
- [ ] Decide the Files-tree change-decoration question with a core API if accepted

Native backends, Jujutsu, review comments, and mutations follow the research brief’s
phases 3 to 5 and are out of scope here.

## Testing Strategy

- Golden manifests and patches from the fixture repositories, with differential tests
  against the installed Git CLI
- Property tests for NUL-delimited status and raw parsing, arbitrary path bytes, and
  truncation
- Route tests for containment, opaque IDs, conditional requests, cancellation, caps, and
  the read-only guarantees (asserted argument vectors and environment)
- Node VM contract tests for the surface and renderer, including disposal, staleness,
  and special-state rendering
- Performance tests with committed budgets for manifest latency, first-diff latency,
  payload sizes, and long-task limits on the fixture matrix

## Rollout Plan

Ship phases in order behind no configuration: the feature is read-only, and the Changes
surface reports capability honestly (hidden or explicitly unavailable when the served
root is not inside a repository, `git` is missing or too old, or ownership checks
refuse). Phase boundaries are safe stopping points; the comparison API shape is fixed in
phase 1 so later phases only add modes, enrichments, and surfaces.
Any renderer library adoption follows the supply-chain cool-off, exact pinning, and
vendoring rules.

## Open Questions

- The exact manifest shape for the repo-scoped navigation surface and how it later
  unifies with directory-scoped container kinds
- Whether the Files tree gains change decorations, and the core decoration API that
  requires (decide before the surface is considered stable)
- Comparison ID encoding: fully self-describing token versus digest plus rebuildable
  server state
- Whether phase 2 batch loading needs NDJSON streaming or per-file requests suffice
- Multi-repository roots and nested repositories under one served root

## Acceptance Criteria

- With `git` absent or the served root outside a repository, browsing is unaffected and
  the surface states why changes are unavailable
- No invocation can write to the repository or execute repository-configured programs;
  tests assert the hardened argument and environment profile
- Requests cannot reach paths outside the served repository; payloads contain no
  absolute paths; file IDs are opaque
- The manifest returns without computing any file patch, and every availability state
  (deferred, binary, too large, timed out, stale, unsupported) is distinct and rendered
- Untracked, renamed, deleted, mode-change, and partially staged files present
  correctly, including provenance badges
- A pathological generated file cannot delay the changes list or freeze the diff view;
  it renders as a bounded, expandable state
- Working-tree edits during viewing surface a stale indicator and refresh path, never
  silently mixed generations
- Committed performance budgets pass on the fixture matrix

## References

- [Web diff viewer architecture research](../../research/research-2026-07-17-web-diff-viewer-architecture.md)
- [Core architecture](../../../architecture.md)
- [Plugin authoring](../../../plugins.md)
- [Design system](../../../design-system.md)
- [Editor plugin editing contract](../../architecture/arch-editor-plugin-editing-contract.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
