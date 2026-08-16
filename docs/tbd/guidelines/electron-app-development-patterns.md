---
title: Electron App Development Patterns
description: How to build a clean, minimal, modern Electron app — process model, build system, backend integration for Node, Bun, Python, or native code, security baseline, packaging, signing, and updates. Also when to choose Tauri, Electrobun, or no shell at all.
category: electron
---
# Electron App Development Patterns

How to build a **clean, minimal, standalone desktop app** on Electron: what belongs in
each process, how to wire an arbitrary backend (Node, Bun, Python, Go, Rust, or a
combination), how to build and package it, and how to ship it signed and updatable.

Electron is a large dependency, so the goal is not to use more of it.
The goal is a small, legible app where Electron supplies exactly three things — a
Chromium renderer, an OS integration layer, and a packaging and update pipeline — and
everything else stays ordinary code you could run without it.

This guideline is prescriptive and version-independent.
For a dated snapshot of the ecosystem (current releases, framework comparison, what
shipping apps actually do), see the accompanying research document referenced under
[Alternatives](#alternatives-to-electron).

## When to Use Electron

Choose Electron when you need **identical rendering everywhere**, a **mature signing,
notarization, and auto-update pipeline**, or **Node/npm libraries in the app process**.
Bundling Chromium is the cost you pay for those three things.

Do not choose Electron when the app is essentially a website with a window around it and
users would accept a browser tab, or when install size is a hard product constraint and
you can absorb per-platform webview differences.
See [Alternatives](#alternatives-to-electron).

Keep this honest: a desktop shell is justified by capabilities a browser cannot give you
— filesystem access, background processes, tray and menubar presence, global shortcuts,
protocol handlers, offline install, native menus, and code signing as a trust signal.
If none of those apply, the shell is overhead.

## Process Model

Electron’s process model is inherited from Chromium, and every architectural decision
follows from it.

| Process | Runtime | Owns | Never does |
| --- | --- | --- | --- |
| **Main** | Node.js | App lifecycle, windows, menus, tray, dialogs, protocol handlers, privileged filesystem and network access, sidecar supervision | Heavy CPU work, blocking I/O, anything that can hang the UI |
| **Preload** | Node.js, sandboxed by default | Exposing a narrow, typed API over `contextBridge` | Business logic, broad IPC surface, raw `ipcRenderer` exposure |
| **Renderer** | Chromium | UI only — the same code you would ship to a browser | Node.js access, direct filesystem or network privilege |
| **Utility** | Node.js | Background work: parsing, indexing, watching, sidecar hosting | Anything requiring the `electron` module |

Two rules follow from the table and prevent most Electron architecture problems:

- **The main process is a supervisor, not a worker.** It is single-threaded and it draws
  no pixels, but blocking it freezes every window.
  Anything measured in hundreds of milliseconds belongs in a utility process or a
  sidecar.

- **The renderer is a web app.** If your renderer code cannot run in a plain browser tab
  against a mock API, the boundary has leaked.
  Keeping it browser-runnable is also what makes it testable without launching Electron.

### Preload and the IPC Boundary

Treat the preload boundary as an **internal RPC surface exposed to potentially hostile
content**, because that is what it is.
The dominant Electron vulnerability class is XSS in the renderer escalating to code
execution through an over-broad preload API.

Expose intent, not capability:

```typescript
// preload.ts — good: verbs the app needs, each individually auditable
contextBridge.exposeInMainWorld("api", {
  readProjectFile: (relPath: string): Promise<string> =>
    ipcRenderer.invoke("project:readFile", relPath),
  onIndexProgress: (cb: (pct: number) => void) => {
    const listener = (_e: IpcRendererEvent, pct: number) => cb(pct);
    ipcRenderer.on("index:progress", listener);
    return () => ipcRenderer.off("index:progress", listener);
  },
});
```

```typescript
// preload.ts — bad: hands the renderer the whole IPC bus and the filesystem
contextBridge.exposeInMainWorld("api", {
  invoke: ipcRenderer.invoke.bind(ipcRenderer), // any channel, any argument
  readFile: fs.readFileSync, // any path on disk
});
```

Every listener you expose needs a disposal path, as above.
Renderer reloads otherwise accumulate listeners in the main process.

On the main side, **validate both the sender and the arguments** of every handler.
A handler that trusts its arguments is a path-traversal or SSRF bug waiting for an XSS:

```typescript
ipcMain.handle("project:readFile", async (event, relPath: unknown) => {
  if (!isTrustedFrame(event.senderFrame)) throw new Error("untrusted sender");
  if (typeof relPath !== "string") throw new TypeError("relPath must be a string");
  const abs = path.resolve(projectRoot, relPath);
  if (!isInside(projectRoot, abs)) throw new Error("path escapes project root");
  return fs.promises.readFile(abs, "utf8");
});
```

Prefer `ipcMain.handle`/`ipcRenderer.invoke` (request/response) over `send`/`on`
(fire-and-forget) for anything with a result, and use `MessagePort` for high-frequency
streams so they bypass the main process entirely.

## Backend Architectures

This is the decision that most shapes a standalone Electron app, and the one most
tutorials skip. “Backend” here means your actual application logic — an indexer, a
language runtime, an inference process, a local server you already have.

There are five patterns.
They compose: a real app often uses two.

| Pattern | Backend language | Transport | Use when |
| --- | --- | --- | --- |
| **1. In-main** | Node/TS only | Direct calls | Logic is light, fast, and non-blocking |
| **2. Utility process** | Node/TS only | `MessagePort`, structured clone | Node logic that is heavy, crash-prone, or long-running |
| **3. Loopback server** | Any | HTTP/WebSocket on `127.0.0.1` | You already have a server, or want streaming and browser-shaped APIs |
| **4. Stdio child** | Any | Newline-delimited JSON or JSON-RPC over stdin/stdout | Any language, no port, no auth, simplest lifecycle |
| **5. Native addon** | C/C++/Rust | In-process FFI (N-API) | Microsecond latency, no process boundary acceptable |

### 1. In-Main

The default. No extra process, no serialization, no lifecycle to manage.
Correct until you block the event loop.

Reach for a different pattern the moment you have a synchronous parse of a large file, a
tight CPU loop, or a library that segfaults.

### 2. Utility Process (Node Backends)

`utilityProcess.fork()` is the supported way to run Node code beside your app.
Prefer it over `child_process.fork()`:

- It launches through Chromium’s Services API, so it participates in Electron’s process
  model, crash reporting, and `app.getAppMetrics()`.
- It can hold a **direct `MessagePort` to a renderer**, so streaming data does not have
  to be relayed through the main process.
- It keeps working when you disable the `runAsNode` fuse.
  `child_process.fork()` depends on `ELECTRON_RUN_AS_NODE`, which that fuse turns off —
  so hardening your app breaks `fork()` and leaves `utilityProcess` intact.
  This interaction surprises people at packaging time; see
  [Security Baseline](#security-baseline).

```typescript
const indexer = utilityProcess.fork(path.join(__dirname, "indexer.js"), [], {
  serviceName: "indexer",
  stdio: "pipe",
});

// Hand the renderer a direct channel; bulk traffic never touches the main process.
const { port1, port2 } = new MessageChannelMain();
indexer.postMessage({ type: "attach" }, [port1]);
window.webContents.postMessage("indexer:port", null, [port2]);
```

Utility processes cannot `require("electron")`. That is a feature: it forces the split
between app logic and shell logic.

### 3. Loopback Server (Any Language)

Run your backend as a normal local server and let the renderer talk to it over HTTP or
WebSocket. This is the right pattern when the backend already exists as a server (a
Python FastAPI app, a Go service), when you want streaming responses, or when you want
the same backend to serve both a desktop app and a browser.

It is also the pattern with the most ways to get it wrong.
Non-negotiables:

- **Bind to `127.0.0.1`, never `0.0.0.0`.** Otherwise you have published the user’s
  local data to their network.
- **Bind to port 0 and read back the assigned port.** Fixed ports collide, and they let
  any other local process squat the port and impersonate your backend.
- **Require a per-launch secret.** Generate a random token at startup, pass it to the
  backend out of band (argv is visible in process listings — prefer an environment
  variable, a pipe, or a file with restrictive permissions), and require it on every
  request. Any process on the machine can reach loopback; the token is what stops another
  app’s page from driving your backend.
- **Check `Origin` and use CORS deny-by-default.** A website in the user’s browser can
  make requests to `127.0.0.1`. The token plus origin checking is what makes this safe.
- **Own the lifecycle.** Kill the child on `will-quit`, on main-process crash, and on
  renderer reload. Orphaned backends holding ports are the signature bug of this pattern.
  Pass the parent PID down and have the child exit when it disappears.

### 4. Stdio Child (Any Language)

Spawn the backend and speak newline-delimited JSON or JSON-RPC over stdin/stdout.

This is the most under-used pattern and usually the best one for a *standalone* app with
a non-Node backend. Compared to a loopback server it has no port, no token, no CORS, no
origin checking, and no orphan risk that a closed pipe does not solve — the entire
authentication problem disappears because the pipe is the capability.
The cost is that you write a small framing layer and give up browser-native streaming.

Route it through the main process or a utility process; do not expose a raw child’s
stdio to the renderer.

### 5. Native Addon

N-API addons or `napi-rs` for Rust, loaded in-process.
Choose this only when a process boundary is genuinely too slow.
The cost is real: per-platform, per-arch prebuilds, `@electron/rebuild` against
Electron’s Node ABI rather than your system Node, `asarUnpack` for the `.node` files,
and a crash in the addon takes your app with it.

### Choosing

Start at pattern 1 and move down only under pressure.
For a Node backend, 1 → 2 covers nearly everything.
For a Python, Go, or Rust backend, **prefer 4 unless you need streaming or already have
an HTTP server, in which case 3.** For a Bun backend, both 3 and 4 work and
`bun build --compile` gives you a single self-contained executable to ship, which makes
packaging markedly simpler than Python’s.

## Packaging a Non-Node Runtime

If your backend is not Node, you are shipping a second runtime, and this is where most
of the packaging pain lives.

**Get the binary out of the asar archive.** Code inside `app.asar` is not a real file on
disk and cannot be executed.
Use `extraResources` for standalone binaries and data files (reached at runtime via
`process.resourcesPath`), and `asarUnpack` for `.node` addons and anything a library
resolves by path. Packagers auto-unpack detected executables and native modules, but
verify rather than assume.

**Resolve paths for both modes.** The same code runs from a source tree in development
and from inside an app bundle in production.
Centralize this in one helper — a wrong `process.resourcesPath` assumption is the
classic “works in dev, fails after build” bug:

```typescript
const backendPath = app.isPackaged
  ? path.join(process.resourcesPath, "backend", exeName)
  : path.join(__dirname, "..", "..", "backend", "dist", exeName);
```

**Build per platform and per architecture.** A macOS universal build needs both `arm64`
and `x64` backend binaries, or a separate build per arch.
Cross-compiling a Python or native backend is usually harder than running a matrix build
on real runners.

**Sign every nested binary.** On macOS the hardened runtime requires that every Mach-O
inside the bundle is signed, including `.so`/`.dylib` files buried inside a Python
distribution. Unsigned nested binaries are the most common notarization failure.
Sign them in an `afterSign`-style hook before the outer bundle is sealed.

Language-specific notes:

- **Python.** Prefer a directory-style build (PyInstaller `--onedir`, or a
  standalone-Python distribution plus your code) over `--onefile`. One-file builds
  unpack to a temp directory at every launch, which is slow, interacts badly with the
  hardened runtime, and complicates signing.
  Expect to sign many nested `.so` files.
- **Bun.** `bun build --compile` produces one executable that embeds the runtime and
  your code. This is the least painful non-Node backend to package.
- **Go/Rust.** A static binary per platform and arch.
  Also easy.
- **Node.** If the backend is Node, you do not need a second runtime at all — use
  pattern 2 and reuse Electron’s.

**Do not depend on a runtime being installed on the user’s machine.** “Requires Python
3.12” is not a standalone app.

## Build System

An Electron app is three build targets with three different environments — main (Node),
preload (Node, sandboxed), renderer (browser) — and the build system’s job is to keep
them separate while giving you one dev command.

**Use a bundler for all three, including main and preload.** Bundling is not only about
size: it resolves `node_modules` at build time, which means your packaged app ships
without a `node_modules` tree, avoids phantom-dependency surprises, and sidesteps the
`import.meta.url` and `__dirname` resolution failures that bite libraries at runtime.
Externalize `electron` itself and any native addons.

The mainstream choices:

- **electron-vite** — Vite for all three targets from one config, with HMR in the
  renderer and hot reload for main and preload.
  The best default for a new app.
- **Electron Forge** — the official first-party toolchain: scaffolding, plugins for
  Vite/webpack, packaging, and publishing in one tool.
  Choose it when you want one integrated tool and its defaults fit.
- **Roll your own** (esbuild/Vite scripts + a separate packager) — maximum control, and
  reasonable for a small app, but you will re-implement the dev loop.

Pair whichever you pick with a packager: **electron-builder** (most configurable
installers, mature differential auto-update) or **`@electron/packager`** via Forge
makers. Forge can also drive electron-builder makers, but publishing, auto-update, and
code signing want a single owner — pick one and let it own distribution end to end.

**Package manager.** npm and pnpm both work with the full Electron toolchain.
Bun is excellent as a runtime and bundler, but the Electron *packaging* tools have
historically been the rough edge — some assume npm lifecycle-script semantics or an
npm-shaped `node_modules`. The low-risk arrangement, if you want Bun, is to use it for
your own code and scripts and let the packaging step run under Node.
Verify current status before assuming either breakage or support; this has been moving.

### ESM

Electron supports ES modules in the main process, with caveats that are easy to trip
over:

- **Main process**: ESM works, but modules load asynchronously.
  APIs that must run before the `ready` event (`app.setPath` and friends) must be
  `await`ed explicitly — otherwise `ready` can fire before your setup finishes.
- **Preload**: ESM preload scripts require the `.mjs` extension (`"type": "module"` is
  ignored), and **sandboxed preload scripts cannot use ESM at all**. Since sandboxing
  should stay on, the practical answer is a **CJS preload**, which a bundler produces
  regardless of your source syntax.
  This is the single most common ESM-in-Electron surprise.
- **Renderer**: the Chromium ESM loader cannot reach Node built-ins or `node_modules`.
  Bundle it, as you would any web app.

Write ESM source everywhere; let the bundler emit the right format per target.

### TypeScript and Shared Types

Define the IPC contract once and have all three targets import it.
This is the highest-leverage typing you can do in an Electron app, because the preload
boundary is otherwise `any` on both sides:

```typescript
// shared/ipc.ts — imported by main, preload, and renderer
export interface Api {
  readProjectFile(relPath: string): Promise<string>;
  onIndexProgress(cb: (pct: number) => void): () => void;
}
declare global {
  interface Window {
    api: Api;
  }
}
```

## Security Baseline

Electron’s defaults are good now — `contextIsolation` on, `nodeIntegration` off,
`sandbox` on. The work is not turning them on; it is **not turning them off** and adding
the things that are not defaults.

Non-negotiable in `webPreferences`:

| Setting | Value | Why |
| --- | --- | --- |
| `contextIsolation` | `true` | Preload runs in a separate JS context from page scripts |
| `nodeIntegration` | `false` | No Node globals in the renderer |
| `sandbox` | `true` | OS-level restrictions on the renderer process |
| `webSecurity` | `true` | Never disable; it removes the same-origin policy |
| `allowRunningInsecureContent` | `false` | No mixed content |
| `experimentalFeatures` | `false` | Unaudited Blink features |

Beyond `webPreferences`:

- **Content Security Policy.** Serve a strict CSP; no `unsafe-eval`, no `unsafe-inline`.
  Use nonces or hashes for anything inline.
  Note that some dev servers rely on `eval`, so apply the strict policy in production
  builds and verify it there.
- **Load app content over a custom protocol, not `file://`.** Register a custom scheme
  with `protocol.handle()` and serve your bundle from it.
  `file://` pages get extra privileges and give an XSS a much larger blast radius.
  A custom protocol also gives you a real origin, which makes CSP and storage behave
  normally.
- **Control navigation and window creation.** Handle `will-navigate` to reject
  navigation away from your app’s origin, and set `webContents.setWindowOpenHandler()`
  to deny by default, opening vetted external URLs with `shell.openExternal`.
- **Never pass renderer-supplied strings to `shell.openExternal`.** Allow-list schemes
  (`https:` and `mailto:`, typically) and validate with a real URL parser.
- **Validate IPC senders and arguments**, as shown under
  [Preload and the IPC Boundary](#preload-and-the-ipc-boundary).
- **Handle permission requests.** `session.setPermissionRequestHandler()` should deny by
  default and allow only what the app needs.
- **Never load remote content in a privileged window.** If you must display third-party
  web content, put it in a separate sandboxed `WebContentsView` with its own session and
  no preload.
- **Stay on a supported Electron major.** Electron ships a new major roughly every eight
  weeks and supports the latest three, tracking Chromium security fixes.
  Being off the supported list means shipping known Chromium CVEs to users.
  Budget for this upgrade cadence as routine maintenance, not as a project.

### Fuses

Fuses are build-time flags flipped into the Electron binary before signing.
They remove capabilities an attacker could otherwise use against your own signed app —
most importantly the ability to run your binary as a generic Node interpreter.
Set them with `@electron/fuses`.

For a typical app, disable `runAsNode`, `nodeOptions`, and `nodeCliInspect`, and enable
`cookieEncryption`, `onlyLoadAppFromAsar`, and `embeddedAsarIntegrityValidation`.

Two consequences to plan for:

- Disabling `runAsNode` breaks `child_process.fork()`. Use `utilityProcess` (see
  [pattern 2](#2-utility-process-node-backends)).
- ASAR integrity validation means the asar hash is embedded at sign time, so any
  post-build modification of `app.asar` breaks the app.
  That is the point, but it does mean fuse flipping and signing must happen in the right
  order in your pipeline.

Verify fuses on the packaged artifact, not in config.
It is easy to configure a fuse and have the packaging order silently drop it.

## Signing, Notarization, and Updates

Unsigned desktop apps are effectively undistributable.
Both platforms now require real identity.

**macOS.** Sign with a Developer ID certificate, enable the hardened runtime, and
notarize. Every nested binary must be signed (see
[Packaging a Non-Node Runtime](#packaging-a-non-node-runtime)). Request entitlements
narrowly — JIT and unsigned-memory entitlements are commonly copy-pasted when they are
not needed. Verify by downloading the built artifact through a browser and launching it
on a clean machine; Gatekeeper only applies quarantine to downloaded files, so a local
build can pass while a real download fails.

**Windows.** Traditional OV certificates produce SmartScreen warnings until reputation
accrues; EV certificates historically avoided that but require hardware tokens, which
are hostile to CI. Cloud signing services (notably Azure Trusted Signing) are now the
mainstream answer: no local key material, works from CI, and carries SmartScreen
reputation. Check current eligibility requirements before committing to one.

**Linux.** No signing gate.
Ship AppImage, `.deb`, and/or Flatpak as your audience requires.

**Updates.** The two mainstream options are `electron-updater` (electron-builder’s
updater; supports differential downloads via blockmaps, works against S3, GitHub
Releases, or a generic server) and Electron’s built-in `autoUpdater` on Squirrel, which
the free `update.electronjs.org` service can back for open-source apps on GitHub
Releases.

Whichever you choose, three things matter more than the choice:

- **Updates must be signature-verified.** An unauthenticated update channel is a remote
  code execution channel with a nice UI.
- **Users should not be forced to restart.** Download in the background, apply on next
  launch, and offer a restart.
- **Have a rollback plan.** A staged rollout is worth the setup cost, because a bad
  auto-update reaches everyone at once.

Expect full-download updates to be large, since the runtime is bundled.
Differential mechanisms reduce this substantially but not to the kilobyte range.

## Alternatives to Electron

Use the same three-part frame for every alternative: **what draws the UI**, **what runs
your code**, and **how mature the distribution pipeline is.** The last one is what teams
underestimate.

- **Tauri** — Rust shell, OS webview, small bundles, mature 2.x with a real plugin
  ecosystem and mobile targets.
  The trade is per-platform webview differences (WebKit on macOS/Linux, WebView2 on
  Windows), which you now test against instead of one Chromium.
  The most credible alternative for a new app that does not need Chromium parity.
- **Electrobun** — Bun runtime, OS webview or optionally bundled Chromium, with built-in
  bsdiff-based delta updates that are dramatically smaller than Electron’s. Reached a
  stable 1.x, so it is no longer a beta bet; still a much smaller ecosystem, so budget
  for solving your own problems.
- **Wails** — Go backend, OS webview.
  Natural if your backend is already Go.
- **Neutralino / Buntralino** — very small shells over system webviews.
  Suited to simple tools, not to feature-heavy apps.
- **No shell** — a local server the user opens in their own browser.
  Zero shell maintenance, no signing, no update pipeline, and no Chromium to ship.
  It gives up native menus, tray presence, protocol handling, and a double-click
  install. For developer tools this is frequently the right answer and is worth genuinely
  considering before writing any shell code.

For current versions, maturity, and a comparison matrix, see
`research-2026-08-16-electron-desktop-architectures.md` in this repository, which
carries the dated snapshot that would otherwise rot inside this guideline.

## Anti-Patterns

- **Business logic in the preload script.** Preload is a bridge.
  Logic there is hard to test, runs with elevated privilege, and grows the attack
  surface.
- **A god IPC channel.** One `invoke("doThing", {...})` handler that switches on a
  string is an unauditable, untypable API. Name channels after operations.
- **Disabling `sandbox` or `contextIsolation` to make something work.** The thing you
  are trying to do belongs in the main process behind a narrow IPC call.
- **A fixed loopback port with no authentication.** Any local process — including a web
  page in the user’s browser — can reach it.
- **Blocking the main process**, including `fs.readFileSync` on user-sized files and
  synchronous JSON parsing of large documents.
  This freezes every window.
- **Shipping `node_modules` instead of a bundle.** Bloats the app and invites
  path-resolution failures after packaging.
- **Testing only the dev build.** Sandbox behavior, asar path resolution, fuses,
  protocol registration, and signing exist only in the packaged app.
  Most Electron bugs live in the gap between `dev` and `dist`.
- **Treating an Electron upgrade as optional.** Falling off the supported majors means
  shipping known Chromium vulnerabilities.

## Pre-Ship Checklist

Run every item against the **packaged, signed artifact**, downloaded to a clean machine.

- [ ] Launches on a machine that never had the toolchain, on each supported OS and arch.
- [ ] Backend starts, is reachable, and **terminates** on quit, crash, and force-quit —
  verified by checking for orphaned processes.
- [ ] `webPreferences` verified at runtime, not just in source.
- [ ] Fuses verified on the packaged binary.
- [ ] CSP active in production with no console violations.
- [ ] Navigation, window-open, and permission handlers reject by default.
- [ ] macOS: notarization accepted; app launches without a Gatekeeper prompt after a
  browser download.
- [ ] Windows: signed, and SmartScreen behavior is understood.
- [ ] Auto-update tested end to end, from the previous released version to this one.
- [ ] Uninstall leaves no orphaned processes or services.

## Related Guidelines

- Monorepo setup: `tbd guidelines pnpm-monorepo-patterns`,
  `tbd guidelines bun-monorepo-patterns`
- TypeScript conventions: `tbd guidelines typescript-rules`
- Supply chain: `tbd guidelines supply-chain-hardening`

## References

**Electron (official)**

- [Process Model](https://www.electronjs.org/docs/latest/tutorial/process-model)
- [Security](https://www.electronjs.org/docs/latest/tutorial/security) — the numbered
  checklist this guideline’s baseline condenses
- [Fuses](https://www.electronjs.org/docs/latest/tutorial/fuses)
- [ES Modules](https://www.electronjs.org/docs/latest/tutorial/esm)
- [utilityProcess](https://www.electronjs.org/docs/latest/api/utility-process)
- [Context Isolation](https://www.electronjs.org/docs/latest/tutorial/context-isolation)
- [Code Signing](https://www.electronjs.org/docs/latest/tutorial/code-signing)
- [Updates](https://www.electronjs.org/docs/latest/tutorial/updates)
- [Release schedule and supported versions](https://releases.electronjs.org/)

**Build and packaging**

- [electron-vite](https://electron-vite.org)
- [Electron Forge](https://www.electronforge.io)
- [electron-builder](https://www.electron.build)
- [electron-builder: application contents](https://www.electron.build/docs/contents/) —
  `extraResources` versus `asarUnpack`
- [electron-builder: macOS notarization](https://www.electron.build/docs/features/code-signing/notarization/)
- [@electron/rebuild](https://github.com/electron/rebuild) — native addons against
  Electron’s ABI

**Alternatives**

- [Tauri](https://v2.tauri.app) — including
  [sidecar patterns](https://v2.tauri.app/learn/sidecar-nodejs/)
- [Electrobun](https://electrobun.dev)
- [Wails](https://wails.io)
- [Bun single-file executables](https://bun.com/docs/bundler/executables)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
