# Plan for a PDF Plugin and Opening Files in Their Default App

**Date:** 2026-11-24

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Phase 1 implemented (bead `mb-df0r`, with `mb-ns7s` for the plugin and SDK,
`mb-hwyo` for the app’s bridge, and `mb-klkl` for verification).
[Open Questions](#open-questions) lists the owner’s decisions.

## Overview

A PDF opens in Metabrowser as bytes: no plugin claims `.pdf`, so the file falls through
to the `binary` kind and its Bytes view.
This plan adds a self-contained built-in `pdf` plugin that previews a PDF with the
browser’s own viewer, and a way to open any browsed file in the app the operating system
assigns to its type, which for a PDF on macOS is Preview unless the user chose another.

The two halves meet in one piece of markup.
The plugin draws an Open link to the file’s raw bytes, marked as a download.
A browser downloads it and applies its own rule for that type; the macOS app intercepts
the same link and hands the file to Launch Services.
The page never asks which host it is in.

## Goals

- A `pdf` kind and a Preview view, entirely inside `builtin_plugins/pdf/`, that render a
  PDF with the host’s native viewer and leave `/raw`’s sandbox as it is.
- A PDF never loads inside another view unasked: the file’s own view mounts the viewer
  directly, and any embedded context gets a card with a Show preview button.
- One Open action per PDF that opens it in its default app in the macOS app and follows
  the browser’s download rule in a browser.
- A host bridge in the macOS app that opens a marked link’s file with its default
  handler, for any file type a plugin marks, with a refusal list for types whose default
  handler runs code.
- Parity: the kind, its classification, and the view’s states have goldens; only the
  native viewer’s paint is browser-only, with a named exemption.

## Non-Goals

- **PDF.js or any rendering library.** GitHub renders with PDF.js, which gives
  first-pages previews and thumbnails at the cost of a large on-demand bundle, a
  third-party dependency under the 14-day cool-off, and parsing untrusted PDFs on the
  application’s origin, where PDF.js has had script execution (CVE-2024-4367). The
  native viewer needs none of that.
  Revisit only if a page-bounded preview inside other views is wanted.
- **Page counts and thumbnails.** Both need a PDF parser or a platform tool (`sips`,
  `qlmanage`, `pdftoppm`); the card shows the name and size.
- **A generic action registry.** Per-file actions belong to the action menu of the
  [menu primitives plan](plan-2026-08-06-menu-primitives-and-file-actions.md) (Phase 1,
  `mb-ojvf`), which is not built.
  The plugin draws its own controls inside its view until then.
- **Opening a file from a browser in a native app.** No web API launches a native
  handler; see [Options Considered](#options-considered).
- **Changing `/raw`.** Its sandbox, cache rules, and content types stay as they are.

## Background

### What Happens to a PDF Today

- No `[[kind]]` matches `.pdf`, so classification ends at `binary` and the Bytes view
  shows the file’s first bytes.
- A Markdown embed of a PDF (`![[report.pdf]]` or `<embed src="report.pdf">`) resolves
  with `mediaKind` `resource` and becomes a plain link to `/raw` (`createMediaElement`
  in `builtin_plugins/markdown/wiki-enhancer.js`). Following it replaces the whole page
  with the PDF.
- The file-type registry already gives PDF a label, a color, and an icon
  (`data/file-rollup-format/recommended-file-types.json`).

### What GitHub Does

Observed on 2026-11-24 on `mozilla/pdf.js` `test/pdfs/tracemonkey.pdf`, a 14-page file:

- The file page mounts an iframe on a separate origin,
  `viewscreen.githubusercontent.com/view/pdf`, with
  `sandbox="allow-scripts allow-same-origin allow-top-navigation"`.
- Inside it PDF.js draws pages onto canvases.
  It drew 5 pages and showed a More Pages button for the rest.
- GitHub’s documentation says only that PDFs render and that links within them are
  ignored
  ([Working with non-code files](https://docs.github.com/en/repositories/working-with-files/using-files/working-with-non-code-files)).
  It states no size limit and nothing about PDFs in diffs.

GitHub pays for a second origin and a rendering library to keep a PDF’s parser away from
github.com. Metabrowser gets the same separation from the browser: the native viewer
parses the PDF in its own process and origin.

### Which Embedding Survives the `/raw` Sandbox

Every `/raw` response carries `Content-Security-Policy: sandbox …`
(`_RawTrustHeaderMiddleware` in `server.py`), with `allow-scripts` only under the
trusted profile. A server sending those exact headers served a 20-page, 216 KB PDF, and
each embedding was captured in a `WKWebView` snapshot (the engine of the macOS app) and
in headless Chrome:

| Embedding | WebKit | Chrome |
| --- | --- | --- |
| `<iframe src="/raw…">`, sandboxed response | blank | blank |
| `<embed type="application/pdf" src="/raw…">`, sandboxed response | renders | viewer loads |
| Top-level navigation to `/raw…`, sandboxed response | renders | viewer loads |
| `<iframe>`, response with no sandbox | renders | renders |

A sandboxed document disables the native viewer in a frame, so an iframe is out.
`<embed>` renders under both profiles without weakening the sandbox.
Headless Chrome drew its viewer’s toolbar but not the page content in any case, so the
Chrome column shows that the viewer was allowed, not that it painted.
`tests/test_pdf_preview_chrome.py` repeats it on Metabrowser itself: Chrome runs an
`<embed>`’s viewer as a target of its own, which loads under the trusted profile, and
the top-level `/raw` tab loads it under both profiles.

## Options Considered

How an Open control can reach a native handler, by host:

| Option | Browser | macOS app | Verdict |
| --- | --- | --- | --- |
| New tab on `/raw` | The browser’s own viewer | Hands the URL to the default browser | Viewing, not opening |
| Download (`<a download>`) | The browser’s rule for the type | Intercepted, opened with Launch Services | **Chosen** |
| `file://` link | Blocked from an `http` page | Not needed | Not viable |
| Custom URL scheme handled by the app | Hands off when the app is installed | Not needed | Later, if wanted |
| Server route that runs `open` | Opens on the server’s machine | Not needed | Rejected |

- **Download** is the closest a page can come to the default handler in a browser.
  Safari opens “safe” files, PDFs and images among them, in their default app after
  downloading, and that preference is on by default.
  Chrome lists the download and lets the user open it, or always open that type.
  Firefox has a per-type setting: its own viewer, the system default, or save.
  Each leaves a copy in the Downloads folder.
- **A custom URL scheme** (`metabrowser://open?…`) would reach the app from any browser,
  but any website could fire it, so the app would have to confirm every request, and
  under `metab --remote` the file is on another machine.
- **A server route that runs `open`** acts on the machine the server runs on.
  Under `metab --remote` that is the remote host, and on any machine it lets a page that
  can reach the port launch applications.

## Design

### Approach

Three principles, from what the app already does:

1. **The page asks for a web-standard action; each host carries it out its own way.**
   `PagePrintRequests` replaces `window.print` in the app so the page’s Print button
   prints natively, and `WebViewRequests` intercepts marked GitHub links in an isolated
   content world. The Open link follows them: a download in a browser, Launch Services in
   the app.
2. **No host detection in plugins.** Nothing reads the user agent or asks whether it is
   in the app. If a later feature needs to know what its host can do, the app publishes a
   descriptor of action names, never a host name; see
   [Host Capabilities Later](#host-capabilities-later).
3. **The facts that gate a local action are decided where they are known.** The app
   knows its own session, so it knows whether a path is a file on this disk or bytes of
   a pinned revision or mirror; the server is never asked to launch anything.

### What Decides Which Actions a PDF Gets

Three facts, each read where it is known, decide what the plugin draws:

| Fact | Values | Known by | How the plugin reads it |
| --- | --- | --- | --- |
| Host | the macOS app, or a browser | the page’s host | `mb.host.supports("open-file")` |
| Subject | a folder on disk, or a pinned revision or mirror | the server | `mb.sourceKind()`: `filesystem` or `git_revision` |
| Trust profile | active content on or off | the server | `mb.capabilities().activeContent` |

- **Host** is the one fact the server cannot know: any browser can reach the app’s
  server port, and `--exit-on-eof` marks how the server was started, not who is viewing.
  So the app says it, in the page.
- **Subject** decides what Open opens in the app: the file itself for a folder, a
  read-only copy of the served bytes for a revision or mirror, which has no file on
  disk.
- **Trust profile** decides whether the viewer can be inline.
  The untrusted shell policy has `object-src 'none'` (`untrusted_shell_csp` in
  `capabilities.py`), which blocks `<embed>`. A pinned revision or mirror is always
  served under it, so every GitHub URL, pull request, and `--untrusted` folder gets the
  card instead of the inline viewer.

What the plugin draws from them:

| Host | Trust | Inline viewer | Actions |
| --- | --- | --- | --- |
| App | active | yes | Open, Download |
| App | inert | no, a card | Open, Download |
| Browser | active | yes | Download, Open in new tab |
| Browser | inert | no, a card | Download, Open in new tab |

- **Open** (app only) opens the file in the app macOS assigns to PDF, Preview unless the
  user chose another.
- **Download** saves a copy: the app shows its save panel, as for any download, and a
  browser follows its rule for the type, which in Safari opens the PDF in Preview by
  default.
- **Open in new tab** (browser only) shows the PDF in the browser’s viewer at full size.
  A top-level `/raw` document renders under the sandbox, as measured above.
  The app leaves it out: its Open already shows the PDF at full size, in Preview.

### Components

#### The `pdf` Plugin

Everything PDF-specific lives in `src/metabrowser/builtin_plugins/pdf/`:

- **`manifest.toml`:** two `[[kind]]` rules with `id = "pdf"`, which combine with OR.
  One matches the magic `%PDF-` (hex `255044462d`) at offset 0, for a PDF whose prefix
  sniffs as binary, whatever its name; the other matches `exts = [".pdf"]`, for a PDF
  whose first 8 KiB is plain ASCII and so sniffs as text.
  One `[[view]]`, `preview`, labelled PDF, client-rendered, default, and not printable:
  the browser’s viewer prints the PDF itself, and Command-P on the page prints the
  shell’s line saying the view is not printable.
- **`index.js`:** registers `pdf/preview`. It draws an action bar and, below it, either
  the viewer or the card; it holds no state but its elements, and `dispose` removes
  them. The viewer is `<embed type="application/pdf" src="/raw?path=<identity>">`,
  filling the content area’s height.
- **`styles.css`:** the bar, the card, and the viewer’s height, in design tokens.

The links use `/raw`’s query form with the path’s identity, which every subject answers.
The path form is refused for a pin (`git_revision_raw` answers 409). Download carries
`download="<basename>"`, since the query form’s file would otherwise be named `raw`.

#### SDK Additions

Two read-only accessors on `window.metabrowser`, both additive, so `PLUGIN_SDK_VERSION`
stays `0.8`:

- **`mb.host`:** `supports(action)` and `actions()`, read from a frozen
  `window.metabrowserHost` the host publishes.
  A browser publishes none, so it supports nothing.
  Plugins ask about an action, never about a host name, so another host (an app for
  another platform, an editor’s web view) can offer the same action by name.
- **`mb.capabilities()`:** `{activeContent, mutations}`, from the `CAPABILITIES` block
  the server already writes into `METABROWSER_SETTINGS`, the profile this page was
  served under.

Both are installed on `window.metabrowser` by `static/view-composition.js`, the
compositor every view mounts through, not by the eager `plugin-sdk.js`: they put the
shell 226 bytes over its startup-script budget, and only a view reads them
(`performance-budgets.toml` has the measurement).

#### The App’s Open-File Bridge

In `apps/macos`, beside `PagePrintRequests` and `WebViewRequests`:

- **Host descriptor:** a user script at document start, in the page’s world and its main
  frame, defines a frozen `window.metabrowserHost = {actions: ["open-file"]}`. It skips
  a document with an opaque origin, so a sandboxed `/raw` document gets none.
  It is a hint for drawing; the bridge checks every request itself.
- **Open-file requests:** a capture-phase click listener in an isolated content world,
  as `WebViewRequests` installs, takes a trusted, unmodified primary click on an
  `a[data-metabrowser-open-file]`, prevents the link’s default, and posts the link’s
  `href`, the attribute’s value (`filesystem` or `git_revision`), and its `download`
  name. The listener skips a document with an opaque origin, and the handler accepts a
  request only from the main frame of the server’s origin
  (`NavigationPolicy.isAppDocument`), naming a `/raw` address on that origin.
- **Opening:**
  - For `filesystem` in a folder window, the app resolves the `path` parameter under the
    folder, takes the real path, and requires it to be a regular file inside the
    folder’s real path; then Launch Services opens it.
  - For `git_revision`, or in a repository window, WebKit downloads the `href` into the
    app’s cache folder (`Caches/<bundle>/Opened/<unique>/<name>`). The app marks the
    copy read-only and quarantined (`URLResourceKey.quarantinePropertiesKey`), then
    opens it.
  - A failure shows an alert that names the file and the reason.
- **Which types open:** only a file whose type conforms to `com.adobe.pdf`,
  `public.image`, or `public.audiovisual-content`, and not to `public.svg-image`: an SVG
  runs scripts, and its default handler is often a browser (`OpenFileTypes` in
  `OpenFilePlan.swift`). Any other is refused, and the alert offers Reveal in Finder for
  a file on disk. A copy is checked by its name before it is downloaded and by its
  content type after. The default handler of a script, an application, an installer
  package, a disk image, or an internet location runs or mounts something, and a page’s
  link should never do that.
  The bridge is generic, so a later plugin widens the list in one place.

### What Stays Unchanged

- `/raw`, its sandbox, and the untrusted shell policy.
- Markdown embeds of a PDF, which stay links; see [Open Questions](#open-questions).
- The shell’s file header, which keeps Copy path in its eyebrow and View on GitHub in
  its corner (design system, View Headers).

### Host Capabilities Later

The descriptor is how any later feature asks what its host can do: Reveal in Finder,
Open in an editor, Quick Look.
Each is an action name the app adds to `actions` and a handler it installs; the plugin
asks `mb.host.supports(name)`. A feature that needs the subject or the profile reads
them as above, so no feature needs to know which host it is in.

## Implementation Plan

One phase, as one pull request: the plugin, the SDK accessors, and the app’s bridge land
together, since the app’s contract pins the marker the plugin draws.

### Phase 1: PDF Plugin and the Open-File Bridge

- [x] `pdf` plugin: manifest, view, styles, and the lists of built-ins (the shim’s,
  `test_plugin_requirements.py`, `check_distribution.py`, `cli-plugins` and the plugin
  counts in other goldens)
- [x] SDK: `mb.host` and `mb.capabilities()`, their types in `types.d.ts`, and
  `docs/plugins.md`
- [x] Parity: `kind: pdf` in `cli-show.tryscript.md`, the `pdf.preview` functional row
  with a browserless session and golden, and a paint exemption for the native viewer
- [x] App: host descriptor, open-file requests, the opening and type policy, alerts,
  their tests, `metab-contract.toml` entries, and the app documents
- [x] Map row in `arch-views-models-routes.md`, a `docs/plugins.md` note, and a
  changelog fragment
- [ ] Verification: the inline viewer and each action in Safari, Chrome, and the app, on
  a folder, a pinned revision, and an `--untrusted` folder

## Testing Strategy

- **Classification:** a PDF with a binary prefix, one with an ASCII prefix, a file named
  `.pdf` that is not a PDF (it stays `pdf` by name, and the viewer shows the browser’s
  error), and a PDF with another name.
  Fixtures carry a high byte after the header, as real PDFs do.
- **Browserless session** (`tests/dom/pdf-preview-session.js`, golden
  `cli-ui-pdf-preview.tryscript.md`): the exact production `index.js` mounted for each
  row of the actions table, with the `/raw` URLs a folder path and a pin’s wire produce,
  replacement, and disposal.
- **SDK:** `mb.host` with no descriptor, with one, and with a malformed one;
  `mb.capabilities()` under each profile.
- **Swift, pure:** the request parsing, the path resolution (`..`, a symlink out of the
  folder, a directory, a missing file), and the type policy.
- **Swift, WebKit:** a trusted click reaches the handler and the link does not navigate;
  a scripted click and a click in a sandboxed `/raw` document do not; the page cannot
  post to the isolated handler; the descriptor appears in the page and not in a
  sandboxed document.
- **Manual:** the matrix in the last task of Phase 1, with screenshots in the pull
  request.

## Rollout Plan

The plugin and the SDK accessors ship in the next `metab` release.
The app reads no new server field: it reads the plugin’s marker, which its contract
pins, so `MetabRequirement.minimumRelease` stays where it is.
An older app shows the plugin’s Download and Open in new tab, since it publishes no
descriptor.

## Open Questions

1. **The inline viewer for untrusted subjects.** `object-src` could admit the query form
   of `/raw` alone (`object-src <origin>/raw`; a source path without a trailing slash
   matches that exact path, and the query is not part of the match).
   Every `/raw` answer is sandboxed, so an object there is a PDF in the browser’s
   viewer, an image, or a scriptless opaque document.
   That would give GitHub URLs and pull requests the inline viewer.
   Recommendation: make that change in its own pull request, reviewed as a policy
   change.
2. **Markdown embeds.** `![[report.pdf]]` stays a link to `/raw`, which replaces the
   page. Should it instead link to the file’s view in Metabrowser, or draw the plugin’s
   card? Either is a change to the Markdown plugin.
3. **The viewer’s title.** Chrome’s viewer titles its toolbar with the address’s last
   segment, `raw`, since the plugin uses `/raw`’s query form, the one a pin answers.
   The path form would show the file’s name for a folder.
   Is that worth a second address for folders only?
4. **A size bound.** The viewer runs out of the page’s process and loads the file
   progressively, so the plan sets no bound on the file’s own view.
   The verification task measures a large PDF; a bound comes only from that measurement.

## References

- Bead `mb-df0r`: the survey, measurements, and options
- [Menu primitives and file actions](plan-2026-08-06-menu-primitives-and-file-actions.md)
- [Opening anything from the CLI and the app](plan-2026-11-17-open-anything-from-cli-and-app.md)
- [Rendering large content](../../../large-content-rendering.md)
- [Plugin system](../../architecture/arch-plugin-system.md) and
  [Parity Registry](../../architecture/arch-parity-registry.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
