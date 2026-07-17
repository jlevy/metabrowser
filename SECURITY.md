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

See [supply-chain security](SUPPLY-CHAIN-SECURITY.md) for dependency and build policy.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
