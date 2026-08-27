# Research: Historical Diff View Spike Results

**Date:** 2026-07-18 (reviewed 2026-08-27)

**Author:** Metabrowser maintainers with research assistance

**Status:** Preserved historical evidence; not a current benchmark gate

## Purpose

Pull request [#12](https://github.com/jlevy/metabrowser/pull/12) contained a quarantined
prototype of a Git adapter and four browser rendering paths.
The product plan and prototype source have been superseded by the File Diff Format, the
production Git source, the built-in diff plugin, and the current performance framework.

The measurements still answer three useful questions:

1. What did exact line totals cost relative to a status-only manifest on a large dirty
   working tree?
2. How much did row gating matter compared with renderer selection?
3. Which library and packaging assumptions need a fresh test before the dependency gate
   reopens?

This document preserves the measured results and their limits.
The complete historical source remains available at commit
[`414a2fc`](https://github.com/jlevy/metabrowser/tree/414a2fc313d45044295d3bae9b1ac77028c6b2bb/spikes/diff-view);
it is intentionally not copied into the current tree.

## Test Environment

The spike ran in a Linux x86-64 cloud development container with Git 2.43 and headless
Chromium driven through Playwright 1.61.0. The renderer fixtures were:

| Fixture | Shape |
| --- | --- |
| `small` | 200-line file with three edit blocks |
| `medium` | one refactor producing about 2,000 patch lines |
| `huge` | a complete lockfile rewrite producing 37,502 patch lines |
| `set50` | 50 small changed files |

The Git fixture was a synthetic dirty repository with 519 changed files: 500 small
edits, a 30,000-line lockfile rewrite, 12 untracked files, renames, deletions, a binary
change, and partial staging.

These are single-environment observations.
The measurements did not alternate control and candidate runs, report distributions, or
preserve machine-load evidence.
They are suitable for architectural direction and unsuitable for a regression threshold.

## Git Adapter Measurements

| Operation | Observed result |
| --- | ---: |
| `status --porcelain=v2 -z` and parse | 10.1 ms |
| `diff HEAD --numstat -z -M` | 98.2 ms |
| Combined manifest | 109.0 ms |
| Per-file patch, ordinary file | 2-3 ms |
| Per-file patch, 30,000-line lockfile | 116.2 ms |
| One-shot `git diff HEAD` | 132.4 ms and 8.8 MB of patch text |

The status parse preserved rename origin, staged and unstaged state on one path, binary
state, and synthesized untracked files under byte and line caps.
The runner used a sanitized environment, `--no-optional-locks`, literal pathspecs, and
disabled hooks, external diff drivers, text conversion, and the filesystem monitor.

`--numstat` accounted for about 90% of the measured combined-manifest time.
The manifest-first design reduced transfer and browser parsing much more than Git
execution: about 100 KB of manifest JSON replaced 8.8 MB of patch text, while the Git
commands still cost 109 ms against 132 ms for the one-shot patch.

### Current Interpretation

The production Git source now models revision comparisons with `--raw` and `--numstat`.
Uncommitted staged, unstaged, and all-working-tree comparisons remain planned.
Before those surfaces choose whether to defer exact totals, remeasure the production
source on the same repository in paired runs.
The July result identifies the likely cost center; it does not set today’s policy.

## Renderer Measurements

`custom` was a 5.5 KB dependency-free table renderer.
`server_html` inserted Python-generated HTML. `gdv` used `@git-diff-view/core` 0.1.6
with a custom DOM layer.
`pierre` used `@pierre/diffs` 1.2.12 with precomputed patch input in its default
nonvirtualized path.

Each cell below reports synchronous settled-frame time; cells with a slash also report
mounted DOM nodes.

| Scenario | Custom | Server HTML | `gdv` core and DOM | Pierre patch input |
| --- | ---: | ---: | ---: | ---: |
| Small | 10.3 ms / 331 | 8.6 ms | 15.1 + 46.9 ms / 325 | 176.2 ms / 994 |
| Medium | 66.3 ms / 6,430 | 71.7 ms | 36.2 + 132.9 ms / 6,310 | 726.8 ms / 18,607 |
| Huge, fully mounted | 2,056 ms / 187,522 | 2,042 ms | 295.7 + 5,994 ms / 187,520 | 75,750 ms / 633,075 |
| Huge, custom gated at 1,500 rows | 195.1 ms | Not tested | Not tested | Not tested |
| 50 files, eight initially mounted | 64.8 ms | Not tested | Not tested | Not tested |
| 50 files, all mounted | 121.6 ms | Not tested | Not tested | Not tested |

Client-side diff computation through jsdiff was slower than patch input: 498.5 ms for
the small fixture, 1,582 ms for medium, 139.3 seconds for the huge plain-text fixture,
and 212.3 seconds with highlighting on the first huge run.

Python generated the server HTML in 0.06 ms and 12 KB for small, 1.07 ms and 246 KB for
medium, and 46.3 ms and 11.5 MB for huge.
Browser insertion and parsing still took about two seconds for the huge fixture, close
to direct DOM construction from structured data.

### Findings Confirmed by Production Work

- **Bound mounted work before changing renderer technology.** The huge custom render
  fell from about two seconds to 195 ms when it stopped at 1,500 rows.
  The production renderer later made collapsed changed rows absent from the DOM and
  added a required zero-hidden-row performance gate.
- **Send patches or semantic lines to the browser.** Client-side computation on the
  pathological pair took minutes.
  The production source computes patches through Git and parses them into File Diff
  Format before rendering.
- **Server HTML did not remove browser work.** The large HTML payload cost about as much
  to insert as structured rows cost to build.
  Server HTML remains plausible for print or export, not as an automatic performance
  shortcut.
- **A library must be tested in its intended high-scale configuration.** The Pierre run
  did not enable its virtualized components or worker pool.
  It demonstrates that the default fully mounted path is a poor fit for the pathological
  fixture; it does not evaluate the library’s best path.
- **`@git-diff-view/core` expected patch hunks.** It did not compute a change from two
  file bodies in this experiment.
  Its model was cheaper than its line-by-line DOM path, but that old result does not
  decide whether a current tokenizer or model-only use is worthwhile.

## Comparison with the Production Renderer

The production fold work used a different corpus and measurement method, so the numbers
below are not a before-and-after benchmark.
They show that the architectural conclusion was implemented and then measured directly.

| Production comparison, 2026-08-26 | Installed control | Folded candidate |
| --- | ---: | ---: |
| Changed lines | 19,654 | 19,654 |
| Total DOM nodes | 182,686 | 6,476 |
| Visible diff rows | 19,654 | 195 |
| Rows retained under collapsed folds | Unbounded | 0 |
| Longest task | 552 ms | 127 ms |
| Tasks over 200 ms | 2 | 0 |
| Whole-comparison mount or projection | 282 ms mount | 5 ms projection |

The production measurement, current test contract, and implementation details live in
the
[general diff rendering plan](../../specs/active/plan-2026-08-17-general-diff-rendering.md#phase-5-large-folded-comparison-responsiveness).

## Packaging Measurements and Correction

The July spike installed its selected packages with lifecycle scripts disabled and
successfully bundled a single unminified ESM entry with esbuild 0.28.1. Repeated builds
of that exact input were byte-identical.

| Artifact | Raw size | Gzip size |
| --- | ---: | ---: |
| Pierre vanilla entry with all Shiki languages | 10.6 MB | 1.82 MB |
| `@git-diff-view/core` | 1.7 MB | 409 KB |
| Custom renderer source | 5.5 KB | Not recorded |

The Pierre output exceeded the repository’s current 1.7 MB per-file vendor cap by more
than six times before compression.
Any later integration needs a deliberate language subset or chunking design and a
measured cap change.

The original report said esbuild needed no lifecycle scripts.
That wording was wrong.
The selected July installation worked under `--ignore-scripts`, but the current esbuild
package declares a `postinstall` script.
A future implementation must inspect the exact cooled-off release and prove its locked
install and execution under the repository’s script policy.
Byte identity must also be re-established for the chosen version, platform,
configuration, and entry graph.

## Disposition

The historical source, generated fixtures, npm lockfiles, and renderer harnesses are not
carried forward:

- the File Diff Format and production Git source supersede the adapter prototype
- the built-in renderer supersedes the custom table prototype
- the current performance loop has stronger browser evidence and budget gates
- the old third-party versions and locks are not valid implementation inputs

The measurements above remain useful for three open decisions: deferring exact totals
for uncommitted changes, reopening the renderer dependency gate for worker tokenization
or virtualization, and choosing a reproducible ESM vendor-build mechanism.

## References

- [Pull request #12](https://github.com/jlevy/metabrowser/pull/12)
- [Historical spike tree](https://github.com/jlevy/metabrowser/tree/414a2fc313d45044295d3bae9b1ac77028c6b2bb/spikes/diff-view)
- [Web Diff Viewer Architecture and Intermediate Representations](../research-2026-07-17-web-diff-viewer-architecture.md)
- [Browser Contributor Toolchain and Distribution](../research-2026-07-18-browser-contributor-toolchain.md)
- [General Diff Rendering](../../specs/active/plan-2026-08-17-general-diff-rendering.md)
- [Web Performance Framework](../../../web-performance-framework.md)
- [Rendering Large Content](../../../large-content-rendering.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
