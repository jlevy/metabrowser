# Architecture: VS Code Extension Host

**Author:** Metabrowser maintainers

**Status:** Draft

## Overview

The VS Code extension makes Metabrowser navigation feel native while reusing the
existing web renderers and plugin runtime.
It combines a native editor tree, one embedded Metabrowser content surface, and a
supervised authenticated server installed through uv.

The completed integration is a packaged, automatically verified extension.
An integrated-browser shortcut, a native tree without embedded content, or a
source-loaded development host is useful during development but does not satisfy the
architecture.

## Goals and Non-Goals

### Goals

- Add a native Metabrowser `TreeView` in its own Activity Bar container
- Open every selected path in one restored extension-owned `WebviewPanel`
- Reuse existing file views, KPress rendering, and the plugin runtime inside the panel
- Start one authenticated Metabrowser server for the selected root in each editor window
- Install an exact compatible server version through uv without requiring user-managed
  Python
- Refresh the native tree from `/api/events` in the extension host
- Restore the selected root and path after editor reload without persisting a port or
  session token
- Test the packaged extension in an isolated real workbench without routine human
  interaction

### Non-Goals

- Replacing VS Code’s Explorer, text editor, Activity Bar, or filesystem APIs
- Rewriting Metabrowser renderers as native editor components
- Supporting vscode.dev or another browser-only extension host
- Running one server for every folder in a multi-root workspace
- Bundling Python, Metabrowser, and an offline wheelhouse in the first release
- Loading arbitrary workspace plugins before Workspace Trust is granted

## System Context

The extension host runs where the selected files live.
It supervises a loopback server, maps the tree API into native editor navigation, and
resolves a client-reachable URL for one embedded content panel.

```text
VS Code TreeView <-> extension host <-> authenticated Metabrowser server <-> files
                           |                         |
                           v                         v
                    WebviewPanel iframe       inventory and events
                           |
                           v
                   existing web renderers
```

In Remote SSH, containers, WSL, and Codespaces, the extension and server execute on the
remote extension host.
The panel uses the editor’s URI resolution rather than assuming that remote loopback is
reachable from the client.

## Design

### Components

#### Native Tree

**Responsibility:** Present lazy Metabrowser navigation through VS Code’s accessible,
keyboard-oriented tree UI.

**Interfaces:** A `TreeDataProvider` backed by `/api/tree?path=<path>&depth=1` and
invalidated by `/api/events`.

#### Content Panel

**Responsibility:** Own one restored `WebviewPanel` containing a sandboxed, content-only
Metabrowser surface.

**Interfaces:** A nonce-protected wrapper and an iframe restricted to the current
resolved Metabrowser origin.

#### Server Supervisor

**Responsibility:** Start, health-check, authenticate, restart, and terminate one server
for the selected root.

**Interfaces:** A machine-readable ready event, `/healthz`, versioned capabilities, and
the existing tree, event, and rendering routes.

#### uv Resolver

**Responsibility:** Find or acquire verified uv and install the exact server release in
an isolated tool environment.

**Interfaces:** An explicit server-command override, a compatible host uv, or a pinned
verified uv executable in extension global storage.

#### Workspace State

**Responsibility:** Persist the selected root and path while treating ports, tokens, and
resolved remote URLs as session-only values.

**Interfaces:** VS Code workspace storage and root-switching commands.

### Data Flow

1. The user activates the Metabrowser view and selects or confirms one workspace root.
2. The resolver selects an explicit command or prepares exact uv-managed Metabrowser.
3. The supervisor starts the child without a shell on `127.0.0.1` and lets the operating
   system select the port.
4. The child emits a versioned ready event; the supervisor then verifies `/healthz` and
   capabilities.
5. The native tree loads lazy children and refreshes affected nodes from `/api/events`.
6. Selecting a file resolves the current client-reachable URL and navigates the single
   content panel through a one-time authentication bootstrap.
7. Reload restores only root and path, then creates a new process, port, token, and
   resolved URL.

### Data Model

Persisted state contains the workspace-folder identity, served-root selection, and
served-root-relative selected path.
Runtime state contains the lifecycle status, child process identity, current origin,
authentication token, capability version, and event connection.

The server ready event has a versioned machine shape such as:

```json
{"event":"ready","host":"127.0.0.1","port":51243,"pid":12345,"protocol":1}
```

Reading the event does not establish readiness by itself.
The supervisor still performs an HTTP health check after routing, middleware, and plugin
startup complete.

### Interfaces

#### External APIs

| Interface | Method | Description |
| --- | --- | --- |
| `/api/tree` | GET | Populate lazy native tree nodes |
| `/api/events` | GET | Refresh navigation and content state |
| `/api/capabilities` | GET | Negotiate server and embedding protocol versions |
| `/healthz` | GET | Confirm machine readiness after the ready event |
| One-time authentication route, path to be finalized | GET | Set an HttpOnly, SameSite session cookie and redirect to a clean URL |
| `?embed=view` | GET | Hide duplicate shell navigation while retaining file views and error states |

The server accepts `--port 0` and emits one JSON ready event only after HTTP service is
available. Standalone loopback behavior remains unchanged unless a host integration
enables session authentication.

#### Internal Interfaces

The extension exposes commands for opening the full Metabrowser UI, switching roots,
restarting the server, and opening the selected file.
It reports Starting, Ready, Restarting, and Error states and resolves remote panel URLs
through `vscode.env.asExternalUri` without caching them across reloads or tunnel
changes.

## Trade-Offs and Alternatives

### Decision 1: Native Navigation With Reused Web Content

**Chosen approach:** Use a native `TreeView` and one embedded Metabrowser content panel.

**Alternatives considered:**

- Embed the complete application, which duplicates navigation and weakens native
  accessibility and commands
- Rewrite every renderer as a native editor component, which duplicates the plugin
  runtime and creates two rendering products
- Use only VS Code’s integrated browser, which does not provide a typed extension-owned
  navigation contract

**Rationale:** The split keeps navigation native while preserving Metabrowser’s existing
renderer investment.

### Decision 2: One Server per Editor Window

**Chosen approach:** Serve one selected root and expose an explicit Switch Root command
for multi-root workspaces.

**Alternatives considered:**

- Start one process per workspace folder, which multiplies ports, tokens, logs, failure
  states, and resource use
- Share a global process across windows, which complicates ownership and cleanup

**Rationale:** One owner and one root produce a bounded lifecycle that can be restored
and terminated reliably.

### Decision 3: Exact uv-Managed Server

**Chosen approach:** Pin the compatible server release and manage it through a verified
uv executable, with an explicit command override for plugin development.

**Alternatives considered:**

- Select an arbitrary Python environment, which makes protocol compatibility and support
  unpredictable
- Execute uv’s shell installer, which bypasses the repository’s supply-chain controls
- Bundle Python and an offline wheelhouse initially, which creates a larger platform
  artifact matrix before the integration is proven

**Rationale:** Exact tool installation provides repeatable compatibility while allowing
uv to supply Python when the host has none.

### Decision 4: Extension-Host Event Ownership

**Chosen approach:** Keep `/api/events` in the extension host rather than a hidden
webview script.

**Alternatives considered:**

- Retain navigation state in the webview, whose scripts may be suspended while hidden
- Poll the complete tree, which increases server work and loses scoped invalidation

**Rationale:** Navigation stays current independently of panel visibility and uses the
editor-owned lifecycle.

## Security Considerations

- Workspace Trust gates command overrides, plugin directories, and server startup
- Untrusted and virtual workspaces remain disabled
- The child starts with an argument array and no shell and binds only to `127.0.0.1`
- Every launch uses a new random token; logs and persisted state exclude tokens
- Iframe authentication uses a one-time URL, an HttpOnly SameSite cookie, and a redirect
  to a clean URL
- The wrapper applies a nonce-based content security policy and restricts `frame-src` to
  the resolved Metabrowser origin
- Managed uv runs from extension-owned storage so workspace Python and uv configuration
  cannot alter bootstrap
- Downloaded uv releases require an exact version and verified digest
- Loopback binding complements rather than replaces safe paths, strict methods, origin
  checks, and session authentication

## Operational Concerns

### Monitoring

The extension exposes lifecycle state, bounded restart attempts, child exit detail,
health failures, event reconnects, and protocol mismatches through an output channel and
user-visible status.

### Logging

Stdout and stderr remain available for diagnosis, with tokens, one-time URLs, and file
contents redacted. Packaged tests retain logs and screenshots only on failure.

### Deployment

Keep the extension under `editors/vscode/` until ownership or release cadence justifies
a split. The Python wheel and VSIX remain separate artifacts with an explicit
compatibility matrix.
The extension uses the repository’s `package-lock.json`, supply chain policy, and Make
targets.

Managed mode includes built-in plugins only.
Workspace or entry-point plugin development uses an explicit server-command override
from a reviewed project environment.

### Scaling

One process serves one root per window.
Lazy tree requests avoid materializing the full inventory in the extension, and the
event stream invalidates affected nodes.
Restart policy and process-tree cleanup remain bounded.

### Verification

The extension adds three layers to the existing Python, browser-contract, and
distribution suites:

1. Unit and server-contract tests cover command resolution, ready-event parsing,
   lifecycle transitions, tree mapping, health, authentication, embed mode, and process
   cleanup.
2. Extension-host tests run the real editor API against a fixture workspace and cover
   activation, commands, server supervision, events, reload state, and Workspace Trust.
3. Packaged workbench tests install the built VSIX into isolated storage, drive the
   Activity Bar, tree, panel, and iframe, and retain logs and screenshots on failure.

The repository’s required verification gate builds the wheel and VSIX, installs the
local artifacts, runs the acceptance journey, and verifies child-process cleanup.
Dynamic ports, tokens, and temporary paths remain outside stable snapshots and committed
artifacts.

## Open Questions

- What are the final authentication-route and embedding-protocol versions?
- Which pinned uv acquisition mechanism satisfies macOS, Windows, and Linux packaging?
- When does offline or first-use evidence justify platform-specific VSIX artifacts?
- Which workbench driver provides maintainable packaged-extension coverage under the
  dependency policy?
- Which remote development and compatible editor forks merit separate support claims?

## References

- [Core architecture](../../architecture.md)
- [Plugin authoring](../../plugins.md)
- [Supply-chain security](../../../SUPPLY-CHAIN-SECURITY.md)
- [uv tools](https://docs.astral.sh/uv/concepts/tools/)
- [uv-managed Python](https://docs.astral.sh/uv/guides/install-python/)
- [VS Code Tree View API](https://code.visualstudio.com/api/extension-guides/tree-view)
- [VS Code Webview API](https://code.visualstudio.com/api/extension-guides/webview)
- [VS Code Workspace Trust](https://code.visualstudio.com/api/extension-guides/workspace-trust)
- [VS Code remote extension support](https://code.visualstudio.com/api/advanced-topics/remote-extensions)
- [VS Code extension testing](https://code.visualstudio.com/api/working-with-extensions/testing-extension)
- [VS Code integrated browser](https://code.visualstudio.com/docs/debugtest/integrated-browser)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
