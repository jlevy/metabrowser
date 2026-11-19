# Feature: Mermaid Diagram Rendering

**Date:** 2026-08-21 (last updated 2026-11-18)

**Author:** Metabrowser maintainers

**Status:** In progress.
Tracked by `mb-qz51`. Revised on 2026-11-18 against GitHub’s served renderer and KPress
0.3.8, which changed four things since the first draft: GitHub now ships Mermaid 12.3.0,
it draws pan, zoom, and expand controls, it renders `.mmd` and `.mermaid` files, and the
documents Metabrowser most often shows from GitHub, a mirror’s and a revision’s, are
rendered inert, where the first draft rendered nothing.

## Overview

A `` ```mermaid `` fence renders as a diagram on GitHub and as a code block in
Metabrowser. This plan renders it everywhere GitHub does, at parity or better, and adds
nothing to the load time of a document that contains no diagram.

The standard is: a page that renders a diagram on github.com renders the same diagram in
Metabrowser, from the same Mermaid release, in a trusted folder and in an untrusted
mirror alike.
Where Metabrowser can do better than GitHub’s cross-origin iframe, it does:
the diagram follows the app’s theme live, prints and selects with the prose, and keeps
its source a click away.

## Goals

- Render Mermaid fences in rendered Markdown in trusted and inert renders
- Render `.mmd` and `.mermaid` files as diagrams, with a Source view, as GitHub does
- Match GitHub’s Mermaid release and its observable configuration
- Match GitHub’s controls: copy source, expand, zoom, and pan
- Add nothing to documents that contain no diagram
- Keep the library vendored and same-origin, so the browser still has no external
  origins and still works offline
- Keep the no-JavaScript fallback: a diagram that cannot render shows its source
- Keep an untrusted document unable to run script or navigate, and say why that holds

## Non-Goals

- Diagrams inside rendered Markdown diffs, which keep showing the fence’s source, as a
  reviewer of a diagram change needs
- Diagram authoring, editing, or export
- GitHub’s other rich fences (`geojson`, `topojson`, `stl`) and its math support
- A build step or bundler

## Background

### What GitHub Does

Read from github.com and `viewscreen.githubusercontent.com` on 2026-11-18, extending
[Mermaid diagram support](../../research/research-2026-08-21-mermaid-diagram-support.md),
which read them on 2026-08-21.

- **Release.** The renderer bundle, `mermaidMarkdown-*.js` at 1,824,314 bytes, embeds
  Mermaid **12.3.0** (it was 11.16.1 in August).
- **Configuration.** Unchanged: `securityLevel: "antiscript"` behind DOMPurify and the
  iframe’s CSP, `theme` `dark` or `default` from the color mode, Mermaid’s default
  `maxTextSize` and `maxEdges`.
- **Isolation.** Each diagram renders in an iframe on another origin.
- **Controls.** Around the diagram: a copy-source button and an expand button that opens
  the diagram in a dialog.
  Inside it, on hover: zoom in, zoom out, reset, and four pan arrows.
- **Files.** A `.mmd` or `.mermaid` blob has Preview, Code, and Blame tabs, Preview
  first, drawing the file as one diagram.
- **Where.** Markdown files, issues, pull requests and their comments, discussions,
  wikis, and gists. A fork’s pull request renders its diagrams like any other.
- **`svg` fences.** Shown as highlighted code, never drawn.

### What Metabrowser Does Today

KPress 0.3.8, the pinned release, emits this for a Mermaid fence when its `diagrams`
option is not `off`:

```html
<figure class="kpress-diagram kpress-mermaid"
  data-kpress-diagram="mermaid" data-kpress-diagram-provider="mermaid"
  data-kpress-diagram-status="source">
  <pre class="kpress-diagram-source"><code class="language-mermaid">…</code></pre>
</figure>
```

and adds `js/diagrams.js` to the asset manifest, which `plugin-sdk.js` loads.
That module returns at once, because it asks for `globalThis.mermaid` and nothing
defines it. The reader sees the source.

An inert render reduces the figure to `<pre><code>`: `figure` is not in
`inert_html.py`’s `ALLOWED_TAGS`, and classes and `data-*` are dropped, so nothing marks
the block as a diagram any more.

KPress also draws a
`` ```svg `` fence as sanitized inline SVG, which GitHub never does. In an inert render, `svg` is in `DROPPED_WITH_CONTENT`,
so the block disappears.

### Cost

Mermaid 12.3.0’s ESM build is a 30,936-byte entry and 105 chunks totaling 5,404,632
bytes; the largest is ELK’s layout engine at 1,620,399 bytes, which loads only for a
diagram that asks for the ELK layout.
The August measurement of 11.17.0 holds in shape: the entry pulls chunks per diagram
type, so a document with flowcharts pays for the flowchart chunks once, and a document
with no diagram pays nothing.
The UMD bundle, by contrast, costs every document 449 ms.

## Design

### Approach

Pin Mermaid 12.3.0, GitHub’s release, and vendor its ESM build.
Load it through the on-demand tier, as a module, the first time a mounted view holds a
diagram, and never otherwise.

Metabrowser draws the diagram itself, in a renderer module in the Markdown plugin that
reads KPress’s figure contract and never sets `globalThis.mermaid`. KPress 0.3.8’s
`initKpressDiagrams` cannot meet the goals as it stands: it has no theme or disposal,
swallows Mermaid’s error, renders only in the document, and draws no controls.
[Division of Work](#division-of-work-kpress-and-metabrowser) lists what KPress should
grow so the renderer can move there.

A trusted render places the SVG in the document.
An inert render places it as an image: Mermaid runs on Metabrowser’s own code path under
`securityLevel: "strict"`, and its SVG is shown through
`<img src="data:image/svg+xml…">`, where it can run no script, load nothing, and
navigate nowhere, whatever Mermaid let through.
The untrusted page’s CSP already admits `data:` images and the application’s own
scripts, and blocks inline script and handlers during the render.

The same CSP admits no `<style>` element, and Mermaid measures its labels inside a
scratch element that holds one, so in an inert render Chrome logs that style as a
blocked inline style, once per diagram, and Mermaid measures in the browser’s default
font. Labels then came out clipped (“truste” for “trusted”). Image mode therefore gives
Mermaid a measuring host whose inline `style` attribute, which the CSP admits for
attributes, sets Mermaid’s own font family and size (`measuringHost` in
`builtin_plugins/markdown/diagrams.js`). The console messages remain and are harmless:
the rule they report is the one meant to hold.

### Division of Work: KPress and Metabrowser

| Concern | Owner | Why |
| --- | --- | --- |
| Recognizing a `mermaid` fence and emitting the figure contract | KPress | It owns Markdown to HTML |
| Leaving a `svg` fence as code under a GitHub-faithful mode | KPress | Same; Metabrowser then selects that mode |
| The figure’s data contract (`data-kpress-diagram`, status, source) | KPress | Shared by every host |
| Vendoring Mermaid and loading it on demand | Metabrowser | Its asset tiers and supply-chain policy |
| Trust: in-document SVG or image | Metabrowser | Only the host knows a view’s trust |
| Reducing an inert render to `<pre lang="mermaid">` | Metabrowser | `inert_html.py` and `inert-html.js` are the allowlist |
| Theme source and live re-render | Metabrowser | It owns `data-theme` |
| Mount, replacement, and disposal per view | Metabrowser | It replaces documents in place |
| Controls: copy, source, expand, zoom, pan | Metabrowser now, KPress later | Published KPress sites want the same parity |
| `.mmd` and `.mermaid` files | Metabrowser | A file kind, not Markdown |

KPress work, filed against KPress rather than here:

1. **`diagrams="mermaid"` draws Mermaid only.** Today every mode but `off` also draws
   `svg` fences. GitHub shows them as code, and Metabrowser’s inert render deletes them.
   Metabrowser passes `diagrams="mermaid"` once a release has it (`mb-1g14`).
2. **A host-configured renderer.** `initKpressDiagrams(root, {mermaid, config})` takes
   the Mermaid API and site configuration (theme, `securityLevel`) from the host rather
   than `globalThis`, merges rather than resets the host’s configuration, and returns a
   binding with `dispose()` and `rerender()`.
3. **Visible errors.** Keep Mermaid’s message on the figure rather than swallowing it.
4. **Controls.** Copy, expand, zoom, and pan, with the behavior below, so a published
   site matches GitHub too.

With 2 through 4 released, Metabrowser’s renderer reduces to a host adapter over
KPress’s behavior, and the controls move upstream.

### Components

**`static/vendor/mermaid/`.** The ESM entry and its chunk directory, without source
maps, from the exact npm pin, listed file by file in `manifest.json`.

**`devtools/vendor_assets.py`.** A directory-shaped entry that copies and hashes a tree.
`TOTAL_CAP_BYTES` rises to cover the measured tree, recorded beside it.
`PER_FILE_CAP_BYTES` stays at 1,700,000, above ELK’s 1,620,399.

**`static/asset-loader.js`.** A bundle entry can be a module: `{"module": url}`.
`ensureModule(name)` imports it once and resolves to its namespace; concurrent callers
share the import.
`server.py` publishes a `mermaid` module bundle at the vendored entry’s
stamped URL, so its relative chunk imports resolve under the same stamp.

**`builtin_plugins/markdown/diagrams.js`.** The renderer, loaded by the plugin on demand
when a view holds a diagram.
`mountDiagrams(root, mb, {mode})` finds KPress figures (trusted) or
`pre[lang="mermaid"]` blocks (inert), loads Mermaid, renders in document order yielding
between diagrams, and returns `{dispose, ready}`. It initializes Mermaid with GitHub’s
observable configuration, except `securityLevel`, which is `strict`: in Mermaid,
`strict` and `antiscript` sanitize labels the same way, and `strict` also disables
`click`, whose navigation GitHub’s CSP blocks anyway.
The theme is `dark` or `default` from the resolved `data-theme`, as on GitHub, and a
diagram’s own `%%{init}%%` or front-matter theme still wins.
A theme change re-renders every drawn diagram.
A failure keeps the source visible with Mermaid’s message above it, including the
`maxTextSize` and `maxEdges` refusals.

**Diagram controls**, in the same module.
A toolbar on hover or focus: copy source, show source or diagram, and expand.
Expand opens a modal dialog filling the window, with zoom in, zoom out, reset, and four
pan buttons, as GitHub has, plus what GitHub lacks: wheel and pinch zoom about the
pointer, drag to pan, and keys (`+`, `-`, `0`, arrows, Escape).
The zoom and pan arithmetic is a pure state machine (`viewTransform`), so a browserless
session drives it.

**`builtin_plugins/markdown/rendered.js` and `transclusion.js`.** After placing a
render, mount diagrams when the root holds one, and dispose them with the view.

**`inert_html.py` and `static/inert-html.js`.** Reduce a KPress Mermaid figure to
`<pre lang="mermaid"><code>…</code></pre>`, GitHub’s own fallback markup, and allow
`lang` on `pre` only with the value `mermaid`.

**`static/plugin-sdk.js`.** `loadKpressAssets` skips KPress’s `js/diagrams.js`: the host
draws diagrams, and loading a module that can only no-op costs a request.

**The `mermaid` kind.** The Markdown plugin claims `.mmd` and `.mermaid` with a default
Diagram view, which mounts the renderer on the file’s text, and a Source view.
The view draws an image when active content is off, like an inert render.

### API Changes

`MetabrowserAssets` and the SDK gain `ensureModule(name)`, and the server publishes the
`mermaid` bundle. The inert allowlist gains one attribute value.
A new kind, `mermaid`, appears in `/api/file`. These are internal contracts that change
together in one commit, and a changelog fragment records what a reader sees.
`PLUGIN_SDK_VERSION` does not move: the change is additive.

## Implementation Plan

One phase: the parts are one feature with one acceptance boundary, a page that renders
on GitHub rendering here.

### Phase 1: Diagrams Wherever GitHub Draws Them

- [x] Vendor Mermaid 12.3.0’s ESM tree through a directory-shaped vendor entry, with the
  pin, `NOTICE.md` entry, license, manifest, and caps recorded beside the measurement
  (`mb-98mi`)
- [x] Add module bundles to the asset loader and publish the `mermaid` bundle
  (`mb-y7zh`)
- [x] Write the renderer: trusted SVG, inert image, theme, error state, disposal
  (`mb-fzm7`)
- [x] Mount it from the rendered view and from transclusions, and stop loading KPress’s
  `diagrams.js` (`mb-fzm7`)
- [x] Drive the theme from `data-theme` and re-render on change (`mb-19sr`)
- [x] Add copy, source toggle, and the expand dialog with zoom and pan (`mb-e9vy`)
- [x] Carry Mermaid through the inert allowlist and render inert diagrams as images
  (`mb-8u9t`)
- [x] Add the `mermaid` kind for `.mmd` and `.mermaid` files (`mb-1vn6`)
- [x] Browserless session, golden, parity rows, Chrome evidence, docs, and changelog
  fragment (`mb-xm9c`)
- [ ] Pass `diagrams="mermaid"` once KPress releases it (`mb-1g14`, blocked on KPress)

## Testing Strategy

**Browserless session** (`tests/dom/markdown-diagrams-session.js`, golden
`cli-ui-markdown-diagrams.tryscript.md`) runs the production renderer against a stub
Mermaid: a diagram-free root never asks for Mermaid; a root with diagrams moves each
figure from `source` through `rendering` to `rendered`; a failure reaches `error` with
the message and source; a theme change re-renders; disposal removes listeners and
dialogs; replacement does not accumulate; inert mode places an image; the toolbar copies
source and toggles it; and the dialog’s zoom and pan transitions are pinned.

**Data parity.** The `mermaid` kind and its views through `/api/file`, and the inert
`<pre lang="mermaid">` through `/api/kpress/render`, each pinned by a golden.

**Real browser** (`tests/dom/markdown-diagrams-chrome.mjs`) is the evidence for the
paint exemption, since Mermaid’s layout measures text: a trusted document renders a
flowchart and a sequence diagram to SVG; an untrusted one renders images that loaded
under the untrusted CSP; a diagram-free document requests no Mermaid file; a malformed
diagram shows its error; the dialog draws the diagram fitted; a `.mmd` file draws; and
no page throws.

**Vendor manifest test.** The existing parity test covers the new tree hash for hash,
with no `node_modules`.

## Rollout Plan

Server, shell, and built-in plugins ship as one artifact, so the phase lands as one pull
request with no flag.
The deliberate cost is the wheel, which grows by the Mermaid tree’s compressed size,
measured and recorded beside `TOTAL_CAP_BYTES`.

## Open Questions

- Should a repository whose documents have diagrams prefetch Mermaid after the first
  one? Measurable now that Mermaid loads through the tier.
- Should the inert image keep selectable text, by rendering it into a sandboxed frame
  instead? The untrusted CSP forbids frames today, and the image is the stricter posture.

## References

- [Mermaid diagram support](../../research/research-2026-08-21-mermaid-diagram-support.md)
  — the August research behind this plan
- [End-to-end load time](plan-2026-08-21-load-time-performance.md) — the loading tier
- [Asset loading tiers](../../architecture/arch-browser-shell.md#asset-loading-tiers)
- [Inert Markdown](../../architecture/arch-server-and-content.md#inert-markdown) — the
  allowlist and the untrusted page’s CSP
- [Mermaid](https://github.com/mermaid-js/mermaid) — upstream project, MIT licensed

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
