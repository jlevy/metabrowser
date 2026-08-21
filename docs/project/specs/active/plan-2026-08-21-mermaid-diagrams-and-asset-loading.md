# Feature: Mermaid Diagrams and a Loading Policy for Large Browser Assets

**Date:** 2026-08-21

**Author:** Metabrowser maintainers

**Status:** Draft

## Overview

A `` ```mermaid `` fence renders as a diagram on GitHub and as a code block in
Metabrowser.
This plan renders it, and it does so without making every document pay for a
3.5 MB diagram compiler.

Those are one piece of work rather than two.
Mermaid cannot join the existing vendored-asset chain, because that chain loads
everything on every page.
Adding Mermaid to it would multiply the browser’s third-party payload by nine.
So the same change that renders diagrams also has to give Metabrowser a way to load a
large library only when it is wanted — and once that exists, the Chart.js stack should
use it too: it costs a measured 374 ms of load time on every document, and only the
agent-log charts view reads it.

The result is one **asset loading policy** with three tiers, and Mermaid as its first
fully lazy consumer.

## Goals

- Render Mermaid fences in rendered Markdown, at parity with GitHub or better
- Add no cost to documents that contain no diagram
- Give browser assets an explicit loading tier — eager, prefetched, or on demand — and
  put each large third-party library in the right one
- Keep every third-party file vendored and same-origin, so the browser still has no
  external origins and still works offline
- Keep the no-JavaScript fallback: a diagram that cannot render shows its source
- Keep diagrams inside the trusted-local invariant: no script execution, no navigation

## Non-Goals

- Diagram authoring, editing, or export
- GitHub’s other diagram fences (`geojson`, `topojson`, `stl`) and its math support
- A build step or bundler.
  Metabrowser ships unbundled browser modules and this plan keeps that.
- Restructuring the eager core shell.
  First contentful paint measures 76–100 ms today and is not the problem.
- The strict application-shell Content Security Policy, which stays deferred to
  [the HTML trust model plan](plan-2026-08-06-html-rendering-and-trust-model.md)

## Background

### What Renders a Diagram Today

Almost all of it. KPress 0.3.3 treats a Mermaid fence as a diagram rather than as code,
and emits a figure that carries the source and its own status:

```html
<figure class="kpress-diagram kpress-mermaid kpress-figure"
  data-kpress-diagram="mermaid" data-kpress-diagram-provider="mermaid"
  data-kpress-diagram-status="source">
  <pre class="kpress-diagram-source"><code class="language-mermaid">…</code></pre>
</figure>
```

It adds `js/diagrams.js` to the render’s asset manifest whenever that markup appears,
and `plugin_sdk.js` already loads every module entry point in that manifest.
So the module is fetched and evaluated today.
It returns on its first line, because `hostMermaid()` reads `globalThis.mermaid` and
Metabrowser never defines it.
The figure stays at `data-kpress-diagram-status="source"` and the reader sees Mermaid
source.

The full analysis is in
[Mermaid diagram support](../../research/research-2026-08-21-mermaid-diagram-support.md),
including what GitHub does, read from its served markup and renderer bundle.

### What Loads Today, and What It Costs

Core shell scripts are local, first-paint critical, and load as ordinary blocking
`<script>` tags. After them, an inline loader walks `optional_script_assets` in
`server.py`, appending one `<script async=false>` at a time and chaining each on the
previous one’s `onload`. Six vendored files, 432,092 bytes, on every page.

Measured against the served repository in Chromium 141 (Playwright build 1194) on this
machine, `/view/README.md`, median of five cold loads:

| Scenario | FCP | DOMContentLoaded | `load` | Transferred |
| --- | --- | --- | --- | --- |
| Today, all vendor assets eager | 76 ms | 218 ms | 853 ms | 823,391 B |
| Chart.js stack blocked | 88 ms | 246 ms | 479 ms | 725,841 B |
| All vendor JS blocked | 100 ms | 252 ms | 330 ms | 719,794 B |

The eager core is fine.
First contentful paint does not move, because the optional chain starts after it.
What moves is `load`: the Chart.js stack alone accounts for about 374 ms, and the whole
vendored chain about 523 ms, of every document’s load.
Transferred bytes move much less than disk bytes because responses are compressed; the
cost is parse and evaluate, which scales with uncompressed size.

The chain is serial by construction, and its per-file gaps are that main-thread work:

| Vendored file | Request start | Response end |
| --- | --- | --- |
| `mustache.min.js` | 218 ms | 234 ms |
| `highlight.min.js` | 285 ms | 298 ms |
| `highlight-toml.min.js` | 364 ms | 368 ms |
| `chart.umd.min.js` | 401 ms | 418 ms |
| `chartjs-plugin-annotation.min.js` | 440 ms | 445 ms |
| `chartjs-adapter-date-fns.bundle.min.js` | 448 ms | 461 ms |

Who actually uses each:

| Library | Bytes | Used by |
| --- | --- | --- |
| Chart.js and its two plugins | 297,531 | The agent-log `charts` view only |
| highlight.js and the TOML grammar | 122,771 | Client-side highlighting of source views |
| Mustache | 11,790 | `metabrowser.render` in the plugin SDK |

Every one already tolerates absence.
`charts.js` guards `typeof Chart === "undefined"`, `app.js` returns early when `hljs` is
undefined, and `plugin_sdk.js` throws a named error when `Mustache` is missing.
That is what makes reclassification mechanical: each guard becomes an await rather than
a bail-out.

### The Lazy ESM Mechanism Already Exists

`plugin_sdk.js` loads KPress’s `toc.js` by dynamic import, captures its named export,
and exposes a per-mount wrapper:

```js
await _loadKpressAssetOnce(url, async () => {
  const mod = await import(url);
  if (mod && typeof mod.initKpressToc === "function") {
    _kpressInitTocFn = mod.initKpressToc;
  }
});
```

`_loadKpressAssetOnce` keeps a loaded set and an in-flight promise map, so concurrent
callers share one load and a repeat is free.
`tsconfig.json` sets `"module": "ES2022"` with `"moduleResolution": "bundler"`, so
dynamic import type-checks.

Nothing new has to be invented.
What is missing is that this machinery is private to the KPress asset path and
hard-codes one module.
Generalizing it is the whole mechanism half of this plan.

Two properties make a vendored Mermaid tree fit it cleanly.
Every import and dynamic import in Mermaid’s ESM build is relative, so no import map is
needed. And its chunk filenames already carry content hashes, so only the entry needs
`_static_asset_url`’s `?v=` cache-buster; the chunks are immutable by name.

## Design

### Approach

Three loading tiers, named, with each large asset assigned to one.

**Eager.** Blocking `<script>` in the shell.
For code without which the first render is wrong.
This is the existing core list and it does not change.

**Prefetched.** Fetched after first paint, during idle, before anything asks for it.
For code that is small relative to its likelihood of being needed, where arriving late
would be visible. highlight.js, its TOML grammar, and Mustache go here.
This is close to what the optional chain does today, with two differences: it yields to
idle instead of racing the tree render, and a consumer can await it rather than
discovering it missing.

**On demand.** Fetched the first time something needs it, never otherwise.
For code that is large, or narrowly used, or both.
The Chart.js stack and Mermaid go here.

The tier is a property of the asset, declared in one place, and the loader is one module
that all three tiers share.
A consumer asks for a library by name and awaits it; whether that resolves instantly,
soon, or after a fetch is the tier’s business, not the caller’s.

### Components

**`static/asset_loader.js` (new).** The one loader.
Exports `ensureAsset(name)` returning a promise that resolves when the named library’s
global is present, plus `prefetchAssets()` for the idle pass.
Generalizes `_loadKpressAssetOnce`’s loaded-set and in-flight-map, handles both classic
scripts that define a global and ESM entries that must be imported and assigned, and
resolves URLs through the asset descriptor the server publishes.
A new module, so it goes under the fully strict `tsconfig.json` gate rather than into
`plugin_sdk.js`, which is on the legacy allowlist.

**`server.py`.** `optional_script_assets` becomes an asset descriptor carrying a tier
per entry, published to the client rather than expanded into an inline script chain.
The eager core block is untouched.
The `metabrowser:optional-asset-loaded` and `metabrowser:optional-assets-loaded` events
that `app.js` uses to re-run `highlightCode()` keep firing, so late-arriving
highlighting still re-enhances the current view.

**`static/vendor/mermaid/`.** `mermaid.esm.min.mjs` plus `chunks/mermaid.esm.min/*.mjs`,
104 files, 3,521,725 bytes, from an exact npm pin.

**`devtools/vendor_assets.py`.** A directory-shaped vendor entry that copies and hashes
a tree, since every entry today is one flat file.
`TOTAL_CAP_BYTES` rises from 3,000,000 with the measured tree size recorded beside it.
`PER_FILE_CAP_BYTES` stays at 1,700,000: Mermaid’s largest chunk is 705,086 bytes.

**`static/plugin_sdk.js`.** Gains `kpressInitDiagrams(container)`, mirroring
`kpressInitToc`: ensure Mermaid, assign `window.mermaid`, import KPress’s `diagrams.js`,
capture `initKpressDiagrams`, run it against the container, return a disposer.
Declared in `static/types.d.ts`.

**`builtin_plugins/markdown/rendered.js`.** Calls `mb.kpressInitDiagrams(container)`
beside its existing `kpressInitToc`, only when the container holds a
`[data-kpress-diagram="mermaid"]` figure, storing the disposer beside `disposeToc`.

### API Changes

`window.metabrowser` gains `kpressInitDiagrams(container)`. This is additive.
`PLUGIN_SDK_VERSION` does not move: the gate is an exact-match test that fails any
plugin declaring a different version, so a bump would force an edit to every built-in
manifest and buy nothing.
Per the repository’s rule, the bump belongs to a break, and this is not one.

`METABROWSER_SETTINGS` gains the asset descriptor the loader reads.
Server, shell, and built-in plugins ship as one artifact, so this changes in one commit.

Mermaid initializes under KPress’s `securityLevel: "strict"`, which encodes HTML in
labels and disables `click`. That is stricter than GitHub’s `antiscript` and is the
correct default for a tool pointed at arbitrary local directories, particularly while
Metabrowser serves no Content Security Policy.
Mermaid’s `maxTextSize` of 50,000 characters and `maxEdges` of 500 stay at their
defaults, which is what GitHub ships, and their failure is surfaced rather than
swallowed.

## Implementation Plan

### Phase 1: The Loader, the Tiers, and Diagrams That Render

- [ ] Add `static/asset_loader.js` with `ensureAsset` and `prefetchAssets`, under the
  strict `tsconfig.json` gate, with the loaded-set and in-flight-map semantics
  generalized from `_loadKpressAssetOnce`
- [ ] Turn `optional_script_assets` into a tiered asset descriptor published to the
  client; keep the two `metabrowser:optional-asset*` events firing
- [ ] Move highlight.js, the TOML grammar, and Mustache to the prefetched tier and run
  that pass on idle
- [ ] Move the Chart.js stack to the on-demand tier and make `charts.js` await
  `ensureAsset("chart")` where it guards `typeof Chart === "undefined"` today
- [ ] Extend `devtools/vendor_assets.py` with a directory entry, raise `TOTAL_CAP_BYTES`
  with the measurement recorded beside it, and leave `PER_FILE_CAP_BYTES` alone
- [ ] Vendor Mermaid at an exact pin, add the `package.json` pin and the `NOTICE.md`
  entry, and check the manifest into `static/vendor/manifest.json`
- [ ] Add `kpressInitDiagrams` to `plugin_sdk.js` and `static/types.d.ts`
- [ ] Call it from `rendered.js`, gated on the figure being present, with disposal
- [ ] Re-run the cold-load profile and record the numbers in this document

### Phase 2: Diagram Parity and the States Around It

- [ ] Drive the Mermaid theme from `data-theme` and re-render diagrams on theme change
- [ ] Add a copy button to the diagram figure, which KPress does not add because the
  figure carries `kpress-diagram-source` rather than `kpress-code`
- [ ] Surface a legible parse error: KPress already sets
  `data-kpress-diagram-status="error"` and restores the source, so the host supplies the
  message
- [ ] Surface the `maxTextSize` and `maxEdges` failures visibly rather than silently
- [ ] Note the change in `CHANGELOG.md`

## Testing Strategy

**Loading tiers.** Assert the eager core block still precedes any tiered asset in the
shell, which `tests/test_index_cdn_origins.py` already checks in its current form.
Assert the Chart.js stack is absent from the initial document and arrives only after the
charts view is opened.
Assert `ensureAsset` returns the same promise for concurrent callers and does not
refetch after resolution.

**Diagrams.** In `tests/dom`: a document with a Mermaid fence mounts and reaches
`data-kpress-diagram-status="rendered"`; a document without one never requests the
Mermaid entry; navigating away disposes; navigating between two diagram documents
replaces rather than accumulates; a theme change re-renders; a malformed diagram reaches
the error state with its source visible.

**Vendoring.** The existing manifest parity test covers the new tree, hash for hash,
with no `node_modules` needed.

**Regression.** Source-view highlighting must still appear when highlight.js arrives on
the prefetch tier rather than the eager chain, driven by the existing
`metabrowser:optional-asset-loaded` re-enhance path.

**Measurement.** Re-run the cold-load profile above after Phase 1 and record it, so the
claim that documents without diagrams pay nothing is a measurement rather than an
intention.

## Rollout Plan

Server, browser shell, and built-in plugins ship as one artifact, so both phases land as
ordinary commits with no flag and no migration.
Phase 1 is independently shippable: it improves load time and renders diagrams.
Phase 2 is polish on a working feature.

The one reversible risk is the wheel size, which roughly doubles: `src/metabrowser` is
948,476 bytes zipped today and the Mermaid tree adds 1,018,858 bytes zipped.
That is a deliberate trade recorded here and beside the size cap, not a number nudged
until a check passes.

## Open Questions

- Should the prefetch tier wait for `requestIdleCallback` or for a fixed delay after
  `load`? Idle is the better default; a timeout fallback is needed for browsers where
  idle never fires under load.
- Should Mermaid prefetch once a diagram figure has been seen in *any* document this
  session, on the theory that a diagram-using repository has more of them?
  Measurable after Phase 1, not before.
- Does the diagram figure want an expand or zoom affordance for large diagrams?
  A 500-node flowchart measures 771,427 bytes of SVG and 7,038 nodes, so the question is
  real, but it is a separate decision from rendering.

## References

- [Mermaid diagram support](../../research/research-2026-08-21-mermaid-diagram-support.md)
  — the research behind this plan
- [Rendering large content](../../../large-content-rendering.md) — the cost model this
  follows
- [Full-page HTML rendering and an explicit trust model](plan-2026-08-06-html-rendering-and-trust-model.md)
  — the trust posture diagrams sit inside
- [Mermaid](https://github.com/mermaid-js/mermaid) — upstream project, MIT licensed

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
