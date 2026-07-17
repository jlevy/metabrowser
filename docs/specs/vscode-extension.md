# VS Code Extension

Status: planned after v0.1.0.

A Metabrowser extension should make the existing application feel native in VS Code and
compatible desktop forks without rewriting its renderers.
The target architecture combines native editor navigation with one embedded Metabrowser
content surface and a supervised server installed through uv.

The complete feature is a packaged, automatically verified extension.
An integrated-browser shortcut, a native tree without embedded content, or a
source-loaded development host is useful during development but is not the finished
integration.

## Goals

- Add a native Metabrowser `TreeView` in its own Activity Bar container.
- Open every selected path in one restored extension-owned `WebviewPanel`.
- Reuse the existing file views, KPress rendering, and plugin runtime inside that panel.
- Start one authenticated Metabrowser server for the selected root in each editor
  window.
- Install an exact compatible server version through uv without requiring users to
  manage Python.
- Refresh the native tree from `/api/events` in the extension host.
- Restore the selected root and path after editor reload without persisting a port or
  session token.
- Test the packaged extension in an isolated real workbench with no routine human
  interaction.

## Non-Goals

- Replacing VS Code’s Explorer, text editor, Activity Bar, or filesystem APIs.
- Rewriting Metabrowser renderers as native editor components.
- Supporting vscode.dev or another browser-only extension host.
- Running one server for every folder in a multi-root workspace.
- Bundling Python, Metabrowser, and an offline wheelhouse in the first release.
- Loading arbitrary workspace plugins before Workspace Trust is granted.

## User Interface

The Primary Sidebar uses a native `TreeDataProvider` backed by
`/api/tree?path=<path>&depth=1`. Native items preserve keyboard navigation,
accessibility, menus, collapse state, and editor theming.
The extension host consumes `/api/events` and invalidates affected tree nodes; hidden
webview scripts are not responsible for navigation freshness.

One `WebviewPanel` owns the content experience.
It embeds a content-only Metabrowser URL in a sandboxed iframe, restores only the
selected root and path, and resolves the current server URL again after restart.
The wrapper applies a nonce-based content security policy and restricts `frame-src` to
the resolved Metabrowser origin.

The built-in integrated browser remains an explicit Open Full Metabrowser command and a
debugging surface. The extension must not depend on an untyped workbench command as its
primary host.

Metabrowser can occupy the left navigation while its Activity Bar item is selected.
It cannot remove Explorer, redefine built-in reveal commands, or become a transparent
replacement for every file operation.

## Server Host Contract

The current `/api/tree`, `/api/events`, and `/api/capabilities` routes provide the main
data plane. Embedding requires four host-neutral additions:

1. **Machine readiness.** Accept `--port 0`, emit one versioned JSON ready event only
   after HTTP succeeds, and expose a cheap `/healthz` route.
2. **Session authentication.** Generate a random token per launch.
   Extension-host API requests may send authorization directly; iframe navigation uses a
   one-time URL that sets an HttpOnly, SameSite cookie and redirects to a clean URL.
3. **Content-only mode.** `?embed=view` hides duplicate shell navigation while retaining
   renderer tabs, plugin assets, print behavior, and error states.
4. **Capability versioning.** Report the server version and embedding protocol so an
   incompatible extension fails with an actionable message.

The ready event should resemble:

```json
{"event":"ready","host":"127.0.0.1","port":51243,"pid":12345,"protocol":1}
```

The extension still health-checks after reading the event.
A child-process message does not prove that routing, middleware, and plugin startup are
ready.

Standalone behavior remains loopback-only and does not require authentication unless a
host integration enables it.

## uv and Plugin Modes

The default server is an exact Metabrowser release in an isolated uv tool environment.
uv may supply a compatible Python when the host has none.
The extension release owns the server-version pin so rollback and protocol testing are
meaningful.

Resolution has three branches:

1. use an explicit `metabrowser.serverCommand` override;
2. use a compatible uv executable on the extension host;
3. download a pinned uv release to extension global storage and verify its digest before
   execution.

The extension must not execute uv’s shell installer or silently select arbitrary virtual
environments. Run managed uv from extension-owned storage so workspace `pyproject.toml`,
`uv.toml`, and Python-version files cannot influence bootstrap.

Managed mode contains built-in plugins only.
Workspace or entry-point plugin development uses the explicit command override from a
reviewed project environment.
A future exact-package setting may translate to uv `--with` arguments, but unbounded
workspace package input is not a safe default.

## Lifecycle and Trust

One process serves one selected root per editor window.
A single-folder workspace selects itself.
A multi-root workspace remembers one selected folder and exposes Switch Root; changing
the root restarts the child and restores the nearest valid path.

The extension:

- activates lazily when its view or command is used;
- starts the child with an argument array and no shell;
- binds it to `127.0.0.1` on an operating-system-selected port;
- reports Starting, Ready, Restarting, and Error states;
- logs stdout and stderr without exposing tokens;
- restarts after a crash only through a bounded, visible policy;
- terminates the complete child process tree on deactivation and editor shutdown.

The extension runs as a workspace extension and disables untrusted and virtual
workspaces. Workspace Trust gates command overrides, plugin directories, and all server
startup. Loopback binding is not sufficient by itself; session authentication, safe
paths, strict methods, and origin checks remain required.

For Remote SSH, containers, WSL, and Codespaces, the extension and server run where the
files live. The native tree calls loopback from the extension host.
The panel resolves a client-reachable URL through `vscode.env.asExternalUri` and must
not cache it across reloads or tunnel changes.
Remote support is a separate tested compatibility claim, not an assumption.

## Repository and Packaging Shape

Keep the extension in this repository under `editors/vscode/` until ownership or release
cadence justifies a split.
The extension may add TypeScript source and npm development dependencies, but it uses
the repository’s exact `package-lock.json`, supply-chain policy, and Make targets.
Production code should prefer VS Code and Node APIs over runtime npm dependencies.

The Python wheel and VSIX are separate artifacts with an explicit compatibility matrix.
The VSIX may later become platform-specific if bundling uv provides enough first-use or
offline value to justify the release matrix.

## Verification Strategy

Use three extension layers in addition to the existing Python, browser-contract, and
distribution suites:

1. **Unit and server-contract tests** cover command resolution, ready-event parsing,
   lifecycle transitions, tree mapping, health, authentication, embed mode, and process
   cleanup.
2. **Extension-host tests** run the real editor API against a fixture workspace and
   cover activation, commands, server supervision, events, reload state, and untrusted
   workspaces.
3. **Packaged workbench tests** install the built VSIX into isolated storage, drive the
   Activity Bar, tree, panel, and iframe, and retain logs and screenshots on failure.

The exact testing packages must be reviewed under the repository’s dependency policy
when implementation starts.
VS Code’s extension test runner and a maintained workbench driver are the expected
starting points; a second overlapping UI driver should not be added without evidence.

The extension work extends `make verify` so the required gate builds the wheel and VSIX,
installs the local artifacts, runs the acceptance journey, verifies child cleanup, and
writes machine-readable evidence.
Dynamic ports, tokens, and temporary paths stay out of stable snapshots and committed
artifacts.

## Delivery Plan

1. Add the machine-ready, health, authentication, embed, and capability-version server
   contracts with tests.
2. Add the extension scaffold, managed-uv resolver, and one-server lifecycle state
   machine.
3. Add the native tree and extension-host event consumer.
4. Add the restored, sandboxed content panel and one-time cookie bootstrap.
5. Add root switching, reload restoration, crash recovery, and complete cross-platform
   process cleanup.
6. Package a VSIX and build the isolated extension-host and workbench acceptance lanes.
7. Validate local macOS, Windows, and Linux before making broader compatibility claims.
8. Add separately automated Remote Development and editor-fork lanes before documenting
   them as supported.

## Acceptance

An installed VSIX in a clean profile can, without human input:

1. select the Metabrowser Activity Bar item;
2. acquire or select verified uv, install the locally built wheel, and start it on port
   zero;
3. authenticate and populate the fixture tree;
4. open representative Markdown, structured, image, and log files in the same panel;
5. observe file creation and modification through `/api/events`;
6. reload the editor and restore root and path with a new port and token;
7. recover visibly from a crashed child after Restart Server;
8. open the complete standalone UI as a diagnostic escape hatch;
9. exit with no uv, Python, server, or browser-driver child processes left behind.

## References

- [Architecture](../architecture.md)
- [Plugin authoring](../plugins.md)
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
