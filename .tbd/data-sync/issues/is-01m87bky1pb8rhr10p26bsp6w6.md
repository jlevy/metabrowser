---
type: is
id: is-01m87bky1pb8rhr10p26bsp6w6
title: "A minimal built-in PDF plugin: native viewer, click-to-load in embedded contexts, Open in Preview from the macOS app"
kind: feature
status: in_progress
priority: 2
version: 11
spec_path: docs/project/specs/active/plan-2026-11-24-pdf-plugin-and-open-in-default-app.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
child_order_hints:
  - is-01m87cgjpq8g1efvm52trz39d1
  - is-01m87cgkbmnfjvt895n7jt2spm
  - is-01m87cgkzzsm8zzbr8ygpmrz5p
  - is-01m87kjmmd19jzgaghbq2fht39
  - is-01m87kjy8n12djdas079ccsdt0
  - is-01m87kka20wzxkvr0p651dzn46
hold: null
hold_until: null
created_at: 2026-11-24T18:03:18.453Z
updated_at: 2026-11-24T20:22:46.590Z
started_at: 2026-11-24T18:18:56.884Z
---
Findings (2026-11-24 survey of origin/main d95398297):

Today: no `pdf` kind. A .pdf falls through to `binary` and opens in the Bytes view. A Markdown `![[x.pdf]]` or `<embed src=x.pdf>` resolves to mediaKind "resource" and becomes a plain link to /raw (wiki-enhancer.js createMediaElement). The file-type registry already has pdf's label, color, and icon.

GitHub (observed on mozilla/pdf.js test/pdfs/tracemonkey.pdf): the blob view mounts an iframe on a separate origin, viewscreen.githubusercontent.com/view/pdf, with sandbox="allow-scripts allow-same-origin allow-top-navigation". It renders with PDF.js (pdfjsLib present) onto canvases. It drew 5 of 14 pages and showed a "More Pages" button. GitHub's docs say only that PDFs render and that links within them are ignored. No size limit or diff behavior is documented.

Measured (a stdlib server sending /raw's exact headers, with a 20-page 216 KB PDF; WKWebView snapshot plus headless Chrome 'new'):
- <iframe src=/raw…> with /raw's CSP sandbox (either profile): blank in WebKit and Chrome. The sandbox disables the native viewer in a frame.
- <embed type=application/pdf src=/raw…> with the sandbox: renders in WebKit; Chrome's viewer UI loads.
- Top-level navigation to /raw with the sandbox: renders in WebKit; Chrome's viewer UI loads (allow-scripts profile).
- <iframe> with no CSP: renders in both.
So <embed> works without weakening /raw's sandbox. Per-instance memory and time for large PDFs are NOT measured yet; measure them before setting any bound.

Proposed design:
1. A built-in `pdf` plugin. It adds a [[kind]] matching magic %PDF- (hex 255044462d) plus .pdf, at a priority above binary, and one client view that mounts <embed type="application/pdf" src="/raw?path=…"> with a dispose path. No new dependency.
2. Embedded contexts (Markdown wiki and HTML embeds, the PR Docs tab, anything future) never auto-mount. They show a compact card (icon, name, size, later page count or thumbnail) with Show preview (click to mount the same embed, lazy, disposable), Open, and Open in Preview (app only). The file's own view mounts the viewer directly below a measured size bound, and shows the card above it.
3. macOS: the app has no web-to-native bridge today; it only calls NSWorkspace.open for external URLs. Add a narrow host message, "open this served path locally". The app resolves the path to a file URL under its open folder (containment checked, or the server reports the resolved path) and calls NSWorkspace to open it in the default PDF app (Preview unless the user changed it). Pinned revisions and GitHub mirrors have no working-tree file: write /raw's bytes to an app cache file first. In a plain browser, offer "Open in new tab" (top-level /raw, which works with the sandbox) and Download instead.
4. Alternative, not recommended now: PDF.js, as GitHub does. It gives first-N-pages and thumbnails, but adds roughly 1 MB or more of on-demand assets, a supply-chain dependency, and parsing of untrusted PDFs in our origin (for example CVE-2024-4367).
5. Parity: the kind and its metadata via metab --api with a golden. The native viewer's paint needs a named browser-only exemption. Decide a CLI equivalent for the open-locally action.

## Notes

PR: https://github.com/jlevy/metabrowser/pull/790
