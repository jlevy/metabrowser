# Research: Mermaid Diagram Support

**Date:** 2026-08-21

**Author:** Metabrowser maintainers

**Status:** Complete

## Executive Summary

A `` ```mermaid `` fence renders as a diagram on GitHub and as a code block in
Metabrowser. Closing that gap is smaller than it looks, because most of the pipeline
already exists and is unused.

KPress already treats a Mermaid fence as a diagram rather than as code.
It emits a
`<figure class="kpress-diagram kpress-mermaid" data-kpress-diagram="mermaid" data-kpress-diagram-status="source">`
wrapper around the source, ships a `js/diagrams.js` behavior that replaces that source
with rendered SVG, and adds that module to the asset manifest whenever a document
contains a Mermaid fence.
Metabrowser already serves KPress assets at `/kpress-static/` and already loads every
manifest entry point, so `diagrams.js` is being fetched and executed today.
It returns immediately, because its first line asks the host for `globalThis.mermaid`
and Metabrowser never defines it.

The missing inputs are therefore two: **a vendored Mermaid library that defines
`window.mermaid`, and a per-mount call into KPress’s `initKpressDiagrams`** alongside
the existing `mb.kpressInitToc`. Everything between those two points is written.

The one real cost is the library.
Mermaid 11.17.0 is large, and how it is loaded decides whether that cost lands on every
page or only on documents that contain diagrams.
Measured in Chromium 141 on this machine:

- The single-file UMD bundle is 3,572,296 bytes and costs 449 ms of fetch, parse, and
  evaluate before a page is interactive, paid on every document including every one that
  contains no diagram.
- The ESM build loads a 30,255-byte entry and pulls per-diagram-type chunks on demand.
  A document containing a flowchart transfers 859,233 bytes across 27 files, renders its
  first diagram in 101 ms, and renders each additional flowchart in about 34 ms.

The recommendation is to vendor the ESM build, load it lazily from the Markdown plugin’s
mount path only when the rendered document contains a diagram figure, and keep KPress’s
`securityLevel: "strict"`. That renders in the document itself rather than in a
cross-origin iframe, which is where Metabrowser can be better than GitHub rather than
merely equal to it: the diagram is real DOM in the served page, so it inherits the
theme, prints with the document, and can be selected and copied with the prose around
it.

## Questions Answered

1. What exactly does GitHub support, at what version, and under what configuration?
2. What happens in Metabrowser today when a document contains a Mermaid fence?
3. What is the smallest change that renders those fences?
4. What does the Mermaid library cost, and which loading strategy is defensible?
5. Where should the boundary sit between Metabrowser core, the Markdown plugin, and
   KPress?
6. What is the security posture for running a diagram compiler over untrusted local
   files?
7. Which GitHub behaviors are worth matching, and which are worth improving on?

## Scope

This covers Mermaid in rendered Markdown documents: the fence syntax, the render path,
the library, theming, error states, and bounds.

GitHub’s other diagram fences (`geojson`, `topojson`, `stl`) and its `$...$` math
support are noted for context but are not proposed here.
Diagram authoring, editing, and export are out of scope.
So is a general offline-asset strategy beyond what the existing vendoring policy already
defines.

## Findings

### What GitHub Actually Does

The following comes from GitHub’s own served markup and from the JavaScript bundle its
renderer loads, both fetched on 2026-08-21, rather than from documentation.

GitHub does not render Mermaid on the server.
For each Mermaid fence, the blob page emits three things: a copyable source snippet, a
`<pre lang="mermaid">` fallback inside a `render-plaintext-hidden` wrapper, and an
enrichment section carrying the diagram source in a `data-json` attribute:

```html
<section class="js-render-needs-enrichment render-needs-enrichment"
  data-host="https://viewscreen.githubusercontent.com"
  data-src="https://viewscreen.githubusercontent.com/markdown/mermaid"
  data-type="mermaid" aria-label="mermaid rendered output container">
  <div class="js-render-enrichment-target" data-json="{&quot;data&quot;:&quot;flowchart LR ...&quot;}">
```

The client injects an iframe pointing at `viewscreen.githubusercontent.com` and posts
the source into it. Rendering happens on that separate origin, in a page whose entire
body is a `<div class="mermaid-view">` and whose only script is a 1,702,052-byte bundle.
User content therefore never executes on `github.com`.

That bundle embeds **Mermaid 11.16.1** (npm’s current release is 11.17.0), and
configures it as:

```js
mermaid.initialize({
  startOnLoad: false,
  secure: ["secure", "securityLevel", "startOnLoad", "maxTextSize"],
  securityLevel: "antiscript",
  flowchart: { diagramPadding: 48 },
  gantt: { useWidth: 1200 },
  pie: { useWidth: 1200 },
  sequence: { diagramMarginY: 40 },
  theme: document.querySelector("html")?.getAttribute("data-color-mode") === "dark"
    ? "dark" : "default",
});
```

Four points follow from that configuration.

**Theming is two-valued.** GitHub maps its color mode onto Mermaid’s `dark` and
`default` themes only.
Its dimmed and high-contrast themes get one of the same two diagram palettes.

**Bounds are Mermaid’s defaults, not GitHub’s.** The bundle carries Mermaid’s
`maxTextSize: 5e4` and `maxEdges: 500` unchanged, so a diagram over 50,000 characters or
500 edges fails with Mermaid’s own message.
GitHub adds no limit of its own.

**`securityLevel` is `antiscript`, and the sandbox does the real work.** `antiscript`
permits `click` interactions and strips only script elements; `strict`, Mermaid’s
default, encodes HTML in labels and disables `click` entirely.
GitHub wraps `mermaid.render` in a second DOMPurify pass with an explicit tag allowlist,
and then relies on the iframe’s Content Security Policy.
That layering is why a `click` directive parses but the resulting navigation fails with
“This content is blocked.
Contact the site owner to fix the issue” — a GitHub staff reply attributes it to the
content security policy, and a user console log names the missing `frame-src` directive.

**Cross-origin isolation has costs GitHub absorbs.** Relative links inside a diagram
resolve against `viewscreen.githubusercontent.com/markdown`, not against the repository,
so they do not work.
The rendered SVG is not part of the blob page’s DOM, so it is not covered by that page’s
selection, copy, or print.

GitHub renders Mermaid in Markdown files, issues, pull requests, discussions, wikis, and
gists. `info` on its own line inside a Mermaid fence prints the deployed version.

### What Metabrowser Does Today

Rendering a document with a Mermaid fence through `kpress_adapter.render_kpress_view`
produces this, verified against the pinned `kpress==0.3.3`:

```html
<figure class="kpress-diagram kpress-mermaid kpress-figure"
  data-kpress-diagram="mermaid" data-kpress-diagram-provider="mermaid"
  data-kpress-diagram-status="source">
  <pre class="kpress-diagram-source"><code class="language-mermaid">graph TD;
 A--&gt;B;
</code></pre></figure>
```

The same render call returns an asset manifest whose entry points include
`js/diagrams.js` at `/kpress-static/v0.3.3/js/diagrams.js`, with an empty import map.
`plugin_sdk.js` validates that manifest and loads every module entry point, so the
module is already fetched and evaluated on any document containing a diagram.

`diagrams.js` then does nothing:

```js
export async function initKpressDiagrams(root = document) {
  const mermaid = hostMermaid();
  if (!mermaid) {
    return;
  }
  mermaid.initialize?.({ startOnLoad: false, securityLevel: "strict" });
  ...
}
```

`hostMermaid()` reads `globalThis.mermaid`, which Metabrowser never sets.
The figure stays at `data-kpress-diagram-status="source"` and the reader sees the
Mermaid source.

Two consequences are worth naming, because they shape the work.
The figure carries `kpress-diagram-source`, not `kpress-code`, so KPress does not add
`js/code-copy.js` for it and the source has no copy button — GitHub gives one.
And `mountRenderedMarkdown` calls `mb.kpressInitToc(container)` per mount but has no
equivalent for diagrams, which matters because Metabrowser replaces
`container.innerHTML` on every navigation while KPress’s own behavior registry binds
against the document once.

### The Shape of the Change

Three edits, in the layers that already own these concerns.

**A vendored library.** `static/vendor/` holds every third-party browser file, copied
from `node_modules` under the exact-pin and `ignore-scripts` policy and recorded in
`manifest.json` with SHA-256 digests.
Mermaid is MIT-licensed and fits that policy, with one structural difference: existing
entries are single flat files, and the Mermaid ESM build is an entry plus a directory of
103 chunks. `devtools/vendor_assets.py` needs a directory-shaped entry, and `NOTICE.md`
needs the usual attribution line.

**A lazy loader and one SDK primitive.** `plugin_sdk.js` already has the pattern, in
`_loadKpressTocModule`: dynamically import a KPress module, capture its named export,
and expose a per-mount wrapper.
Diagrams want the same shape — capture `initKpressDiagrams`, expose
`mb.kpressInitDiagrams(container)` — plus one extra step before it, importing the
vendored Mermaid entry and assigning `window.mermaid` so `hostMermaid()` succeeds.
The import must be triggered by the presence of `[data-kpress-diagram="mermaid"]` in the
mounted container, not at page load.

**A call from the Markdown plugin.** `rendered.js` gains a
`mb.kpressInitDiagrams(container)` call next to its existing `kpressInitToc`, with a
disposer stored alongside `disposeToc`.

Adding a method to the SDK is additive.
`sdk_version` is an exact-match gate that fails a plugin declaring anything other than
the host’s `PLUGIN_SDK_VERSION`, so bumping it would force an edit to every built-in
manifest to buy nothing; per the repository’s rule, the bump belongs to a break, and
this is not one.

Mermaid must not join `optional_script_assets` in `server.py`. That chain loads eagerly
on every page, which is the one loading decision the measurements below rule out.

### What the Library Costs

Measured against Mermaid 11.17.0 in Chromium 141 (Playwright build 1194) on this
machine, serving the unmodified `dist` over loopback with no compression.
Absolute times are pessimistic on faster hardware; the shape is what transfers.

Bundle sizes on disk, source maps excluded:

| Artifact | Files | Bytes | Note |
| --- | --- | --- | --- |
| `mermaid.min.js` (UMD) | 1 | 3,572,296 | Self-contained; defines `window.mermaid` |
| `mermaid.esm.min.mjs` (entry) | 1 | 30,255 | Loads chunks on demand |
| `chunks/mermaid.esm.min/*.mjs` | 103 | 3,491,470 | Full set; only some load per document |

Every import and dynamic import in the ESM build is relative, so the vendored tree needs
no import map.

What a document actually transfers and how long it takes to draw, one diagram per fresh
browser context:

| Diagram | Files | Bytes | Render (ms) | SVG bytes | SVG nodes |
| --- | --- | --- | --- | --- | --- |
| Module load, before any render | 19 | 753,765 | — | — | — |
| Flowchart, 6 nodes | 27 | 859,233 | 101 | 17,195 | 122 |
| Sequence, 4 actors | 22 | 872,890 | 62 | 25,240 | 86 |
| Class diagram | 27 | 846,566 | 116 | 20,662 | 151 |
| State diagram | 26 | 835,292 | 107 | 28,186 | 74 |
| ER diagram | 24 | 825,281 | 88 | 9,258 | 80 |
| Gantt | 20 | 804,262 | 37 | 8,144 | 40 |
| Pie | 39 | 1,482,813 | 142 | 3,651 | 17 |
| Git graph | 40 | 1,507,118 | 162 | 8,721 | 34 |

Two readings matter.
The floor is about 754 KB, paid once per document that has any diagram at all.
Above that floor the marginal cost is per diagram *type*, not per diagram: pie and git
graph each pull roughly 650 KB more than a flowchart does, and every flowchart in a
document after the first pulls nothing.

Cost against diagram size, same flowchart shape scaled up:

| Flowchart nodes | Render (ms) | SVG bytes | SVG nodes |
| --- | --- | --- | --- |
| 6 | 101 | 17,195 | 122 |
| 25 | 193 | 45,931 | 388 |
| 100 | 547 | 158,895 | 1,438 |
| 250 | 1,575 | 388,595 | 3,538 |
| 500 | 2,778 | 771,427 | 7,038 |

Doubling node count roughly doubles render time from 100 nodes upward.
That is close to linear, unlike the quadratic CSS-wrapping path documented in
[rendering large content](../../large-content-rendering.md), so this is a cost that can
be bounded by a number rather than one that has to be fixed by changing the mechanism.
The synthetic flowchart carries one edge per node, so Mermaid’s own `maxEdges: 500`
default lands near where the measured cost becomes noticeable, which is a reason to keep
it rather than raise it.

Repeated diagrams of one type on a single page, 20 flowcharts:

| Measure | Value |
| --- | --- |
| Bytes transferred, whole page | 859,233 across 27 files |
| First diagram | 101 ms |
| Each subsequent diagram | 32–39 ms |
| All 20 diagrams | 750 ms, 2,180 DOM nodes |

Against that, eager UMD loading measured 3,572,296 bytes and 449 ms of fetch, parse, and
evaluate before the page was ready, on every document whether or not it has a diagram.

Packaging cost: `src/metabrowser` is currently 3,080,267 bytes uncompressed and 948,476
bytes zipped. The vendored Mermaid ESM tree adds 3,521,725 bytes uncompressed and
1,018,858 bytes zipped, so the wheel payload roughly doubles.
That exceeds `TOTAL_CAP_BYTES = 3_000_000` in `devtools/vendor_assets.py`, which today
holds a vendored total of 432,092 bytes.
`PER_FILE_CAP_BYTES = 1_700_000` is not exceeded: the largest single Mermaid chunk is
705,086 bytes. Raising the total cap is a deliberate decision that should be made with
these numbers recorded beside the constant, not a number nudged until the check passes.

### Security

Mermaid compiles untrusted text into SVG and inserts it into the page, which is a real
attack surface rather than a theoretical one.
Snyk Labs’ survey of diagram renderers documents the concrete classes:
`click ... call href "javascript:alert(...)"` under `securityLevel: "loose"`, sanitizers
that cover flowcharts and miss other interactive diagram types, and entity-encoded
protocol bypasses.
Their recommendations are `strict` or `sandbox`, sanitizing across all
diagram types rather than selectively, and a Content Security Policy that blocks
`javascript:` URLs as defense in depth.

Three facts about Metabrowser’s position:

- KPress already initializes with `securityLevel: "strict"`, which encodes HTML in
  labels and disables `click`. That is stricter than GitHub’s `antiscript`, and it is
  the correct default for a tool pointed at arbitrary local directories.
- Metabrowser serves no Content Security Policy today, and the strict application-shell
  policy is explicitly deferred in
  [the HTML trust model plan](../specs/active/plan-2026-08-06-html-rendering-and-trust-model.md)
  pending removal of inline handlers.
  Mermaid rendering therefore has one fewer layer than GitHub’s arrangement, which makes
  keeping `strict` more important, not less.
- The governing invariant in that plan is that browsed content gets exactly the
  privilege a browser would give the same file opened directly.
  Rendering a diagram under `strict` grants no script execution and no navigation, so it
  sits inside that invariant.

Mermaid’s `securityLevel: "sandbox"` renders into a sandboxed iframe and is the closest
in-library analogue to GitHub’s architecture.
It is the right escape hatch if the conservative trust profile from that plan ever needs
one, and the wrong default, because it gives up exactly the in-document behavior that
makes local rendering better than GitHub’s.

## Key Insights

**The work is smaller than the feature sounds, and the cost is concentrated in one
decision.** The render path, the markup contract, the error states, the asset manifest,
and the module loader all exist.
What is missing is a global and a function call.
Nearly all of the engineering judgment in this feature is about how to load a 3.5 MB
library without making every non-diagram document pay for it.

**Rendering in-document is a genuine advantage, not a shortcut.** GitHub’s cross-origin
iframe is the right answer for a service rendering strangers’ content to millions of
readers, and it costs GitHub working relative links, in-document selection and copy, and
printing with the surrounding page.
Metabrowser serves one user their own files on loopback.
Rendering in the page yields a diagram that inherits the design tokens, prints with the
document, and behaves like the rest of the prose — which is what
“[prefer native behavior](../../large-content-rendering.md)” already asks for elsewhere
in this codebase.

**The marginal cost is per diagram type, which changes what to bound.** A document with
20 flowcharts costs no more to load than one with a single flowchart, and 750 ms to
draw.
A document with one of each of eight diagram types pays the chunk cost eight times.
A bound on “diagrams per document” would be measuring the wrong thing.

**Matching GitHub is mostly about the states around the diagram.** Rendering the happy
path is one function call.
The remaining differences are a copy button, a legible parse error, and a theme that
follows the app rather than being fixed at load — the same details that separate the
current source view from a finished one.

## Comparison Matrix

| Criterion | GitHub | Metabrowser today | Recommended |
| --- | --- | --- | --- |
| Mermaid version | 11.16.1, deployed by GitHub | none | 11.17.0, pinned in `package.json` |
| Render location | Cross-origin iframe | not rendered | In-document SVG, same origin |
| `securityLevel` | `antiscript` plus DOMPurify plus CSP | `strict`, unreachable | `strict` |
| `click` and links | Parsed, blocked by CSP | n/a | Disabled by `strict` |
| Theme | `dark` or `default` by color mode | n/a | Follows `data-theme`, re-renders on change |
| Fallback without JS | Source `<pre>` | Source `<pre>` | Source `<pre>` |
| Copy source | Yes | No | Yes |
| Parse errors | Mermaid’s own message | n/a | Visible message, source restored |
| Bounds | `maxTextSize` 50,000, `maxEdges` 500 | n/a | Same, surfaced visibly |
| Selection, copy, print with prose | No | n/a | Yes |
| Cost on diagram-free documents | Zero | Zero | Zero |
| Offline | n/a | n/a | Yes, fully vendored |

## Options Considered

### Option A: Vendored ESM, Lazily Loaded (Recommended)

**Description:** Vendor `mermaid.esm.min.mjs` and its chunk directory.
On mount, if the rendered container holds a `[data-kpress-diagram="mermaid"]` figure,
dynamically import the entry, assign `window.mermaid`, then call KPress’s
`initKpressDiagrams` through a new `mb.kpressInitDiagrams(container)`.

**Pros:**
- Documents without diagrams pay nothing; documents with them pay 754 KB and 101 ms for
  the first, about 34 ms for each additional diagram of the same type.
- No import map: every specifier in the build is relative.
- Reuses the existing `_loadKpressTocModule` pattern and the existing vendoring policy.
- Keeps the library offline and same-origin, matching the wheel’s no-external-origins
  property.

**Cons:**
- Roughly doubles the compressed wheel payload and requires raising `TOTAL_CAP_BYTES`.
- `devtools/vendor_assets.py` must learn directory entries, since the tree is 104 files
  rather than one.
- 103 chunk filenames carry content hashes, so a version bump rewrites the manifest
  wholesale and its diff is not reviewable file by file.

### Option B: Vendored UMD, Loaded Eagerly

**Description:** Add `mermaid.min.js` to `optional_script_assets` alongside Chart.js and
highlight.js, defining `window.mermaid` at page load.

**Pros:**
- One file, one manifest entry, no change to `vendor_assets.py`.
- Matches how every other vendored library is loaded today.

**Cons:**
- 3,572,296 bytes and 449 ms of fetch, parse, and evaluate on every document, including
  every one with no diagram.
- Exceeds `PER_FILE_CAP_BYTES` as well as the total cap.
- Spends the largest asset in the wheel on a feature most documents do not use.

### Option C: Server-Side Prerendering

**Description:** Render Mermaid to SVG in the server and return it in the KPress HTML.

**Pros:**
- No browser library and no client cost.
- Diagram SVG would be cacheable alongside the rendered document.

**Cons:**
- Mermaid is a browser library.
  Prerendering it means `mermaid-cli` and a headless Chromium, which is a Node and
  browser dependency inside a Python wheel that installs with `uv`.
- Contradicts the offline, single-artifact packaging the repository already maintains.
- Would have to reimplement KPress’s diagram contract rather than use it.

### Option D: Sandboxed Iframe, GitHub’s Architecture

**Description:** Render each diagram inside a sandboxed iframe, either through Mermaid’s
`securityLevel: "sandbox"` or a `srcdoc` iframe of Metabrowser’s own.

**Pros:**
- Strongest isolation, and the closest match to GitHub’s posture.
- A natural fit for the conservative trust profile in the HTML trust model plan.

**Cons:**
- Gives up in-document selection, copy, and printing — the specific advantages
  Metabrowser has over GitHub here.
- Requires height messaging per diagram and per resize.
- Under `securityLevel: "strict"` the content has no script and no navigation already,
  so the isolation buys little at the default trust level.

Worth keeping as an opt-in under the conservative profile, not as the default.

### Eliminated Options

- **Remote CDN or `mermaid.ink`:** every third-party browser file is vendored so the
  page has no external origins and works offline.
  A remote diagram service would also send the contents of local files to a third party.
- **A subset of chunks:** vendoring only common diagram types would shrink the tree, but
  an unsupported type would fail on a missing chunk rather than degrade, which is
  exactly the “just works” property this is meant to deliver.
- **An optional install extra:** a `metabrowser[diagrams]` extra keeps the base wheel
  small, at the price of making the feature absent by default in a tool whose Markdown
  rendering is a headline capability.

## Recommendations

1. Take Option A. Vendor the Mermaid ESM build, load it lazily from the Markdown
   plugin’s mount path, and keep `securityLevel: "strict"`.
2. Raise `TOTAL_CAP_BYTES` in `devtools/vendor_assets.py` to accommodate a measured
   3,521,725-byte tree, and record the measurement beside the constant.
   Leave `PER_FILE_CAP_BYTES` alone; the largest chunk is 705,086 bytes.
3. Expose exactly one new SDK method, `kpressInitDiagrams(container)`, mirroring
   `kpressInitToc`, and give it a disposer.
   Do not bump `PLUGIN_SDK_VERSION`; the change is additive and the gate is exact-match.
4. Drive the Mermaid theme from `data-theme` and re-render on theme change, rather than
   fixing it at initialization as GitHub does.
5. Give the figure a copy button and a visible parse-error state.
   KPress already sets `data-kpress-diagram-status="error"` and restores the source; the
   host supplies the message.
6. Keep Mermaid’s `maxTextSize` and `maxEdges` defaults and surface the failure visibly
   rather than silently, per “degrade visibly” in
   [rendering large content](../../large-content-rendering.md).
7. Treat Option D as the conservative-profile behavior when the HTML trust model lands,
   not as a second default to maintain now.

## Next Steps

Carried into
[Mermaid diagram rendering](../specs/active/plan-2026-08-21-mermaid-diagram-rendering.md),
which owns the implementation.
The loading decision below is generalized in
[end-to-end load time](../specs/active/plan-2026-08-21-load-time-performance.md).

- [ ] Extend `devtools/vendor_assets.py` with a directory-shaped vendor entry and raise
  the total cap with the measurement recorded.
- [ ] Vendor Mermaid 11.17.0, pin it in `package.json`, and add the `NOTICE.md` entry.
- [ ] Add lazy Mermaid loading and `kpressInitDiagrams` to `plugin_sdk.js` and
  `types.d.ts`, and call it from `rendered.js` with disposal.
- [ ] Wire diagram theme to `data-theme`, including re-render on change.
- [ ] Add the copy button and the visible parse-error state.
- [ ] Cover lazy mount, replacement, disposal, and theme change in `tests/dom`, and
  cover the vendored manifest in the existing vendoring test.
- [ ] Note the user-visible change in `CHANGELOG.md`.

## Methodology

GitHub’s behavior was read from primary artifacts rather than documentation: the served
HTML of a blob page containing Mermaid fences, the `viewscreen.githubusercontent.com`
renderer page, and its 1,702,052-byte JavaScript bundle, all fetched on 2026-08-21. The
version string, the `initialize` call, the `maxTextSize` and `maxEdges` defaults, and
the DOMPurify allowlist are quoted from that bundle.
GitHub’s rationale for blocking `click` navigation is community discussion plus one
staff reply, not documentation, and is reported as such.

Metabrowser’s current behavior was verified by rendering Mermaid fences through
`kpress_adapter.render_kpress_view` against the pinned `kpress==0.3.3` and reading the
returned HTML and asset manifest, and by reading `diagrams.js` from the installed
package.

Library measurements were taken in Chromium 141 (Playwright build 1194) driving the
unmodified Mermaid 11.17.0 `dist` over a loopback HTTP server with no compression, one
fresh browser context per diagram so no module cache carried over.
Transfer figures count deduplicated response bodies; render time is `performance.now()`
around `mermaid.render`. Packaging figures are `zip -9` of the respective trees.

Not established: whether browser find-in-page reaches text inside GitHub’s cross-origin
iframe, and how these render times scale on lower-powered hardware.
Neither changes the recommendation.

## References

- [Creating diagrams](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams)
  — GitHub documentation
- [Include diagrams in your Markdown files with Mermaid](https://github.blog/developer-skills/github/include-diagrams-markdown-files-mermaid/)
  — GitHub blog
- [Mermaid](https://github.com/mermaid-js/mermaid) — upstream project, MIT licensed
- [Mermaid usage and `securityLevel`](https://mermaid.js.org/config/usage.html) —
  upstream documentation
- [More than flowcharts: exploiting diagram renderers](https://labs.snyk.io/resources/exploiting-diagram-renderers/)
  — Snyk Labs, independent security research
- [Using `click` with MermaidJS causes “This content is blocked”](https://github.com/orgs/community/discussions/46096)
  — GitHub community discussion, includes a staff reply
- [What is the version of Mermaid used in GitHub Markdown?](https://github.com/orgs/community/discussions/37498)
  — GitHub community discussion
- [Rendering large content](../../large-content-rendering.md) — this repository’s cost
  model
- [Full-page HTML rendering and an explicit trust model](../specs/active/plan-2026-08-06-html-rendering-and-trust-model.md)
  — this repository’s trust posture

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
