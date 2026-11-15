# Feature: Mermaid Diagram Rendering

**Date:** 2026-08-21 (last updated 2026-11-14)

**Author:** Metabrowser maintainers

**Status:** Draft; not started.
The on-demand loading tier it uses is implemented: `static/asset-loader.js`
(`ensureAsset`) and `on_demand_script_bundles` in `server.py`. That loader injects
classic scripts only, so the Mermaid ESM entry needs a dynamic import or a module entry
in `asset-loader.js` (`mb-y7zh`). Tracked by `mb-qz51`.

## Overview

A `` ```mermaid `` fence renders as a diagram on GitHub and as a code block in
Metabrowser. This plan renders it, at parity with GitHub or better, and adds nothing to
the load time of a document that contains no diagram.

Most of the pipeline already exists.
KPress treats a Mermaid fence as a diagram rather than as code, ships a `js/diagrams.js`
behavior that swaps the source for rendered SVG, and lists that module as an asset entry
point which `plugin-sdk.js` already loads.
It returns on its first line, because it asks the host for `globalThis.mermaid` and
Metabrowser never defines it.

The missing inputs are a vendored library and a per-mount call.
The library is 3.5 MB, which is why this plan uses the on-demand loading tier from
[end-to-end load time](plan-2026-08-21-load-time-performance.md) rather than defining
one of its own. Mermaid is that tier’s largest consumer and its clearest test.

## Goals

- Render Mermaid fences in rendered Markdown, at parity with GitHub or better
- Add nothing to documents that contain no diagram
- Keep the library vendored and same-origin, so the browser still has no external
  origins and still works offline
- Keep the no-JavaScript fallback: a diagram that cannot render shows its source
- Keep diagrams inside the trusted-local invariant: no script execution, no navigation

## Non-Goals

- The asset loading tiers themselves, which belong to
  [end-to-end load time](plan-2026-08-21-load-time-performance.md)
- Diagram authoring, editing, or export
- GitHub’s other diagram fences (`geojson`, `topojson`, `stl`) and its math support
- A build step or bundler

## Background

Rendering a Mermaid fence through `kpress_adapter.render_kpress_view` against the pinned
`kpress==0.3.5` produces a figure that carries its own source and status:

```html
<figure class="kpress-diagram kpress-mermaid"
  data-kpress-diagram="mermaid" data-kpress-diagram-provider="mermaid"
  data-kpress-diagram-status="source">
  <pre class="kpress-diagram-source"><code class="language-mermaid">…</code></pre>
</figure>
```

The same render returns an asset manifest listing `js/diagrams.js`, which
`plugin-sdk.js` already fetches and evaluates.
The figure stays at `data-kpress-diagram-status="source"` and the reader sees Mermaid
source.

[Mermaid diagram support](../../research/research-2026-08-21-mermaid-diagram-support.md)
carries the full analysis: what GitHub does, read from its served markup and renderer
bundle, and what the library costs.
The two measurements that decide the design: the single-file UMD bundle is 3,572,296
bytes and costs 449 ms of fetch, parse, and evaluate on every document, while the ESM
build loads a 30,255-byte entry and pulls chunks per diagram type — 859,233 bytes and
101 ms for a document with a flowchart, then about 34 ms for each additional diagram of
the same type.

Two properties make the ESM tree loadable with no build step: every specifier in it is
relative, so no import map is needed, and its chunk filenames already carry content
hashes, so only the entry point needs a cache-buster.

## Design

### Approach

Vendor the Mermaid ESM build.
Load it through the on-demand tier when a mounted document contains a diagram figure,
and never otherwise.
Then hand it to KPress, which owns everything downstream.

### Components

**`static/vendor/mermaid/`.** The ESM entry plus its chunk directory, 104 files,
3,521,725 bytes, from an exact npm pin.

**`devtools/vendor_assets.py`.** A directory-shaped vendor entry that copies and hashes
a tree, since every entry today is one flat file.
`TOTAL_CAP_BYTES` rises from 3,000,000 with the measured tree size recorded beside it.
`PER_FILE_CAP_BYTES` stays at 1,700,000: the largest Mermaid chunk is 705,086 bytes.

**`static/plugin-sdk.js`.** Gains `kpressInitDiagrams(container)`, mirroring
`kpressInitToc`: ensure Mermaid through the asset loader, assign `window.mermaid`,
import KPress’s `diagrams.js`, capture `initKpressDiagrams`, run it against the
container, and return a disposer.
Declared in `static/types.d.ts`.

**`builtin_plugins/markdown/rendered.js`.** Calls `mb.kpressInitDiagrams(container)`
beside its existing `kpressInitToc`, only when the container holds a
`[data-kpress-diagram="mermaid"]` figure, storing the disposer beside `disposeToc`.

### API Changes

`window.metabrowser` gains `kpressInitDiagrams(container)`. This is additive, and
`PLUGIN_SDK_VERSION` does not move: the gate is an exact-match test, so a bump would
force an edit to every built-in manifest and buy nothing.

Mermaid initializes under KPress’s `securityLevel: "strict"`, which encodes HTML in
labels and disables `click`. That is stricter than GitHub’s `antiscript` and is the
correct default for a tool pointed at arbitrary local directories, particularly while
Metabrowser serves no Content Security Policy.
Mermaid’s `maxTextSize` of 50,000 characters and `maxEdges` of 500 stay at their
defaults, which is what GitHub ships, and their failure is surfaced rather than
swallowed.

Rendering a diagram in the document rather than in a cross-origin iframe is where this
can be better than GitHub: the SVG inherits the design tokens, prints with the document,
and takes part in selection and copy, none of which GitHub’s isolation allows.

## Implementation Plan

The on-demand asset tier from
[end-to-end load time](plan-2026-08-21-load-time-performance.md) is on `main`, but
`asset-loader.js` injects classic scripts only, so the Mermaid ESM entry needs a dynamic
import or a module entry in `asset-loader.js` ([Open Questions](#open-questions)).

### Phase 1: Diagrams That Render

- [ ] Extend `devtools/vendor_assets.py` with a directory entry, raise `TOTAL_CAP_BYTES`
  with the measurement recorded beside it, and leave `PER_FILE_CAP_BYTES` alone
  (`mb-98mi`)
- [ ] Vendor Mermaid at an exact pin, add the `package.json` pin and the `NOTICE.md`
  entry, and check the manifest into `static/vendor/manifest.json` (`mb-98mi`)
- [ ] Load Mermaid on demand (a dynamic import, or a module entry in `asset-loader.js`)
  and add `kpressInitDiagrams` to `plugin-sdk.js` and `static/types.d.ts` (`mb-y7zh`)
- [ ] Call it from `rendered.js`, gated on the figure being present, with disposal
  (`mb-fzm7`)
- [ ] Confirm through the load-time harness that a document with no diagram requests
  nothing new
- [ ] Cover lazy mount, replacement, disposal, and theme change in `tests/dom`
  (`mb-xm9c`)

### Phase 2: Parity and the States Around the Diagram

- [ ] Drive the Mermaid theme from `data-theme` and re-render diagrams on theme change
  (`mb-19sr`)
- [ ] Add a copy button to the diagram figure, which KPress does not add because the
  figure carries `kpress-diagram-source` rather than `kpress-code` (`mb-e9vy`)
- [ ] Surface a legible parse error: KPress already sets
  `data-kpress-diagram-status="error"` and restores the source, so the host supplies the
  message (`mb-e9vy`)
- [ ] Surface the `maxTextSize` and `maxEdges` failures visibly rather than silently
  (`mb-e9vy`)
- [ ] Note the change in `CHANGELOG.md`

## Testing Strategy

In `tests/dom`: a document with a Mermaid fence mounts and reaches
`data-kpress-diagram-status="rendered"`; a document without one never requests the
Mermaid entry; navigating away disposes; navigating between two diagram documents
replaces rather than accumulates; a theme change re-renders; a malformed diagram reaches
the error state with its source visible.

The existing vendor manifest parity test covers the new tree hash for hash, with no
`node_modules` needed.

The load-time harness confirms the claim that a diagram-free document pays nothing, so
that claim is a measurement rather than an intention.

## Rollout Plan

Server, shell, and built-in plugins ship as one artifact, so both phases land as
ordinary commits with no flag.
Phase 1 is independently shippable; Phase 2 is polish on a working feature.

The one deliberate cost is the wheel: the Mermaid tree adds 1,018,858 bytes zipped.
`git archive --format=zip` of `src/metabrowser` measures 886,342 bytes at this plan’s
commit (`602b78d5`) and 2,142,620 bytes at `c098e6a8`, so a tree that roughly doubled
the package then adds about half again now.
That trade is recorded here and beside the size cap.

## Open Questions

- `asset-loader.js` loads classic scripts only, and the Mermaid entry is an ES module.
  Either the loader gains a module entry, or `kpressInitDiagrams` imports the entry
  directly the way `_loadKpressTocModule` in `plugin-sdk.js` imports KPress’s TOC
  module, which is what `mb-y7zh` describes.
- Should a diagram-using repository prefetch Mermaid after the first diagram is seen, on
  the theory that it has more?
  Measurable once Mermaid loads through the tier, not before.
- Does a large diagram want an expand or zoom affordance?
  A 500-node flowchart measures 771,427 bytes of SVG and 7,038 nodes, so the question is
  real, but it is separate from rendering.

## References

- [Mermaid diagram support](../../research/research-2026-08-21-mermaid-diagram-support.md)
  — the research behind this plan
- [End-to-end load time](plan-2026-08-21-load-time-performance.md) — the loading tier
  this depends on
- [Asset loading tiers](../../architecture/arch-browser-shell.md#asset-loading-tiers) —
  the policy
- [Rendering large content](../../../large-content-rendering.md) — the cost model
- [Mermaid](https://github.com/mermaid-js/mermaid) — upstream project, MIT licensed

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
