# Security Policy

## Supported Versions

Security fixes are provided for the latest published MetaBrowser release.
Before the first stable release, upgrades may include compatibility changes documented
in the release notes.

## Reporting a Vulnerability

Do not open a public issue for a vulnerability.
Use GitHub’s private vulnerability reporting for
[jlevy/metabrowser](https://github.com/jlevy/metabrowser/security) when it is available,
or contact the maintainer through the email address in the package metadata.

Include the affected version, impact, reproduction steps, and a minimal sanitized
fixture. Do not send credentials, private logs, customer data, or an archive of a served
filesystem.

## Security Boundaries

MetaBrowser is a trusted-local-client tool, not a public-facing web server.
It does not provide a public-service authentication or tenant-isolation boundary.
Serving on another interface can expose file contents beneath the selected root and
should be done only within a trusted network boundary; never expose MetaBrowser directly
to the internet.

Plugins execute JavaScript in the MetaBrowser page and installed entry-point plugins may
execute Python data hooks.
Install plugins only from trusted sources.
The served data root is never an automatic plugin source.

Path handling is designed to keep file access beneath the selected root.
Reports of a path traversal, symlink escape, unsafe archive handling, cross-origin
exposure, or plugin trust bypass are security issues.

See [supply-chain security](SUPPLY-CHAIN-SECURITY.md) for dependency and build policy.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
