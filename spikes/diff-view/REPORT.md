# Diff View Spike Report

**Date:** 2026-07-18

**Status:** Complete

Measurements from the spikes under this directory, on this repository’s cloud dev
container (Linux x86_64, headless Chromium via Playwright 1.61.0, git 2.43). Fixtures:
`small` = 200-line file, 3 edit blocks; `medium` = single-file refactor, ~2,000 patch
lines; `huge` = full lockfile rewrite, 37,502 patch lines; `set50` = 50 small files.

## Backend: Hardened Git Adapter

Synthetic dirty repository: 519 changed files, including 500 small edits, a 30k-line
lockfile rewrite, 12 untracked files, renames, deletions, a binary change, and partial
staging.

| Operation | Result |
| --- | --- |
| `status --porcelain=v2 -z` + parse | 10.1 ms |
| `diff HEAD --numstat -z -M` | 98.2 ms |
| Manifest total (status + numstat) | 109.0 ms |
| Per-file patch (typical file) | 2-3 ms |
| Per-file patch (30k-line lockfile) | 116.2 ms |
| One-shot `git diff HEAD` for contrast | 132.4 ms, 8.8 MB of patch text |

Correctness verified in the manifest: renames carry `oldPath`, partial staging reports
`staged` and `unstaged` on the same file, binary and untracked files are flagged, and
untracked synthesis respects byte/line caps.
The hardened invocation profile (sanitized env, `--no-optional-locks`, disabled
fsmonitor/hooks/ext-diff/textconv, literal pathspecs) worked without incident.

**Learnings.** Manifest-first is validated, but the win over one-shot is in transfer and
parse (a manifest is ~100 KB of JSON versus 8.8 MB of patch text), not in git time.
`--numstat` is 90% of manifest latency; totals should be deferrable or computed in a
second request so the changes list can paint from status alone (~10 ms).
Porcelain v2 and NUL-delimited parsing were straightforward; no library needed.

## Renderers

All scenarios render the same fixtures.
`renderMs` is synchronous wall time to a settled frame; node counts include open shadow
roots.

| Scenario | custom | server_html (insert) | gdv core+DOM | pierre (patch input) |
| --- | --- | --- | --- | --- |
| small | 10.3 ms / 331 nodes | 8.6 ms | 15.1 + 46.9 ms / 325 | 176.2 ms / 994 |
| medium | 66.3 ms / 6,430 | 71.7 ms | 36.2 + 132.9 ms / 6,310 | 726.8 ms / 18,607 |
| huge (full) | 2,056 ms / 187,522 | 2,042 ms | 295.7 + 5,994 ms / 187,520 | 75,750 ms / 633,075 |
| huge (gated at 1,500 rows) | 195.1 ms | n/a (whole-payload) | n/a | n/a |
| set50 initial (8 eager + lazy) | 64.8 ms | n/a | n/a | n/a |
| set50 all 50 mounted | 121.6 ms | n/a | n/a | n/a |

Additional pierre scenarios (client-side diffing via jsdiff from file contents): small
498.5 ms; medium 1,582 ms; huge with plain-text language 139.3 s; huge with highlighting
212.3 s (first run).
Server-precomputed patch input (`processFile`, `isGitDiff`) removes that cost entirely,
confirming the manifest+patch architecture.
`gdv:medium:syntax_init` (lowlight model) was 13.3 ms.

Server-side HTML rendering in Python: small 0.06 ms / 12 KB, medium 1.07 ms / 246 KB,
huge 46.3 ms / 11.5 MB of HTML.

**Learnings.**

- **Gating is the decisive lever, not renderer choice.** Full-mounting the lockfile
  rewrite costs ~2 s in the best case and 76 s in the worst; the gated render costs 195
  ms. Every fast product in the research gates large diffs; the spike confirms why.
- **The custom renderer meets the plan’s bar.** Typical agent-change files render in
  10-70 ms with zero dependencies (5.5 KB source).
  The 50-file changeset paints in 65 ms with progressive mounting.
- **Client-side diff computation is disqualifying for pathological files.** jsdiff on
  the 18k/19.5k-line pair costs 2-3.5 minutes regardless of highlighting.
  Diffs must come precomputed from the server (or a worker with a better algorithm),
  which is the plan’s architecture.
- **`@pierre/diffs` must be used with its virtualization and workers to be viable at the
  high end.** In its default non-virtualized `FileDiff` configuration it builds 3.4x
  more DOM than the table renderers and spends tens of seconds on the pathological case
  on the main thread. Its `CodeView`/virtualized components and worker pool (untested
  here; `CodeView` is beta-line) are the intended path, at real integration complexity.
  For typical files it is 10-20x slower than the custom table but absolutely fine
  (176-727 ms) and visually richer.
- **`@git-diff-view/core` is a patch presenter, not a differ.** Given only file contents
  it silently produces zero diff lines (API gotcha); it requires git-format hunks as
  input. Its model layer is cheap (15-296 ms), but its per-line getter DOM path was 3x
  slower than the custom table on huge, and it adds 409 KB gzip for little benefit over
  owning the table.
- **Server-rendered HTML is not a shortcut.** Insert+parse of 11.5 MB of server HTML
  costs the same ~2 s as building the DOM client-side from JSON, and the payload is much
  larger. It remains attractive only as an export/print projection.

## Packaging (Option C validation)

- Quarantined npm installs with `ignore-scripts` worked for every package; esbuild
  needed no lifecycle scripts.
- esbuild single-entry unminified ESM bundling of `@pierre/diffs` (56 packages
  installed) produced **byte-identical output across repeated builds** (sha256
  compared), supporting the committed-vendor-artifact + CI rebuild-diff design.
- Bundle sizes: pierre vanilla entry **10.6 MB raw / 1.82 MB gzip** (full Shiki language
  set); gdv core 1.7 MB raw / 409 KB gzip; custom renderer 5.5 KB raw.
  The pierre artifact exceeds the current vendor caps (1.7 MB/file, 3 MB total) by 6x
  raw; adopting it requires language-subset entry points and a deliberate cap raise.
- The preinstalled Playwright Chromium drove all pages headlessly via `executablePath`;
  a pinned `playwright` npm package (1.61.0) was the only harness dependency.

## Spec Refinements Fed Back

1. Phase 1 manifest should return from porcelain status alone and treat numstat totals
   as a deferrable second step (quantified: 10 ms vs 109 ms).
2. The per-file patch gate (default max rows before load-more) is the core requirement
   for agent workflows; 1,500-4,000 rows keeps worst-case renders under ~250 ms.
3. The phase 3 renderer gate gains measured criteria: any library must be adopted in its
   virtualized/worker configuration, with language-subset bundles, and beat the custom
   renderer’s numbers above on the same fixtures.
4. `@git-diff-view/core`’s input contract (hunks required) matches the server-patch
   architecture but its DOM layer is not worth its size; if reused at all, it would be
   as a model/tokenizer only.

## Disposition

Keep as reference under `spikes/diff-view/` (committed sources and lockfiles; generated
artifacts and `node_modules` ignored).
The custom renderer and the adapter parsing code are intentionally close to production
shape and can seed the phase 1 implementation.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
