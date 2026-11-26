# Threat Model

**Status:** Current.
Written on 2026-11-24 from an audit of the code at the PDF plugin’s second phase.
It is the reason for each security policy Metabrowser has: a change to a policy names
the threat below that it answers, or adds one, in the same pull request.
[Known Gaps](#known-gaps) lists where the code falls short of this model, each with its
bead. [SECURITY.md](../../../SECURITY.md) states the result for users.

## What Metabrowser Is

Metabrowser is a local tool: one reader runs `metab` on their own machine and reads its
pages in their own browser or in the macOS app.
It has no accounts, no authentication, and no tenant isolation; it binds to `127.0.0.1`
by default. The reader, their browser and operating system, the installed `metab`, and
the plugins the reader installed are trusted.
What it reads is not: the files under a served folder, a repository fetched from a URL,
and a pull request’s text and changes can all be written by someone else.

## Assets

- **The reader’s files.** Everything the reader’s account can read, not only the served
  folder. The server reads files with the reader’s privilege.
- **The application’s authority.** The `/api` routes, what they read, and the state they
  change: pins, refreshes, cached records, and settings.
- **Credentials.** The `gh` CLI’s login, which Metabrowser runs `gh` with, and the Git
  credentials an acquisition may use.
- **The macOS app’s privileges.** Opening a file in its default app, the host descriptor
  in its pages, and the windows it opens.
- **The cache and state.** Git stores, pull-request records, and the event log under the
  cache, configuration, and state roots.
- **The reader’s privacy.** Which documents they open, from which network address.
- **The reader’s time.** A server that stays responsive whatever it is shown.

## Adversaries

- **A content author** (the one that matters most).
  Whoever wrote a file in a served folder, a repository opened from its URL, or a pull
  request: a hostile README, a crafted PDF or SQLite file, a YAML bomb, a symlink
  pointing out of the tree, an archive received whole with its `.git` directory.
  They control bytes Metabrowser parses and shows, and nothing else.
- **A website.** Any page the reader opens in the same browser.
  It can make the browser send requests to `127.0.0.1`, point its own domain at
  `127.0.0.1` (DNS rebinding), and frame what will let it.
- **The network.** An observer or attacker on a network a server is reachable from: a
  wildcard bind (`--host 0.0.0.0`), or the path of `--remote`’s SSH tunnel.
- **Another local account.** One that can write a directory Metabrowser reads its cache,
  configuration, or `metab` from.
- **A plugin or dependency.** A plugin is code the reader chose to install, so a
  malicious one is out of scope ([Accepted Risks](#accepted-risks)); a compromised
  dependency is the supply chain’s, which
  [SUPPLY-CHAIN-SECURITY.md](../../../SUPPLY-CHAIN-SECURITY.md) answers.

## Trust Boundaries

| Boundary | What crosses it | Where it is held |
| --- | --- | --- |
| Served root | A requested path | `paths_safe.py`, `source.py` ([Safe Paths](arch-server-and-content.md#safe-paths)) |
| Trust profile | Whether a source’s content may run | `capabilities.py`; per request by `capabilities_for` |
| Application page | Browsed markup, into the shell | KPress sanitizing (trusted); `inert_html.py` and `static/inert-html.js` (untrusted) |
| Untrusted page policy | What the page may load, frame, or embed | `capabilities.untrusted_shell_csp` |
| `/raw` | A browsed file’s bytes, as a document | The sandbox and headers `_RawTrustHeaderMiddleware` writes |
| `/api` | A request from a page | `_HostValidationMiddleware`: the Host allowlist and origin proof |
| Server-side parsers | Browsed bytes, into Python | Size and time bounds, child processes ([T7](#t7-parsing-browsed-bytes-exhausts-or-takes-over-the-server)) |
| Git | A browsed repository’s objects and config | The read policies in `git/process.py` |
| `gh` | API paths and queries | `builtin_plugins/github/gh.py` |
| The macOS app’s bridge | A click on a marked link, into Launch Services | `apps/macos/Sources/ShellCore/Web/OpenFile*.swift` |

## Threats

Each threat says what the adversary wants, the policy that answers it, the evidence that
holds the policy, and the risk that remains, with why it is accepted.

### T1. Browsed Content Runs in the Application Page

A content author wants script in the page that holds the application’s authority.

- **Policy.** Browsed content never runs in the application page.
  Trusted Markdown is rendered by KPress in sanitized mode.
  Untrusted content (an `--untrusted` folder, every pinned revision, every repository
  from a URL, and a pull request’s text on any page) passes one allowlist twice, on the
  server and in the browser, which keeps no script, style, frame, object, form, event
  attribute, or link that is not `http`, `https`, or in the tree.
  The untrusted page runs only scripts from the application’s own paths and its nonce
  ([The Untrusted Page Policy](arch-server-and-content.md#the-untrusted-page-policy)).
- **Evidence.** `tests/test_inert_html.py` holds the two allowlists equal and runs a
  hostile corpus through both; `tests/test_untrusted_markdown.py` pins the page policy
  and fails on an inline handler.
- **Residual.** The trusted profile keeps KPress’s richer render, with its two known
  limits in
  [Rendering Browsed Content](arch-server-and-content.md#rendering-browsed-content).
  Accepted: a trusted folder is the reader’s own, and the reader chooses `--untrusted`
  for one that is not.
  The diagram frame lays out an untrusted document’s Mermaid with scripts in the
  application’s origin (`sandbox="allow-scripts allow-same-origin"`), held by its own
  policy and Mermaid’s sanitizing rather than an opaque origin.
  Accepted for now because the frame loads nothing and its policy admits only its own
  modules; tracked in [Known Gaps](#known-gaps).

### T2. A Browsed File Runs as a Document With the Application’s Origin

A content author wants their HTML, SVG, or script file, opened through `/raw`, to read
the application’s cookies, storage, or `/api`.

- **Policy.** Every `/raw` answer, errors included, carries a CSP sandbox without
  `allow-same-origin`, so it has an opaque origin, and `nosniff`. Under the untrusted
  profile the sandbox also drops `allow-scripts`, a script-capable type is answered as
  text, and a request whose destination is code is refused
  ([Raw Responses](arch-server-and-content.md#raw-responses)).
- **Evidence.** `tests/test_content_trust.py`, including the test that a new return path
  cannot miss the headers; `tests/test_raw_profile_cache_chrome.py`.
- **Residual.** A trusted folder’s sandboxed document still runs script and reaches the
  network, and `/raw` answers whether a path exists.
  Accepted: that is what the same file opened from disk can do.
  The type comes from the host’s `mimetypes` database for a name that gives one; see
  [Known Gaps](#known-gaps).

### T3. A Browsed File Is Framed or Embedded in the Application Page

A content author wants a viewer or a frame of their choosing to start inside the page,
or to make the page embed another of the application’s addresses.

- **Policy.** Only the application’s own code makes a frame or an object; the allowlist
  drops both from content.
  Only the file page mounts the PDF view, so a diff, an overview, or a Markdown document
  never starts a viewer.
  The untrusted page policy admits a frame and an object from `/raw` itself, by exact
  path, and nothing else, so the PDF view’s `<embed>` of a file’s bytes is the one thing
  that can be framed or embedded, and it keeps `/raw`’s sandbox.
  Chrome draws an `<embed>`’s PDF in a frame of the same address and checks it against
  `frame-src`, which is why both directives name it.
  The HTML preview, whose frames are `/raw/<path>`, is removed under this profile.
- **Evidence.** `tests/test_pdf_preview_chrome.py` loads the viewer on an untrusted page
  with no policy violation and sees an object at `/api/file` refused;
  `tests/test_untrusted_markdown.py` and `tests/test_serve_pin.py` pin both directives
  and that `/raw` is never a code source;
  `tests/golden/cli-ui-pdf-surfaces.tryscript.md` shows each surface’s policy and
  asserts a mounted diff holds no embed, object, or frame.
- **Residual.** The browser’s PDF engine (PDFium in Chrome, PDFKit in Safari and the
  app) parses an author’s PDF when the reader opens its file page, not only when they
  click Open in new tab.
  Accepted: it is the same engine, in the browser’s own sandbox, that one more click
  reaches, and it is how a browser treats any PDF link.

### T4. A Path Leaves the Served Root

A content author wants `..` or a symlink in the tree to reach the reader’s other files.

- **Policy.** Every path is resolved, symlinks followed, and checked to be inside the
  resolved root before it is read; a NUL is refused.
  A pin reads only its own store, and follows only in-tree symlinks.
- **Evidence.** `tests/test_paths_safe.py`, `tests/test_raw_path_route.py`, and the
  symlink tests in `tests/test_git_revision_content_routes.py`.
- **Residual.** The check and the open are two steps, so a process that can change the
  served tree between them can swap in a symlink.
  Open; see [Known Gaps](#known-gaps).

### T5. A Website Reads or Drives the Server

A website wants to read files through the reader’s browser, or change state.

- **Policy.** Every request’s `Host` must be on an allowlist (loopback, a concrete
  `--host`, and `METABROWSER_ALLOWED_HOSTS`), which stops DNS rebinding.
  `/api` also requires same-origin proof (`Sec-Fetch-Site`, or a matching `Origin`),
  refuses `Origin: null`, and needs `application/json` for a state-changing method, so a
  form cannot post to it.
  There is no CORS. The untrusted page cannot be framed.
- **Evidence.** `tests/test_host_validation.py`; the origin-proof matrix and the
  content-type tests in `tests/test_content_trust.py`.
- **Residual.** The trusted shell sends no `frame-ancestors`, so another site can frame
  it and try to trick a click on its controls.
  Open; see [Known Gaps](#known-gaps).
  `/raw` is outside the origin proof so that subresources load; a website can make the
  browser fetch a raw file but cannot read the answer.

### T6. The Network Reads the Reader’s Files

An attacker on the network wants to reach the server.

- **Policy.** The server binds to `127.0.0.1` unless told otherwise.
  `--remote` runs the far server on its own loopback and reaches it through SSH. A
  wildcard bind is never added to the Host allowlist.
- **Residual.** A server bound to another interface serves every file under its root to
  whoever reaches it, with no authentication.
  Accepted and documented in SECURITY.md: Metabrowser is not a network service.

### T7. Parsing Browsed Bytes Exhausts or Takes Over the Server

A content author wants a file whose parsing hangs the server, exhausts its memory, or
exploits a parser.

- **Policy.** Every read on a request path is bounded, and a parser that can run long
  runs where it can be stopped:
  - untrusted Markdown in a long-lived child with a deadline;
  - SQLite in reader processes with resource limits, an opcode budget, a read-only
    authorizer, and no virtual tables for untrusted sources;
  - YAML front matter through the bounded loader, with an expansion budget;
  - gzip under compressed, decompressed, and time caps;
  - Git object reads under size and time caps.
    The constants are beside their definitions (`settings.py`, `gz_io.py`,
    `frontmatter_yaml.py`, `sqlite_access.py`).
- **Server-side PDF rendering**, for the preview card (`mb-7tcl`), follows the same rule
  and one more: PDFium is a native parser of attacker-written bytes, and a browser runs
  it only inside its own sandbox.
  So every preview is rendered in a child process
  (`builtin_plugins/pdf/render_child.py`) under a deadline, with its input and output
  bounded, a minimal environment, and resource limits set before it reads a byte: CPU
  seconds, no file growth, no core file, no new process, and on Linux its address space.
  A preview of an untrusted source’s PDF (an `--untrusted` folder, a pin, any blob of a
  comparison) is rendered only when that child is also sandboxed: on macOS a
  `sandbox-exec` profile that denies by default, so it opens no socket, writes no file,
  starts no process, and reads nothing outside the interpreter’s, PDFium’s, and the
  system’s libraries and fonts (`preview_isolation.macos_profile`). Where the probe
  finds no such sandbox (Linux today), an untrusted source’s card has no image and says
  why, and a trusted folder’s PDFs still get one, since they are the reader’s own; where
  it finds one, a trusted folder’s are rendered in it too.
  The PNG the child writes is checked against the encoder’s own form before the server
  keeps or serves it, and it is served with `nosniff` and a policy that runs nothing.
  The renderer is a pinned dependency under the supply-chain cool-off, declared by the
  `pdf` plugin alone.
- **Evidence.** `tests/test_inert_render_deadline.py`, `tests/test_sqlite_access.py`,
  `tests/test_frontmatter_bounds.py`, and the alias-bomb test in
  `tests/test_structured_diff_projection.py`; for the PDF preview,
  `tests/test_pdf_preview_sandbox.py` (macOS: a render under the probed profile, and a
  write, a connection, a fork, an exec, and a read of the reader’s file refused under
  it, each allowed bare), `tests/test_pdf_preview_routes.py` (no image for an untrusted
  source or a blob without a sandbox, the deadline’s kill, the input bound, the image
  answer’s headers), and `tests/test_pdf_preview.py` (the rule’s table, the PNG
  validator).
- **Residual.** A trusted folder’s Markdown renders in a server thread with no deadline.
  Accepted: the folder is the reader’s. The structured Tree view parses YAML and JSONC
  under the 8 MiB input cap only, without the bounded loader.
  Open; see [Known Gaps](#known-gaps).
  A memory-safety bug in PDFium rendering a trusted folder’s PDF runs as the reader.
  Accepted: a trusted folder is the reader’s own files.

### T8. A Browsed Repository Runs Commands

A content author wants Git to run a program they name: a hook, a textconv or diff
driver, or a filter.

- **Policy.** Every Git read sets `core.hooksPath=/dev/null` and `core.fsmonitor=false`.
  A store Metabrowser acquired is read with isolated configuration, no textconv, and no
  external diff.
- **Evidence.** The revision tests in `tests/test_checkout_revisions.py` and
  [Open Modes: Showing a Revision Never Writes the Checkout](arch-open-modes.md#showing-a-revision-never-writes-the-checkout).
- **Residual.** A served folder’s own repository keeps its `.git/config`, so its
  textconv and external-diff drivers run, even under `--untrusted`. That config is the
  reader’s when they made the clone, but not when they received the directory whole.
  Open; see [Known Gaps](#known-gaps).

### T9. Credentials Leak

A content author or website wants the reader’s GitHub token or Git credentials.

- **Policy.** Metabrowser never reads, stores, or logs a token: it runs `gh`, which
  holds it, with a cleaned environment, a deadline, and an output cap, and admits only
  API paths and read-only GraphQL it recognizes.
  The status route reports which login and token source are in use, never a token.
  The event log redacts token shapes, and cache records refuse credential-shaped keys
  and URLs with credentials.
  Acquisition runs Git with `HOME=/dev/null` and a protocol allowlist of `https` and
  `file`.
- **Evidence.** `tests/test_github_gh_process.py`; the `no-real-gh` shim makes any
  unexpected `gh` call in a test fail.
- **Residual.** The environment `gh` gets is not pinned by a test.
  Open; see [Known Gaps](#known-gaps).

### T10. The macOS App Opens or Runs What It Should Not

A content author wants a link or a file to make the app run code or open something
dangerous.

- **Policy.** The app loads only its own server’s origin in a window and sends a clicked
  external link to the default browser.
  Its bridges live in an isolated content world, so page script cannot post to them, and
  they take only a trusted, unmodified click on a link to this server’s `/raw`. Open
  opens only PDFs, images, and audio or video (never SVG), judged by type, and a copy of
  a pinned source’s bytes is quarantined and read-only, so Gatekeeper still judges it.
- **Evidence.** `OpenFileTests.swift`, `OpenFileWebKitTests.swift`, and
  `NavigationAndFoldersTests.swift`; `tests/test_macos_app_pins.py` holds the link the
  app takes to the one the plugin draws.
- **Residual.** A file opened in place from a trusted folder is not quarantined.
  Accepted: it is already on the reader’s disk.
  Whether a save-panel download is quarantined is unverified; see
  [Known Gaps](#known-gaps).

### T11. Another Local Account Tampers With State

Another account wants to plant a store, a record, or a `metab` that Metabrowser trusts.

- **Policy.** The cache, configuration, and state roots refuse any ancestor another
  account can write, use private modes and no ACLs, and are reached by directory handle
  without following links.
  Writes are atomic. The app refuses a `metab` another account could change.
- **Evidence.** `tests/test_cache_layout.py`, `tests/test_cache_atomic.py`,
  `tests/test_cache_routes.py`; [Repository Cache](arch-repository-cache.md).
- **Residual.** None known beyond the platform’s own.

## Accepted Risks

These are decisions, not gaps:

- **No authentication.** The server is for one reader on one machine (T6).
- **Plugins are trusted code.** A plugin runs JavaScript in the page and an installed
  plugin’s Python in the server, under either profile.
  The reader installs plugins; the served root and the home directory are never a plugin
  source ([Plugins](../../plugins.md)).
- **`--remote` serves the far folder trusted.** It is the reader’s own folder on their
  own machine; pass `--untrusted` to the far side for one that is not.
- **The trusted profile is richer.** A trusted folder’s Markdown and HTML preview run
  more than an untrusted one’s (T1, T2).
- **The browser’s PDF engine reads PDFs on their file pages** (T3).
- **`/_debug/*` is outside the origin proof.** It exists only with
  `METABROWSER_DEBUG=1`.

## Known Gaps

Each is a place the code falls short of the model above.
Each has a bead, and the fix updates this list.

| Gap | Threat | Bead |
| --- | --- | --- |
| The trusted shell can be framed by another site | T5 | `mb-o1yt` |
| The structured Tree view’s YAML and JSONC parsing is not under the bounded loader | T7 | `mb-1sbb` |
| A served folder’s own textconv and external-diff drivers run under `--untrusted` | T8 | `mb-ejc1` |
| `/raw` checks a path and then opens it, so a swapped symlink can escape | T4 | `mb-8wb7` |
| `/raw` types depend on the host’s `mimetypes` database | T2 | `mb-kkvo` |
| No test pins the environment `gh` runs with | T9 | `mb-6cge` |
| The diagram frame runs untrusted layout in the application’s origin | T1 | `mb-jisr` |
| A save-panel download in the app may not be quarantined | T10 | `mb-0frx` |
| The cache has no size bound beyond the free-space reserve | T11 | `mb-w9gj` |

## References

- [SECURITY.md](../../../SECURITY.md): the policy for users and how to report
- [Server and Content: Content Trust Model](arch-server-and-content.md#content-trust-model)
- [Open Modes: Security Requirements](arch-open-modes.md#security-requirements)
- [macOS App: The Trust Boundary](arch-macos-app.md#the-trust-boundary)
- [Plugins: Trust Model and Discovery](../../plugins.md#trust-model-and-discovery)
- [The PDF plan](../specs/active/plan-2026-11-24-pdf-plugin-and-open-in-default-app.md)
- [SUPPLY-CHAIN-SECURITY.md](../../../SUPPLY-CHAIN-SECURITY.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
