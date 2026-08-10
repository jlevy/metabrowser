# Feature: Full-Page HTML Rendering and an Explicit Trust Model

**Date:** 2026-08-06

**Author:** Metabrowser maintainers

**Status:** Draft

## Overview

Metabrowser shows `.html` files as syntax-highlighted source and offers no way to see
the page.
This plan adds a rendered preview for HTML files that reproduces what a browser
would show when opening the file directly, and it introduces the explicit trust model
that makes such rendering safe to enable by default.
The governing invariant: content viewed through Metabrowser gets exactly the privilege a
browser would give the same file opened directly — rendering fidelity without access to
Metabrowser’s server-side APIs, which belong to the application’s own pages.

The rendering feature and the trust model ship together because they are the same
decision. Rendering a browsed file’s HTML means executing its JavaScript, and the only
question that matters is *what origin that script runs on*. Answer it correctly and
rendering can default to on.
Answer it by convenience — an iframe pointed at the existing `/raw` endpoint — and
browsing a directory becomes equivalent to running its contents.

This plan also closes two existing holes: `/raw` already serves any in-root `.html` file
as `text/html` on the application origin with no sandbox or constraining headers, and
`/api` accepts cross-site fire-and-forget requests, including one that writes beneath
the served root.

## Goals

- Render full-page static HTML with the fidelity of opening the file in a browser,
  including relative stylesheets, images, scripts, and sibling links
- Keep the source view available for every HTML file and choose the default view by
  detecting whether the file is a full page or a fragment
- Guarantee that browsed content viewed through Metabrowser has no more privilege than
  the same file opened directly in a browser — in particular, no access to Metabrowser’s
  server-side APIs
- Contain rendered content in a browser-enforced opaque origin, and require same-origin
  proof on every `/api` route so content can neither read nor invoke the API
- Replace the implicit “everything local is trusted” posture with a named capability set
  that is resolved at startup, published to the client, and re-checked on the server
- Give operators one switch that turns on the conservative profile for browsing content
  they do not trust
- Close the unsandboxed `/raw` execution path with an unconditional response sandbox
  rather than an enumerated list of dangerous types, and close the cross-site
  fire-and-forget path to `/api` that exists today
- Keep the main documentation truthful at every point in the rollout: SECURITY.md
  describes what is enforced now, and this spec owns the deltas

## Non-Goals

- Authentication, multi-tenancy, or any posture that makes Metabrowser safe to expose
  publicly — the trusted-local boundary in [SECURITY.md](../../../../SECURITY.md) is
  unchanged
- The strict application-shell Content Security Policy tracked separately, which is
  blocked on removing inline shell and plugin handlers
- Per-directory or per-file trust decisions, trust prompts, or a persisted trust
  database
- Relaxing markdown sanitization; see “What stays unconditional” below
- Server-side HTML rewriting, script stripping, or link rewriting as a substitute for an
  origin boundary
- Executing HTML from outside the served root, and following `file://` or absolute-path
  references out of it
- A general proxy for remote subresources; a page that loads CDN assets does so
  directly, as it would in a browser

## Background

### What happens today

`.html` and `.htm` are listed in `BROWSER_TEXT_EXTS`, so `/api/file` returns them
through the text branch.
No classifier claims them, so they fall through to the catch-all `text` kind, whose view
registry contains exactly one entry: `{id: "source", default: true}`. The built-in text
plugin escapes the content into `<pre><code>` with an XML highlighting hint.
Because `views.length` is 1, no tab bar renders.
There is no rendered mode and no affordance suggesting one could exist.

Separately, `GET /raw?path=...` streams any file beneath the root at the media type
`mimetypes.guess_type` infers from its name.
Its only current caller is the image renderer’s `<img src="/raw?path=...">`. Nothing in
the UI links to it for HTML.

### The existing trust model

Trust today is binary, global, and implicit.
The served root is assumed to be trusted-local, and the security boundaries that exist
are about *reaching* the server rather than about the *content* it serves:

- A Host-header allowlist defeats DNS rebinding.
- `paths_safe` containment keeps reads beneath the root through traversal and symlinks.
- Plugin discovery deliberately excludes the served root and the home directory, on the
  stated principle that “browsing data must not cause its JavaScript to execute in the
  Metabrowser page.”
- Markdown is rendered through KPress in its `sanitized` trust mode, which strips
  `<script>`, `on*` handlers, and `javascript:` URLs with nh3.
- Everything else is entity-escaped by hand before `innerHTML`.

No CSP is emitted anywhere; it was deferred deliberately because a nominal strict policy
would break the shell’s remaining inline handlers.

There is no per-root configuration object at all — the root is a single mutable
module-level `ROOT_DIR` — and no capability flags.
The mutation gate specified for trusted-local editing (`--allow-edits`,
`METAB_ALLOW_EDITS=1`, a `CAPABILITIES` block in `client_settings_dict()`) is designed
but not yet implemented.

### The gap

The plugin trust boundary states the correct principle, and `/raw` violates it.

A `.html` file beneath the served root, reached at `/raw?path=...`, is a document on the
application’s own origin.
Its scripts can read every API the application exposes — `/api/file` and `/raw` for any
path beneath the root — and can post the results anywhere, because no CSP constrains
`connect-src`. Browsing a directory that contains one hostile HTML file is therefore
sufficient to read the entire served root.

This matters more than “trusted-local” suggests, because browsed files are precisely the
category that cannot be assumed trustworthy.
Saved web pages, scraped output, crawled corpora, email exports, agent transcripts, and
test fixtures in `node_modules` are all ordinary things to point a file browser at, and
all of them routinely contain HTML written by someone else.

This is not only a disclosure problem, because a write primitive already exists:
`POST /api/kpress/export` renders a served-root file and writes the artifact beneath the
root. Same-origin script reaches it trivially, and no route anywhere validates the
`Content-Type` header — `request.json()` parses whatever bytes arrive — so even a
*cross-site* page can fire a simple `text/plain` POST at the loopback server whose body
parses as JSON. The Host allowlist does not intervene: it exists to stop DNS rebinding,
where the attacker must read the response through a domain they control, and a
fire-and-forget write sends the genuine `Host` header.
Browsers are only partway to closing that gap themselves (Chromium’s Private Network
Access preflights; other engines lag), so today’s protection is best described as
accidental. The exposure widens further once `POST /api/mutate` lands, and a server-side
capability re-check does not help: the request carries the user’s own origin and is
indistinguishable from a legitimate one.

`.svg` deserves a specific mention.
`guess_type` maps it to `image/svg+xml`, which is script-capable when navigated to at
top level. The image renderer’s `<img>` tag is safe, because images do not run script in
that context, but a direct link to `/raw?path=evil.svg` is not.

So the feature request arrives on top of an existing hole, and the obvious
implementation would widen it from something no UI links to into a one-click affordance.

## Design

### Threat model

Browsed content rendered in any Metabrowser view gets exactly the privilege a browser
would give that file when opened directly, and nothing more.
In particular it does not reach Metabrowser’s server-side API surface, which exists for
the application’s own pages.

That single sentence decides every other choice below, so it is worth stating what it
implies. It is not “browsed content is safe,” because a local page opened in a browser
can still make network requests, fingerprint, and phone home.
It is that *being viewed through Metabrowser must not add capability*. The application
is a viewer, and a viewer that silently upgrades its content’s authority has stopped
being one.

This splits everything the server sends into two classes with different privilege:

| Class | Routes | Origin | Holds API capability |
| --- | --- | --- | --- |
| Application surfaces | `/`, `/static`, `/api/*`, plugin assets | Application origin | Yes — this is what they are for |
| Content surfaces | `/raw`, `/raw/{path}` | Always opaque | Never |

The shell and its plugins are first-party code shipped in the wheel, and they need the
API set to function.
Browsed files are data, and data must not execute with the viewer’s authority.
The plugin trust boundary already draws this line for *where plugin code may come from*;
this draws the same line for *what browsed content may do*.

Two mechanisms enforce it, and both are needed because each covers a case the other
misses.
An opaque origin stops content from reading the API. A same-origin requirement on
the API stops content from *invoking* it.
The sections below take them in turn.

### Giving content an opaque origin

An `<iframe src="/raw/...">` without a `sandbox` attribute is same-origin with the
application. The framed document can reach `window.parent`, read `document.cookie` and
`localStorage`, and call every API as the user — the exact capability upgrade the threat
model forbids. That is not acceptable even under a “trusted drive” reading, because
trusting a drive means trusting the operator’s intent in choosing it, not having audited
every HTML file beneath it.

The fix is to give the framed document an opaque origin:

```html
<iframe sandbox="allow-scripts allow-popups allow-forms allow-downloads"
        referrerpolicy="no-referrer" …>
```

`allow-scripts` without `allow-same-origin` is the load-bearing combination.
The browser assigns the document a unique opaque origin, so scripts run and the page
looks exactly as it would standalone, but it cannot touch the parent, cannot read
cookies or storage, and its `fetch` calls to Metabrowser’s APIs are cross-origin
requests whose responses CORS will not let it read — the server sends no
`Access-Control-Allow-Origin`, so what comes back is opaque.

A separate real origin, on a second port or a different loopback name, would achieve the
same isolation through the browser’s ordinary origin model rather than through a sandbox
attribute. It is rejected because it costs a second listener, a second entry in the host
allowlist, and a port in every URL the user sees, to buy isolation the opaque origin
already provides.

`allow-scripts` and `allow-same-origin` must never appear together.
The HTML specification notes that the combination lets the framed document remove its
own sandbox attribute from the parent, which defeats the mechanism entirely.

`allow-top-navigation` is also withheld, so a hostile page cannot navigate the whole tab
to a phishing target.
`allow-popups` is granted because static documentation links with `target="_blank"` are
common and popups inherit the sandbox unless `allow-popups-to-escape-sandbox` is also
set, which it is not.

Subresources still work: stylesheets apply, images load, classic scripts execute, and
nested iframes and framesets load their frames, each in its own opaque origin.
The precise fidelity envelope is worth stating, because it is exactly the invariant’s:
the preview matches opening the file from disk via `file://`, not hosting it on a local
HTTP server. Beyond `file://` parity it adds working classic scripts and stylesheets;
what stays outside the envelope is anything that needs a real origin — `localStorage`
throws, same-document `fetch` responses are unreadable, ES modules and CORS-gated
webfonts do not load — because opaque origins have none, and `/raw` sends no
`Access-Control-Allow-Origin` to compensate.
It must not: an `Access-Control-Allow-Origin` on `/raw` would let any website in a
browser without Private Network Access enforcement read files beneath the root, and
`Access-Control-Allow-Origin: null` specifically would hand that read to every sandboxed
document anywhere. Static content does not care about any of this, and the source view
remains one click away.

This containment is why rendering can default to on without coupling it to the mutation
gate. With an origin boundary, “render this page” grants no power over the served root.
Without one, enabling rendering would silently confer every capability the application
has — which is exactly the coupling that makes trust models incoherent.

### Closing the API to content: CORS blocks reading, not sending

An opaque origin is necessary and not sufficient, and the gap is easy to miss because
CORS is usually described as if it blocked the request.

It does not. For a simple request — a `GET`, or a `POST` whose content type is
`text/plain`, `application/x-www-form-urlencoded`, or `multipart/form-data` — the
browser *sends* it and then withholds the response from the caller.
For an attack whose payload is the side effect rather than the answer, that is no
protection at all. A sandboxed preview can therefore still reach
`POST /api/kpress/export` today, and `POST /api/mutate` once it lands, fire-and-forget,
without ever reading a byte back.
This is ordinary CSRF, and no sandbox token prevents it.
The same shape works from any website against the loopback server, as the background
section describes, so this check defends against the open web, not only against
previewed files.

Strictly, opening the same file directly in a browser has the same power over a loopback
server, so the letter of “same as a regular browser” is satisfied.
The intent is not: browsed content would be reaching Metabrowser’s server-side
components. Because Metabrowser is the thing serving that content, it can do better than
the browser baseline here, and should.

The enforcement point is the API, not the content.
Every `/api/*` route requires proof that the request came from an application surface:

- `Sec-Fetch-Site: same-origin`, or an `Origin` header matching the application origin.
- A request carrying `Origin: null` is rejected.
  This is precisely what an opaque-origin document sends, so the check separates the two
  resource classes exactly along the line the threat model draws.
- State-changing routes additionally require the `application/json` `Content-Type`
  *header*, which makes any cross-origin attempt a non-simple request that triggers a
  CORS preflight no cross-origin caller can pass, and are never reachable by `GET`. The
  header check must be explicit: Starlette’s `request.json()` parses the body bytes
  without ever looking at the header, so today a `text/plain` simple request sails
  through to the handler.

This belongs in `_HostValidationMiddleware`, which already inspects request headers to
decide admissibility and already exists to stop a different confused-deputy attack.
It is the same shape of check at the same layer, and the two share the “reject before
routing” path.

The check is what makes `allow-forms` safe to grant, and it is worth being explicit that
the safety comes from the server, not the sandbox: a form POST to `/api/mutate` from a
sandboxed document is a simple request that the browser will happily send, and the
`Origin: null` rejection is the only thing that stops it.

`/raw` is deliberately *not* behind this check.
Content surfaces must stay loadable as subresources or relative stylesheets and images
break, which is the whole point of the feature.
That leaves a previewed page able to probe for the existence of files under the root
through load and error events on `<img>` and `<script>` tags.
It cannot read their contents — `fetch` is still opaque, and canvas is tainted — so this
is an existence oracle, not disclosure.
Accepting a narrow oracle to keep `/raw` usable as content is the deliberate trade, and
it is the line the two-class table draws: `/raw` is content, `/api` is authority.

### The server enforces the boundary, not the client

An iframe attribute only protects content reached through the application’s own UI. A
user who opens `/raw/report.html` in a new tab, or a page that links to it, gets a
top-level same-origin document with no sandbox at all.

The authoritative boundary therefore belongs on the response, and applies to **every**
`/raw` response without inspecting its type:

| Header | Value |
| --- | --- |
| `Content-Security-Policy` | `sandbox allow-scripts allow-popups allow-forms allow-downloads` |
| `X-Content-Type-Options` | `nosniff` |

The CSP `sandbox` directive applies the same opaque-origin treatment as the iframe
attribute, at the transport layer, however the resource is reached.

Applying it unconditionally rather than to a list of script-capable types is the more
important half of this choice.
A type list has to be right about the HTML family, `image/svg+xml`, the XML types,
XHTML, `.svgz`, and whatever `mimetypes.guess_type` returns on a platform whose
`/etc/mime.types` we have never seen — and the media type is inferred from an
attacker-chosen *file extension*. Enumerating dangerous types is a bug waiting for the
first name nobody thought of.
Sandboxing everything has no such failure mode, and costs nothing: the directive
constrains documents, so a stylesheet or image loaded as a subresource is unaffected,
and `allow-downloads` keeps saving a file working.

`nosniff` then closes the reverse direction: without it, a `.txt` or extension-less file
whose bytes look like markup can be content-sniffed into HTML by some browsers.

The layers end up in the right order.
The server’s headers hold even if a future renderer forgets the attribute; the iframe
attribute holds even if a response escapes the header path; and the API’s same-origin
check holds even if both fail.

One implementation note: the headers must be applied on all three branches of
`raw_file`, including the gzip passthrough, so a `.html.gz` is not an escape hatch.

`frame-ancestors` is deliberately absent, and an earlier draft of this design got it
wrong. `frame-ancestors 'self'` looks like an obvious hardening, but the directive
matches every document in the ancestor chain, and inside a previewed page that chain
starts with the preview document itself — whose origin is opaque and can never match
`'self'`. It would therefore break every nested browsing context in previewed content:
framesets and saved pages with iframes, which are exactly the legacy static HTML this
feature exists to show.
And it defends nothing here, because anti-framing protects content whose interactions
carry authority; sandboxed raw content has none.
The residual it leaves — an external page in a browser without Private Network Access
enforcement can *display* in-root files it cannot read, and observe frame load events as
an existence probe — is the same class of oracle already accepted for `<img>` below, and
the Host allowlist plus PNA continue to narrow it.

### Relative URLs require a path-shaped raw route

This is the largest practical obstacle to “renders as it would in a browser,” and it is
not a security problem — it decides the URL design.

With `src="/raw?path=docs/page.html"`, the document’s base URL is `/raw`. A relative
reference to `style.css` resolves to `/style.css`, and `../img/logo.png` escapes the
route entirely. Every relative stylesheet, image, script, and sibling link in a real
static page breaks.

Serving the same bytes from a path-shaped URL fixes this by construction: at
`/raw/docs/page.html`, `style.css` resolves to `/raw/docs/style.css` and lands on the
right file. No rewriting, no `<base>` injection, no proxy.

Add `GET /raw/{path:path}` alongside the existing query form rather than replacing it.
The query form is public API with a live caller in the image renderer, and both routes
resolve through the same `_safe_path` and share one response builder.

### Trust model: one capability set, independent switches

The consistent model is a single capability block resolved once at startup, published to
the client as a presentation hint, and re-checked on the server for every request that
depends on it. This is the convention the file-actions plan already establishes for
mutations; this plan generalizes it rather than adding a parallel mechanism.

| Capability | Default | Disable with | Governs |
| --- | --- | --- | --- |
| `active_content` | on | `--no-active-content`, `METAB_ACTIVE_CONTENT=0` | HTML preview, script execution on content surfaces |
| `mutations` | off | `--allow-edits`, `METAB_ALLOW_EDITS=1` to enable | `POST /api/mutate` |

The API same-origin requirement is not in this table because it is not a capability.
It is the boundary that makes the capabilities meaningful, holds under every setting,
and has no flag to turn it off.

One profile switch, `--untrusted` (`METAB_UNTRUSTED=1`), sets every capability to its
conservative value. It is the answer to “I am about to browse a corpus I did not write,”
and it is one flag rather than a list to remember.
Individual flags override it, so `--untrusted --allow-edits` is expressible and means
what it says.

The defaults are deliberately asymmetric, and the asymmetry is the point rather than an
inconsistency. `mutations` defaults off because it changes the user’s disk and no
containment makes that reversible; that decision is already made and this plan does not
revisit it. `active_content` defaults on because the origin sandbox makes it a
presentation choice rather than a grant of authority.
What is consistent is the *mechanism* — one block, one resolution point, server
authoritative, client flags as hints, disabled affordances that explain themselves
rather than disappearing.

With `active_content` off, HTML files render source only, the preview tab is absent
rather than disabled (there is nothing to explain about a view that cannot exist), and
the raw routes drop `allow-scripts` from the sandbox directive so a direct link renders
markup but executes nothing.
Dropping the token is the same no-type-enumeration philosophy as the unconditional
header: earlier drafts downgraded “script-capable types” to `text/plain`, which
reintroduced the type list this design just removed, and broke innocent uses (a styled
page becomes unreadable as plain text) while the CSP change degrades exactly the one
thing the flag is about.

Resolution follows the established path: new options on `metab serve` in `cli/main.py`
and `cli/serve.py`, resolved into an immutable capability object before application
construction, published through `client_settings_dict()` as a `CAPABILITIES` block on
`window.METABROWSER_SETTINGS`, and reported by `GET /api/capabilities` alongside the
watcher mode it already returns.

### Full-page detection selects the default view, not the only view

Classification is by extension, which is what the classifier layer supports: a built-in
`html` kind matching `.html` and `.htm`, mirroring the existing markdown plugin’s shape.
The kind declares two views — `Preview` and `Source` — so the existing tab bar appears
without new shell machinery.

Content sniffing decides only which of the two is `default`. The server reads a bounded
prefix of the file (4 KiB is ample), skips a BOM, leading whitespace, and comments, and
looks case-insensitively for `<!doctype html`, `<html`, `<head`, `<body`, or
`<frameset`. A hit means full page and defaults to `Preview`; anything else is treated
as a fragment and defaults to `Source`.

Making detection choose the default rather than gate the feature is what keeps the
behavior predictable.
A fragment still previews if the user asks, a full page still shows its source, and a
misdetection costs one click instead of hiding a capability.
The bounded read also satisfies the standing rule against unbounded filesystem work on
request paths.

Templating languages are the known imperfection: a Jinja or Handlebars `.html` file
looks like a full page and previews with its `{{ }}` markers visible.
That is a reasonable thing to show, and the source tab is adjacent.

### What stays unconditional

Markdown sanitization does not become configurable, and `--untrusted` does not tighten
it because it is already at its strict setting.

The reason is the origin boundary again.
Markdown renders as a fragment injected into the application document, where there is no
containment whatsoever — unsanitized markdown HTML is same-origin script execution by
definition. The HTML preview path is safe because it has an origin boundary, not because
HTML is somehow more trusted, so extending “trusted rendering” to the inline path would
grant real authority while appearing to be the same decision.

If a user wants full fidelity for a document with embedded scripts, the answer is the
preview path, not a weaker nh3 profile.
This keeps one invariant that is easy to state and to test: content rendered inline in
the application document is always sanitized; content that runs as authored always runs
in an opaque origin.

### Relationship to the deferred application CSP

This plan does not depend on the strict shell CSP and does not unblock it.
The policies here are attached to `/raw` responses, which contain no inline shell or
plugin handlers, so the constraint that deferred the shell policy does not apply.
The highest-risk endpoint gets a real policy now, and the shell refactor proceeds on its
own schedule.

## API Changes

| Interface | Method | Description |
| --- | --- | --- |
| `/raw/{path}` | GET | Path-shaped raw file access so relative references resolve correctly |
| `/raw` | GET | Unchanged query form, sharing the new response headers |
| `/api/*` | all | Requires same-origin proof (`Sec-Fetch-Site` or `Origin`); `Origin: null` rejected |
| `/api/file` | GET | Returns kind `html` with `preview` and `source` views for HTML files |
| `/api/capabilities` | GET | Adds the resolved capability block |

Response headers on both raw routes are as tabulated above.
No request accepts a client-supplied absolute path, and both routes resolve through
`_safe_path`.

The same-origin requirement is a compatibility change for anyone calling `/api` routes
from scripts: `curl` and same-origin `fetch` are unaffected (no `Origin` header, or a
matching one), but a cross-origin caller that previously worked by accident stops
working. That is the vulnerability being fixed, not collateral damage.

## Documentation Plan

SECURITY.md gains a “Content Trust Model” section **with this spec**, before any code
lands. It documents the two response classes, states that browsed content never executes
inline in the application page (escaped source, nh3-sanitized markdown), and names the
two boundaries that are not yet enforced — `/raw` executing on the application origin,
and `/api` accepting requests without origin proof, including the export write path.
Documenting the unenforced state plainly is deliberate: the repository is public either
way, the spec spells out the mechanics regardless, and a security document that
describes the intended model as if it were current would be worse than either.
The architecture doc’s related-documentation list links to it.

Each phase then updates the documentation it invalidates, in the same change:

- **Phase 1** rewrites the not-yet-enforced list into enforced guarantees: content
  responses are sandboxed unconditionally, and `/api` requires same-origin proof.
- **Phase 2** documents `--no-active-content`, `--untrusted`, and the environment
  variables in SECURITY.md and the README warning block, when the flags exist.
- **Phase 4** documents the preview, its containment, and the capability report, and
  adds the invariant sentence to SECURITY.md as a stated guarantee rather than a plan.

No documentation describes a flag or behavior before the phase that ships it.

## Implementation Plan

### Phase 1: Close the content-to-API paths

Independently valuable and shippable without any UI change.
Both halves of the boundary land together: the sandbox stops reading, the same-origin
check stops invoking.

- [ ] Add a shared response-header builder for `raw_file` covering all three branches
- [ ] Send the unconditional CSP `sandbox` header and `nosniff` on every raw response
- [ ] Require same-origin proof on `/api/*` in `_HostValidationMiddleware`, rejecting
  `Origin: null`
- [ ] Add regression tests for the gzip passthrough, `.svg`, and cross-origin `/api`
  rejection
- [ ] Update the SECURITY.md not-yet-enforced list to enforced guarantees

### Phase 2: Capability plumbing

- [ ] Add the capability object, resolved before application construction
- [ ] Add `--no-active-content`, `--untrusted`, and their environment variables
- [ ] Publish the block through `client_settings_dict()` and `/api/capabilities`
- [ ] Drop `allow-scripts` from the raw sandbox directive when `active_content` is off
- [ ] Document the flags in SECURITY.md and the README warning block

### Phase 3: Path-shaped raw route

- [ ] Add `GET /raw/{path:path}` sharing one resolution and response path with `/raw`
- [ ] Cover traversal, symlink escape, and percent-encoding equivalence between routes

### Phase 4: The HTML kind and preview

- [ ] Add the bounded full-page sniff with a documented byte budget
- [ ] Add the built-in `html` kind with `preview` and `source` views and sniff-chosen
  default
- [ ] Add the preview renderer with the sandbox attribute set and a disposal path
- [ ] Suppress the preview view entirely when `active_content` is off
- [ ] Document the preview, its containment envelope, and the invariant in SECURITY.md
  as shipped guarantees

## Testing Strategy

The security-relevant assertions are about headers and attributes, both of which are
cheap to test directly and are the kind of property that regresses silently.

- Assert the exact `sandbox` token set on the rendered iframe, and specifically assert
  that `allow-same-origin` is absent — the single most important invariant here
- Assert the raw response headers are present and identical on all three branches,
  including the gzip passthrough, and on both route shapes
- Assert `/api` routes reject `Origin: null` and foreign origins, and accept requests
  bearing the application origin or no `Origin` at all (`curl` compatibility)
- Simulate the CSRF shape directly: a `POST` with a form content type and `Origin: null`
  against a mutating route must be rejected before the handler runs
- Assert that `active_content` off removes the preview view and removes `allow-scripts`
  from the raw sandbox directive
- Cover the sniff with full pages, fragments, leading comments, BOM-prefixed files,
  uppercase doctypes, empty files, and a file whose first 4 KiB is whitespace
- Cover relative-reference resolution end to end: a page with a sibling stylesheet and a
  subdirectory image renders with both fetched from the expected raw paths
- Cover a page containing a nested same-directory iframe and a frameset page: frames
  must load, which is the regression test for the absent `frame-ancestors` directive
- Extend the existing path-containment suite to the new route rather than duplicating it
- Verify the preview disposes on pane replacement and does not leak a frame per tab
  switch

## Rollout Plan

Phase 1 ships on its own as a security fix and should not wait for the rest.
It changes no UI and no legitimate workflow, but it is not behaviorally invisible: a
cross-origin caller that worked by accident stops working, and a direct `/raw` link to
an HTML file now renders in a sandbox.
Both are the fix, and the changelog should say so.

Phases 2 through 4 ship together, because a preview without the capability switch is the
thing this plan argues against.
Defaults are chosen so that the common case — a developer browsing their own working
tree — sees only a new, working preview tab and no new flags.

Documentation lands with the phase that makes it true, per the documentation plan above.

## Open Questions

- Should a stricter tier also constrain the preview’s network access
  (`default-src 'self'`, `connect-src 'none'`), trading a hostile page’s ability to
  phone home against breaking legitimate pages that load CDN assets?
  This is a natural third capability but should not block the first four phases.
- In-frame navigation cannot be observed from the parent, by design — clicking a sibling
  link moves the preview without updating the URL hash, the nav tree, or the source tab.
  Accepting this matches browser behavior; the alternative requires giving up the origin
  boundary, so the question is what orientation affordance to offer, not whether to
  intercept.
- Should `.svg` gain a rendered preview through the same mechanism, now that the sandbox
  makes it safe?
- Does the VS Code extension host need a distinct policy, given its own webview sandbox?

## Acceptance Criteria

- A full-page static HTML file with relative stylesheets, images, and scripts renders in
  the preview as it does when opened directly in a browser
- Browsed content viewed through Metabrowser can do nothing it could not do when opened
  directly in a browser: script in a previewed file cannot read the parent document,
  cannot read any response from `/api/*` or `/raw`, and cannot invoke any `/api` route —
  including fire-and-forget `POST`s that never read the response
- The same containment holds for a raw URL opened directly in a new tab, not only for
  the in-application preview
- Every HTML file offers a source view, and the default view follows full-page detection
- `--untrusted` disables the preview and stops script execution on raw responses
- Capability state is reported by the server and never inferred from the client
- Markdown rendering remains sanitized under every capability setting
- Documentation states the content-execution boundary alongside the existing
  trusted-local warning

## References

- [Core architecture](../../../architecture.md)
- [Plugin authoring](../../../plugins.md) — trust model and discovery
- [Security policy](../../../../SECURITY.md)
- [Menu primitives and gated file actions](plan-2026-08-06-menu-primitives-and-file-actions.md)
- [Trusted-local file editing](plan-2026-07-16-trusted-local-file-editing.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
