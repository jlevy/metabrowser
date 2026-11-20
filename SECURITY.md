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

## The Served-Root Boundary

Metabrowser is a trusted-local-client tool, not a public-facing web server.
It has no authentication or tenant isolation: anyone who can reach the server can read
every file beneath the served root.
It binds to `127.0.0.1` by default.
Serve on another interface only inside a trusted network, and never expose Metabrowser
directly to the internet.

Within that boundary, Metabrowser keeps file access beneath the served root, keeps
browsed content from running with the application’s privilege, and serves any Git source
it acquired under the untrusted profile.
Browsed content gets the privilege a browser would give the same file opened directly,
never Metabrowser’s server-side API.
[Server and content](docs/project/architecture/arch-server-and-content.md) describes the
content-trust model that enforces this.

Plugins run JavaScript in the application page, and installed entry-point plugins may
run data hooks on the server, so install plugins only from sources you trust.
The served root is never an automatic plugin source; [the plugin guide](docs/plugins.md)
lists where plugins are found.

Report as security issues: path traversal or symlink escape, unsafe archive handling,
browsed content reaching `/api` or the application page, cross-origin exposure, plugin
trust bypass, and a link sent to the macOS app that runs, clones, or reaches anything
its [trust boundary](docs/project/architecture/arch-macos-app.md#the-trust-boundary)
does not allow.

## Trust Settings

**Host names.** Every request’s `Host` header is checked against an allowlist, which
stops DNS rebinding: a hostile site pointing its own domain at `127.0.0.1` to read your
files as if same-origin.
Loopback names and a concrete `--host` value are allowed automatically.
`METABROWSER_ALLOWED_HOSTS` adds comma-separated names for reaching a wildcard bind.
Each name it adds is a domain whose pages may read Metabrowser’s responses, so list only
names you control.

**Content trust.** `--untrusted` turns off active content and keeps mutations off;
`--no-active-content` and `--allow-edits` set those switches one at a time.
A flag outranks its environment variable, so `--untrusted` stays conservative whatever
the environment says.
The command-line guide owns the [trust flags](docs/command-line.md#content-trust) and
every [environment variable](docs/command-line.md#environment-variables).

**Images from the web.** Untrusted Markdown, a repository opened from its URL, a pull
request’s text, or a folder served with `--untrusted`, shows its images from the web
over `https`, as github.com does: the page’s Content-Security-Policy admits `https:`
images, the allowlist keeps only an address written in full over `https`, and each is
fetched with no referrer: the image says so, and so does the page’s
`Referrer-Policy: no-referrer`, which covers an image a Mermaid diagram names.
An image runs no script and reads nothing of the page, but its host learns that your
browser fetched it, and from what address of yours, and the browser requests whatever
address the document names, including an `https` address on your own machine or network,
as it would for any web page.
**Block remote images**, in the Metabrowser menu and off unless you tick it, shows every
such image as its alt text and narrows the policy to this origin, so the browser sends
no request for one
([the policy](docs/project/architecture/arch-server-and-content.md#the-untrusted-page-policy)).
On a trusted folder’s page, which has no policy to narrow, the box affects a pull
request’s text, a commit’s, and a Markdown diff, through the allowlist alone; the
folder’s own Markdown is the reader’s and is not changed.

**`.env` files.** Metabrowser reads `.env` and `.env.local` from the working directory
and its parents, so running `metab` inside a cloned repository reads that repository’s
files too. A file there may set only the logging settings named in `ALLOWED_KEYS` in
`src/metabrowser/dotenv.py`, and Metabrowser warns when it ignores one of its own
variables in a file.
Everything else, `METABROWSER_ALLOWED_HOSTS`, the `METAB_*` trust switches, and
`METABROWSER_PLUGINS_DIRS` among them, is read only from the process environment: export
it in your shell or pass the flag.
The rule is an allowlist because the loader cannot tell a file you wrote from one in the
repository you are browsing.

See [supply-chain security](SUPPLY-CHAIN-SECURITY.md) for dependency and build policy.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
