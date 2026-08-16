# Research: Electron and Desktop Shell Architectures

**Date:** 2026-08-16

**Status:** Complete — snapshot of the desktop-shell landscape and its implications for
Metabrowser.

## Overview

Metabrowser runs as a local Python server that the user opens in a browser.
That is a deliberate architecture, and this research does not propose changing it.
But two roadmap items — the
[VS Code extension host](../architecture/arch-vscode-extension-host.md) and the “other
trusted desktop integrations” it is meant to generalize — sit next to the question of
what a desktop shell would cost and buy, and the answer should be written down rather
than re-derived.

This document is the dated companion to the durable guideline,
`electron-app-development-patterns` (forked into `docs/tbd/guidelines/`), which carries
the prescriptive material.
The split follows the cadence rule in `common-doc-guidelines`: version numbers and
ecosystem state rot, so they live here with a date on them, and the guideline stays
version-independent.

## Questions to Answer

1. What is the current state of Electron and its build/packaging toolchain?
2. What are the general architectures for wiring an arbitrary backend — Node, Bun,
   Python, or a combination — into a desktop shell?
3. Are the lightweight alternatives (Tauri, Electrobun, Wails) yet credible for
   production?
4. What do shipping desktop apps actually do?
5. What, if anything, does this mean for Metabrowser?

## Scope

Included: desktop shells that render a web UI, their build and distribution pipelines,
and backend-integration patterns.

Excluded: native UI toolkits (SwiftUI, WinUI, GTK, Qt), mobile targets, and any
recommendation to change Metabrowser’s current architecture.

## Findings

### Version Snapshot

Versions as published on the npm registry on 2026-08-16. Re-check rather than trust this
table; it is a snapshot, not a maintained baseline:

```shell
npm view electron dist-tags
```

| Package | Current | Notes |
| --- | --- | --- |
| `electron` | 43.4.0 | Chromium M150, Node 24 |
| `@electron-forge/cli` | 7.11.2 | 8.0.0 is **alpha only** — full ESM, Vite 8 |
| `electron-builder` | 26.x | 27.0.0 in alpha |
| `electron-vite` | 5.0.0 | 6.0.0 in beta |
| `@electron/fuses` | 2.1.3 |  |
| `@electron/packager` | 20.3.0 |  |
| `electron-updater` | 6.8.9 | 7.0.0 in alpha |
| `vite` | 8.2.1 | Rolldown-based |
| `electrobun` | 1.18.1 | **Stable 1.x**, no longer beta |
| `@tauri-apps/cli` | 2.11.4 |  |

Electron ships a major roughly every eight weeks and supports the **latest three**. As
of this snapshot that is 43, 42, and 41; 41 leaves support at the end of August 2026.
The practical consequence is that an Electron app carries a standing upgrade obligation
of roughly one major every two months, or it ships known Chromium CVEs.

Two entries deserve emphasis because they invert prior guidance:

- **Electron Forge 8 is not released.** It exists only as alphas.
  Guidance that assumes a stable Forge 8 (full ESM packages, Vite 8/rolldown, Node
  ≥22.12) is premature; 7.11.x is what you actually install today.
- **Electrobun reached a stable 1.x** (announced February 2026, currently 1.18.1, with a
  2.x beta line). It is no longer a beta-quality bet, which is the single largest change
  in the alternatives landscape.

### Backend Architectures

The substantive gap in the previous guidance was that it treated “which package manager”
as the central decision while never addressing how non-JavaScript backend code attaches
to the shell at all.
That is the decision that actually shapes a standalone app.

Five patterns exist, covered prescriptively in the guideline: in-main, utility process,
loopback server, stdio child, and native addon.
The findings worth recording here:

- **`utilityProcess` supersedes `child_process.fork`** for Node-side background work.
  It launches via Chromium’s Services API, participates in Electron’s crash reporting
  and metrics, and can hold a `MessagePort` directly to a renderer so bulk data never
  transits the main process.

- **There is a non-obvious interaction between hardening and process spawning.**
  Disabling the `runAsNode` fuse — standard hardening, since it stops your signed binary
  being used as a generic Node interpreter — breaks `child_process.fork()`, which relies
  on `ELECTRON_RUN_AS_NODE`. `utilityProcess` is unaffected.
  Teams typically discover this when hardening a previously working app.

- **Stdio is under-rated relative to loopback HTTP** for non-Node backends.
  A loopback server has to solve port assignment, per-launch authentication, origin
  checking, and orphan cleanup — four problems that all exist because loopback is
  reachable by every process on the machine, including a web page in the user’s browser.
  A pipe is a capability, so stdio dissolves all four.
  Loopback earns its complexity when the backend is already an HTTP server or the app
  needs streaming.

- **Packaging a second runtime is where the real cost is**, and it is language-shaped.
  Bun’s `--compile` produces one self-contained executable.
  Go and Rust produce static binaries.
  Python is materially harder: directory-style builds are strongly preferred over
  one-file (which unpacks to temp on every launch and interacts badly with the macOS
  hardened runtime), and every nested `.so` inside the distribution must be individually
  signed or notarization fails.

### Alternatives

|  | Electron | Tauri 2 | Electrobun 1 | Wails | No shell |
| --- | --- | --- | --- | --- | --- |
| Renders with | Bundled Chromium | OS webview | OS webview or Chromium | OS webview | User’s browser |
| App code runs in | Node | Rust | Bun | Go | Anything |
| Rendering parity | Identical everywhere | Per-platform | Per-platform (or parity with Chromium) | Per-platform | Per-browser |
| Install size | Largest | Small | Small | Small | None |
| Update payloads | Large; differential helps | Small | Smallest (bsdiff deltas) | Small | N/A |
| Distribution maturity | Highest | High | Moderate | Moderate | N/A |
| Ecosystem size | Largest | Large | Small | Moderate | N/A |

The honest summary: **Electron’s remaining moat is rendering parity plus the most mature
signing and update pipeline**, not capability.
Tauri 2 is the credible default alternative for a new app.
Electrobun’s stable 1.x makes its delta-update story — dramatically smaller than
Electron’s — worth real evaluation rather than a footnote, at the cost of a much smaller
ecosystem to borrow solutions from.

### What Shipping Apps Do

The large production Electron apps (VS Code, Slack, Discord, Figma, Notion, Linear,
Obsidian, 1Password, Signal, Cursor) converge on the same shape, and it matches the
guideline’s prescriptions:

- A thin main process that supervises rather than works.
- Heavy work in separate processes — VS Code’s extension host is the clearest example,
  and it is the same pattern as a utility process or a sidecar.
- A renderer that is an ordinary web app, testable in a browser.
- Substantial investment in the packaged-artifact path, because that is where the bugs
  are.

They stay on Electron for rendering parity and distribution maturity, and they treat the
eight-week upgrade cadence as routine maintenance.
None of this argues that a new app should start on Electron; it argues that the
architecture above is what survives contact with scale.

## Key Insights

**The previous revision of the guideline was structured around the wrong question.** It
was organized as “which package manager works with Electron,” with Bun compatibility as
its spine.
That is a real but minor decision, and it is also the fastest-rotting material
in the document. The durable questions are process model, backend integration, security
posture, and distribution — which the previous revision covered in a single short
section or not at all.

**A large “verified fact” in the previous revision did not survive checking.** It
reported that Electron 39.x fails to initialize on macOS 14.6 while working on macOS
15.x, presented this as verified with a root-cause analysis, and propagated it into a
version-compatibility matrix.
Six months later there is no corresponding upstream issue, the “next actions” (reproduce
on a second machine, file upstream) were never completed, and Electron 39 is now out of
support. The reported symptom — `require('electron')` returning a string path and
`process.type` being `undefined` — is the *documented* behavior of Electron’s npm
package when the module is loaded under plain Node.js rather than the Electron binary,
which makes a local invocation difference the far more likely explanation than an OS
regression.

The transferable lesson is about document structure, not about that bug: a section
labeled **Verified Facts** invites unverified material to inherit its credibility.
Confidence is better expressed inline, next to each claim, where it can be checked and
corrected independently.

**Recency and reliability are not the same axis.** The previous revision cited Reddit
threads, a promotional dev.to post, and Stack Overflow answers alongside primary
documentation, under a heading that marked them as opinions but placed them in the same
document as the guidance.
In a document an agent will load as instructions, that distinction does not survive.
Primary sources — official docs, issue trackers with reproductions, the registry — are
the only things worth citing in a guideline.

## What This Means for Metabrowser

Nothing changes in the near term, and that is the finding.

Metabrowser’s current architecture — a local Python server the user opens in their own
browser — is the “no shell” column of the comparison table, and for a developer tool it
is a strong position: no signing, no notarization, no update pipeline, no Chromium to
ship, no eight-week upgrade obligation, and the renderer is genuinely a web app because
it is served to a real browser.

If a desktop shell is ever wanted, the work is already well-shaped for it:

- The server is a **loopback HTTP backend**, which is architecture 3 in the guideline.
  The gaps to close would be the ones that pattern always has: bind to port 0 and read
  the assigned port back, require a per-launch token, check `Origin`, and tie the
  child’s lifetime to the parent.
- The renderer boundary is already clean, since the browser shell talks to `/api/*` over
  HTTP and nothing else.
- Packaging would inherit Python’s difficulty, which is the hardest of the runtimes
  covered here — directory-style builds and per-`.so` signing on macOS.

The nearer-term roadmap item, the VS Code extension host, is a different shape and
unaffected by any of this.
Its “supervised authenticated server” design is the same hardening list as the loopback
pattern above, which suggests that work is worth doing in a host-neutral way — as
`arch-vscode-extension-host.md` already intends — so that any future desktop shell
reuses it rather than re-solving it.

## Open Questions

1. Is there real demand for a Metabrowser desktop shell, or does the browser-based model
   fully serve the audience?
   Nothing in the current roadmap requires one.
2. If a shell were wanted, would Tauri or Electrobun serve better than Electron, given
   that Metabrowser does not need Chromium rendering parity?
   Its renderer already targets whatever browser the user runs.
3. Does Electrobun’s delta-update mechanism hold up in practice at 1.x? It is the most
   differentiated claim in the alternatives space and the least independently verified.

## References

Primary sources only; see the guideline’s reference section for the full list.

- [Electron releases and support schedule](https://releases.electronjs.org/)
- [Electron security checklist](https://www.electronjs.org/docs/latest/tutorial/security)
- [Electron fuses](https://www.electronjs.org/docs/latest/tutorial/fuses)
- [Electron utilityProcess](https://www.electronjs.org/docs/latest/api/utility-process)
- [Electron ES modules](https://www.electronjs.org/docs/latest/tutorial/esm)
- [electron-builder application contents](https://www.electron.build/docs/contents/)
- [Electrobun v1 announcement](https://blackboard.sh/blog/electrobun-v1/)
- [Tauri 2](https://v2.tauri.app)
- [Bun single-file executables](https://bun.com/docs/bundler/executables)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
