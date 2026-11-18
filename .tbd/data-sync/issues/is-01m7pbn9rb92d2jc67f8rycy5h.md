---
type: is
id: is-01m7pbn9rb92d2jc67f8rycy5h
title: "KPress: an embeddable, reflow-free print indicator a host turns on (replaces Metabrowser's document print button)"
kind: feature
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-18T03:36:57.866Z
updated_at: 2026-11-18T03:36:57.866Z
---
Follow-up to mb-07a1, which moved Metabrowser's print button from the file header into the upper right corner of a rendered document's card, behind a mount option (`printIndicator: true`, `builtin_plugins/markdown/rendered.js`), drawn by Metabrowser itself (`builtin_plugins/markdown/print-indicator.js`, placement in `markdown.css`). The owner asked that this become part of KPress, as an optional print indicator a host turns on, if that is cleaner. It is: KPress 0.3.8 already ships the nearest thing, the opt-in `doc-actions` widget (`format/static/js/doc-actions.js`, `components.css` "Document actions"), which pins a PDF and an MD badge to the card's corner. It does not fit an embedded document yet. This bead is the KPress change; then Metabrowser replaces its own button with KPress's and removes print-indicator.js and its CSS.

What KPress 0.3.8 does today (read from the installed package):
- `runtime.render_view` takes `widgets` and echoes them, and adds `js/doc-actions.js` to the assets, but the widget's mount is emitted only by the standalone page template (`page.html.jinja`, `_widget_mounts`), so an embedding host builds the mount and calls `mountDocActions(el, config)` itself. doc-actions.js imports `runtime.js`, KPress's page runtime, which Metabrowser does not load.
- An inert render (Metabrowser's untrusted profile: every served mirror and `--untrusted`) runs no KPress script, so a client-rendered widget cannot appear there at all.
- The print control is a "PDF" text badge labelled "Export PDF", with a native `title` tooltip. Metabrowser's control is the printer glyph (the icon the header had), named "Print document", with the app's own tooltip (`data-tip-text`); Metabrowser draws no native `title` tooltips (docs/design-system.md, "One Tooltip, and It Is Ours").
- Placement moves the document: `.kpress-long-text:has(.kpress-doc-actions):not(:has(> h1:first-child)) { padding-block-start: 3rem }` pushes a paragraph-first document 0.5rem down when the widget mounts, and the 28px button at a 1rem inset ends 44px below the card's padding edge, past the card band's 2.5rem (40px) top padding, so a leading heading without its top margin (Metabrowser sets `h1:first-child { margin-block-start: 0 }`) is overlapped by 4px.
- It shows in every band, including below the 48rem container boundary where KPress draws no card and pads the column 1rem and 0.75rem, so there it covers the first line.
- With no card ancestor it falls back to the page's first `.kpress[data-kpress-card="on"]`, which on a page holding several documents (a folder Overview's README, nested transclusions) can be the wrong one.

What KPress needs (proposed API and markup):
1. A render option for embeds, `print_indicator: bool = False` on `KPressRenderRequest` and `RenderOptions` (or `widgets: {"doc-actions": {"print": true, "markdown": false, "print_style": "icon"}}` honoured by `render_view`), that makes the fragment itself carry the control, server-rendered, last inside the card so `h1:first-child` rules still apply:
   <article class="kpress kpress-doc" data-kpress-card="on" data-kpress-print-indicator="on">
     <div class="kpress-doc-layout ...">
       <nav class="kpress-toc">...</nav>
       <div class="kpress-prose kpress-long-text">
         ...document...
         <button type="button" class="kpress-print-indicator kpress-no-print" data-kpress-print aria-label="Print">
           <svg class="kpress-print-indicator-icon" aria-hidden="true"><use href="#kpress-icon-printer"></use></svg>
         </button>
       </div>
     </div>
   </article>
   Static markup works under a host profile that runs no KPress script: the host binds the click itself. No `title` attribute, or an option to leave it out; a host labels it (`data-kpress-print-label` or the host's own attribute).
2. A JS entry for hosts that run KPress, `initKpressPrintIndicator(root, {print?: () => void}) -> dispose`, exported from its own module without importing `runtime.js`, mirroring `initKpressToc(container, config)`: it binds the button in *root*'s own card (never another document's), calls `config.print ?? window.print`, and its disposer removes the listener.
3. Placement that moves nothing: absolute in the card's padding corner, `.kpress-long-text:has(> .kpress-print-indicator) { position: relative }`, centred in a corner square no larger than the card's block-start padding and trailing inset (2.5rem in both card bands), through tokens such as `--kpress-print-indicator-size` (host maps it to its icon-button size) and `--kpress-print-indicator-corner`; and no padding change for any document. Expose the card band's block-start padding as a token (`--kpress-card-padding-block-start`) so the corner is computed, not restated.
4. Shown only where the card is drawn, `@container kpress-doc (min-width: 48rem)`, and hidden in print (`kpress-no-print`).
5. Document the invariant hosts rely on beside the narrow TOC toggle: the indicator stays inside the card, the toggle in the trailing gutter `--kpress-toc-toggle-clearance` reserves (Metabrowser moves the toggle to the trailing side in `markdown.css`), so the two never meet; and in the wide band the rail is outside the card.

Then in Metabrowser: raise the kpress pin and its SUPPLY-CHAIN-SECURITY.md record, map `printIndicator` to the new option in `render_kpress_view` / `fetchKpressRender`, bind the click and the owner mark in the inert path, delete print-indicator.js and its markdown.css block, and keep tests/dom/document-print-chrome.mjs and tests/dom/markdown-print-indicator-session.js passing against KPress's markup.
