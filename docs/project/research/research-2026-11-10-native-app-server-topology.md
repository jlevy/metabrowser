# Research: Server Topology, Lifecycle, and Agent Handoff for the Native App

**Date:** 2026-11-10

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Complete

Extends [Native macOS App for Metabrowser](research-2026-11-08-macos-app-packaging.md)
(2026-11-08), whose “Use Cases Under Exploration: Agent-Controlled Servers” and
“Security Models” sections laid out the options without choosing.
This brief answers most of the questions that section left open, with code reading,
measurements, and platform probes.

## Overview

The native macOS app spike (`apps/macos/`) runs one `metab` server per opened folder as
a child process and stops it when the folder’s last window closes.
That works, but it leaves the questions that decide whether the app feels instant:

- How should the app make switching between recently opened folders effortless, in one
  window or across many, as the user prefers?
- Should there be a server per window, per folder, or one shared server, and where
  should crawling run?
- Should the server’s lifetime be tied to the app, independent of it, or optionally
  decoupled?
- How does an agent show the user something, so that Metabrowser opens a folder or a
  file on request, and should the agent simply run the app?

This brief assumes `metab` is installed (a CLI install, the first step of the earlier
brief’s plan) and keeps the repository’s standing constraints: every capability is a
`metab` route or command with a golden transcript, shells add platform behavior only,
and the product is “effortlessly fast”, with no spinner within about 50 ms.

## Summary

- **Fast switching comes from warmth, not from the number of processes.** The spike
  already has a server per folder; switching back is slow because closing a window kills
  its server. A new server needs 0.7–1 s before it can answer and up to 30 s of one core
  to finish indexing 228,000 files (313,000 entries), while a request to a warm server
  takes 12–27 ms. Keep a folder’s index alive after its window closes, and discard web
  views first: each costs 155–210 MB against a server’s fixed cost of about 65 MB.
- **Warm is cheap on ordinary folders and not on log-heavy ones.** An idle warm server
  uses 0.2–0.8% of a core, but 11–17% indefinitely on trees with tens of thousands of
  files under `.logs` and `.state`, most likely because an activity tracker re-polls all
  of them every 5 s. Budget warm folders by measured idle CPU and footprint, and fix the
  tracker.
- **Make the contract “a root is an origin, listed in a registry”**, and keep the
  topology behind it reversible.
  Run a process per root: it needs no server refactor, runs walks in parallel, and
  isolates failures. Four servers started together are as fast as one, and memory adds up
  linearly. Two objections to one shared process failed when measured (a walk barely
  slows other requests in the same process, and closing a root’s runtime returned about
  84% of its memory), but it would save only the fixed cost per root.
  Consolidating roots that share a trust profile stays an option for later, chosen on
  memory if many warm folders become common.
- **The app owns servers by default, for privacy identity, not for lifetime.** macOS
  charges a server the app spawns to the app; it charges a server an agent starts to the
  agent’s host, which under Claude Desktop is a versioned binary that loses its grants
  on every update. Servers the CLI starts get an idle exit; a registry lets either side
  attach, and a per-root lock keeps a root to one live server.
  A login item is not needed yet.
- **Windows: native tabs across folders,** one shared `tabbingIdentifier`, a
  tabs-or-windows preference, and a quick switcher that lists open, warm, and recent
  folders.
- **Agents get one front door:** a `metab` client mode (named here
  `metab TARGET --present`) used through the skill.
  It hands the request to the app through LaunchServices, the way VS Code’s and Zed’s
  command-line tools reach their apps, or pushes a `navigate` event to a live root’s
  pages, or starts a server and opens a browser, or prints a link, and it reports which.
  Running the app’s executable directly is the wrong channel: it starts a second process
  instead of reaching the running one.
- **No probed sandbox lets a shell command launch the app.** Codex’s default also blocks
  loopback and sockets; Gemini’s default still reaches a live server; Claude Code’s
  sandbox, off by default, needs configuration.
  So `metab` runs outside the agent’s sandbox, as an excluded or approved command, or
  behind an optional MCP adapter, which Claude Code documents, and Codex’s source
  suggests, runs outside the sandbox (neither was run here).

## Questions to Answer

1. What makes switching between recent folders fast, in one window or in many?
2. A server per window, per folder, or one shared server?
3. Where and in what order should crawling run?
4. Who owns the server process, and how long does it live?
5. How does an agent ask Metabrowser to show something, and what happens when nothing is
   running?
6. Which channels can a sandboxed agent use?
7. What does each choice cost to change later?

## Scope

**In scope:** the macOS app over a CLI install; process topology; index lifetime;
process ownership and privacy attribution; the window and switching model; discovery and
the control plane; agent handoff, including sandboxed agents; measurements of what a
server costs on this hardware.

**Out of scope:** the app-managed runtime and distribution (the earlier brief); choosing
the security model, which is weighed here but still open; Windows and Linux; the design
of a persisted index; the project-plugin trust spec.

## Terms

- **Root:** a folder (or a Git pin) that a server serves and indexes.
- **Walk:** the server’s background crawl of a root: an FSEvents watcher plus a
  breadth-first scan that builds the in-memory index.
- **Open, warm, cold:** a root with a live web view and index; with an index and no web
  view; with neither, only a registry entry.
- **Origin:** scheme, host, and port.
  Each root has its own today, because each server has its own port.
- **Registry:** owner-only state files listing live servers, their roots, URLs, owners,
  versions, and boot ids, so the CLI, the app, and agents find what is running.
- **Present:** ask whatever is running to show a target (a root, a path, a line range)
  to the user.
- **Rendezvous:** a handoff in which the CLI opens a one-shot socket, passes only its
  name to the app in a URL, and receives the result over the socket.
- **Responsible process:** the process macOS’s privacy system (TCC) charges for a
  child’s file access, and in whose name it prompts.
- **Trust profile:** the per-process flags that change what a server may do, such as
  `--untrusted` and the plugin folders.

## Findings

### What a Server Does for a Root

Read from the source at `901ea3c0`.

- **The walk is eager, per process, and in memory.** The lifespan installs one recursive
  FSEvents watcher, waits for it, and starts the walker
  (`inventory_engine/providers/python_inventory.py`). The walker builds the gitignore
  matcher, then scans one directory at a time in a thread, but stores and aggregates
  every entry on the event-loop thread, where it competes with requests.
  It stops at 500,000 files.
  Nothing persists: two servers on one root each walk and watch, and a restart walks
  again. Only the Git and pull-request cache under `~/.cache/metabrowser` survives
  restarts and is shared across processes, with locks.
- **First paint never waits for the walk.** `/view/` inlines up to 200 root rows from
  whatever has been walked so far; Git and GitHub reads are lazy, and the page requests
  pull-request data in idle time after first paint.
- **Startup announces the port before binding it.** `metab` picks a port with a
  bind-and-release probe from 8411, prints `Serving … at URL`, and only then starts
  uvicorn, which runs the lifespan before it binds.
  Two concurrent launches can choose the same port (inferred).
  There is no ready event, health route, identity route, or `--port 0`.
- **What ties a process to one root:** the root global, imported by 14 modules including
  the plugin SDK, and the source session, used by 17. The inventory runtime and event
  bus already live on `app.state`, the coordinator can replace its root atomically, the
  GitHub checkout state is keyed by root, and the plugin registry does not depend on the
  root. The browser has about 87 absolute `/api` and `/view` literals and no root
  segment, so one origin per root is the cheap way to host several roots.
- **Nothing outside a page can change what it shows,** apart from file changes the
  watcher pushes and the mirror routes.
  There is no `navigate` event and no authentication: requests without `Origin` or
  `Sec-Fetch-Site` pass.
  Inside the page, `window.metabrowser.navigation.open()` exists.
  Pages are addressable as `/view/<percent-encoded segments>[/]#L10-L20`, so an agent
  could build a link if it knew the root’s port; nothing records it.
- **Folder pages reattach silently to whatever answers their port.** Only pin pages
  carry a token (the commit) that detects a different server.
- **The skill starts a new background server for every request** and reports its URL;
  `--api` and `--show` run in-process with their own walk and never reach a running
  server.
- **Related open work:** `mb-x4y5` (a VS Code host design, unimplemented, with a JSON
  ready event, an OS-chosen port, `/healthz`, and a one-time token); `mb-vmzy`
  (session-scoped root selection, the in-process multi-root precursor); `mb-jalf`
  (should the walk leave the serving process); H21 and `mb-omhf` (persist the index).

### What a Server Costs

Measured on an Apple M1 Pro (8 performance and 2 efficiency cores, 32 GB) running macOS
26.5.2 with the 0.12.0 release, with cache and config homes isolated in scratch
directories, while other agents kept the load average mostly between 13 and 20.
Tolerances follow the project’s policy: back-to-back pairs judged per pair, with 1.3x as
the rough-cut tolerance on a machine this loaded.
Each cell is the median and range of six runs, except idle CPU (two runs); the
footprints are midpoints of their ranges (67–74 MB medium, 415–444 MB large).

| Measure | Small (102 files) | Medium (this repository, 9,179 files indexed) | Large (a working repository, 227,705 files and 312,603 entries indexed) |
| --- | --- | --- | --- |
| Spawn to the `Serving` line | 0.80 s (0.58–2.34) | 0.67 s (0.58–0.75) | 0.92 s (0.59–1.51) |
| Spawn to the first `/view/` 200 | 0.90 s (0.67–2.44) | 0.77 s (0.67–0.85) | 1.03 s (0.69–1.61) |
| Walk complete | about 1 s | 1.3 s | 30.5 s (28–38) |
| CPU until the walk settles | 0.77 s | 0.98 s | 26.8 s, about 90% of one core |
| Peak RSS and footprint | 86 and 67 MB | 95 and 70 MB | 451 and 430 MB |
| A warm `/view/` plus `/api/tree`, median of 20 | 10 + 1.7 ms | 13 + 5.2 ms | 21 + 5.9 ms |
| Idle CPU over 60 s | 0.2–0.3% | 0.4% | 16–17%, steady |

- **Cost follows indexed files, not files on disk.** The walker skips hidden directories
  other than `.logs` and `.state`; the large tree holds 368,798 files and indexes
  227,705 of them.
- **Cold and warm caches are the same.** Serving a local folder writes nothing to disk,
  so there is no cache to warm.
  The OS file cache was warm in every run; a first launch after a reboot was not
  measured.
- **Servers in parallel cost almost nothing extra.** One or four small servers started
  together each reached `/view/` in 0.68–0.72 s; eight took 0.82–1.01 s, 1.3–1.5x. Four
  heavier folders (9,000–76,000 indexed files) started together finished in the slowest
  one’s solo time. Memory is strictly additive (88, 347, and 695 MB of RSS for one, four,
  and eight servers), and eight idle small servers used 2.2% of one core in total.
  Under memory pressure their RSS fell from 691 to 494 MB as macOS compressed idle
  pages, so budgets belong in footprint, not RSS.
- **Two servers on one root share nothing:** on the large tree, 2 × 27 s of CPU and 918
  MB, against 442 MB for one.
- **Idle cost follows files under `.logs` and `.state`.** A tree of 36,000 indexed files
  with none idled at 0.77% of a core; one of 76,000 with 31,000 such files at 11%; the
  large tree, with 35,000, at 16–17%. Every 5 s the activity tracker reads every
  trackable file under those directories from the catalog and polls each one
  (`active_tracker.py`); the correlation is measured, the cause read from the code, not
  profiled (`mb-z46o`).

Further probes, one or two runs each:

| Probe | Result |
| --- | --- |
| Walk of 387,255 entries (295,396 files) | 26–44 s; 43.8 s with an event-stream client attached against 26–33 s without, consistent with `mb-jalf` (50 s against 21 s) |
| Memory per indexed entry | about 1–2 KB over a baseline of 60–100 MB: 87 MB for this repository (9,179 files); 439–568 MB at 387,000 entries; a running server at 313,000 entries held 665 MB |
| Request latency during a 295,000-file walk in the same process | cheap routes p95 6–14 ms, against 2–5 ms after the walk; uncached Markdown renders about 15% slower per byte (n=15) |
| A walk in another process | no effect on a foreground server’s renders (99.5 against 104.6 ms per 100 KB) |
| Closing a large root inside a shared process | two inventory runtimes in one process; closing the 387,255-entry one took the footprint from 378 to 86 MB and from 399 to 87 MB within 6 s, about 84% of its share (a 75-entry runtime alone is 28–29 MB) |
| Replacing a large root inside one runtime | `replace_root` to a 75-entry root left 172–173 MB after 12 s, about 61% of the share returned |
| Web views | 155–210 MB per window’s WebContent process with real pages; the GPU and networking processes are shared (32 and 13 MB) |

Two of these went against expectation.
Loop contention, the obvious objection to one process holding several roots, barely
moved foreground latency at one walk; the cost lands on the walk itself.
And closing a runtime returns most of its memory, so a shared process can evict, as long
as it closes runtimes rather than replacing a root in place.
Both rest on thin evidence: single runs, a sequential client, and an inventory without
the rest of the server’s caches.
Set against them, the fixed cost a shared process would save is small: about 65 MB of
footprint and 1 s of CPU per root, while index memory (1–2 KB per entry) and walk CPU
(about 0.1 ms per entry) are paid per root in any topology.

### What macOS Decides

Probed on macOS 26.5.2 by reading each process’s responsible process (a read-only
private call), plus Apple documentation and Apple DTS forum posts.

| How the server starts | macOS charges privacy access to |
| --- | --- |
| The app spawns it (the spike today) | the app (observed). Other apps’ helpers reparented to launchd still report their app; the spike’s server was not tested detached, and DTS warns that daemonizing often breaks the link |
| An agent’s shell starts it | the agent’s host: under Claude Desktop, a versioned `claude` binary, so grants are lost on each update; under Codex, ChatGPT.app |
| Terminal starts it | Terminal |
| An `SMAppService` agent the app registers | the app, per DTS (2024); in 2026 DTS called tracing a daemon to its app “rather limited”, and a bare executable in `Contents/MacOS` worked where a separate helper bundle did not; a script cannot be charged to any product |
| The app is launched through `open` or `NSWorkspace` | the app |

- **Open-panel grants reaching a child are still untested.** For an unsandboxed app the
  grant is a `com.apple.macl` extended attribute keyed by the app, not a TCC database
  row, and no source says whether a child benefits.
  The worst case is one prompt per protected location, in the app’s name.
- **`responsibility_spawnattrs_setdisclaim`** makes a child its own responsible process.
  It is undocumented, and a disclaimed `python3` would become an unsigned identity keyed
  by its path, the cause of lost-grant reports elsewhere.
  Not for this app.
- **App Nap does not reach a child server.** The kernel copies a parent’s QoS clamp but
  not its role to children; the spike’s server stayed at normal priority while the app
  moved between focal and non-focal.
  A warm server keeps crawling when the app is hidden, so the app must pace walks
  itself.
- **Hidden web views are throttled.** A hidden window’s web process dropped to
  background priority within a second.
  A web view removed from its window is suspended by default
  (`WKPreferences.inactiveSchedulingPolicy`), which would stop its event stream, so a
  sidebar switcher must change that policy.
- **Cookies are shared across ports.** Every `127.0.0.1` server shares one cookie jar
  (RFC 6265 §8.5). Preferences stored as cookies therefore carry across servers today,
  and a session cookie with a fixed name would collide.
  Name cookies by port or boot id, or give a root with a different trust profile its own
  `WKWebsiteDataStore`.
- **Window tabs are free.** With `tabbingMode` automatic and one shared
  `tabbingIdentifier`, macOS supplies the tab bar, Merge All Windows, Move Tab to New
  Window, tab dragging, and the system “prefer tabs” setting.
  The spike uses one identifier per folder, which keeps folders from merging.
  `NSDocumentController.noteNewRecentDocumentURL` gives the Dock and File menu recents
  without `NSDocument` (that folders qualify is inferred).
- **Second launches are already forwarded** by LaunchServices as Apple Events to the
  running instance; a second process starts only with `open -n`, a direct exec, or a
  second copy. Two installed copies with one bundle id share defaults and Application
  Support, so development builds need their own bundle id and URL scheme, and any lock
  on server ownership must be keyed to the user, not the copy.
- **Opening things in a running app:** `open -a` delivers paths only, and its `--args`
  reach only a new process; a custom URL scheme carries any data but any process can
  fire it, web pages after a browser prompt, and if two apps claim it the target is
  undefined; a Unix socket carries anything with replies, between processes of the same
  user, and its path is limited to 104 bytes; a named XPC service needs a launchd job; a
  distributed notification reaches only a running, active app, one way, and may be
  dropped. VS Code’s command-line tool always starts the app through `open -n -g -a`, so
  the app rather than the terminal is charged, then forwards its arguments over a
  per-version socket.

### What Agents Can Reach

Codex 0.157.0 and Gemini CLI 0.62.0 profiles were probed; Claude Code’s sandbox runtime
was read at source (`f7a0f19`).

| Channel | Unsandboxed | Codex default | Claude Code sandbox | Gemini default profile |
| --- | --- | --- | --- | --- |
| Launch an app (`open -a`, a URL scheme) | yes | no | no, unless `allowAppleEvents` | no |
| Connect to `127.0.0.1` | yes | no | through its proxy if allow-listed, or with `allowLocalBinding` | yes |
| Listen on loopback | yes | no | with `allowLocalBinding` | yes |
| Connect to a Unix socket | yes | no, unless allowed per directory | no, unless the path is in `allowUnixSockets` | yes |
| Post a distributed notification | yes | no | yes | not checked |
| Run a local MCP server | yes | outside the sandbox (inferred from source) | outside the sandbox (documented) | not checked |

- Claude Code’s sandbox is off by default; `excludedCommands: ["metab *"]` runs `metab`
  outside it through the normal permission flow.
  Codex offers per-prefix approval.
- **A CLI driven through a skill is the channel coding agents use most reliably**;
  Playwright’s documentation now recommends its CLI for coding agents and MCP for
  specialized loops. MCP serves agents without a shell, and is how JetBrains, Figma, and
  Chrome DevTools expose running apps; JetBrains’ tools take a `projectPath` argument to
  choose the window.
- **Vendors mostly hand the user a link:** Codex renders file citations as `vscode://`
  or `cursor://` links that the user clicks.
- **Local control surfaces are a recurring bug class:** Zoom’s port-19421 server, MCP
  Inspector before 0.14.1, and Claude Code’s IDE WebSocket before 1.0.24 each accepted
  requests from web pages.
  The rules that follow: no side effects on `GET`, a token or a non-simple header on
  every control route, an `Origin` check on event streams, and the Host allowlist.
  The MCP specification requires `Origin` validation for HTTP servers and recommends
  stdio for local ones.
- **A URL scheme must carry no authority.** Any local process or a clicked link fires it
  without a prompt. Zed’s command-line tool passes only a rendezvous name in
  `zed-cli://`, and the app connects back for the real request.

### What Comparable Apps Do

| Question | What they do |
| --- | --- |
| Processes for many projects | Apps running only their own code use one process with per-project state: Zed, JetBrains (one JVM, an application-wide index with a task queue per project), Sublime, Finder, Xcode. Separate processes isolate third-party code: VS Code’s extension host per window, Chrome’s renderers, JupyterLab Desktop’s server per session window |
| Fast switching | Zed keeps recently used workspaces live in one window and drops unpinned ones; VS Code’s same-window switch reloads and restores from disk; JetBrains keeps other projects live in its JVM. Chrome keeps a spare renderer started, and JupyterLab Desktop pre-launches “free” servers to cut load times |
| One window or many | A preference with a per-action override: Zed’s `cli_default_open_behavior` (asked on first CLI use), JetBrains’ New, Current, or Ask, VS Code’s `window.openFoldersInNewWindow`. JetBrains and VS Code support macOS native tabs. A folder already open gets its window focused |
| Indexing several projects | One bounded pool with the focused project first; none index closed projects; JetBrains persists its index |
| Server lifetime | Ollama and Livebook stop the server with the app; LM Studio keeps serving from the menu bar and can start at login; Postgres.app’s servers outlive the app until its menu helper quits; Docker Desktop’s Resource Saver stops the VM when idle and restarts it in 3–10 s |
| Handoff from a CLI | VS Code and IntelliJ forward arguments over a socket in the user data directory and clean up stale ones; Zed’s rendezvous returns output and an exit code; Livebook queues URLs until its server is ready; VS Code gives each integrated terminal its window’s socket in `VSCODE_IPC_HOOK_CLI` |

One counterexample: Ollama sends SIGTERM to any `ollama serve` holding its port, which
would kill a server a user or agent started.
The app should never signal a server it did not start.

## Key Insights

The question bundles seven decisions, and its framing conflates several of them:

| Axis | The decision | Today |
| --- | --- | --- |
| Topology | which process owns a root’s index, and which origin serves it | a process and port per root |
| Warmth | how long an index and a web view live | both die with the last window |
| Ownership | who starts a server, whom macOS charges, who outlives whom | app children, orphaned if the app crashes |
| Windows | how roots map to windows and tabs | a window per root |
| Control plane | how a client finds what runs and asks it to show something | none |
| Authority | which roots may be served, and who may add one | any path from any local process |
| Address | whether a root keeps its URL across restarts | a port walk from 8411 |

- **“A server per folder so switching is quick” confuses topology with warmth.** The
  spike has a server per folder and switches back slowly, because it kills them.
- **“So crawling can happen in sequence” is a scheduling policy.** Separate processes
  allow walks in parallel on separate cores; one process runs every walk through one
  event loop. Either can order walks, frontmost first.
- **“A single server” and “a single crawling process” are different things.** One place
  to ask (the control plane) does not require one owner of every index.
- **“Tied to the app or a different lifecycle” splits three ways:** who starts a server
  (which sets its privacy identity), how long it lives (an idle policy), and who may
  attach (the registry).
  “Optionally decoupled” falls out of a registry and an idle exit and needs no daemon.
- **“The agent connects to the server or controls the UI” splits into reading and
  presenting.** Agents already read in their own process through `--api`; presenting
  reduces to opening a URL-shaped target.
- **A server per window is dominated:** two windows on one root would walk twice.
- **Warm means two things:** a live index and a live web view have different costs, and
  web views, not servers, bound how many folders can stay open.

## Options Considered

### Topology

| Option | Mechanism | Fails how | Cost to change later |
| --- | --- | --- | --- |
| **A1: a process per root** (today) | today’s server plus host mode | about 65 MB of footprint and 1 s of CPU per root; a 0.7–1 s spawn per cold root; overlapping roots walk twice | none |
| **A2: one process, one origin** (the earlier brief’s option S) | a root segment in every URL | as A3, and it removes per-root origin isolation and touches about 87 browser literals | large |
| **A3: one process, an origin per root** | a listener per root, with the root taken from request context | one hang freezes every window; walks share one loop; one trust profile per process | moderate to large on the server (the root global and source session), none in the browser |
| **A4: a hub over A1** | a supervisor process with one control address | a new daemon with its own lifecycle and version skew | additive |

A1 and A3 look the same to the page and to a shell: a root is an origin taken from a
registry. That keeps the choice reversible, as long as the shell closes a root through a
verb and does not assume a process per root.
A1 alone gives failure isolation and parallel walks: on this machine a day-old server
accepted connections but answered none of 8 requests in 20 s, and the app’s servers on
the next ports were unaffected (cause not diagnosed; its output goes to a terminal, so a
full pipe does not explain it).
Four heavy folders started together finished in the slowest one’s solo time, which one
event loop is unlikely to match (not measured).
What A3 would save is the fixed cost: about 65 MB and 1 s of CPU per extra root, or
about 0.5 GB with eight warm folders.

### Warmth

| Tier | Holds | Fixed cost per root | Reopening costs |
| --- | --- | --- | --- |
| **Open** | a web view and a live index | 155–210 MB of WebContent, plus the index | nothing |
| **Warm** | a live index, no web view | about 65 MB under A1, a few MB under A3, plus 1–2 KB per entry; 0.2–0.8% of a core idle, or 11–17% on log-heavy trees | a page load from a warm server (unmeasured in WebKit) |
| **Cold** | a registry entry | nothing | a spawn (0.7–1 s to first paint) and a full walk |

- **Linger and restore:** keep a root warm after its last window closes, capped by the
  server’s measured footprint and idle CPU, and evict the least recently shown.
- **Discard web views** of background tabs beyond a small number; a discarded tab
  reloads from its warm server.
- **A rootless, pre-imported process** removes the spawn floor for cold roots; the
  lifespan already tolerates no root.
  This is also the first step toward A3.
- **A persisted index** with FSEvents replay would make cold nearly as fast as warm.
  It reverses a stated non-goal and stores private file names, so it needs owner-only
  storage and its own design.

### Ownership

| Option | Charged to | Lifetime | Cost |
| --- | --- | --- | --- |
| **C1: app-owned children** | the app, stably | until the app quits, or idle eviction | needs exit on stdin EOF so a crashed app leaves no orphans |
| **C2: CLI-detached** | the agent’s host or the terminal | forever, unless it has an idle exit | unstable privacy identity under agent apps |
| **C3: a login item** (`SMAppService`) | the app | always on | a user-visible background entry, a restart protocol after updates, and attribution to verify on macOS 15, 26, and 27 |
| **C4: owner-agnostic** | whoever started it | per owner | every server writes the same registry entry, with its owner as a field |

### Windows and Switching

| Option | What the user gets | Cost |
| --- | --- | --- |
| **D1: a window per root** (today) | separate windows only | none |
| **D2: native tabs across roots** | one shared `tabbingIdentifier`: tabs or windows by system setting or app preference, Merge All Windows, drag a tab out | a shell-only change |
| **D3: one window with a sidebar of roots** (Zed’s model) | a built-in project list | custom split view; detached web views need a different scheduling policy |
| **D4: a switcher served by `metab`** | the same recents list in the app and in a browser tab | a roots route, and admitting sibling origins in the app’s navigation policy |

### Control Plane

| Transport | Reaches | Replies | From a default agent sandbox |
| --- | --- | --- | --- |
| `open -a Metabrowser PATH` (works today, folders only) | the app, starting it if needed | no; drops the selection and flags | fails |
| `metabrowser://` carrying the request | the app | no | fails; fireable by pages and links, so it may carry no authority |
| Rendezvous through LaunchServices (Zed) or `open` then a socket (VS Code) | the app, starting it if needed | yes | fails |
| A server’s control verbs over an owner-only Unix socket | a live server | yes | fails under Codex and Claude Code unless the path is allowed; works under Gemini’s default |
| Loopback HTTP with a token | a live server | yes | fails under Codex; needs configuration in Claude Code; works under Gemini’s default |
| A distributed notification | a running, active app | no; one way, may be dropped | passes Claude Code’s sandbox runtime, not Codex |
| An MCP stdio adapter over the same routes | whatever `metab` reaches | yes | outside the sandbox in Claude Code (documented) and Codex (inferred from source) |
| A printed link the user clicks | the app or a tab | no | always works |
| Executing the app binary | a second instance | no | wrong: bypasses LaunchServices and makes the caller the responsible process |

## Recommendations

1. **Contract:** a root is an origin, listed in a `metab` registry with identity,
   health, version, owner, and a boot id, at most one live server per root, and a small
   set of verbs: identity, present, clients, and close, plus open when a spare process
   arrives (Phase 3).
2. **Topology:** a process per root.
   A shared process for roots that share the default trust profile is a later option,
   taken only if many warm roots make the 65 MB fixed cost matter and the gates below
   pass.
3. **Warmth:** three tiers, with web views scarce and indexes generous; a persisted
   index is the end state.
4. **Ownership:** servers the app starts are its children; servers the CLI starts have
   an idle exit; nothing ever signals a server it did not start; no login item yet.
5. **Windows:** native tabs across roots, a tabs-or-windows preference, per-request
   overrides, and a quick switcher over open, warm, and recent roots.
6. **Control:** one CLI front door that carries intents, not content: present, close,
   identity, and later open.
   Agents keep reading through `--api` in their own process.

### Phasing from the Spike

**Phase 0: shell only.**

- Keep a server running after its folder’s last window closes; cap warm roots by each
  server’s measured footprint and idle CPU; evict the least recently shown; stop all on
  quit.
- Use one `tabbingIdentifier` with a tabs-or-windows preference, and discard the web
  views of background tabs beyond a small number.
- Add a quick switcher (open, warm, and recent roots, searchable) and register folders
  with `NSDocumentController` so the Dock and File menu show recents.
  Until Phase 2 serves the roots list from a route, the switcher’s membership and order
  are a named shell-only exemption in the parity table.
- Restore the last session lazily: recreate its tabs, start the front tab’s server, then
  the others one at a time, and none in a protected location until its tab is selected.
  The launch gate that serializes starts becomes the crawl scheduler.
- Accept a file from `open -a` and select it inside its folder, instead of refusing it.
- Health-check a server with a deadline before attaching a window.
  Send the server’s stderr straight to its log file instead of through a pipe the app
  drains, so a stalled app cannot block it; stdout stays a pipe for the `Serving` line,
  and later the JSON ready line.

**Phase 1: host mode and the registry in `metab`** (the earlier brief’s layering item 1,
extended).

- **Server:** a sticky port (the registry remembers a root’s port; fall back to one the
  OS chooses), a JSON ready line after bind, a token on stdin, exit on stdin EOF,
  `--idle-exit`, and the control verbs only (identity, present, clients, close) on an
  owner-only Unix socket, whose path must fit macOS’s 104-byte limit.
  Content routes stay on loopback behind the page token.
- **Routes:** identity and health; `present`, which pushes a `navigate` event to the
  most recently visible of the root’s connected pages; `clients`; and `close`.
- **Registry:** one owner-only state file per live process, written after bind and
  listing its roots; readers drop dead process ids and failed identity probes.
  A per-root lock serializes find-or-start, so a root has at most one live server.
- **Page:** follow `navigate`, reload once on a new boot id, and refuse a root mismatch.
- **Client mode:** `metab TARGET --present` (name open), with `--new-window`.
- **App:** register the `metabrowser://` scheme (the spike’s `Info.plist` declares none
  and its delegate drops non-file URLs), a rendezvous handler that replies with what it
  did, and the owner and version shown per window.

**Phase 2: roots as state.** Recent and added roots move from the app’s defaults into
`metab` state with provenance, served by a route so a browser tab gets the same
switcher. Apply the security policy chosen for adding roots.
Add the optional MCP stdio adapter, with each tool naming one route.

**Phase 3: measured.** A rootless, pre-imported spare process with an `open` verb, which
takes one root at a time and removes the spawn floor for cold roots, as JupyterLab
Desktop’s pre-launched servers do.
The spare serves default-profile roots only and binds the root’s sticky port when it
opens it.
One spare covers one cold open and then takes 0.7–1 s to replace, so a burst of
opens still meets the floor.
If many warm roots make the fixed cost matter, the same process takes further roots of
the same trust profile, each with its own listener and its own runtime, closed rather
than replaced. A persisted index follows if re-walks remain common.

**Gates before one process holds several roots:**

- With two walks running and a real page attached, foreground p95 stays under 50 ms.
- Five open-and-close cycles of a large root in a full server, with its render and
  rollup caches, leave the footprint within 1.2x of the first residue.
- A hung shared process is detected and restarted within a few seconds, and re-walking
  its roots is acceptable without a persisted index.
- A log-heavy root’s activity-tracker tick, whose catalog read and patch run on the
  event loop, does not raise other roots’ p95.

### Falsifiable Claims

1. After Phase 0, switching to a tab with a live web view takes under 50 ms and to a
   warm root under 300 ms; today a closed root takes at least 0.7 s plus a walk.
2. Through Phase 1, the footprint stays under (live web views × 210 MB) + (live servers
   × 70 MB) + (indexed files × 2.2 KB) + 100 MB for the app and the shared WebKit
   processes.
3. After Phase 1, `--present` returns in under 1 s when the root is live, which requires
   the client mode not to import the server (`metab --version` alone took 0.36–0.52 s
   here), and no CLI-started server outlives its idle timeout.
4. After Phase 3’s first step, a cold root paints in under 300 ms.

### CLI Parity

| New surface | `metab` equivalent | Evidence |
| --- | --- | --- |
| identity, health, `clients`, `close`, and later `open` | routes reached through `--api` | goldens |
| `present` and the page’s follow logic | a route and the client mode | a golden, and a browserless golden session against the production JavaScript |
| The live-server registry | a listing mode with `--json` | a golden against a fixture runtime directory |
| Persisted roots | list, add, and remove over routes | goldens |
| Idle exit, stdin EOF, ready line | serve flags | a reference-host test |
| The MCP adapter | each tool names one registered route | `devtools/check_parity.py` |
| The Phase 0 quick switcher’s membership and order | an interim shell-only exemption, replaced by the roots route in Phase 2 | `ShellCore` tests |
| Tabs, web-view discarding, window fronting, LaunchServices delivery, consent sheets | shell-only exemptions, each named | the QA playbook and `ShellCore` tests |

Fleet policy (warm caps, restore order) stays in the shell until a second shell needs
it.

### “Show X” End to End

1. The agent runs `metab /repo/docs/plan.md#L40 --present` through the skill, outside
   its sandbox as an excluded or approved command, or calls the MCP adapter.
   To read the file, it keeps using `--api` in its own process.
2. `metab` resolves the target to a root and a view address: the most specific
   registered root that contains the path, else today’s rule (a file serves its folder).
3. **The app is installed and preferred** (a stored preference): `metab` opens a
   one-shot socket and passes its name to the app through LaunchServices, which starts
   the app if needed. The app queues the request until its runtime is ready, finds the
   root’s live server (attaching to one it does not own, and showing its owner) or
   starts one as its own child (so privacy prompts name the app, with a stable
   identity), presents the target, fronts its tab, and replies with the root, URL,
   owner, and where it was delivered.
4. **No app, root live:** `metab` calls `present` on that server.
   A connected page navigates; with none, `metab` opens the browser.
5. **Nothing running, no app:** `metab` starts a server detached in its own session with
   an idle exit (charged to the agent’s host, so privacy prompts may recur), waits for
   the ready line, opens the browser through a one-time login URL, prints the plain URL,
   and exits.
6. **Blocked:** with the app installed, `metab` prints a `metabrowser://` link that
   opens a registered root directly and a new root only after an in-app confirmation;
   without the app, it prints the command for the user to run outside the sandbox.
   It exits with a distinct code and never claims to have shown anything it did not.

Because each root has its own origin, “which window” is answered by the pages connected
to that root. This also answers “should the agent call the app binary”: the agent calls
one command that opens the native app whenever it is installed, but that command is
`metab`, and it reaches the app through LaunchServices.

## Where This Breaks

- **Web views are the ceiling in any topology.** Ten open tabs are 1.5–2 GB of
  WebContent. If a discarded tab reloads slowly from a warm server in WebKit, the warm
  tier loses most of its value.
- **Overlapping roots** (`/repo` and `/repo/docs` opened separately) hold two indexes
  unless the registry resolves the narrower one into the wider.
- **Default sandboxes** block launching the app, and most block the rest, so
  “effortless” depends on configuration outside Metabrowser’s control; the MCP adapter
  is the mitigation, still unverified here.
- **Version skew grows with lifetime.** A warm server survives a `uv tool upgrade` it
  should not, and restarting it costs a re-walk until an index persists.
- **Large roots on small Macs:** three 300,000-entry roots are about 1.5 GB in any
  topology.
- **Log-heavy folders are expensive to keep warm** until the activity tracker stops
  re-polling every candidate (`mb-z46o`); a fixed warm count would let a few such
  folders use a core between them.
- **Tokens across ports:** a cookie-borne token would reach every sibling server,
  including one serving untrusted content.
  Name cookies per server, or give odd-trust roots their own data store.
- **A browser cannot be fronted:** `present` can navigate a hidden browser tab; only the
  app can raise a window.
- **The case for consolidating now:** one process would open any folder in milliseconds,
  give one address to agents and tabs, and host a single browsing context and search
  across folders, while Phase 1 is a set of small distributed-systems problems (stale
  state files, process-id reuse, start races, a reaper).
  The answer here is that the evidence for consolidation is thin and the registry
  contract keeps the door open, so the gates come first.

## Open Questions

- Does a folder chosen in the app’s Open panel cover a child server, or does each
  protected location prompt once?
  (Test with a Developer ID build and a test account.)
- How fast does WebKit reload a discarded tab from a warm server?
- Do eviction and contention hold in a full server, with render and rollup caches, two
  concurrent walks, and a real page?
- Why does `replace_root` keep about 85 MB more than closing a runtime?
  This matters to `mb-vmzy`.
- What hung the day-old server, and would a hung shared process be detected in time?
- Which security policy applies to roots that arrive by agent request (see the earlier
  brief’s Security Models)?

## Next Steps

- [ ] Extract the decisions into a plan under `docs/project/specs/active/`, with Phase 0
  as its first part, and track each phase as beads.
- [ ] Implement Phase 0 in the spike and verify the first falsifiable claim.
- [ ] Fix the activity tracker’s idle cost (`mb-z46o`) before warm folders ship.
- [ ] Fold host mode and the registry into `mb-x4y5`’s draft host design, so the VS Code
  host and the app share one protocol.
- [ ] Measure the open questions above before Phase 3.
- [ ] Update the skill to use the front door once it exists, and document the sandbox
  settings (`excludedCommands`, Codex prefix approval) it needs.

## Methodology

Five research tracks and a design review ran in parallel on 2026-11-10:

- **Code:** the server, shell, and skill read at `901ea3c0`, with line citations.
- **Measurements:** the installed 0.12.0 release on small, medium, and large roots, cold
  and warm caches, one to eight concurrent servers, and idle cost over 60 s, with
  isolated cache and config homes and ports far from the user’s servers; 88 servers in
  all, each confirmed stopped.
- **Precedents:** VS Code, Zed, JetBrains, Sublime, Obsidian, Finder, Xcode, Chrome,
  Ollama, LM Studio, Postgres.app, Docker Desktop, JupyterLab Desktop, Livebook, and
  Tailscale, read at pinned tags and commits.
- **macOS:** responsible-process probes, throttling observations, Apple documentation,
  DTS posts, and XNU source; no registrations or persistent changes.
- **Agents:** Codex and Gemini CLI sandbox probes, Claude Code’s sandbox runtime at
  source, and agent-vendor documentation.
- **Design review:** an independent first-principles review that decomposed the
  decision, proposed thresholds that would flip each choice, ran its own latency and
  memory probes, and argued against its own recommendation; it was revised once the
  other tracks reported.

**Not tested:** Open-panel grants for child processes; attribution under a Developer ID
build or on macOS 15 and 27; WebKit tab reload times; a full server under repeated
eviction; two concurrent walks in one process with a real page; a first launch with a
cold OS file cache; MCP servers running outside each agent’s sandbox.

## References

- Earlier briefs:
  [Native macOS App for Metabrowser](research-2026-11-08-macos-app-packaging.md),
  [Desktop App Packaging](research-2026-08-16-desktop-app-packaging.md)
- Repository: [Views, Models, and Routes](../architecture/arch-views-models-routes.md),
  [rendering large content](../../large-content-rendering.md), `apps/macos/README.md`,
  `skills/metabrowser/SKILL.md`
- Apple:
  [SMAppService](https://developer.apple.com/documentation/servicemanagement/smappservice),
  [tabbingMode](https://developer.apple.com/documentation/appkit/nswindow/tabbingmode-swift.property),
  [noteNewRecentDocumentURL](https://developer.apple.com/documentation/appkit/nsdocumentcontroller/notenewrecentdocumenturl(_:)),
  [inactiveSchedulingPolicy](https://developer.apple.com/documentation/webkit/wkpreferences/inactiveschedulingpolicy-swift.property),
  [WKWebsiteDataStore(forIdentifier:)](https://developer.apple.com/documentation/webkit/wkwebsitedatastore/init(foridentifier:)),
  [WKProcessPool](https://developer.apple.com/documentation/webkit/wkprocesspool); DTS
  threads [756510](https://developer.apple.com/forums/thread/756510),
  [678819](https://developer.apple.com/forums/thread/678819),
  [731504](https://developer.apple.com/forums/thread/731504),
  [853725](https://developer.apple.com/forums/thread/853725),
  [769918](https://developer.apple.com/forums/thread/769918),
  [124121](https://developer.apple.com/forums/thread/124121);
  [XNU task_policy.c](https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/kern/task_policy.c);
  [Qt on the responsible process](https://www.qt.io/blog/the-curious-case-of-the-responsible-process);
  [Eclectic Light on the MACL attribute](https://eclecticlight.co/2026/04/21/the-macl-extended-attribute/);
  [RFC 6265 §8.5](https://www.rfc-editor.org/rfc/rfc6265#section-8.5)
- Agents and sandboxes:
  [Claude Code sandboxing](https://code.claude.com/docs/en/sandboxing),
  [sandbox-runtime at f7a0f19](https://github.com/anthropic-experimental/sandbox-runtime/blob/f7a0f19fd3b4437bcf808f9c18c1f73e9f1a9889/src/sandbox/macos-sandbox-utils.ts),
  [Codex Seatbelt policy](https://github.com/openai/codex/blob/ac54a05173d090b9fdfa181ea49b92f45aff2681/codex-rs/sandboxing/src/seatbelt.rs),
  [Gemini CLI sandbox](https://geminicli.com/docs/cli/sandbox/),
  [Playwright CLI](https://playwright.dev/agent-cli/introduction),
  [JetBrains MCP server](https://www.jetbrains.com/help/idea/mcp-server.html),
  [MCP Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md),
  [MCP security best practices](https://modelcontextprotocol.io/specification/latest/basic/security_best_practices),
  [Chrome Local Network Access](https://developer.chrome.com/blog/local-network-access),
  [Datadog on CVE-2025-52882](https://securitylabs.datadoghq.com/articles/claude-mcp-cve-2025-52882/),
  [Oligo on CVE-2025-49596](https://www.oligo.security/blog/critical-rce-vulnerability-in-anthropic-mcp-inspector-cve-2025-49596),
  [FastMCP from OpenAPI](https://gofastmcp.com/integrations/openapi)
- Precedents:
  [VS Code main process](https://github.com/microsoft/vscode/blob/1.145.3/src/vs/code/electron-main/main.ts#L352-L480),
  [VS Code CLI](https://github.com/microsoft/vscode/blob/3cb23da891/src/vs/code/node/cli.ts),
  [VS Code window selection](https://github.com/microsoft/vscode/blob/1.145.3/src/vs/platform/windows/electron-main/windowsMainService.ts#L671-L679),
  [Zed CLI](https://github.com/zed-industries/zed/blob/v1.27.0/crates/cli/src/main.rs#L584-L603),
  [Zed multi-workspace](https://github.com/zed-industries/zed/blob/v1.27.0/crates/workspace/src/multi_workspace.rs#L295-L303),
  [Zed windows and projects](https://zed.dev/docs/windows-and-projects.html),
  [IntelliJ DirectoryLock](https://github.com/JetBrains/intellij-community/blob/bff0637366fd7be895085563b56e4711f4f89423/platform/platform-impl/bootstrap/src/com/intellij/platform/ide/bootstrap/DirectoryLock.java#L63),
  [JetBrains projects](https://www.jetbrains.com/help/idea/open-close-and-move-projects.html),
  [Sublime indexing](https://www.sublimetext.com/docs/indexing.html),
  [Obsidian URI](https://obsidian.md/help/Extending+Obsidian/Obsidian+URI),
  [Chrome process model](https://chromium.googlesource.com/chromium/src/+/main/docs/process_model_and_site_isolation.md),
  [Ollama app server](https://github.com/ollama/ollama/blob/v0.40.16/app/server/server.go#L109-L280),
  [LM Studio headless](https://lmstudio.ai/docs/app/api/headless),
  [Postgres.app](https://github.com/PostgresApp/PostgresApp/blob/v2.9.6/Postgres/AppDelegate.swift#L202-L209),
  [Docker Desktop settings](https://docs.docker.com/desktop/settings-and-maintenance/settings/),
  [JupyterLab Desktop](https://github.com/jupyterlab/jupyterlab-desktop/blob/master/user-guide.md),
  [Livebook Desktop](https://github.com/livebook-dev/livebook/blob/v0.19.10/rel/app/macos/Sources/Livebook/Livebook.swift#L22-L127)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
