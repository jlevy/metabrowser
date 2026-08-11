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

Two boundaries are documented here because they are **not yet enforced**. Until they
are, point Metabrowser only at roots whose files you trust as much as the application
itself, exactly as the trusted-local warning above says:

- `/raw` serves in-root files at their native media type on the application origin with
  no sandboxing headers, so following a direct `/raw` link to an HTML or SVG file
  executes that file’s scripts with the application’s privileges.
- `/api` routes do not require proof that a request originated from the application’s
  own pages. The Host allowlist stops DNS rebinding, where the attacker must read the
  response; it does not stop fire-and-forget cross-site requests, and
  `POST /api/kpress/export` writes rendered output beneath the served root.

The
[HTML rendering and trust model plan](docs/project/specs/active/plan-2026-08-06-html-rendering-and-trust-model.md)
closes both: content responses get a browser-enforced opaque origin, `/api` routes
require same-origin proof, and an `--untrusted` profile disables active content
entirely. The governing invariant it introduces: content viewed through Metabrowser gets
exactly the privilege a browser would give the same file opened directly, and never
Metabrowser’s server-side API.

See [supply-chain security](SUPPLY-CHAIN-SECURITY.md) for dependency and build policy.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
