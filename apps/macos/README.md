# Metabrowser for macOS

**Status:** Spike. This is step 1 of Option D in the
[macOS app research brief](../../docs/project/research/research-2026-11-08-macos-app-packaging.md):
a hand-written Swift app that uses an existing command-line install of `metab`.

## What It Is

A native macOS app, written with AppKit and `WKWebView`, that finds your CLI install of
`metab`, starts one server per folder you open, and shows each folder in its own window.
It is a thin wrapper.
Everything Metabrowser shows comes from `metab`, the page talks to its server directly
over HTTP and server-sent events, and the page never calls a shell API. The app adds
only what a browser tab cannot give: a Dock icon, folders dropped on it or opened with
Open With, native menus and windows, and server lifetimes it controls.

It is not a distribution.
It installs nothing: no Python, no uv, no Metabrowser.
It has no notarization, updater, DMG, Homebrew cask, URL scheme, or CI job.
It runs on arm64 Macs with macOS 15 or later.
[Gaps to Close](#gaps-to-close) maps what is missing to the brief.

## Build, Test, and Run

You need macOS 15 or later, Xcode 26 (Swift 6.2 or later), and a CLI install:

```shell
uv tool install metabrowser
```

From the repository root (each target delegates to `apps/macos/Makefile`, and each
prints a skip message on systems other than macOS):

```shell
make macos-test                      # unit tests (swift test)
make macos-app                       # build, assemble, and sign build/Metabrowser.app
make macos-run FOLDER="$HOME/notes"  # build the app and open a folder with it
make macos-build                     # debug build only
make macos-clean                     # remove .build and build
```

`make verify` neither needs nor runs Swift, so Linux CI is unchanged.

`scripts/build-app.sh` builds a release binary, strips it, lays out the bundle, stamps
the version, generates the icon from `scripts/generate-icon.swift`, and signs.
It signs ad hoc by default, which runs on this Mac only.
Set `SIGN_IDENTITY="Developer ID Application: Name (TEAMID)"` to sign with the hardened
runtime and a secure timestamp.
`VERSION`, `BUILD`, `ARCHES` (for example `"arm64 x86_64"`), and `ICON=0` are documented
in the script. The script does not notarize.

To run the tests against a real server too:

```shell
cd apps/macos
METABROWSER_SHELL_TEST_METAB=$HOME/.local/bin/metab swift test
```

Where to look while it runs:

- **Server log:** `~/Library/Logs/Metabrowser/<folder>-<hash>.log`, mode 0600. It holds
  the server’s output, with the app’s lifecycle events interleaved: start command, pid,
  announced URL, readiness time, stop, and exit status.
  File > Reveal Server Log opens it.
- **App log:** `log stream --predicate 'subsystem == "io.github.jlevy.metabrowser"'`.
- **Web Inspector:** Safari’s Develop menu, in debug builds or after
  `defaults write io.github.jlevy.metabrowser WebInspectorEnabled -bool true`.
- **Start over:** `defaults delete io.github.jlevy.metabrowser` forgets the saved
  runtime and the recent folders, so the next launch runs discovery again.

## Architecture

| Path | Holds |
| --- | --- |
| `Package.swift` | SwiftPM only: no Xcode project and no package dependencies. Swift 6 language mode with main-actor default isolation. |
| `Sources/ShellCore/Supervision/` | Spawning a server, recognizing it as ready, and stopping it. |
| `Sources/ShellCore/Runtime/` | Finding `metab`, the child environment, short commands, and saved settings. |
| `Sources/ShellCore/{Logs,Folders,Web}/` | Server logs, recent folders, and the navigation policy. |
| `Sources/Metabrowser/` | The AppKit app: lifecycle, menus, folder sessions, windows, and the SwiftUI status and settings views. |
| `Tests/ShellCoreTests/` | Swift Testing tests of everything in `ShellCore`, with fake processes and fake machines, plus the real `posix_spawn` path with `/bin/sh` children. |
| `Resources/Info.plist`, `scripts/` | The bundle’s property list, the bundle script, and the icon generator. |

`ShellCore` holds everything that can be tested without a window; it imports no AppKit
or WebKit. The app target is the platform behavior the brief exempts from the CLI parity
rule: finding a runtime before one exists, windows, menus, the Dock, and file events.

### A Folder’s Server

1. **Open.** File > Open Folder, File > Open Recent, a drop on the Dock icon or on a
   window, Open With, and `open -a Metabrowser.app FOLDER` all arrive at one method.
   The folder’s canonical path keys one session, so one root has one server and one
   window (plus any tabs the page opens).
2. **Spawn.** `ServerSupervisor` runs
   `metab ROOT --no-open --host 127.0.0.1 --port 8411` with `posix_spawn`: in its own
   process group (`POSIX_SPAWN_SETPGROUP`), with only the descriptors it is given
   (`POSIX_SPAWN_CLOEXEC_DEFAULT`), with default signal handling restored, and with the
   folder as its working directory, so `.env` lookup matches `metab .` in Terminal.
   Its stdout and stderr go to the server log and to an in-memory tail.
   Its stdin is a pipe the app holds open, ready to become the parent-death signal.
3. **Ready.** The server prints `Serving ROOT at http://127.0.0.1:PORT/view/` before its
   socket listens, so the supervisor parses that line and then polls the URL for a 2xx,
   within 60 seconds. The line must start with `Serving ` and end with the URL, and a
   folder whose path contains a line break is refused, since its name could forge the
   line; the JSON ready line of host mode removes this class of problem.
   `LaunchGate` lets one server start at a time, because `metab` chooses its port by
   probing and binds later, so two servers starting together could choose the same port.
4. **Show.** The window loads the URL in a `WKWebView` with the persistent default
   website data store, because Metabrowser keeps preferences in host-only cookies.
   A native “Starting” view covers the window until the page commits; its spinner
   appears only after 300 ms.
5. **Fail.** If the server exits, never announces itself, or never answers, the window
   shows the reason, the last lines of output, Retry, Reveal Logs, and Runtime Settings.
   Nothing restarts automatically.
   After Retry, each window returns to the page it showed, on the new port.
6. **Stop.** Closing a folder’s last window stops its server: SIGTERM to the process
   group, up to 5 seconds, then SIGKILL, up to 2 more seconds (a process stuck in
   uninterruptible I/O, such as a hung network mount, ignores even SIGKILL, and quit
   must not wait on it), then SIGKILL to anything left in the group.
   Quitting stops every server, including servers of windows closed moments before,
   before the app exits, also when the quit comes from SIGTERM, SIGINT, or SIGHUP sent
   to the app.

Every child is ended by one tracked termination, whoever asks for it: a stop, a restart,
a newer launch, or a start that gave up.
A stop waits for all of them, and a launch first waits for any left by the launch it
replaced, so overlapping restarts cannot drop a running child.
`ServerFleet` holds the open and still-stopping servers for the app delegate, which is
how its quit ordering is tested.

`ServerLaunch` is the seam for the brief’s host mode.
It owns the arguments, the stdin line, the readiness parser, the readiness URL, and the
authorization a window installs before loading (`WebAuthorization.cookie`).
`CLIServeLaunch` implements it for today’s server; a host-mode launch replaces it
without changing the supervisor or the windows.

### Finding the Runtime

Setup runs on the first launch, and again from Settings > Find Again.
It looks in this order and runs `metab --version` on each candidate that exists:

1. the path saved by a previous setup;
2. `METABROWSER_METAB`;
3. `~/.local/bin/metab`;
4. uv’s tool bin directory (`UV_TOOL_BIN_DIR`, `XDG_BIN_HOME`, `XDG_DATA_HOME/../bin`,
   or `~/.local/bin`, as uv documents);
5. `/opt/homebrew/bin` and `/usr/local/bin`;
6. the `PATH` of your login shell.

The login shell comes last and runs only when the earlier locations miss `metab`, `git`,
or `gh`. It runs your shell startup files in the app’s name, which can take seconds and
can raise privacy prompts you never saw in Terminal.
One install reached two ways is tried once.
Setup saves the runtime and the absolute paths of `git` and `gh`; later launches only
check that the saved `metab` is still executable, so they start no extra process.
If nothing is found, Settings shows the install command and every place it looked.
Settings also chooses another `metab` with an open panel, runs `metab --doctor`, and
reveals the logs folder.

### The Child’s Environment

The server’s environment is built from an allowlist, never inherited.
It keeps `HOME`, `USER`, `LOGNAME`, `TMPDIR`, locale names, `SSH_AUTH_SOCK` (`metab`
runs Git over ssh in batch mode, so ssh remotes need the agent), and the proxy variables
`HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`, and `ALL_PROXY` in either case, and sets:

- `PATH` to the directories of the `git` and `gh` found at setup, then
  `/usr/bin:/bin:/usr/sbin:/sbin`. A Finder launch would otherwise give the server
  Apple’s `git` shim and no `gh`.
- `PYTHONNOUSERSITE=1`, so packages in `~/.local/lib/python*` cannot shadow the
  server’s.
- `PYTHONUNBUFFERED=1`, so the log is current.

Nothing else passes: no `UV_*`, `VIRTUAL_ENV`, `PYTHONHOME`, or `PYTHONPATH` from a
Terminal launch.

### The Window

- **Navigation:** the server’s origin (scheme, host, and port) stays in the window.
  A clicked link to another `http`, `https`, or `mailto` URL opens in the default
  browser; the same URL reached by script, redirect, form, or Back and Forward is
  cancelled, so a page cannot open the browser by itself, and Back to a page of a server
  that restarted on another port does nothing.
  `file://` and other schemes are cancelled.
  `target=_blank`, `window.open`, and Command-click on links to the same server open a
  new tab of the folder’s window.
- **Downloads:** `WKDownload` with a save panel that opens in Downloads.
  Choosing the destination is user intent, so no Downloads privacy prompt appears.
  A confirmed Replace removes the existing file first, since `WKDownload` refuses a
  destination that exists.
- **Browser features:** Back and Forward (Command-\[ and Command-\]), Reload, zoom
  (persisted), Print through `printOperation`, Find through `NSTextFinder` with a find
  bar container, JavaScript `alert`, `confirm`, and `prompt` as sheets, and file inputs.
  If the web content process dies, the window reloads, at most twice in 30 seconds, and
  then shows the status view.

### Pitfalls Found in the Live Run

Two defects only appeared when the built app was quit with SIGTERM, and both orphaned
the server. Each fix is commented at the code that would bring it back.

- **Quit from a dispatch handler deadlocks.** `.terminateLater` spins a nested run loop
  until the servers stop, and that loop cannot drain the main dispatch queue while one
  of the queue’s own blocks is on the stack.
  The signal handler therefore schedules the quit with `CFRunLoopPerformBlock`.
- **Main-actor default isolation traps off the main queue.** A Dispatch handler closure
  written in a main-actor context is inferred main-actor, and Swift 6’s runtime check
  raises SIGTRAP when it runs on another queue.
  Handlers for other queues must be marked `@Sendable`.

## Why It Lives in This Repository

The app lives here, in `apps/macos`, rather than in a repository of its own:

- **The host protocol is a contract between the app and `metab`.** Its next steps (port
  0, a ready line, a stdin token, `/healthz`) change the server and the shell together.
  In one repository each change, its reference host, and the shell that consumes it land
  in one commit, as `docs/development.md` asks of internal contracts.
- **Releases stay coupled.** Each Metabrowser release will produce an app build with its
  own lock for the app-managed runtime.
- **Shells sit side by side.** The drafted
  [VS Code host](../../docs/project/architecture/arch-vscode-extension-host.md) would
  live beside it as `apps/vscode`, sharing the host protocol, docs, and issue tracker.

Nothing here ships to PyPI: `/apps/` is excluded from the sdist in `pyproject.toml`, and
`devtools/check_distribution.py` fails the build if an `apps` path reaches the sdist or
wheel.

A separate repository would make sense if the app gained its own release cadence (shell
updates through Sparkle that do not follow Metabrowser releases), needed signing secrets
that should not reach this repository’s CI, or had to support several Metabrowser
versions through a published host protocol.
Then the CLI install would be an external consumer, and the protocol a versioned
boundary with its own compatibility rules.

## Gaps to Close

Each gap points to the part of the brief that closes it.

| Gap | The spike today | Brief |
| --- | --- | --- |
| **Session token and cookie exchange** | None: like the CLI, the server answers any local process. `WebAuthorization.cookie` is the slot. | Layering item 1; Security Models |
| **Port 0 and a JSON ready line** | Ports walk up from 8411; the `Serving` line is parsed and the URL polled; `LaunchGate` serializes starts. | Layering item 1 |
| **Exit on stdin EOF** | The stdin pipe is held open, but today’s server ignores it, so a crashed or force-quit app orphans its servers until they are stopped by hand; an orderly quit does not. An interim option is a pidfile per server and reaping stale groups at the next launch, which needs a start-time check against pid reuse; it is not implemented. | Layering item 1 |
| **Descendants in other groups** | The group kill reaches only the server’s own process group. Git and `gh` run in their own groups, which the server ends on its graceful path; a server that needs SIGKILL leaves them running. | Layering item 1 (bounded shutdown that ends those groups) |
| **`/healthz`** | Readiness polls the `/view/` entry page. | Layering item 1 |
| **Rootless runtime report** | `metab --version` validates; `--doctor` output is shown as text. | Layering item 2 |
| **Explicit tool paths** | `git` and `gh` are found by their directories on `PATH`. | Layering item 5 |
| **Privacy-safe I/O** | Usage descriptions are declared; a protected folder prompts in the app’s name with no in-app guidance. | Layering item 6; macOS Platform Rules |
| **Settings served by Metabrowser** | A native Settings window. | Layering item 7 |
| **App-managed runtime** | None: a CLI install is required. | Recommendation 5.2; Wrapping uv |
| **Notarization and updates** | Ad hoc or Developer ID signing only: no `notarytool`, DMG, cask, or Sparkle. | Recommendation 6 |
| **WebKit measurement gate** | Not run. Large-content bounds were measured in Chrome; `window.print()` and drag and drop are not yet checked by hand. | Recommendation 4 (`mb-etqi`) |
| **Multi-root and attach** | One server per root; no attaching to an agent’s server, no state files, no `metabrowser://` hand-off from the CLI. | Use Cases Under Exploration; Sharing an Installation |
| **macOS CI** | `swift test` runs locally only. | Next Steps |

## Known Limitations

- Only folders open; a dropped file shows an alert.
- Closing a folder’s last window stops its server, so reopening it starts a new one.
- A restarted server comes back on a new port, and local storage is per origin, as with
  the CLI.
- State-home variables (`XDG_CACHE_HOME`, `METABROWSER_CACHE_DIR`, and the rest) are not
  passed to the server, so the app always uses the default homes.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
