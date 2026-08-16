# Research: Desktop App Packaging for Metabrowser

**Date:** 2026-08-16

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Complete

## Overview

Metabrowser currently ships as a Python package: `uv tool install metabrowser` or
`uvx metabrowser@latest`, a local Starlette server, and whatever browser the user has.
This research evaluates how to offer it as a **native desktop app** that is easy to
install and update, bundles the uv-managed Python server, keeps the extension system
working, and leaves room for Rust-backed performance work.

The generic groundwork lives in the tbd built-in guidelines, which were researched
against primary sources (framework repositories, registry queries, updater source code,
and the build configurations of ~22 shipping open-source apps) in August 2026:

- `tbd guidelines electron-app-development-patterns`
- `tbd guidelines tauri-app-development-patterns`
- `tbd guidelines electrobun-app-development-patterns`

This document holds only the metabrowser-specific analysis: the facts of this codebase,
how they constrain the options, and a recommendation.

## Questions to Answer

1. Which shell, if any: Electron, Tauri, Electrobun, or none?
2. How do we ship the uv+Python server inside a signed, auto-updating app?
3. How do extensions—pip/uv packages with entry points and in-process Python hooks—keep
   working in a packaged app?
4. What is the update story, and what integrity guarantees does it carry?
5. Where does Rust fit: native wheels inside the Python env, or a rewrite of the server?
6. What are the prerequisites regardless of approach?

## Scope

**In scope:** desktop packaging for macOS, Windows, and Linux; the Python runtime and
extension environment; update integrity; the relationship between a shell and the
existing browser/`uvx` tier.

**Out of scope:** mobile; app-store distribution; the remote/SSH mode (unchanged by any
option here); redesigning the plugin API (touched only where an option would force it).

## Findings

### What Metabrowser Is, Packaging-Wise

Read from the source at the research date:

- **The UI is already a browser app.** A Starlette/uvicorn server serves static,
  vendored JS (~14k lines, no Node build step); the CLI opens the user’s browser via
  `webbrowser`. There is no shell today.
- **Plugins are manifest + JS with optional in-process Python.** Discovery is three-tier
  (built-in, `metabrowser.plugins` entry points from installed packages, local
  directories with `manifest.toml`). Rendering plugins such as `markdown` are pure
  manifest+JS; `[[data_hook]]` blocks declare Python sidekick handlers
  (`module:callable`) **imported into the server process at startup**. Extensions are
  distributed as pip/uv packages, so a **user-writable Python environment at runtime**
  is a hard requirement.
- **Rust-backed wheels are already in the dependency tree**: `watchfiles` (Rust notify
  underneath) and `pydantic-core`. Future Rust bindings are the ordinary maturin/PyO3
  wheel path, not a new architecture.
  The `fdu` engine (spun out of `research-2026-08-06-file-rollup-engine.md`) is the
  concrete first candidate.
- ~20k lines of Python; `requires-python >= 3.12`.
- **No auth token was found in the serve path** (`server_utils.py`, `cli/serve.py`). If
  that holds, it is a prerequisite finding: the server reads the filesystem, and a
  loopback port is reachable by every local process.
  A per-session token belongs in every option below, including the status quo.

### What the Framework Layer Offers (Condensed)

Full analysis is in the guidelines; the facts that matter for this decision:

- **Update integrity differs in kind, not degree.** Tauri’s updater verifies the
  downloaded payload with minisign against a public key compiled into the app and aborts
  on failure. Electron’s Squirrel/electron-updater path refuses incorrectly signed
  updates. Electrobun’s updater verifies nothing—no signature, no digest—which makes any
  update-endpoint compromise a code-execution channel.
- **Engine control versus engine inheritance.** Electron ships its own Chromium; Tauri
  and Electrobun inherit the OS webview.
  On Linux WebKitGTK the documented breakage includes **drag-and-drop that does not
  work** (drop events never fire; file drops can navigate the webview), media served
  over the frameworks’ own asset protocols failing, and Wayland rendering glitches—each
  issue-cited in the Tauri guideline.
  Fonts and typography differ per engine on every platform.
- **Size claims are conditional.** Tauri’s small installers are real for msi/deb with a
  thin frontend, but AppImage always bundles WebKitGTK (70MB+), and any bundled runtime
  dominates the total.
- **Rust toolchains cost CI time**: a measured 3–5x against JS-only pipelines, with no
  cross-compilation.

### Cross-Cutting Design (Applies to Any Shell)

These decisions matter more than the framework choice; the generic versions live in the
Electron guideline’s Attaching a Backend and Signing sections.

1. **Two-layer artifact.** An immutable signed layer (shell, python-build-standalone
   interpreter tree, a pinned `uv` binary, metabrowser code, a hash-pinned lock) and a
   mutable per-user environment under app data, materialized on first run by the bundled
   uv syncing the bundled lock.
   Never install into the signed bundle: on macOS that breaks the code-signature seal.
   Extensions install into the app-data environment—the same operation `uvx` users
   perform today.
2. **Update-integrity chain.** Shell updates arrive through the platform’s signed
   updater; each shell version carries a new hash-pinned lock; the bundled uv applies
   only what that signed lock names.
   The only code outside the chain is what the user explicitly installed, which is pip’s
   own trust model stated honestly.
3. **macOS signing.** Every Mach-O in the interpreter tree is signed individually in an
   `afterPack`-style hook with the hardened runtime.
   The Python binary additionally needs
   `com.apple.security.cs.disable-library-validation`, because sidekick wheels install
   after signing and would otherwise fail to load.
4. **Loopback token.** The shell (or CLI) generates a per-session token; the server
   requires it; the shell injects it.
   Without this, any local process can browse the user’s filesystem through the API.
5. **Process lifecycle.** Spawn the server with stdio pipes in its own process group;
   kill the tree on quit; restart with backoff.
   Never leave an orphan.
6. **Keep the frontend framework-free.** The UI already speaks only HTTP/SSE to the
   server. Preserving that—no shell APIs in page JS—keeps the shell a swappable commodity
   and keeps the plain-browser tier working.

## Key Insights

- **The extension model is the binding constraint.** Entry-point discovery walks
  installed Python packages, and sidekicks import into the server process.
  Any option that removes the writable Python environment removes the extension system
  as designed.
- **The bundled Python tree dominates size** (~50–100MB with dependencies), so Tauri’s
  headline size advantage shrinks to modest in this application.
- **Linux drag-and-drop breakage lands directly on a file manager.** For most apps it is
  a footnote; here it argues strongly for a controlled engine on Linux.
- **The Rust-performance road is already paved.** The hot paths (file watching,
  validation) run on Rust wheels today, and `fdu` exists as a standalone engine.
  Performance work composes with every packaging option; it does not require one.
- **A shell adds no security by itself.** The loopback exposure exists today and is
  unchanged by wrapping the server in a window; the token is the fix, not the shell.

## Comparison Matrix

| Criterion | A: No shell (uvx) | B: Electron shell | C: Tauri shell | E: Rust rewrite |
| --- | --- | --- | --- | --- |
| Install/update UX | uv-native; no app affordances | Signed installer + verified updates | Signed installer + minisign updates | Best possible (single binary) |
| Update integrity | uv lockfile hashes | Squirrel: refuses unsigned | Minisign: verifies payload | Would use platform updater |
| Rendering consistency | User’s browser (varies) | Controlled Chromium | Per-OS webview (varies) | Per-choice |
| Linux drag-and-drop | Browser-native (works) | Works | **Broken today** (WebKitGTK) | Depends on shell |
| Extension model | Native | Unchanged (two-layer env) | Unchanged (two-layer env) | **Broken as designed** |
| Rust-wheel road | Native | Native | Native | Superseded |
| Added install size | 0 | ~85–120MB | ~10–15MB + Python tree | Smallest |
| CI cost | None | JS-only | 3–5x (Rust, no cross-compile) | Highest (port + toolchain) |
| Main risk | Feels non-native | Chromium patch cadence | Linux webview until Tauri 3 (GTK4) | ~20k-LOC port of a moving target |

## Options Considered

### Option A: No Shell (Status Quo, Polished)

**Description:** Keep `uvx metabrowser` and the user’s browser as the delivery vehicle;
optionally add niceties like a browser app-mode window.

**Pros:**

- Install and update are already solved by uv, including release cool-off policy.
- Zero signing burden; no new CI.
- The remote/SSH mode depends on exactly this shape.

**Cons:**

- No dock/taskbar identity, file associations, tray, or single-instance behavior.
- Rendering varies with the user’s browser.
- Does not answer the “native app” ask; this is the floor, not the ceiling.

### Option B: Electron Shell (Recommended)

**Description:** A thin Electron app: one `BrowserWindow` onto the loopback URL with the
token injected, plus the two-layer Python artifact, packaged with electron-builder and
updated via the Squirrel/electron-updater path.

**Pros:**

- **Controlled rendering engine**: consistent typography (a core product value) and
  working drag-and-drop on all three platforms.
- Signed, verified auto-update out of the box; mature signing/notarization tooling.
- The shell is unusually thin here—no contextBridge surface to speak of—so the
  framework’s main complexity (IPC security) barely applies.
- File associations, tray, single-instance, dock identity.
- Extension model unchanged via the two-layer environment.

**Cons:**

- ~85–120MB installed; memory baseline of a bundled Chromium.
- The Chromium patch cadence becomes our responsibility (roughly every 8 weeks a major;
  security patches between).

### Option C: Tauri Shell

**Description:** The same thin-shell and two-layer design with a Tauri 2 window; the
Python tree ships as a bundled resource (the Yaak pattern), not an `externalBin`.

**Pros:**

- Best-in-class updater: minisign verification of the payload against a compiled-in
  public key.
- Smallest shell overhead (~10–15MB before the Python tree).
- Tight capability scoping by default.

**Cons:**

- **Linux WebKitGTK drag-and-drop is broken today**, a direct hit on a file manager;
  media-over-asset-protocol failures and Wayland glitches are also documented.
  Tauri 3.0’s GTK4/WebKitGTK 6.0 migration is the pending fix.
- Typography varies per engine, against the product’s core promise.
- Rust toolchain in CI: 3–5x build time, per-OS builds only.
- The size advantage mostly evaporates under the Python tree.

**Verdict:** a credible second implementation if Windows/macOS-first and shell size ever
matters; do not promise Linux on it before testing drag-and-drop on real hardware.

### Option E: Rust Rewrite or Auto-Port of the Server

**Description:** Port the ~20k-line Python server to Rust (axum or similar), making the
backend a single static binary; agent-assisted porting makes this mechanically feasible.

**Pros:**

- Packaging, signing, and updating become trivial; best startup and memory.
- Pairs naturally with Tauri (the server could become in-process commands).

**Cons:**

- **Breaks the extension model as designed.** Sidekicks are Python imported into the
  server process; entry-point discovery walks installed Python packages.
  A Rust server supports neither without embedding Python, which reinstates everything
  the rewrite removed.
  Redefining plugins as manifest + JS + out-of-process hooks would fix this and add
  isolation—but that is a plugin-API redesign, not a packaging decision.
- The performance case is unproven: the hot paths already run on Rust wheels, and the
  interpreter mostly orchestrates.
  Measure before porting.
- Forks velocity against a moving target, and raises the bar for the Python-hackability
  the README promises.

**The middle road is already in motion:** keep the Python core and move measured hot
paths into Rust wheels (maturin/PyO3), with `fdu` as the first engine.
Wheels ride the same environment, lock, and update chain as every other dependency,
under every option above.

### Eliminated Options

- **Electrobun:** eliminated for public distribution.
  Its updater performs no signature or digest verification of the payload (verified
  against `Updater.ts` and the Zig extractor in the guideline research), Windows
  binaries ship unsigned, and the project is effectively single-maintainer.
  See `tbd guidelines electrobun-app-development-patterns`.

## Recommendations

1. **Add the loopback token first.** It is a prerequisite for every option, including
   today’s `uvx` tier.
2. **Ship Option B**: an Electron shell over the unchanged server, with the two-layer
   artifact and the signed-lock update chain.
3. **Keep the `uvx` + browser tier working**; the shell is one consumer of the same
   server, and the remote/SSH mode depends on it.
4. **Keep the frontend framework-free** (HTTP/WS only, no shell APIs in page JS), so a
   Tauri or thinner shell remains a cheap pivot rather than a migration.
5. **Do performance as Rust wheels** (`fdu` first), not a server rewrite; revisit the
   rewrite only if the plugin model is ever redefined away from in-process Python.
6. **Re-evaluate Tauri when 3.0 lands** its GTK4/WebKitGTK 6.0 migration and Linux
   drag-and-drop verifiably works.

## Next Steps

- [ ] Verify the no-token finding and add per-session loopback auth to the server.
- [ ] Spike the two-layer artifact: PBS tree + bundled uv + first-run env
  materialization from a hash-pinned lock, on one platform.
- [ ] Prototype the Electron shell window with token injection and process-group
  lifecycle management.
- [ ] Measure real bundle and installed sizes with the full dependency set.
- [ ] Test extension install (entry-point package with a native wheel) into the app-data
  env under a signed, hardened-runtime build on macOS.

## Methodology

The framework layer was researched for the tbd guidelines in August 2026: versions from
the npm/crates registries directly; updater behavior read from source (Tauri’s
`plugins/updater/src/updater.rs`, Electrobun’s `Updater.ts` and `extractor/main.zig`);
platform behavior from framework issue trackers; and conventions from the build
configurations of ~22 shipping open-source desktop apps.
Metabrowser-specific facts come from reading this repository’s source (`pyproject.toml`,
`plugin_loader/`, `plugin_api.py`, `cli/serve.py`, `server_utils.py`,
`builtin_plugins/`) at the research date.
The loopback-token finding is an absence of evidence from a targeted search, not a
verified guarantee, and is flagged for verification above.

## References

- tbd guidelines (generic layer): `tbd guidelines electron-app-development-patterns`,
  `tbd guidelines tauri-app-development-patterns`,
  `tbd guidelines electrobun-app-development-patterns`
- [python-build-standalone](https://github.com/astral-sh/python-build-standalone)
  (relocatable CPython; Astral)
- [uv](https://github.com/astral-sh/uv) (installer; `uv pip sync` against hash-pinned
  locks)
- [Tauri updater source](https://github.com/tauri-apps/plugins-workspace/blob/v2/plugins/updater/src/updater.rs)
  (minisign verification, read directly)
- [electron-builder](https://www.electron.build/) and
  [Squirrel/electron-updater](https://www.electron.build/auto-update) (Electron
  packaging and verified updates)
- [fdu](https://github.com/jlevy/fdu) (standalone Rust file-rollup engine; first
  candidate for a native wheel)
- Prior research: `research-2026-08-06-file-rollup-engine.md` (native engine decision),
  `docs/architecture.md`, `docs/plugins.md` (plugin model)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
