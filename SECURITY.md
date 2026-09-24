# Security Policy

## Supported Versions

Security fixes are provided for the latest published Metabrowser release.
During the `0.x` series, upgrades may include compatibility changes documented in the
release notes.

## Reporting a Vulnerability

Do not open a public issue for a vulnerability.
Use GitHub’s private vulnerability reporting for
[jlevy/metabrowser](https://github.com/jlevy/metabrowser/security) when it is available,
or contact the maintainer through the email address in the package metadata.

Include the affected version, impact, reproduction steps, and a minimal sanitized
fixture. Do not send credentials, private logs, customer data, or an archive of a served
filesystem.

## Security Boundaries

Metabrowser is a trusted-local-client tool, not a public-facing web server.
It does not provide a public-service authentication or tenant-isolation boundary.
Serving on another interface can expose file contents beneath the selected root and
should be done only within a trusted network boundary; never expose Metabrowser directly
to the internet.

Plugins execute JavaScript in the Metabrowser page and installed entry-point plugins may
execute Python data hooks.
Install plugins only from trusted sources.
The served data root is never an automatic plugin source.

Every request’s `Host` header is checked against an allowlist to defeat DNS rebinding,
where a malicious website points its own domain at 127.0.0.1 and reads files with what
the browser treats as same-origin requests.
Loopback names and a concrete `--host` value are permitted automatically.
Additional trusted names for reaching a wildcard bind can be listed in the
`METABROWSER_ALLOWED_HOSTS` environment variable (comma-separated); every name added
there extends the set of domains whose pages the browser will let read responses, so
list only names you control.
That variable is read from the process environment only; a `.env` or `.env.local` file
contributes only the two names named under Content Trust Model below.

Path handling is designed to keep file access beneath the selected root.
Reports of a path traversal, symlink escape, unsafe archive handling, cross-origin
exposure, or plugin trust bypass are security issues.

## Content Trust Model

Metabrowser serves two classes of responses with different privilege.
Application surfaces — the shell at `/`, static assets, every `/api` route, and plugin
assets under `/plugin-static` — are first-party code from the installed wheel and
operator-installed plugins, and they use the full server API. Content surfaces serve the
browsed files themselves: file previews through `/api/file` and raw bytes through
`/raw`.

Browsed content never executes inside the application page.
Source views are entity-escaped before insertion, and markdown is rendered through
KPress in its sanitized mode, which strips scripts, event-handler attributes, and
`javascript:` URLs.
Plugin discovery never treats the served root as a plugin source (see
[plugin trust](docs/plugins.md)).

KPress’s sanitized mode is a document renderer’s policy, and it keeps what a document of
its own may use: stylesheets, images, SVG and its `url()` paint servers, classes the
application styles, `data-*` attributes KPress’s own scripts act on, and `id` and
`name`. Inside the application page each of those is an attack from a document a reader
did not write.
So when active content is off — every served mirror, where a fork’s author
controls the head’s Markdown, and a folder served with `--untrusted` — and for every
pull-request comment, Markdown reaches the page only as an allowlist of plain markup,
applied twice: on the server by `src/metabrowser/inert_html.py`, and in the page by
`static/inert-html.js`, which parses the HTML into an inert `<template>` and inserts
only nodes rebuilt from the allowlist.
The allowlist keeps paragraphs, headings, emphasis, code, quotes, lists, tables, and
details, links, and images inside the served tree; no class, `id`, `name`, `data-*`,
style, or event attribute; and no SVG, MathML, media, stylesheet, frame, form, or
script. An outside image becomes a link to it, a link keeps only an `http`, `https`, or
in-document address and opens outside the page in a new tab with no opener or referrer,
and no KPress script is loaded for such a document: the render’s asset list keeps only
its stylesheets. A trusted folder keeps KPress’s rich rendering.

With active content off the application page also carries a Content-Security-Policy, a
second line behind the allowlist.
Scripts run only from the application’s own static paths, `/static/` and
`/plugin-static/`, and the shell’s inline scripts only by a nonce fresh on every
response; no inline event handler runs, and the application writes none.
The browsed tree’s own files, served under `/raw`, are never among them.
Stylesheets come from those paths and `/kpress-static/`, the Markdown worker from
`/plugin-static/`, and images (with the `data:` images the stylesheet draws, and the
repository’s own images through `/raw`), fonts, and requests from this origin.
The page frames nothing, since the untrusted profile removes the HTML preview, its only
frame, and nothing may frame it (`frame-ancestors 'none'` and `X-Frame-Options: DENY`);
plugins, `<base>`, and form submission are off.
`style-src-attr 'unsafe-inline'` keeps inline `style` attributes, because the
application writes them for layout; an outside `url()` in one is still an image the
image rule refuses, and untrusted Markdown carries no `style` attribute at all.
`capabilities.untrusted_shell_csp` is the policy, and `tests/test_untrusted_markdown.py`
pins it and fails when the application writes an inline handler.

In the same profile `/raw` never serves a browsed file as code: a request whose
`Sec-Fetch-Dest` is a script, stylesheet, worker, or worklet is refused with 403, and a
JavaScript or CSS file is sent as `text/plain` with `nosniff`, which no browser runs or
applies, for a browser that sends no fetch metadata.

In an inert render, references to the application rather than the tree — a query alone,
or a root-relative `/api`, `/_debug`, or `/raw` address however spelled — lose their
address, and so does any link or image past the link enhancer’s limit.
The enhancer resolves the rest in a detached document before the page adopts it, so an
image loads only the address it gave.
Wiki links and embeds, which travel as `data-*` attributes, become plain text.

Content responses through `/raw` and `/raw/{path}` are sandboxed on the wire.
Every raw response — including gzip passthrough, SVG, HTML, and error bodies — carries
`Content-Security-Policy: sandbox allow-scripts allow-popups allow-forms allow-downloads`
and `X-Content-Type-Options: nosniff`. The sandbox assigns an opaque origin, so script
in a browsed file cannot read the application document, cookies, storage, or `/api`
responses. `frame-ancestors` is omitted so nested iframes and framesets in a sandboxed
page still load: the opaque ancestor origin would never match `'self'`. `/raw` is not
behind the API origin check, because stylesheets and images must remain loadable as
subresources; a previewed page can still probe file existence through load and error
events, but cannot read those bytes.
When active content is off, the sandbox omits `allow-scripts` so a direct `/raw` link
still renders markup and loads subresources, but executes nothing.

`/api` routes require same-origin proof.
The server accepts `Sec-Fetch-Site: same-origin` or an `Origin` header matching the
application origin, and refuses `Origin: null` and foreign origins.
`Sec-Fetch-Site: none` is accepted as well: that is a user-initiated navigation — a
typed URL, a bookmark, a restored tab — with no initiator document, so it carries no
attacker-controlled origin, and a hostile page cannot make a browser send it.
Requests with neither header — `curl` and `metab --api` — still work.
State-changing methods additionally require `Content-Type: application/json`, so a
cross-site form or `text/plain` POST cannot reach a write path such as
`POST /api/kpress/export`. The Host allowlist still stops DNS rebinding; the origin
check stops fire-and-forget invocation.

`--untrusted` (`METAB_UNTRUSTED=1`) is the conservative content-trust profile: it
disables active content and keeps mutations off.
`--no-active-content` (`METAB_ACTIVE_CONTENT=0`) is the individual switch that drops
`allow-scripts` from the raw sandbox, renders Markdown inert, and sends the page’s
Content-Security-Policy.
`--allow-edits` (`METAB_ALLOW_EDITS=1`) publishes `mutations: true`; no write route
consumes that flag yet.
Individual flags override the profile.
A flag on the command line outranks the environment in both directions, so `--untrusted`
stays conservative whatever the `METAB_*` variables say, and only another flag —
`--untrusted --allow-edits` — lifts it.
The `METAB_*` variables themselves are read from the process environment only, never
from a `.env` or `.env.local` file, so browsing a cloned repository from inside it
cannot let that repository choose how far it is trusted.
`METABROWSER_PLUGINS_DIRS` is kept from those files for the same reason and a sharper
one: a directory plugin is JavaScript that runs in the application page, so a file in
the browsed tree naming its own plugin directory would execute code there.
Name it in the environment, or pass `--plugins-dir`. The resolved block is on
`window.METABROWSER_SETTINGS.CAPABILITIES` and `GET /api/capabilities`; the server is
authoritative.

Those names are examples of a general rule rather than a list of exceptions.
A `.env` or `.env.local` file may contribute only `METABROWSER_LOG_LEVEL` and
`METABROWSER_REQUEST_LOG`. Every other name is read from the process environment or not
at all, and Metabrowser logs a warning naming any of its own variables it ignored.

The rule is an allowlist because the loader cannot tell a file the operator wrote from
one in the repository being browsed, and a denylist secures only the names somebody
thought of. The environment decides which program runs: `BROWSER`, which the standard
library’s browser launcher honors, `GIT_EXTERNAL_DIFF`, which the `git diff` behind the
diff views executes, and `PATH`.

Membership has one test: the name must be read by a parser no value can break, so that a
hostile file cannot make the program do anything but what the knob means.
One of the two is checked against the known level names and the other is an equality
test. The rendering budgets are deliberately outside it — each is parsed with `int()` at
import and bounds a read on a request path, so a file value could stop the process from
starting or lift a cap that keeps a large document from exhausting memory.

`.html` and `.htm` files open as the `html` kind, with Preview and Source tabs.
Preview loads the file in an iframe whose `src` is the path-shaped `/raw/{path}`
document URL, so relative stylesheets, images, scripts, and sibling links resolve.
The iframe sandbox is `allow-scripts allow-popups allow-forms allow-downloads` with
`referrerpolicy="no-referrer"`. It never includes `allow-same-origin` or
`allow-top-navigation`. When active content is off, Preview is omitted and Source is the
only view. Preview also offers **Open as full page**, an ordinary `target="_blank"` link
to that same raw URL with `rel="noopener noreferrer"`: containment is identical there,
because the sandbox is a header on the response rather than an attribute on the frame.

Fidelity matches opening the same file in a browser: classic scripts, styles, images,
and nested frames work.
`localStorage`, same-document `fetch`, ES modules, and CORS webfonts do not, and `/raw`
never sends `Access-Control-Allow-Origin` to compensate.

By default, sandboxed scripts can still run, phone home, and use `/raw` as an existence
oracle. `--untrusted` omits the preview and stops script execution on raw responses.

A Git source acquired from a `file://` URL is third-party content, and every mode that
opens it, serving included, runs it under the untrusted profile: `--untrusted` is
implied, the `METAB_*` enables are ignored, and `--allow-edits` is refused.
A server serving such a pin reads only that pin’s store.
It answers `/api/cache/…` with `unsupported_for_subject`, so the records that name every
other cached source are never served beside acquired content, and it answers the
path-shaped `/raw/{path}` the same way, because the preview that is that form’s only
consumer is never offered there.

Content viewed through Metabrowser gets exactly the privilege a browser would give the
same file opened directly, and never Metabrowser’s server-side API.

See [supply-chain security](SUPPLY-CHAIN-SECURITY.md) for dependency and build policy.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
