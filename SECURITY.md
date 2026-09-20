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
That variable is read from the process environment only, never from a `.env` or
`.env.local` file.

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
`allow-scripts` from the raw sandbox.
`--allow-edits` (`METAB_ALLOW_EDITS=1`) publishes `mutations: true`; no write route
consumes that flag yet.
Individual flags override the profile.
A flag on the command line outranks the environment in both directions, so `--untrusted`
stays conservative whatever the `METAB_*` variables say, and only another flag —
`--untrusted --allow-edits` — lifts it.
The `METAB_*` variables themselves are read from the process environment only, never
from a `.env` or `.env.local` file, so browsing a cloned repository from inside it
cannot let that repository choose how far it is trusted.
The resolved block is on `window.METABROWSER_SETTINGS.CAPABILITIES` and
`GET /api/capabilities`; the server is authoritative.

`.html` and `.htm` files open as the `html` kind, with Preview and Source tabs.
Preview loads the file in an iframe whose `src` is the path-shaped `/raw/{path}`
document URL, so relative stylesheets, images, scripts, and sibling links resolve.
The iframe sandbox is `allow-scripts allow-popups allow-forms allow-downloads` with
`referrerpolicy="no-referrer"`. It never includes `allow-same-origin` or
`allow-top-navigation`. When active content is off, Preview is omitted and Source is the
only view.

Fidelity matches opening the same file in a browser: classic scripts, styles, images,
and nested frames work.
`localStorage`, same-document `fetch`, ES modules, and CORS webfonts do not, and `/raw`
never sends `Access-Control-Allow-Origin` to compensate.

By default, sandboxed scripts can still run, phone home, and use `/raw` as an existence
oracle. `--untrusted` omits the preview and stops script execution on raw responses.

Content viewed through Metabrowser gets exactly the privilege a browser would give the
same file opened directly, and never Metabrowser’s server-side API.

See [supply-chain security](SUPPLY-CHAIN-SECURITY.md) for dependency and build policy.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
