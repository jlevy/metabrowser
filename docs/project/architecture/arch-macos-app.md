# Native macOS App Architecture

**Status:** Built: an alpha AppKit and `WKWebView` shell in `apps/macos/`, built from
source. `.github/workflows/macos-app.yml` builds and tests it on each push and pull
request that its path filter matches, a change to the app among them; its release
pipeline has run only with an ad hoc signature.
Planned: host mode, the agent front door, a signed and notarized release, and updates,
in the [native macOS app plan](../specs/active/plan-2026-11-10-native-macos-app.md).
The WebKit measurement gate failed on 2026-11-11 (`mb-gvtw`), and its rerun is open
(`mb-76nv`).

The app finds a command-line install of `metab`, starts one server per folder the user
opens, and shows each folder in a native window or tab.
Everything a window shows comes from that server: the page talks to it over HTTP and
server-sent events and never calls into the app, so any shell can replace another.
The app adds what a browser tab cannot: a Dock icon, folders opened with Open With or
dropped on it, native menus, windows, and tabs, a session that comes back at the next
launch, and server lifetimes it controls.
[Using the app](../../macos-app.md) is a user guide, and building, testing, and
releasing it is [the app’s README](../../../apps/macos/README.md).

## Modules

Paths are under `apps/macos/`.

| Path | Holds |
| --- | --- |
| `Sources/ShellCore/Supervision/` | Spawning a server, recognizing it as ready, checking its health, and stopping it |
| `Sources/ShellCore/Runtime/` | Finding `metab`, settling which one runs, and the child environment |
| `Sources/ShellCore/Setup/` | The version floor, the first-run steps, file watches, the restart offer after an upgrade, and the launch notice |
| `Sources/ShellCore/Logs/`, `Folders/`, `Web/` | Server logs; folder identity, titles, files opened inside folders, tab placement, and the saved session; the navigation policy, web view configuration, tab discards, reloads, and downloads |
| `Sources/ShellCore/App/` | Which build is running (`AppIdentity`), and the title-bar mark |
| `Sources/ShellViews/` | `DropAwareWebView` and `WebContainerView`, a library of their own so that the WebKit gate’s driver builds the same views |
| `Sources/Metabrowser/` | The AppKit app: lifecycle, menus, folder sessions, windows, and the SwiftUI status and settings views |
| `webkit-gate/` | The WebKit measurement gate and its driver, which no product ships |

`ShellCore` holds every decision that can be tested without a window, and imports no
AppKit; it imports WebKit only for the web view’s configuration and downloads, which its
tests run in a windowless `WKWebView`. The app target connects those decisions to AppKit
and WebKit. It is the platform behavior the
[packaging brief](../research/research-2026-11-08-macos-app-packaging.md) exempts from
the [parity rule](../../../AGENTS.md#cli-and-functional-ui-parity): finding a runtime
before one exists, windows, menus, the Dock, and file events.

## A Server per Folder

1. **Open.** File > Open, Open Recent, the Dock menu, a drop, Open With, `open -a`, and
   the restore all reach one `FolderSession` per folder, keyed by its canonical path, so
   a root has one server however many windows and tabs show it.
2. **Spawn.** `ServerSupervisor` runs `CLIServeLaunch`’s command,
   `metab ROOT --no-open --exit-on-eof --host 127.0.0.1 --port N`, from
   `CLIServeLaunch.defaultBasePort`. `SpawnedProcess` starts it with `posix_spawn` in
   its own process group, with only the descriptors it names, default signal handling,
   and the folder as its working directory, so `.env` lookup matches `metab .` in
   Terminal. Its stderr is the server log itself, so an app that stalls cannot block it
   on a full pipe; its stdout is a pipe the app reads for the announcement and appends
   to the log; and its stdin is a pipe the app holds open.
3. **Ready.** The server prints `Serving ROOT at URL` before its socket listens, so the
   supervisor parses that line (`CLIServeLaunch.parseServingLine`) and polls the URL for
   a 2xx (`HTTPReadiness`) within `SupervisorPolicy.startupTimeout`. A root whose path
   holds a line break is refused, since its name could forge the line.
   `LaunchGate` lets one server start at a time, because `metab` picks its port by
   probing and binds it later.
4. **Show.** The window’s `WKWebView` uses the persistent default data store
   (`WebConfiguration.make`), since Metabrowser keeps preferences in host-only cookies.
   A status view covers it until the page commits, and only the navigation the window
   submitted last can reveal the page (`PageReveal`), so a late commit cannot hide a
   server’s failure.
5. **Check.** A window that joins a running server first asks for the entry page within
   `SupervisorPolicy.healthDeadline`, since a hung server keeps its pid; one that does
   not answer is stopped, and fails.
6. **Fail.** Every window of the folder shows the reason, the last lines of output, and
   Retry. Nothing restarts by itself; after Retry, each window returns to its page on the
   new port.
7. **Stop.** Closing a folder’s last window stops its server: SIGTERM to the process
   group, `SupervisorPolicy.shutdownGrace`, SIGKILL, `killWait`, then SIGKILL to
   anything left in the group.
   The leader is reaped only after that, so its pid, which is the group’s id, cannot
   pass to another process while signals are still sent.

Every child is ended by one tracked termination (`ServerSupervisor.retire`), whoever
asks. Each launch and stop advances a generation, so work for an older one stops, and a
folder whose last window closed is shut down for good, so closing it during a restart
leaves nothing running.
`ServerFleet` holds the open and still-stopping servers, and quitting waits for all of
them, also on SIGTERM, SIGINT, or SIGHUP (`AppDelegate.installTerminationSignals`).

`ServerLaunch` is the seam for host mode: it owns the arguments, the stdin line, the
readiness parser and URL, and what a window installs before loading
(`WebAuthorization`), so a host-mode launch replaces `CLIServeLaunch` without changing
the supervisor or the windows.

Each folder’s server writes `<folder>-<hash>.log` in `AppIdentity.logsDirectory`, which
both variants share, with the app’s lifecycle events between its lines (`ServerLog`). A
launch claims its log before it spawns (`FolderLog`, `ServerLogLease`), so a second
running copy of the app, or an earlier session still stopping, writes a log of its own.

### After a Crash

A crashed or force-quit app cannot stop its servers, so each server ends with the app.
The app starts it with `--exit-on-eof` and holds its stdin pipe, the kernel closes that
pipe however the app ends, and the server reads EOF and stops itself
(`src/metabrowser/cli/stdin_lifeline.py`); `LiveMetabTests` checks this against a real
server.
Nothing is recorded on disk to signal later, because between a check and `kill` a
pid can pass to another process.
Not covered: a server so wedged that its stdin watcher thread cannot run, which an
orderly quit still ends with SIGKILL, and descendants in other process groups.

## Choosing a metab

`RuntimeDiscovery.discover` runs on the first launch and from Settings > Find Again.
It tries, in order, the path a previous setup saved, `METABROWSER_METAB`,
`~/.local/bin/metab`, uv’s tool bin directory, the Homebrew prefixes, and last the login
shell’s `PATH`, which runs only when the earlier places miss `metab`, `git`, or `gh`,
because it runs the user’s shell startup files in the app’s name.
Setup saves the runtime with the paths of `git` and `gh` (`RuntimeSettings`), so a later
launch starts no process to find them.

Checking a candidate executes it, so the app runs a `metab` it found by itself only if
no other account can change it (`ExecutableTrust`): every directory and link from `/`,
and the file, belong to this user or root, none is writable by its group or every
account, and no access control entry grants a change.
A standard Homebrew prefix is group-writable, so its `metab` is refused.
The rule holds again just before each child spawns
(`RuntimeOperations.launchableSetup`). A file chosen with Choose metab… runs as chosen.

Every start asks for the accepted runtime twice (`FolderServer`): before it stops
anything, and just before the child spawns (`ServerSupervisor.mayLaunch`). While none is
accepted, a start spawns nothing, its windows say so, and it goes ahead once one is.
When searches, rechecks, and choices overlap, the one started last wins
(`RuntimeSelection`, `RuntimeOperations`).

The server’s environment is built from an allowlist, never inherited
(`ChildEnvironment`). `PATH` is the directories of the `git` and `gh` found at setup,
then the system’s, since a Finder launch would otherwise give the server Apple’s `git`
shim and no `gh`, and nothing from a Terminal launch’s `UV_*`, `VIRTUAL_ENV`, or
`PYTHONPATH` passes.

### The Version Floor

`MetabRequirement.minimumRelease` in `Sources/ShellCore/Setup/MetabVersion.swift` is the
oldest `metab` the app runs: the first release with `GET /api/identity` and
`--exit-on-eof`. A development build of that release counts as it, or no checkout would
run, so the number alone does not prove the flag, and `RuntimeDiscovery.validate` runs
`metab --exit-on-eof --version`. A printed version decides by its number; exit status 2
naming the flag means a build that predates it, which is too old whatever its number;
anything else rejects the `metab` with the probe’s last line.
Below the floor, discovery tries the next place.
`MetabRequirement.upgradeCommand` asks uv for a floor rather than a pin, because uv
keeps the requirement in the tool’s receipt.

The app notices an upgrade by the executable’s fingerprint (`FileFingerprint`: device,
inode, size, modification time, and mode), compared every `SetupWatch.interval` and when
the app becomes active.
A change counts once two looks agree (`FileWatch`), and then nothing starts from the old
runtime until a check validates one.
If open folders run servers that the same `metab` started at another version, an alert
offers to restart them (`RuntimeUpgrade`). An upgrade run in Terminal can still reach
running servers’ environment before the app notices.

### First Run

When a search finds no usable `metab`, Settings shows only the missing steps, each a
command to copy (`SetupGuide`):

| Found | Steps shown |
| --- | --- |
| No uv | uv’s installer, then the `metab` step in a new Terminal window |
| uv, no `metab` | `RuntimeDiscovery.installCommand` |
| A `metab` in uv’s tool directory that does not run | A reinstall |
| A `metab` below the floor, or built before the flag | `MetabRequirement.upgradeCommand` |

Until the floor is on PyPI (`MetabRequirement.isReleased`), every case ends instead in
`make install` at the source checkout the app was built from, then Choose metab…. The
app asks a uv that passes `ExecutableTrust` where `metab` will appear
(`uv tool dir --bin`), watches there and every place discovery looks, and when `metab`
appears searches again and opens the folders that were waiting.
It never runs an installer itself.

A copy opened from its disk image, or translocated by Gatekeeper, cannot be replaced in
place. macOS has no API for either, so `LaunchLocation` reads the bundle’s path and
volume, as Sparkle does, and the app shows a notice that says to move it to
Applications.

## Windows

- **Title.** The folder’s short name, from `GET /api/identity` once the server is ready
  and from the path until then (`FolderIdentity.localFolder`). `window.title` is the
  short name too, or the full name while two open folders share a short name
  (`WindowTitle.windowTitles`). The page’s own `<title>` is for a browser’s tab.
- **Size.** `NewWindowFrame` sizes a new window as a share of its screen’s visible frame
  and cascades the next one from the window placed last.
- **Navigation.** `NavigationPolicy` keeps the server’s origin in the window.
  A clicked link to another `http`, `https`, or `mailto` URL opens in the default
  browser; the same URL reached by script, redirect, or history is cancelled, and so are
  `file://` and other schemes.
- **Downloads.** `WKDownload` with a save panel.
  A confirmed Replace downloads to a staging file on the same volume and renames it over
  the original only when it finishes (`StagedDownload`).
- **Crashes.** If the web content process dies, the window reloads within
  `RecoveryBudget.webContent`, and then shows the status view.
- **Reload.** Command-R reloads in every state a folder window can be in (`PageReload`,
  `PageMenu`): the page; its page again once the server answers a health check; or the
  server, as Retry does.
  A sheet the page opened is cancelled first (`PageSheets`).

### Tabs, Files, and Recents

- **Tabs.** Every folder window shares one tabbing identifier, so Merge All Windows and
  tab dragging combine any folders.
  `FolderPlacement` puts a new folder in a tab, a window, or as System Settings prefers.
- **Background tabs.** Each window’s shown tab keeps its page, and so do the most
  recently shown background tabs up to
  [`TabDiscardPolicy`](../../../apps/macos/Sources/ShellCore/Web/TabDiscardPolicy.swift)’s
  limit, whose comment holds its measurement.
  Every other background tab gives up its web view, which ends its WebContent process,
  and reloads from the running server when shown, keeping only its address.
- **Files.** A file opens in the most specific open folder that contains it, or else in
  its own folder, as `metab FILE` does (`OpenTarget`), at the view route `metab` spells
  (`PageAddress.view`). A page requested while the server is not ready loads once it is
  (`NextPage`).
- **Recents.** Opening a folder registers it with `NSDocumentController`, and File >
  Open Recent and the Dock menu list what macOS keeps; the app keeps no list of its own.

### Session Restore

`SessionStore` saves the folder windows, front first, with each window’s tabs, shown
tab, and frame and each tab’s folder and page, to `session.json` in
`AppIdentity.supportDirectory`, `FolderWindows.saveDelay` after a change and at quit
before the servers stop.
Each save renames a private temporary file over the old one, so a launch after a crash
finds a whole session, and two copies saving at once leave the last one’s.

A launch reads the file once, as a regular file of at most `SessionStore.byteLimit`, and
rebuilds at most
[`RestoreBudget.standard`](../../../apps/macos/Sources/ShellCore/Folders/SavedSession.swift),
whose comment holds its measurement.
Only each window’s shown tab loads its page.
Servers start one at a time, each after the one before is ready or has failed: the front
tab’s first, then the tabs the other windows show, then the rest (`RestoreQueue`,
`RestoreRun`). A tab selected meanwhile starts next.

The file may have been edited, and a folder on a path replaced or relinked, so every
root is admitted again before anything starts (`RootAdmission`). Only a root whose
identity is certain warms in the background: a walk from `/` opens each component with
`O_NOFOLLOW`, enters no mount but the system’s and the Data volume’s, and never opens a
protected location (`ProtectedLocations`); the folder it reaches must be on the home
folder’s volume, and the kernel’s name for it is the root’s identity.
Anything less certain waits for its tab under its saved spelling, and selecting the tab
resolves the path then (`RootActivation`), moving its tabs to the folder it now leads
to. A folder in a protected location starts only when one of its tabs is selected, so a
launch raises no privacy prompt for a folder nobody is looking at.
A background root is admitted again at its turn and just before its server spawns; a
process that changes the path after that check can still win, and macOS enforces its
privacy grants regardless.

## The Title-Bar Accessory

AppKit draws a system title in one font and color, so the window hides it and draws its
own in a leading title-bar accessory (`TitleAccessoryController`), and the app icon’s
mark in a trailing one (`TitleBarMarkController`).

- **Placement.** On macOS 26 a leading accessory sits where the system title sits, after
  the window buttons, in the same font and title-bar height; `TitleAccessory.swift`
  holds the measured insets.
  A centered toolbar item would make the title bar taller and center the title, which
  macOS 26 puts at the leading edge.
- **No proxy icon.** AppKit drops the proxy icon when a leading accessory is present, so
  Command-click, right-click, or VoiceOver’s Show Menu on a local folder’s title opens
  its path menu, from `representedURL`.
- **The mark.** The partial M and the B, drawn as paths from the icon masters’ glyph
  group, which `AppIcon/make-glyphs.swift` copies into `AppIconMarkGeometry.swift`; a
  test checks the copy against both masters.
  `TitleBarMarkLayout` places it, and `AppIconMark.titleBarFills` gives the light title
  bar deeper tints that meet WCAG contrast for graphics; both comments hold their
  measurements.
- **A link.** A click opens `ProjectLinks.repository` in the default browser, and a
  press that moves `TitleBarMarkInteraction.dragDistance` drags the window instead.
  `TitleBarMarkInteraction` decides each pointer event and is tested event by event.
- **System behavior.** The title dims when its window is not main in the active app,
  AppKit dims the mark with it, and both follow light and dark mode.

## WebKit Differences

The page is the one any browser opens, and the app handles what WebKit does differently:

- **`window.print()`** reaches only private `WKUIDelegate` methods, so a user script
  replaces it in the main frame with a message to the app (`PagePrintRequests`), which
  prints only for a document whose security origin is the server’s own.
  It checks the origin, not the URL, because a `/raw` response’s CSP sandbox gives it an
  opaque origin.
- **A dropped file** would make WebKit navigate to its `file://` URL, so
  `DropAwareWebView` takes file and folder drops before WebKit sees them and hands them
  to the app (`FileDrop`).
- **`javaScriptCanOpenWindowsAutomatically`** defaults to on in macOS, so
  `WebConfiguration.restrict` turns it off and a previewed HTML file cannot open tabs by
  itself.
- **Printing** runs modally for the window, which `BrowserWindowController.printPage`
  explains.

### Measured in WebKit

The [packaging brief](../research/research-2026-11-08-macos-app-packaging.md) keeps the
`WKWebView` shell only if WebKit holds the large-content bounds that
[rendering large content](../../large-content-rendering.md) sets in Chrome, within 1.3
times Chrome in every back-to-back pair on one machine.
`make macos-webkit-gate` runs `apps/macos/webkit-gate/run.mjs`, whose header lists its
cases: it serves both engines the same generated corpora and committed diff benchmark
pages from one `metab`, runs the in-page `probe.js` in the app’s own web view class and
in Chrome over the DevTools protocol at the same viewport and device pixel ratio, each
sample a fresh browser with an empty cache, and runs a warm-up pair and then five pairs
per case, alternating which engine goes first.
A metric passes when every pair does; a pair under 5 ms in both is reported, not judged,
since WebKit rounds `performance.now()` to 1 ms (`webkit-gate/summary.mjs`).

The run of 2026-11-11 was on an Apple M1 Pro MacBook Pro with 32 GB, macOS 26.5.2,
WebKit 21624.2.5.11.8 (Safari 26.5.2), Chrome 152.0.7977.83, `metab` 0.12.1.dev214 from
`8b0603f7`, and the harness at `1c028e84`, with a load average of 9 to 15, Low Power
Mode on, and the screen locked.
Times are medians of five pairs; a ratio is WebKit’s value over Chrome’s in one pair.

| Bound | Case and metric | Chrome | WebKit | Pair ratios | Verdict |
| --- | --- | ---: | ---: | --- | --- |
| `TEXT_PREVIEW_CHUNK_BYTES` | Source, 16 MiB file: open, response end to laid out | 337 ms | 564 ms | 1.58–1.72 | **fail** |
|  | Open, navigation to next frame | 952 ms | 1,362 ms | 1.31–1.45 | **fail** |
| `TEXT_PREVIEW_MAX_CHUNK_BYTES` | Load more to 4 MiB, response end to laid out | 419 ms | 2,383 ms | 5.63–5.83 | **fail** |
|  | Load more to 8 MiB | 803 ms | 4,004 ms | 4.84–5.06 | **fail** |
|  | Load more to 16 MiB (an 8 MiB click) | 1,664 ms | 7,848 ms | 4.50–4.88 | **fail** |
|  | The same click, to next frame | 2,662 ms | 8,256 ms | 3.05–3.20 | **fail** |
|  | Scrolling 16 MiB, frame work | 85–164 ms | 0–3 ms | 0.00–0.07 | pass |
| One 2 MiB line | Open, response end to laid out | 193 ms | 270 ms | 1.37–1.42 | **fail** |
|  | Open, navigation to next frame | 561 ms | 1,054 ms | 1.84–2.04 | **fail** |
| `SYNTAX_HIGHLIGHT_MAX_BYTES` | YAML, 512 KiB, 27,854 spans | 285 ms | 347 ms | 1.13–1.24 | pass |
|  | Markdown, 4,603 spans | 114 ms | 162 ms | 1.37–1.48 | **fail** |
|  | JSON, 20,307 spans | 212 ms | 251 ms | 1.15–1.22 | pass |
|  | Dense JSON, 307,591 spans | 1,371 ms | 1,699 ms | 1.19–1.25 | pass |
|  | TypeScript, 22,494 spans | 336 ms | 471 ms | 1.27–1.45 | **fail** |
| `BINARY_PREVIEW_CHUNK_BYTES` | Binary, 32 MiB file: open, response end to laid out | 220 ms | 424 ms | 1.86–1.99 | **fail** |
| `BINARY_PREVIEW_MAX_BYTES` | Six Load more clicks to 32 MiB, each response end to laid out | 100–419 ms | 159–960 ms | 1.39–2.46 | **fail** |
|  | Last click (8 MiB), to next frame | 775 ms | 1,335 ms | 1.66–1.77 | **fail** |
|  | Scrolling 32 MiB, frame work | 5.5–6.3 ms | 12–13 ms | 1.76–2.91 | **fail** |
|  | Renderer footprint, without graphics | 1,029 MiB | 238 MiB | 0.23–0.26 | pass |
| `LINES_PER_BLOCK` | Binary, 8 MiB loaded: scroll to the middle, frame work | 2.1 ms | 4.0 ms | 1.25–4.76 | **fail** |
| `DEFAULT_ACCENT_RUN_BUDGET` | Accented binary, 8 MiB, 247,322 elements: open | 88 ms | 197 ms | 2.15–2.36 | **fail** |
|  | Load more clicks, response end to laid out | 77–338 ms | 168–820 ms | 2.13–2.70 | **fail** |
| `LAYOUT_PROJECTION_BATCH_FILES` | Diff layout benchmark, 1,000 files: mount | 59 ms | 26 ms | 0.42–1.08 | pass |
|  | Median blocking layout switch | 22 ms | 31 ms | 1.38–1.47 | **fail** |
|  | Slowest blocking layout switch | 68 ms | 89 ms | 1.21–1.32 | **fail** |
| Intraline work budget | Unrelated long lines, over budget | 36 ms | 21 ms | 0.56–0.58 | pass |
|  | 8 MiB similar line, refined | 24 ms | 26 ms | 1.07–1.11 | pass |
|  | 8 MiB unrelated lines, over budget | 37 ms | 20 ms | 0.51–0.57 | pass |
| Element height | Height laid out for a 100,000,000 px element | 16,777,214 px | 33,554,428 px |  | reported |

Not measured: the server-side bounds, which are the same whichever engine asks, the diff
fold and first-screen mount, which have no committed fixture, and the Pulls panel, which
needs a signed-in `gh`.

- **Layout is where WebKit falls behind.** The request, JSON parsing, and DOM building
  took about as long in both engines; the forced style and layout after them took the
  difference. JavaScriptCore was faster on pure computation, as the intraline cases show.
- **The source view’s Load more appended one text node per chunk,** which WebKit lays
  out three to five times slower than Chrome; on a bare page, text nodes of at most
  65,536 characters laid out in 0.53 to 0.56 of Chrome’s time.
  The source view splits appended text that way since #367 (`TEXT_NODE_MAX_LENGTH` in
  `static/source-append.js`); after it the Load more row still measured 2.25 to 2.46
  times Chrome and the first-click probe 2.45 to 2.51 times, and the gate reruns
  (`mb-76nv`).
- **WebKit does not defer new `content-visibility` blocks as Chrome does,** so the
  binary view ran 1.4 to 2.7 times Chrome; highlighting and the diff switch, 1.1 to 1.5
  times, show the general cost of style and layout under these conditions.
- **Memory and scrolling favor WebKit,** and WebKit drew at 30 frames a second in Low
  Power Mode against Chrome’s 120, which adds up to 33 ms to every metric that waits for
  a frame.

The brief’s answer to a failed bound is to make the bound engine-specific, make a core
change that also helps Safari, or ship its Electron fallback; the choice is the owner’s
and is open.

### `window.print()` and Drag and Drop

`run.mjs --checks` scripts both in the app’s web view class and configuration, with the
app’s navigation policy and `PagePrintRequests` installed as the app installs them, and
drags delivered to the web view’s drop methods as AppKit delivers a drag from Finder.
On the machine above, the Print button sent one request from the main frame of the
server’s own page and File > Print’s path printed the document alone, and a dropped file
and a dropped folder both reached `onFileDrop` before WebKit saw them.

## Why It Lives in This Repository

The host protocol is a contract between the app and `metab`, so a change to it lands in
both in one commit, as [AGENTS.md](../../../AGENTS.md#compatibility-and-legacy-code)
asks of internal contracts.
Nothing in `apps/` ships to PyPI: `devtools/check_distribution.py` fails the build if an
`apps` path reaches the sdist or wheel.
A separate repository would make sense if the app gained its own release cadence, needed
signing secrets this repository’s CI should not hold, or had to support several `metab`
versions through a published protocol.

## Planned

The [plan](../specs/active/plan-2026-11-10-native-macos-app.md) and the
[packaging brief](../research/research-2026-11-08-macos-app-packaging.md)’s Layering
section and Recommendations hold each of these:

- **Host mode:** port 0 and a JSON ready line in place of the port walk and
  `LaunchGate`, a session token through `WebAuthorization` in place of today’s open
  loopback server, `/healthz`, and a shutdown that also ends descendants in other
  process groups.
- **The runtime:** a rootless runtime report, explicit tool paths, and an app-managed
  runtime, so a CLI install is optional.
- **In the app:** guidance before a protected folder’s privacy prompt, and Settings
  served by Metabrowser in place of the native window.
- **Distribution:** a Developer ID release built by CI on a `macos-v*` tag, updates
  beyond `brew upgrade --cask`, and a fixed DMG window layout.
- **Beyond one server per root:** recent roots kept by `metab` behind a route, attaching
  to an agent’s server, and a `metabrowser://` hand-off.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
