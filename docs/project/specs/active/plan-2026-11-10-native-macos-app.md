# Plan for the Native macOS App

**Date:** 2026-11-10 (last updated 2026-11-11)

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Draft. Epic `mb-1apq` tracks every item below as a bead.
Phase 1 is in progress.

## Overview

Metabrowser gets a native macOS app: a thin AppKit and `WKWebView` shell over the same
`metab` server that any browser can open.
The app should feel like a first-class Mac app (fast to switch between folders, clear
about which window is which, easy to download and install) while `metab` stays the
product and every capability stays runnable and testable from the command line.

This plan turns two research briefs into tracked work:

- [Native macOS App for Metabrowser](../../research/research-2026-11-08-macos-app-packaging.md)
  chose the shell (a hand-written Swift app), the layering, the runtime strategy, and
  distribution.
- [Server Topology, Lifecycle, and Agent Handoff](../../research/research-2026-11-10-native-app-server-topology.md)
  chose how the app uses servers: a process per root behind a registry, warm folders,
  app-owned servers, native tabs, and one front door for agents.

It also uses a sister app as a guide: an earlier Electron app by the same author, in a
private repository, with an end-to-end macOS build, signing, and download pipeline and a
carefully designed icon.
What fits is adapted to a modern native toolchain; nothing names or ships that app.

## Goals

- Every window and browser tab says which folder it shows, at a glance.
- Switching between recently opened folders is effortless, in one window or many.
- A user can download a signed, notarized app and open it like any other Mac app.
- Agents can ask Metabrowser to show the user something, and it appears in the app or a
  browser.
- The app and its icon read as a sister of that app.
- Every user-visible behavior has a `metab` route or command with a golden transcript;
  the app adds only platform behavior.

## Non-Goals

- Windows and Linux apps (the earlier brief keeps Tauri as the path if they become
  near-term).
- The Mac App Store: its sandbox rules out serving arbitrary folders and downloaded
  code.
- Choosing the security model for agent-added roots; it is weighed in the briefs and
  decided before Phase 4.

## Background

The spike in `apps/macos/` (branch `claude/macos-app-spike`, jlevy/metabrowser#341)
discovers a CLI install of `metab`, runs one server per folder as a child process, and
shows each folder in a native window.
It is verified end to end on fresh launches, and it is not to be merged until the user
decides; core `metab` changes land on `main` through their own pull requests.

Two problems prompted this plan.
Every window is titled “Metabrowser”, because the served page’s title never names its
folder. And there is no way yet to build something a user can download.

## Design

### Principles

- **`metab` is the product, shells are wrappers.** Data semantics (identity, membership,
  ordering, persisted state) live in routes reached through `metab`; the app renders
  them and adds platform behavior (windows, tabs, menus, the Dock, LaunchServices,
  signing).
- **Modern and native.** Swift 6 with strict concurrency, AppKit, `WKWebView`, SwiftPM,
  and Apple’s own tools (`codesign`, `notarytool`, `stapler`, `hdiutil`); no third-party
  runtime dependencies; macOS 15 and later on arm64.
- **Effortlessly fast.** Prefetch what the user plausibly needs next; never show a
  spinner within about 50 ms.
- **Adapt the sister app, don’t copy Electron.** Keep its release discipline, variants,
  and icon design; drop what only Electron needs.

### Folder Identity

Every root a server browses has an identity, served by `GET /api/identity` and reached
through `metab --api`:

```json
{
  "short_name": "fdu",
  "full_name": "~/wrk/github/fdu",
  "kind": "folder",
  "kind_label": "Local folder",
  "title": "fdu • Metabrowser"
}
```

- **Local folder:** `short_name` is the folder’s own name (`/` for the filesystem root,
  `~` for the home folder); `full_name` is its path with the home folder as `~`.
- **Cached mirror** (a pure cache location, served by `metab <git-url>`): `short_name`
  is the repository name; `full_name` is the origin abbreviated to `host/owner/repo@ref`
  (or `@` and 12 hex digits for a commit pin), never the path in the cache; `kind_label`
  is “Cached mirror”.
- **Title:** the short name, a bullet (U+2022), and “Metabrowser”.
  The served page uses it as its `<title>`, so browser tabs show it too.
- Phase 3 extends the same route with the process id, boot id, and version that host
  mode needs.

### Window and Tab Titles

- The visible title shows the short name prominent and bold, then a small bullet and
  “Metabrowser” in a lighter secondary style.
  AppKit cannot style part of a system title, so the app hides the system title and
  draws a native-looking attributed title in the title bar.
- The window’s plain title is the same text, for the Window menu, Mission Control, the
  Dock, and accessibility.
- A native tab shows only the short name; its tooltip shows the full name.
- The full name and kind appear as the subtitle or tooltip, and a local folder sets the
  window’s represented URL, so the proxy icon and Command-click path menu work.

### Icon and Brand

The app icon is a sister of the sister app’s Figma-designed icon, version 6.

- **Base:** its squircle, gray rim with its bevel, inset near-black panel with its inner
  border and diagonal sheen, and the inner shadow that presses each letter into the
  surface, copied from its Figma originals (SVG exports of the release and canary icons)
  rather than rebuilt from pixels.
- **Mark:** the first half of an M, drawn as `|\/`, then a clean B. The M’s rising
  diagonal ends in a vertical cut, so the partial M’s right side is a vertical face
  parallel to the B’s stem, separated from it by a gap matching the sister app’s gap
  between its two glyphs.
  The half-M is hand-drawn on Reddit Mono Bold’s construction, the face the sister app’s
  letters are set in; the B is Reddit Mono Bold’s own B, which that app also used
  unedited for its letter.
- **Colors:** gem tones with the sister app’s radiance (its fills’ lightness and
  saturation) in the hue families of Metabrowser’s file-overview colors: a citrine or
  old-gold yellow for the JavaScript brownish yellow, and an amethyst purple for the
  Markdown purple, with the hues warmed or moved toward violet only as far as needed to
  stay radiant without turning lemon or periwinkle.
- **Variants:** a canary icon for pure development builds, local or built on GitHub, and
  the regular dark icon for every release, as the sister app does.
  The canary keeps the sister app’s canary scheme (a gold rim and warm sheen), so the
  two apps’ development builds match too.
- **Source:** SVG masters checked in, generated from the sister app’s SVGs by a
  parameterized glyph generator: the junction style (a gap with a vertical face, or the
  M overlaid on the B with the B’s corner beveled parallel to the M’s diagonal), the gap
  or channel width, the stem, diagonal, and vertex dimensions, the cap line and
  baseline, and the fills are named parameters in one checked-in file, so a tweak is a
  one-line change and a rebuild.
  A script renders every size reproducibly with native tools, with small-size masters if
  16 to 64 px need them.
  The sister app’s own files stay out of this repository.

### Build, Signing, and Distribution

One command produces a downloadable release, adapted from the sister app’s pipeline:

- **Versions:** `apps/macos/VERSION` is the one source, a release is tagged
  `macos-v<VERSION>` (checked against the file in CI), and the build number is the
  commit count, so shallow clones are refused.
- **Variants:** every pure development build, local or from a CI run on a branch, pull
  request, or `main`, is the dev variant (`Metabrowser Dev.app`,
  `io.github.jlevy.metabrowser.dev`, the canary icon, and a `-dev` suffix on any URL
  scheme). Only the release path (`make release`, `make notarize`, or an explicit
  `VARIANT=release` on the command line; a stray environment variable is ignored)
  produces the release variant (`Metabrowser.app`, `io.github.jlevy.metabrowser`, the
  regular dark icon). The DMG check refuses a release image with the canary icon or
  without the published one.
  Two installed copies therefore never share defaults or a scheme, and a development
  build is never mistaken for a release.
- **Signing:** Developer ID with the hardened runtime and a secure timestamp, inside
  out, never `--deep`; the build fails if any entitlement appears, since a `WKWebView`
  shell needs none; ad-hoc signing for development builds.
- **Notarization:** `notarytool --wait --output-format json`, with the status read from
  the JSON and the notary log always saved, using a keychain profile locally or an App
  Store Connect API key in CI, then stapling and a Gatekeeper assessment.
  A three-state `NOTARIZE` setting lets pull requests build without secrets while a
  release tag can never skip notarization silently.
- **Preflight:** an official build checks for a Developer ID identity, notary
  credentials, the published icon, and a clean tree before it compiles, and lists every
  problem at once.
- **Packaging:** a DMG built with `hdiutil` alone, holding the app, an Applications
  link, and the app icon as the volume icon, signed, notarized, and stapled, with a
  SHA-256 checksum written after stapling; a downloader-style check attaches it
  read-only and verifies its contents, signatures, staple, and Gatekeeper result.
  A fixed DMG window layout needs a `.DS_Store` that Apple’s tools cannot write, so
  Finder arranges the window.
- **Distribution:** a draft GitHub release that a person publishes, marked not latest so
  it never displaces the `metab` releases, and a generated cask for a personal Homebrew
  tap.
- **CI:** a drafted `macos-app` workflow builds the dev variant on pull requests and
  `main`, and on a `macos-v*` tag signs, notarizes, and drafts the release from secrets
  held in a protected environment.
  Adding it, and gating the existing `publish.yml` to `v*` tags so a macOS tag never
  triggers a PyPI publish, both wait for the user’s approval of workflow changes.
- **What a downloader needs:** until the app-managed runtime exists (Phase 5), the app
  uses a `metab` CLI install and shows the install command when it finds none.
- **Status:** built and tested end to end with ad-hoc signing on
  `claude/macos-release-build`. This Mac has no Developer ID identity, so the first real
  release needs one installed, plus notary credentials.

### Servers, Switching, and Agents

The server-topology brief’s recommendations, in brief:

- **A process per root** behind a registry contract (a root is an origin, at most one
  live server per root).
  A shared multi-root process stays a gated later option, since it would save only about
  65 MB and 1 s of CPU per root.
- **Warm folders:** keep a folder’s server after its window closes, budgeted by measured
  footprint and idle CPU; web views (155–210 MB each) are discarded first.
- **App-owned servers,** so privacy prompts name the app with a stable identity; servers
  the CLI starts exit when idle.
- **Native tabs across folders**, a tabs-or-windows preference, and a quick switcher.
- **One front door for agents,** `metab TARGET --present`, which hands off to the app
  through LaunchServices, navigates a live page, starts a server and opens a browser, or
  prints a link, and reports which.
  Sandboxed agents run it outside their sandbox or through an optional MCP adapter.

## Implementation Plan

Each phase is a pull-request boundary.
Core `metab` work goes to `main`; native app work stays on the spike branch until the
user decides to merge it.

### Phase 1: Identity, Titles, Icon, and a Downloadable Build

- [ ] Folder identity model and `GET /api/identity`, with goldens (`mb-n9p6`), in review
  in jlevy/metabrowser#353.
- [ ] The page title is `<short name> • Metabrowser` (`mb-2agt`), in the same pull
  request.
- [ ] Native window title, tab title, subtitle, and proxy icon (`mb-wgl7`).
- [ ] App icon in the sister app’s style, from its vector originals (`mb-mpm3`).
- [ ] Adopt the sister app’s build, signing, and download pipeline for the Swift app
  (`mb-nnhs`).
- [ ] Developer ID signing, notarization, a DMG, and a Homebrew cask (`mb-e9fm`).
- [ ] Development builds with their own bundle id, scheme, and icon (`mb-9xl0`).
- [ ] A macOS CI job, with the release workflow pending approval (`mb-x4fy`).
- [ ] tbd desktop guideline updates from what that pipeline teaches (`mb-s5ay`).

### Phase 2: Warm Switching in the Shell

- [ ] Fix the activity tracker’s idle cost first (`mb-z46o`).
- [ ] Keep folders warm after their windows close (`mb-e7im`).
- [ ] Native tabs across folders with a tabs-or-windows preference (`mb-ssed`).
- [ ] Quick folder switcher and Dock and File menu recents (`mb-9lf4`).
- [ ] Lazy session restore (`mb-lc8c`).
- [ ] Open a file from `open -a` and select it inside its folder (`mb-tssz`).
- [ ] Health-check servers before attaching; send stderr straight to the log
  (`mb-1poj`).

### Phase 3: Host Mode, the Registry, and the Agent Front Door

- [ ] Host mode: a ready line after bind, sticky ports, a stdin token, stdin-EOF exit,
  and idle exit (`mb-qzny`), generalizing the VS Code host design (`mb-x4y5`).
- [ ] The live-server registry with a per-root find-or-start lock (`mb-5xi4`).
- [ ] Control verbs on an owner-only socket: identity, present, clients, close
  (`mb-1zyp`).
- [ ] Pages follow `navigate` events and reload once on a new boot id (`mb-54r1`).
- [ ] The agent front door, `metab TARGET --present` (`mb-idri`).
- [ ] The app’s `metabrowser://` scheme, rendezvous handler, and attach (`mb-rtgh`).
- [ ] The skill uses the front door and documents sandbox settings (`mb-ko5d`).

### Phase 4: Roots as State and the MCP Adapter

- [ ] Persist recent and added roots in `metab`, served by a roots route (`mb-a5ru`).
- [ ] An optional MCP stdio adapter over registered routes (`mb-5lgp`).

### Phase 5: Runtime and Updates

- [ ] The WebKit measurement gate against the Chrome-measured bounds (`mb-etqi`).
- [ ] An app-managed runtime from a bundled uv and a hash-pinned `pylock.toml`
  (`mb-lrcd`).
- [ ] Updates: cask upgrades and an in-app notice, Sparkle later (`mb-fl72`).
- [ ] The project-plugin trust spec (`mb-m1mw`).

### Phase 6: Measured Follow-Ups

- [ ] Measure what the topology brief left open (`mb-3vpj`).
- [ ] A rootless, pre-imported spare process (`mb-bbod`).
- [ ] `replace_root` keeps about 85 MB more than closing a runtime (`mb-58sk`), which
  matters to session-scoped roots (`mb-vmzy`).
- [ ] A persisted index, if re-walks stay common (`mb-omhf`).

## Testing Strategy

- **Core:** unit tests for identity derivation; golden transcripts through `metab --api`
  for every new route; browserless golden sessions for page behavior such as following
  `navigate`; `devtools/check_parity.py` for parity rows.
- **Shell:** `ShellCore` unit tests for every model and policy (titles, warm budgets,
  restore order), live tests against a real `metab`, and fresh-launch runs: a first
  launch with settings cleared, a second folder through `open -a`, reopening a folder,
  quitting with no leftover server, and relaunching with saved settings.
- **Release:** `codesign --verify --deep --strict`, `spctl --assess`, `hdiutil verify`,
  and a downloaded-DMG install on a clean account before each published release.
- **Visual:** title bar and icon checks by screenshot in light and dark mode, key and
  non-key windows, and icon legibility at 16 to 1024 px.

## Rollout Plan

- Core pull requests merge to `main` after review and CI, and ship with the next `metab`
  release.
- The app stays on the spike branch until the user decides to merge native code.
- Releases are built locally until the CI workflow is approved, and published only on
  the user’s explicit go-ahead: notarizing and publishing reach Apple and GitHub.

## Open Questions

- Which Developer ID certificate and notarization credentials should releases use?
  None is installed on the build Mac yet.
- Should the release workflow be added under `.github/`?

## References

- Research:
  [Native macOS App](../../research/research-2026-11-08-macos-app-packaging.md),
  [Server Topology, Lifecycle, and Agent Handoff](../../research/research-2026-11-10-native-app-server-topology.md),
  [Installing the Native App Through uv and `metab`](../../research/research-2026-11-11-uv-and-macos-app-install.md)
- Code: `apps/macos/README.md`, `skills/metabrowser/SKILL.md`,
  [Views, Models, and Routes](../../architecture/arch-views-models-routes.md)
- tbd guidelines: `macos-webview-shell-patterns`, `desktop-python-runtime-patterns`,
  `electron-app-development-patterns`
- Pull requests: jlevy/metabrowser#341 (spike), jlevy/metabrowser#352 (research and this
  plan), jlevy/metabrowser#353 (folder identity)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
