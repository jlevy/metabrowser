# Architecture: Server and Content

**Status:** Built, in `server.py`, `paths_safe.py`, `http_caching.py`,
`capabilities.py`, and `inert_html.py`. Planned: write routes; `--allow-edits` publishes
the `mutations` capability, and no route consumes it yet
([trusted-local editing plan](../specs/active/plan-2026-07-16-trusted-local-file-editing.md)).

The server is a Starlette application that serves one subject, a folder or a pinned Git
revision, to a browser on the same machine.
It owns the request path from the socket to a route, the boundary that keeps every read
inside the served root, the validators that make caching safe, and the trust model that
decides what a browsed file may do in the page.
How the CLI starts it is in [Command Line](arch-cli.md); how inventory changes reach the
browser is in [Live Delivery](arch-live-delivery.md).

## The Deployable Unit

The server, the browser shell, and the built-in plugins ship as one artifact.
The shell page carries no validator, so every load fetches it from the running build,
with that build’s configuration inlined by `client_settings_dict` (`settings.py`).
`_static_asset_url` stamps each local asset address with a digest of its bytes
(`asset_stamps.py`), and only a request with the current stamp is answered immutable, so
a browser keeps an asset only at an address that names its bytes.
`encoded_assets.py` holds an asset answered at its current stamp in memory, read and
compressed once, within `MAX_ENCODED_ASSET_BYTES`. An already-open tab keeps the
JavaScript it loaded until it reloads.

`/api/*`, `window.metabrowser`, `METABROWSER_SETTINGS`, and the plugin manifest are
therefore internal contracts, changed everywhere in one commit; see
[AGENTS.md](../../../AGENTS.md) and
[Compatibility and Legacy Code](../../development.md#compatibility-and-legacy-code).

## Request Flow

Middleware runs outermost first, as `middleware` in `server.py` lists it:

1. `_RawTrustHeaderMiddleware` sandboxes every `/raw` response, including errors written
   by layers inside it.
2. `_HostValidationMiddleware` checks the `Host` header and the same-origin proof for
   `/api` (see [API Origin Proof](#api-origin-proof)).
3. `SourcePinGuard` (`source_routes.py`) refuses, as `409 pin_changed`, an `/api`
   request made for a commit the server no longer serves.
4. `_SlowRequestLogMiddleware` adds `Server-Timing` and logs slow requests; see
   [Real-Time Debugging](../../realtime-debugging.md).
5. `TimedGZipMiddleware` (`server_timing.py`) compresses responses and times the
   encoding. Event streams are never compressed, and `delivery.py` decides, for this
   layer and for stamped assets alike, which clients are sent gzip: every one that
   accepts it, except a loopback client without proxy headers of a server started for
   local use, as the macOS app starts it
   ([Compression](../../command-line.md#compression)).

Routes come from `routes` in `server.py`, `add_inventory_routes` in `events_route.py`,
the Git, cache, source, and identity route tables, and each plugin’s routes.
`GET /api/routes` lists what this build serves, and
[Views, Models, and Routes](arch-views-models-routes.md) indexes them.
Two typed failures have application-wide handlers: an exhausted provider work bound is
`503 inventory_query_limit`, and a capability the active subject lacks is
`409 unsupported_for_subject`.

Every route reads the active subject from the source session (`get_source_session()`). A
route that needs a folder calls `require_filesystem_hooks` or
`require_source_capability`; a route that serves a Git pin branches to
`git/content_routes.py`. Subjects and their capabilities are described in
[Source Sessions and Pins](arch-source-sessions-and-pins.md).

Opening a file follows this sequence:

1. The canonical `/view/<path>` URL or a tree selection supplies a served-root-relative
   path. A fragment names a location inside the document, never a file.
2. `/api/file` resolves the path safely, derives its logical extension, and runs plugin
   classifiers before the built-in fallbacks (`_classify_with_plugins`).
3. The envelope carries the chosen kind and the ordered view descriptors that manifests
   contribute.
4. The shell resolves each `(kind, view)` pair in its registry, mounts the default view
   at once, and mounts the others the first time their tab is selected; see
   [Plugin System](arch-plugin-system.md) and [Browser Shell](arch-browser-shell.md).

The bare origin redirects to `/view/` with a temporary `307`, so the served root has one
URL. Inventory routes answer from the current partial index with progress metadata
rather than waiting for a complete walk.

## Safe Paths

`paths_safe._safe_path` is the filesystem address of every read.
It resolves `ROOT_DIR / requested`, following symbolic links, and returns nothing unless
the result is inside the resolved root by path components (`Path.relative_to`), never by
string prefix. A name the platform cannot express, such as one with an embedded NUL, is
refused rather than raised.

Two spellings of a path reach the server, and each has one entry point:

- **Platform names:** `/view/<path>` and `/raw/<path>` are human-facing URLs and name
  the file as a person would write it; they go straight to `_safe_path`.
- **Inventory identities:** `/api/*` and `/raw?path=` speak the canonical identities the
  inventory publishes, which escape `%` and undecodable bytes.
  They resolve through `resolve_session_identity` (`source.py`), which decodes the
  identity with `native_inventory_path` before the same containment check.

Changing the root fires every `register_root_callback`, which clears root-scoped caches.
Gzip and zlib files keep their logical extension and are read transparently through
`gz_io.ArtifactPath`, within the decompression bounds that module defines.
Request bodies are bounded by `MAX_REQUEST_BODY_BYTES`, and preview reads by the
constants in `settings.py`; see
[Rendering Large Content](../../large-content-rendering.md).

## Validators and Caching

`http_caching.build_scoped_etag` is the only producer of a validator, and
`tests/test_http_caching.py::test_no_module_builds_its_own_validator` fails the build if
one is built anywhere else.
The tag folds in `BUILD_TAG`, the build’s identity, because a response is a rendering of
a file: a tag derived from the file alone would hand back a stale rendering after an
upgrade changed how the file renders.
`etag_headers` sends `Cache-Control: no-cache`, which requires revalidation and so makes
the validator authoritative rather than advisory.
`immutable_headers` is for a body that cannot change at its address, and
`stamped_asset_cache_control` for the application’s own stamped assets.

- **Files** validate on the file’s identity: its `mtime_hash` plus whatever the
  representation depends on.
- **Per-file projections**, such as JSONL views and charts, are memoized in `MtimeCache`
  instances (`projections.py`) keyed by path and checked against the file’s modification
  fingerprint on every read.
- **Inventory-derived responses** validate on the provider’s engine version, because
  their bodies summarize many files.

`/api/rollup` tags its body with the served root, the engine version (session, sequence,
scope fingerprint, semantic fingerprint), and the request’s shape: path, depth, and
every ranking bound, so two clients asking for different shapes at one version never
share a body. Three layers sit behind the tag:

1. **`304`:** a client that already holds the answer gets `304 Not Modified`.
2. **Retained body:** `_ROLLUP_BODY_CACHE`, bounded by `ROLLUP_BODY_CACHE_ENTRIES`,
   serves a client that arrives without the tag, such as a second tab.
3. **Single flight:** clients that arrive together await one build in
   `_ROLLUP_IN_FLIGHT`. The build is its own task, awaited through `asyncio.shield`, so
   a client that disconnects cancels only its own wait; the build finishes for everyone
   still waiting and is retained for the next request
   (`tests/test_rollup_route.py::test_disconnecting_client_does_not_cancel_shared_build`).
   A build whose pinned version moved falls back to one unpinned coherent read.

`/api/catalog` first makes a constant-work checkpoint read; a checkpoint it has seen
maps to a known tag, so an unchanged catalog is a `304` or a retained body without
reading a record. On a change it hashes exactly what the envelope carries, paths and
logical extensions, so a size or time change alone does not invalidate it.

**What a `304` promises.** The tag names the served root, so one root’s body never
answers for another.
It covers the whole body, because every field is a function of the index at that
version, the request’s bounds, or a constant.
And the version only moves forward within a provider session, so a tag is never reused
for different content.
A `304` therefore means the index has not changed; what that says about the filesystem
is [Freshness](arch-live-delivery.md#freshness) in Live Delivery.
During a scan the version moves on every write, so nothing is reused, which is correct:
the answer is changing.

## Content Trust Model

Metabrowser serves two classes of response with different privilege.
**Application surfaces** (the shell, static assets, every `/api` route, and plugin
assets under `/plugin-static`) are first-party code from the installed wheel and
operator-installed plugins, and use the full server API. **Content surfaces** serve the
browsed files themselves: previews through `/api/file` and bytes through `/raw`. A
browsed file gets the privilege a browser would give the same file opened directly, and
never Metabrowser’s server-side API.

### Rendering Browsed Content

Browsed content never executes in the application page.
Source views are entity-escaped before insertion, and Markdown renders through KPress in
its sanitized mode, which strips scripts, event-handler attributes, and `javascript:`
URLs. Plugin discovery never treats the served root as a plugin source; see
[Plugins](../../plugins.md).
A render’s `diagnostics` are what the reader’s Diagnostics disclosure shows, faults the
author can fix, such as a broken anchor; what the sanitizer removed (`html_sanitized*`)
is answered apart, in `sanitizer_diagnostics`, for `--api` and debugging
(`kpress_adapter.is_sanitizer_diagnostic`).

KPress’s sanitized mode is a document renderer’s policy: it keeps stylesheets, images,
SVG and its `url()` paint servers, classes, `data-*` attributes its own scripts act on,
and `id` and `name`. In the application page each of those is a tool for a document the
reader did not write.
A trusted folder keeps them, so the application’s document-wide handlers (copy, Load
more, address crumbs, and print) act only on an element carrying `data-mb-owner` with a
value drawn when the page loads, which a document written earlier cannot spell, and the
tooltip ignores a rendered document’s markup.
Two limits remain:

- The tooltip exclusion covers only a rendered Markdown document
  (`.metabrowser-kpress-host`). Another view that inserts a document’s own markup into
  the page would need the same exclusion.
- A trusted document keeps its stylesheets, whose attribute selectors can match the
  page’s `data-mb-owner` value character by character and report it through `url()`
  loads; a document fetched after that, such as a later edit to a watched file, could
  then carry the value.

### Inert Markdown

With active content off, Markdown reaches the page only as an allowlist of plain markup,
applied twice: on the server by `inert_html.py`, and in the page by
`static/inert-html.js`, which parses the HTML into an inert `<template>` and inserts
only nodes rebuilt from the allowlist.
Active content is off for every served mirror, where a fork’s author controls the head’s
Markdown, for a folder served untrusted, and for every pull-request comment.
Such a document keeps no stylesheet, class, or `data-*`, which removes both limits
above.

Such a document is also rendered off the server’s interpreter: `/api/kpress/render`, on
a folder and a pin alike, renders it in the server’s Markdown child
(`diff/markdown_projection_worker.py`) under `INERT_RENDER_DEADLINE_MS`, never on a
server thread, and reduces it to the allowlist there.
A render the child does not finish is answered `"type": "kpress_render_refused"` with a
`code`: `render_deadline` and `renderer_exited` (`422`, kept by the document for a
while, with `remembered` true on an answer from the kept refusal), and
`renderer_unavailable` and `renderer_busy` (`503`, not kept).
The Markdown view then shows the document’s source under one line saying why
(`builtin_plugins/markdown/render-refusal.js`).

The allowlist keeps paragraphs, headings, emphasis, code, quotes, lists, tables,
details, and links and images inside the served tree.
It drops every class, `id`, `name`, `data-*`, style, and event attribute, and all SVG,
MathML, media, stylesheets, frames, forms, and scripts.
An outside image becomes a link to it.
A link keeps only an `http`, `https`, or in-document address and opens outside the page
with no opener or referrer.
No KPress script loads for such a document.

In an inert render, an address that points at the application rather than the tree, a
query alone or a root-relative `/api`, `/_debug`, or `/raw` address however spelled,
loses its address, as does any link or image past the link enhancer’s limit.
The enhancer resolves the rest in a detached document before the page adopts it, so an
image loads only the address it gave.
Wiki links and embeds, which travel as `data-*` attributes, become plain text.

### The Untrusted Page Policy

With active content off, the shell also carries a Content-Security-Policy and
`X-Frame-Options: DENY`, a second line behind the allowlist.
`capabilities.untrusted_shell_csp` is the policy: scripts run only from the
application’s own static paths and, for the shell’s inline scripts, by a nonce fresh on
every response; no inline event handler runs, and the application writes none.
The browsed tree’s files under `/raw` are never script sources.
Images admit this origin, `data:` images the stylesheet draws, and the exact avatar host
for application-owned author portraits, whose URLs provider and browser code validate.
The page frames nothing, since the untrusted profile removes the HTML preview, its only
frame; nothing may frame it; and plugins, `<base>`, and form submission are off.
Inline `style` attributes stay allowed because the application writes them for layout;
untrusted Markdown carries none.
`tests/test_untrusted_markdown.py` pins the policy and fails when the application writes
an inline handler.

### Raw Responses

Every `/raw` and `/raw/{path}` response, including gzip passthrough, SVG, HTML, and
error bodies, carries the sandbox `raw_sandbox_csp` builds from `_RAW_SANDBOX_TOKENS`
(`capabilities.py`) and `X-Content-Type-Options: nosniff`. The sandbox assigns an opaque
origin, so script in a browsed file cannot read the application document, cookies,
storage, or `/api` responses.
`frame-ancestors` is omitted so nested frames inside a sandboxed page still load: the
opaque ancestor origin would never match `'self'`. `/raw` is not behind the API origin
check, because stylesheets and images must load as subresources; a previewed page can
probe whether a file exists through load and error events, but cannot read its bytes.

- **Active content off:** the sandbox omits `allow-scripts`, so a direct `/raw` link
  renders markup and loads subresources but runs nothing.
  A request whose `Sec-Fetch-Dest` is a script, style, or worker destination
  (`_CODE_DESTINATIONS`) is refused with `403`, and a script or stylesheet is sent as
  `text/plain` for a browser that sends no fetch metadata.
- **Raster images** (`_PROFILE_INDEPENDENT_MEDIA_TYPES` in `server.py`) run nothing, as
  an image or as a document, so their sandbox omits `allow-scripts` under both profiles.
  The route decides by the type it chose, so a `304` and a multipart range answer carry
  the same policy.

**Caching under two profiles.** Those headers belong to the profile that sent them, and
an answer a browser keeps without asking is replayed without reaching the server, under
whichever profile serves the origin by then.
So only an answer whose execution headers are the same under both profiles, a raster
image’s, is kept as immutable, and only at the query form’s `v` while that is the
version the file has now.
`v` comes from `_raw_version`, which the render route hands each file a Markdown
document embeds (`raw_versions`, bounded by `_MAX_RAW_VERSIONS`): a digest of the file’s
resolved path, size, modification and change times, inode, and device, of the trust
profile and its sandbox, and of the build, so a replaced file is a new address.
Every other answer is `Cache-Control: no-cache`: an SVG or HTML document, an unversioned
address, a stale version, the path form `/raw/{path}`, which is never versioned, and
every error. `tests/test_raw_profile_cache_chrome.py` follows a link the trusted profile
gave to an SVG after the switch, in Chrome.

A `/raw` `ETag` (`_raw_identity`) names the file (its name, size, modification and
change times, and inode), the representation, the trust profile, the sandbox policy, and
the build. Only a matching tag in `If-None-Match` earns a `304`; `*` and
`If-Modified-Since` alone get the whole response, because neither says which profile
made the copy a browser holds.
Back and forward navigation is not a new load: a browser may show again, from its
history, a `/raw` document with the headers it was sent then, until reload.
Only `no-store` would rule that out, at the cost of every image’s `304`.

### HTML Preview

`.html` and `.htm` files open as the `html` kind, with Preview and Source.
Preview loads the path-shaped `/raw/{path}` URL in an iframe, so relative stylesheets,
images, scripts, and sibling links resolve.
The frame’s sandbox (`PREVIEW_SANDBOX` in `builtin_plugins/html/index.js`) never
includes `allow-same-origin` or `allow-top-navigation`, and the frame sends no referrer.
**Open as full page** is an ordinary new-tab link to the same URL with
`rel="noopener noreferrer"`; containment is identical there, because the sandbox is a
header on the response rather than an attribute of the frame.
Fidelity matches opening the file in a browser: classic scripts, styles, images, and
nested frames work; `localStorage`, same-document `fetch`, ES modules, and CORS webfonts
do not, and `/raw` never sends `Access-Control-Allow-Origin` to compensate.
By default, sandboxed scripts can still run, reach the network, and use `/raw` as an
existence oracle. With active content off, Preview is omitted and Source is the only
view.

### API Origin Proof

`_HostValidationMiddleware` checks every request’s `Host` against an allowlist to defeat
DNS rebinding, where a hostile site points its own name at `127.0.0.1` and reads files
with what the browser treats as same-origin requests.
Loopback names, a concrete `--host`, and the names in `METABROWSER_ALLOWED_HOSTS` pass;
anything else is `421`.

`/api` routes also need same-origin proof, which the Host check cannot give because a
hostile page sends a genuine `Host`. The server accepts `Sec-Fetch-Site: same-origin`,
an `Origin` matching the application, or `Sec-Fetch-Site: none`, a user-initiated
navigation with no initiator document, which a page cannot make a browser send.
It refuses `Origin: null` and foreign origins with `403`, and accepts a request with
neither header, as `curl` and `metab --api` send.
State-changing methods additionally need `Content-Type: application/json`, or `415`, so
a cross-site form or `text/plain` POST cannot reach a write path such as
`POST /api/kpress/export`.

### Trust Switches

`resolve_capabilities` (`capabilities.py`) resolves one capability block per process:
`active_content` and `mutations`. The untrusted profile turns active content off and
keeps mutations off; the individual switches override the profile; and a flag on the
command line outranks the environment in both directions, so only another flag lifts
`--untrusted`. The flags and their variables are documented in
[Command Line](../../command-line.md).
The resolved block is on `window.METABROWSER_SETTINGS.CAPABILITIES` and
`GET /api/capabilities`, and the server is authoritative.

The trust variables are read from the process environment only.
A `.env` or `.env.local` file may contribute only the names in `ALLOWED_KEYS`
(`dotenv.py`), and Metabrowser warns about any of its own names it ignored.
The rule is an allowlist because the loader cannot tell a file the operator wrote from
one in the repository being browsed, and a denylist secures only the names somebody
thought of. A name qualifies only if its parser is total, so a hostile file cannot make
the knob mean anything else.
The rendering budgets fail that test: each is parsed with `int()` at import and bounds a
read on a request path, so a file value could stop the process from starting or lift a
cap.
`METABROWSER_PLUGINS_DIRS` is kept out because a directory plugin is JavaScript that
runs in the application page.
A file that is not regular or exceeds `MAX_DOTENV_BYTES` is skipped with a warning, and
`${VAR}` is left as written, so a browsed file cannot hold the command by blocking its
read.

### Acquired Git Sources

A Git source acquired from a URL is third-party content.
Every mode that opens it, serving included, runs it under the untrusted profile:
untrusted is implied, the environment’s enables are ignored, and `--allow-edits` is
refused. A server serving such a pin reads only that pin’s store.
It answers `/api/cache/…` with `unsupported_for_subject`, so records that name other
cached sources are never served beside acquired content, and answers the path-shaped
`/raw/{path}` the same way, because the preview that is that form’s only consumer is
never offered there.

### Borrowed Objects

A store may borrow objects from a checkout the reader names with `--checkout`, through
Git’s `objects/info/alternates`; the mechanism is in
[Mirror Acquisition and Refresh](arch-mirror-acquisition-and-refresh.md).
Borrowing changes nothing about what is served or how, and nothing about it can lift the
untrusted profile.

- **Its configuration is never consulted.** No Git process runs in the checkout.
  Its remotes, refs, and object format are read as bounded regular files, so a FIFO
  cannot block a command, and Git reads the borrowed objects under the store’s own
  configuration, so the checkout’s hooks, `core.fsmonitor`, `core.sshCommand`, and diff
  drivers do not run. Nothing is written to it.
- **Its bytes are trusted as a served folder’s are.** Git does not verify an object’s
  hash when it reads one, so whoever can write the checkout can decide what a pull
  request’s files look like.
  That is already true of `metab <checkout>`, and it is why only a checkout the reader
  names lends: one found by walking up from the working directory is printed as a
  suggestion and never borrowed from.
- **Its refs and boundary are not believed.** The store’s refs are only what the origin
  sent. The checkout’s remote-tracking tips only tell the origin what need not be sent,
  and its shallow boundary is used only as a cut of the commit graph, which can make a
  merge base uncertain but never certain and wrong.
- **The alternates file is checked.** A store whose alternates file names anything but
  the directory its record names is refused as damaged, and the checkout is checked
  again on every open and before every fetch; one that has grown alternates of its own,
  or whose directory holds another repository, is refused as `lender_missing`.
- **Its path is display text.** It appears in `/api/source/status` and the heading’s
  tooltip, and no route takes it back as an input.

## References

- [SECURITY.md](../../../SECURITY.md): reporting and the trust settings
- [Command Line](../../command-line.md): trust flags and environment variables
- [Live Delivery](arch-live-delivery.md): the event stream and what a quiet one means
- [Rendering Large Content](../../large-content-rendering.md): bounds on one file

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
