# Plan for the Native macOS App

**Date:** 2026-11-10 (last updated 2026-11-12)

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Draft. Epic `mb-1apq` tracks every item below as a bead.
Phase 1 is in progress, and the v1 milestone (`mb-s4y1`, below) is under way.

## Overview

Metabrowser gets a native macOS app: a thin AppKit and `WKWebView` shell over the same
`metab` server that any browser can open.
The app should feel like a first-class Mac app (fast to switch between folders, clear
about which window is which, easy to download and install) while `metab` stays the
product and every capability stays runnable and testable from the command line.

This plan turns three research briefs into tracked work:

- [Native macOS App for Metabrowser](../../research/research-2026-11-08-macos-app-packaging.md)
  chose the shell (a hand-written Swift app), the layering, the runtime strategy, and
  distribution.
- [Server Topology, Lifecycle, and Agent Handoff](../../research/research-2026-11-10-native-app-server-topology.md)
  chose how the app uses servers: a process per root behind a registry, warm folders,
  app-owned servers, native tabs, and one front door for agents.
- [Setup Flows for `metab` and the Native macOS App](../../research/research-2026-11-11-uv-and-macos-app-install.md)
  chose how users get both installed: the CLI first and then the app, or the app first
  with a first-run flow that makes the same CLI install.

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
  decided before Phase 4, which persists added roots.
  Phase 3 does not wait for it, because its front door starts a server for a new root
  only after the user confirms that root in the app.

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
- **Modern and native.** Swift 6.3 with strict concurrency, AppKit, `WKWebView`,
  SwiftPM, and Apple’s own tools (`codesign`, `notarytool`, `stapler`, `hdiutil`); no
  third-party runtime dependencies; macOS 26 and later on arm64. The user set the floor
  at the newest release on 2026-11-11, so the app can use current APIs without fallbacks
  for older systems.
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
  parallel to the B’s stem.
  Chosen on 2026-11-11 after side-by-side review: the cut ends the diagonal in a point
  19.337 units below the cap line (of a 512-unit master), and a 34-unit gap, a little
  more than the M’s 31.464 stem, separates the face from the intact B, so the gap reads
  as the M’s missing right stroke.
  The mark is 242 units wide, against the sister app’s 222. The half-M is hand-drawn on
  Reddit Mono Bold’s construction, the face the sister app’s letters are set in; the B
  is Reddit Mono Bold’s own B, which that app also used unedited for its letter.
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
  The chosen values (`junction` gap, `faceTopFlat` 0, `faceDrop` 19.337, `gap` 34) are
  in the release and development parameter files, which differ only in their base; the
  earlier designs stay as alternate parameter files for comparison.
  A script renders every size reproducibly with native tools, with small-size masters if
  16 to 64 px need them.
  The sister app’s own files stay out of this repository.

### Build, Signing, and Distribution

One command produces a downloadable release, adapted from the sister app’s pipeline:

- **Versions:** `apps/macos/VERSION` is the one source, a release is tagged
  `macos-v<VERSION>` (checked against the file in CI), and the build number is the
  commit count, so shallow clones are refused.
- **Variants:** every pure development build, local or from a CI run on a branch, pull
  request, or `main`, is the dev variant (`build/dev/Metabrowser.app`,
  `io.github.jlevy.metabrowser.dev`, the canary icon, and a `-dev` suffix on any URL
  scheme). Only the release path (`make release`, `make notarize`, or an explicit
  `VARIANT=release` on the command line; a stray environment variable is ignored)
  produces the release variant (`build/release/Metabrowser.app`,
  `io.github.jlevy.metabrowser`, the regular dark icon).
  Amended 2026-11-11 at the user’s request: both are named Metabrowser, and the canary
  icon and the About box’s first line (“Development build” or “Release”, then the
  version, build, and commit) tell them apart.
  Amended 2026-11-12 at the user’s request (`mb-d71s`): both keep their files in folders
  named Metabrowser, server logs in `~/Library/Logs/Metabrowser/`, Apple’s place for
  them, which Console.app lists, and the saved session in
  `~/Library/Application Support/Metabrowser/` instead of a folder named by the bundle
  identifier, so a development build and a release restore the same windows.
  Their settings and recent folders stay apart by bundle identifier.
  Files saved by earlier, unreleased builds in `Metabrowser Dev/` or the bundle
  identifier’s folder are not moved.
  One name has a cost: the two bundles cannot both sit in `/Applications` under it, so a
  development build normally runs from `build/dev/`. The app’s README
  ([Variants](../../../../apps/macos/README.md#variants)) has the details.
  The DMG check refuses a release image with the canary icon or without the published
  one. Two installed copies therefore never share defaults or a scheme, and a development
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
  The user approved the build, test, and ad hoc release-rehearsal workflow and the gate
  that keeps the existing `publish.yml` to the Python package’s `v<version>` tags, so a
  macOS tag never triggers a PyPI publish, for the v1 milestone (`mb-x4fy`). The signing
  and notarizing release job still waits for the user’s approval and the credentials
  (Open Questions).
- **What a downloader needs:** the app uses a `metab` CLI install and shows the install
  command when it finds none; Phase 5 adds a first-run flow that makes that install for
  the user.
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

### Milestone: v1, a Usable App

On 2026-11-11 the user asked for the spike to become a full, usable app that meets the
tbd coding guidelines.
`mb-s4y1` tracks that milestone.
It draws its items from Phases 1, 2, and 5. Its work lands as a native GitHub stack on
the spike, each layer a pull request whose base is the layer below:
jlevy/metabrowser#341 (the spike, with CI and the review fixes), jlevy/metabrowser#359
(everyday use), jlevy/metabrowser#361 (setup), jlevy/metabrowser#362 (guidelines and
robustness), and jlevy/metabrowser#363 (the engine gate’s record).
None of it merges until the user says.

The steps run in this order, which the beads record as dependencies:

1. **CI** (`mb-x4fy`): a workflow that builds and tests the app on a macOS runner and
   rehearses an ad hoc release with the DMG check, and a gate that keeps `publish.yml`
   to the Python package’s `v<version>` release tags.
   The user approved both for this milestone.

2. **Review fixes** (`mb-o2kn`): every finding of the first review round on #341.

3. **Coding guidelines** (`mb-nns2`): tbd has no Swift guideline, so its
   language-neutral rules apply: general coding and comments, error handling, testing
   and TDD (decision logic in `ShellCore`, with tests), filesystem, release engineering,
   supply chain, and backward compatibility.

4. **Robustness:** health checks before attaching and server stderr written to the log
   (`mb-1poj`); no server outliving a crashed app (`mb-hwa9`); and the variant gaps in
   the sources (`mb-9xl0`). The first plan reaped those servers at the next launch until
   host mode’s stdin-EOF exit (`mb-qzny`) replaced that.
   Review on jlevy/metabrowser#362 showed that a reaper cannot tie a recorded process id
   to the process it later signals, so the stdin-EOF exit came first:
   `metab --exit-on-eof`, a serve-mode flag, stops the server when its stdin closes, and
   the app starts every server with it and holds the pipe, so the kernel ends each
   server however the app ends.
   Host mode keeps its other parts in Phase 3.

5. **Engine gate** (`mb-gvtw`): the WebKit measurement gate the packaging brief sets
   before the Swift shell grows further.
   The large-content cases measured in Chrome (see
   [rendering large content](../../../large-content-rendering.md)) are run in the app’s
   `WKWebView` and recorded beside the Chrome numbers with their method, and
   `window.print()` and drag and drop are checked by hand.
   A failure goes back to the brief’s fallback, Electron, before steps 6 and 7.

   The gate ran on 2026-11-11 and failed; the numbers and method are in
   [rendering large content](../../../large-content-rendering.md#measured-in-webkit).
   Its largest failure, the source view’s Load more at 4.5 to 5.8 times Chrome, has a
   measured cause and a core fix (`mb-551q`, its own pull request to `main`), and the
   gate reruns under normal conditions after that fix (`mb-76nv`). The binary view’s
   forced layout is tracked separately (`mb-pzy2`). The gate’s checks also found that
   the page’s Print button and a dropped file did nothing; jlevy/metabrowser#359 fixed
   both (`mb-j3eu`, `mb-3h2m`). Steps 6 and 7 went ahead meanwhile; whether the failures
   that remain after the rerun call for the fallback is the owner’s decision.

6. **Setup:** the first run without `metab` (`mb-su30`), the version policy (`mb-895s`),
   and the disk-image notice (`mb-3n79`), as Phase 5 describes, and both flows in the
   installation guide (`mb-2hqz`).

7. **Everyday use:** opening a file (`mb-tssz`), recents (`mb-cqxd`), native tabs
   (`mb-ssed`), and lazy session restore (`mb-lc8c`). Recents are the list macOS keeps
   through `NSDocumentController`, behind the Dock menu and File > Open Recent; it
   replaces the app’s own list in `UserDefaults`, so the app owns no membership or
   order. Recent roots persisted in `metab` and the switcher over them stay in Phase 4.

8. **Independent review** (`mb-niod`): the strong tier reviews the upgraded app (senior,
   security, and correctness), and every finding is addressed, with follow-up rounds
   until a round finds nothing new.

9. **End to end** (`mb-hwxu`): the dev and release-rehearsal builds are rebuilt and,
   with fresh app settings on the build Mac, run through both setup flows, an old
   `metab`, a launch from the disk image, and every manual check the earlier steps
   record. Other macOS versions, standard accounts, and a Mac without the Command Line
   Tools (`mb-5fp7`), and Gatekeeper with a Developer ID build (`mb-e9fm`), are not
   covered; that is v1’s named limitation.

Outside the milestone, each for a stated reason:

- warm folders (`mb-e7im`), which wait on the tracker fix (`mb-z46o`);
- host mode and the agent front door, which are Phase 3;
- the app-private runtime (`mb-lrcd`), which is optional;
- “Install for me” (`mb-34oi`), which waits on the clean-account matrix (`mb-5fp7`);
- the clean-account matrix itself (`mb-5fp7`), which needs other machines and accounts;
- a Developer ID release (`mb-e9fm`), which needs the owner’s certificate.

### Phase 1: Identity, Titles, Icon, and a Downloadable Build

- [x] Folder identity model and `GET /api/identity`, with goldens (`mb-n9p6`), merged in
  jlevy/metabrowser#353.
- [x] The page title is `<short name> • Metabrowser` (`mb-2agt`), in the same pull
  request.
- [ ] Native window title, tab title, subtitle, and proxy icon (`mb-wgl7`).
- [ ] App icon in the sister app’s style, from its vector originals (`mb-mpm3`).
- [ ] Adopt the sister app’s build, signing, and download pipeline for the Swift app
  (`mb-nnhs`).
- [ ] Developer ID signing, notarization, a DMG, and a Homebrew cask (`mb-e9fm`).
- [ ] Development builds with their own bundle id, scheme, and icon (`mb-9xl0`).
- [ ] A macOS CI job (`mb-x4fy`), approved for the v1 milestone; a signed release
  workflow comes later.
- [ ] tbd desktop guideline updates from what that pipeline teaches (`mb-s5ay`).

### Phase 2: Warm Switching in the Shell

- [ ] Fix the activity tracker’s idle cost first (`mb-z46o`).
- [ ] Keep folders warm after their windows close (`mb-e7im`).
- [ ] Native tabs across folders with a tabs-or-windows preference (`mb-ssed`).
- [ ] Lazy session restore (`mb-lc8c`).
- [ ] Open a file from `open -a` and select it inside its folder (`mb-tssz`).
- [ ] Health-check servers before attaching; send stderr straight to the log
  (`mb-1poj`).

### Phase 3: Host Mode, the Registry, and the Agent Front Door

No root is admitted on an agent’s request alone.
Socket ownership authenticates the user, not the agent, so a request through the front
door, by rendezvous or by link, may present a root the app already has open or warm, or
one with a live server the app can attach to.
For any other root, the app starts a server as its own child only after the user
confirms that root in the app.

- [ ] Host mode: a ready line after bind, sticky ports, a stdin token, stdin-EOF exit,
  and idle exit (`mb-qzny`), generalizing the VS Code host design (`mb-x4y5`). No
  client’s credential, the app’s web views included, is a cookie, since a page can send
  a cookie to every port on its host whatever its data store or host name.
  The credential is a token in the `Authorization` header that one shell helper adds
  only to requests for the page’s own origin, with redirects refused; host mode also
  gates the first page load and the event stream (the topology brief’s Tokens across
  ports) and passes the cross-port check under Testing Strategy.
- [ ] The live-server registry with a per-root find-or-start lock (`mb-5xi4`).
- [ ] Control verbs on an owner-only socket: identity, present, clients, close
  (`mb-1zyp`).
- [ ] Pages follow `navigate` events and reload once on a new boot id (`mb-54r1`).
- [ ] The agent front door, `metab TARGET --present`, which reports a declined
  confirmation as blocked (`mb-idri`).
- [ ] The app’s `metabrowser://` scheme, rendezvous handler, and attach, with that
  confirmation (`mb-rtgh`).
- [ ] The skill uses the front door and documents sandbox settings (`mb-ko5d`).

### Phase 4: Roots as State, the Switcher, and the MCP Adapter

- [ ] Persist recent and added roots in `metab`, served by a roots route; the chosen
  security model decides which of them skip Phase 3’s confirmation (`mb-a5ru`).
- [ ] Quick folder switcher, listing the roots route’s roots with live servers from the
  registry (`mb-9lf4`). The switcher’s membership and order come from `metab`, so it
  needs no shell-only exemption.
  Dock and File menu recents, which macOS keeps, are v1’s `mb-cqxd`.
- [ ] An optional MCP stdio adapter over registered routes (`mb-5lgp`).

### Phase 5: Setup, Runtime, and Updates

The two standard setup flows come first; see the
[setup flows brief](../../research/research-2026-11-11-uv-and-macos-app-install.md).

- [ ] Flow 1, CLI first: `uv tool install metabrowser`, then the DMG or the cask,
  documented in the installation guide and checked end to end on clean accounts.
  The app gets a required minimum `metab` version (later, the host-protocol version),
  names the exact upgrade command, notices `uv tool upgrade`, and offers to restart the
  servers it started from the old version (`mb-895s`). An upgrade run in Terminal can
  reach a running server before the app notices; the setup brief records that gap.
  Any upgrade the app runs itself waits as Reinstall and Remove do (below).
  The app also flags a launch from the disk image (`mb-3n79`). The installation guide
  covers both flows (`mb-2hqz`).
- [ ] Flow 2, app first with no CLI: copyable commands for only the missing steps,
  continuing by itself when `metab` appears; then an “Install for me” button that runs
  the user’s uv, or a signed uv inside the app, to make Flow 1’s CLI install (`mb-su30`,
  then `mb-34oi`). Its Reinstall and Remove stop the app’s servers on that install, then
  change nothing while the registry lists another server using it: the app names each
  one and its owner, asks the user to stop it, and checks again, and it never signals a
  server it did not start.
- [ ] Narrowed: an optional app-private runtime from a bundled uv and a hash-pinned
  `pylock.toml`, for offline, managed, or hash-pinned setups, built only on demand
  (`mb-lrcd`).
- [ ] The WebKit measurement gate against the Chrome-measured bounds, run in v1
  (`mb-gvtw`); the broader owner acceptance stays `mb-etqi`.
- [ ] Updates: cask upgrades and an in-app notice, Sparkle later (`mb-fl72`). Each
  installed copy has one updater, and an update replaces the bundle whole.
- [ ] A clean-account matrix for both flows, on macOS 26 and later, admin and standard
  accounts, with and without the Command Line Tools (`mb-5fp7`).
- [ ] Optional: a separate bundle id for release-rehearsal builds (`mb-nneo`).
- [ ] The project-plugin trust spec (`mb-m1mw`).
- [ ] Later, once both flows pass: `metab` installs, reports, and removes the app from
  the notarized release ZIP, verifying it itself because a command-line download carries
  no quarantine (`mb-92d9`), with the ZIP and a release manifest beside the DMG
  (`mb-5jr9`) and a bundle-id lookup filtered to Applications folders (`mb-56nq`).

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
- **Credentials:** a page from one server sends none of its credentials to any other
  port, in the app’s `WKWebView`, Safari, and Chrome.
  The check covers a subresource, a redirect, a navigation, and a `fetch`, each both to
  the page’s own host name on another port and to a sibling host name, and a listener
  that records request headers whatever `Host` it receives.
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
- CI builds and tests the app once `mb-x4fy` lands.
  Signed releases are built locally until a release workflow is approved, and published
  only on the user’s explicit go-ahead: notarizing and publishing reach Apple and
  GitHub.

## Open Questions

- Which Developer ID certificate and notarization credentials should releases use?
  None is installed on the build Mac yet.
- Should a signed release workflow be added under `.github/`? The build-and-test
  workflow is approved; signing and notarizing in CI need the credentials above.

## References

- Research:
  [Native macOS App](../../research/research-2026-11-08-macos-app-packaging.md),
  [Server Topology, Lifecycle, and Agent Handoff](../../research/research-2026-11-10-native-app-server-topology.md),
  [Setup Flows for `metab` and the Native macOS App](../../research/research-2026-11-11-uv-and-macos-app-install.md)
- Code: `apps/macos/README.md`, `skills/metabrowser/SKILL.md`,
  [Views, Models, and Routes](../../architecture/arch-views-models-routes.md)
- tbd guidelines: `macos-webview-shell-patterns`, `desktop-python-runtime-patterns`,
  `electron-app-development-patterns`
- Pull requests: jlevy/metabrowser#341 (spike), jlevy/metabrowser#352 (research and this
  plan), jlevy/metabrowser#353 (folder identity), jlevy/metabrowser#357 (the v1
  milestone), and the v1 stack above the spike: jlevy/metabrowser#359,
  jlevy/metabrowser#361, jlevy/metabrowser#362, and jlevy/metabrowser#363

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
