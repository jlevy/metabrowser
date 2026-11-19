# Feature: Host Mode

**Date:** 2026-11-18

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Decided, and nothing but the stdin lifeline, `--exit-on-eof`, is built.
The owner took Decisions HM-1 to HM-6 under [Key Decisions](#key-decisions) on
2026-11-19, each as this plan recommended, and the beads were split the same day to
follow [HM-1](#decision-hm-1-when-discovery-lands) A, so agents can find a server before
the credential is built.
Clarifications dated 2026-11-19, from an independent review, are marked at the decisions
they touch.
What the [native macOS app plan](plan-2026-11-10-native-macos-app.md) decided
stays decided, and [Settled Decisions](#settled-decisions) cites it.
A companion to
[View Model and View State](plan-2026-11-18-view-model-and-view-state.md),
[Agent Interface for Objects and View State](plan-2026-11-18-agent-interface.md), and
the [implementation map](plan-2026-11-18-object-model-implementation-map.md).
Written against `main` at `42e4bd1bb`.

## Overview

The Metabrowser UI is a standalone web app that a `metab` server serves.
A **host** is any program that starts a server, owns its process, and shows its pages: a
shell with a browser tab, the macOS app, a VS Code extension, or a host not written yet.
**Host mode** is the contract between `metab` and a host, and the way an agent finds and
reaches a server however it came to exist.

The owner asked:

> “We should make sure everything is self-documented via the CLI, and it works to run
> the UI standalone as a web app within the Mac OS app (or perhaps within other apps in
> the future) and is used to give full visibility to agents to launch the server or
> access the server or be launched by the native app.”

Host mode was planned as Phase 3 of the macOS app plan, for one host.
This plan restates it for any host, joins it to the view model’s records, and separates
**discovery**, which servers are live and where, from the **credential**, who may reach
one, so the first need not wait for the second.

## Goals

- One host contract that the macOS app, a browser tab, and a later host meet the same
  way, held by a reference-host test.
- An agent finds every live server, reads its view states, and sends it intents with the
  same `metab` commands, whoever started the server.
- An agent learns all of it from `metab` alone, and every verb and listing has a golden.

## Non-Goals

- Reopening what the macOS plan settled.
- The view model’s records and consent: `ViewState`, `Intent`, and the `control` setting
  are that plan’s.
- A second agent protocol.
  The command line, taught by the skill, is the complete agent surface.
  An MCP adapter over the same routes (`mb-5lgp`) is an optional idea for later, and
  nothing here depends on it.
- Servers on another machine, reached through `--remote`.

## Background

Paths are under `src/metabrowser/` unless they start with `docs/`, `apps/`, `tests/`, or
`skills/`. On `main`:

- **The lifeline is built.** `--exit-on-eof` stops a server when its stdin closes
  (`cli/stdin_lifeline.py`, jlevy/metabrowser#366), and the app passes it to every
  server. It took the place of a planned reaper
  ([v1, step 4](plan-2026-11-10-native-macos-app.md#milestone-v1-a-usable-app)). The
  flag also marks a local start for compression: `serving_locally()` is true only for a
  server started with it, on a loopback bind, outside a remote session
  (`cli/main.py:1009`, `cli/serve.py:385-387`). The `control` default of
  [VM-5](plan-2026-11-18-view-model-and-view-state.md#decision-vm-5-consent-and-trust)
  makes the bind and environment tests itself, tests each request’s peer, and does not
  read the flag, so a server started with `metab ROOT`, on its default loopback bind, is
  local too.
- **The announcement is text.** `Serving <root> at <url>` is printed before the socket
  listens (`cli/serve.py:412`), so the app parses it, as the `serving` line
  [its contract with `metab`](../../architecture/arch-app-contract.md) declares, and
  then polls (`CLIServeLaunch`,
  `apps/macos/Sources/ShellCore/Supervision/ServerLaunch.swift:54`). A path with a line
  break could forge it, so the app refuses such a root (`:119`).
- **The port is a walk** up from `--port`, which refuses 0 (`cli/main.py:761`), so a
  root can return on another port, which is another origin.
- **There is no credential.** A request with neither `Origin` nor `Sec-Fetch-Site`
  passes the `/api` origin check (`server.py:833-855`), so any process that reaches the
  port calls any route.
- **`--present` delivers to the app or a browser**
  ([Opening Anything from the CLI and the App](plan-2026-11-17-open-anything-from-cli-and-app.md)).
  For a browser it starts a detached server that runs until it is killed
  (`cli/present.py:1261`), a new one on every call.
- **Nothing lists live servers.** No state file, socket, token, ready line, sticky port,
  or idle exit exists; `GET /api/identity` answers naming fields alone
  (`root_identity.py:115-128`); and no shell module reads `sessionStorage`.

Host mode is planned in the macOS plan’s
[Phase 3](plan-2026-11-10-native-macos-app.md#phase-3-host-mode-the-registry-and-the-agent-front-door),
from the
[topology brief](../../research/research-2026-11-10-native-app-server-topology.md#phasing-from-the-spike),
as beads `mb-qzny`, `mb-5xi4`, `mb-1zyp`, `mb-54r1`, `mb-idri`, `mb-rtgh`, and
`mb-ko5d`, which [HM-1](#decision-hm-1-when-discovery-lands) A split into the beads of
the [Implementation Plan](#implementation-plan).
[Opening Anything from the CLI and the App](plan-2026-11-17-open-anything-from-cli-and-app.md)
took a first-release slice of its front door, `--present` through LaunchServices, and
its Phase 2, the round trip, rests on the same beads.

### Settled Decisions

| Settled | Source |
| --- | --- |
| A process per root; a root is an origin; at most one live server per root | [Servers, Switching, and Agents](plan-2026-11-10-native-macos-app.md#servers-switching-and-agents) |
| A host’s servers are its children, so privacy prompts name the host; a server the CLI starts exits when idle | The same, and the brief’s [Recommendations](../../research/research-2026-11-10-native-app-server-topology.md#recommendations) |
| No client’s credential is a cookie. It is a per-launch token in the `Authorization` header, which one shell helper adds only to requests for the page’s own origin, with redirects refused; the first page load and the event stream are gated | Phase 3 (`mb-qzny`), and the brief’s [Where This Breaks](../../research/research-2026-11-10-native-app-server-topology.md#where-this-breaks) |
| Only control verbs are served on an owner-only socket; content routes stay on loopback behind the token | Phase 3 (`mb-1zyp`) |
| The rules under [Safety Rules](#safety-rules), and a link scheme that carries no authority | Phase 3 (`mb-rtgh`) |
| One front door, `metab TARGET --present`, carries intents and not content; an agent reads content in its own process | The brief’s Recommendations |
| The verbs carry the view model’s records, and the command line, taught by the skill, is the complete agent surface | The view model plan’s [Reading](plan-2026-11-18-view-model-and-view-state.md#reading) and VM-9; the agent interface plan’s [AI-1](plan-2026-11-18-agent-interface.md#decision-ai-1-the-agent-surface) |

## Design

### Hosts

The shell is the same web app in every host.
It talks to its server over HTTP and server-sent events and never calls into its host
([macOS App](../../architecture/arch-macos-app.md)), so the view state’s publisher and
applier behave the same everywhere
([Hosts](plan-2026-11-18-view-model-and-view-state.md#hosts)). A host supplies a
**launcher**, which starts and owns the server, and a **surface**, which shows its
pages.

| Host | Launcher | Surface | State |
| --- | --- | --- | --- |
| A browser tab | A shell, the user’s or an agent’s | A tab in any browser | Built |
| The macOS app | `ServerSupervisor`, with each server its child | `WKWebView` | Built, on the CLI’s serve mode |
| VS Code | The extension host | A webview’s frame | A [draft design](../../research/archive/research-2026-07-17-vscode-extension-host.md) (`mb-x4y5`) |

Engines differ where no browserless test can show it, so each host verifies these before
it relies on the part named:

- **Every host:** the reference-host sequence against its own launcher, and the
  [Credentials check](plan-2026-11-10-native-macos-app.md#testing-strategy) in its
  engine.
- **`WKWebView`, viewer identity.** A viewer is keyed in `sessionStorage`
  ([VM-6](plan-2026-11-18-view-model-and-view-state.md#decision-vm-6-viewer-identity)),
  its first use in the shell.
  It must be available under the app’s persistent data store, survive a full load, be
  absent in a tab the app discarded, and be copied to a window a page opens.
- **`WKWebView`, the event stream.** Count connections per host with several tabs open,
  and check that a hidden or detached web view’s scheduling does not stop the stream.
  Under the token, a streamed `fetch` replaces `EventSource` (`static/app.js:7579`,
  `:8808`), which sends no header.
- **`WKWebView`, the credential.** The app hands the token only to a frame whose
  `WKFrameInfo.securityOrigin` matches, and its navigation policy keeps cross-port
  navigations out of a view.
  `WebAuthorization`’s cookie case (`ServerLaunch.swift:22`) is removed.
- **A browser tab and VS Code:** how the surface first receives the token, since a
  navigation carries no header.
  The brief proposes a one-time login address, and the VS Code draft’s session cookie
  gives way to the header token.

### The Host Contract

| Part | What the server does | State |
| --- | --- | --- |
| Lifeline | Stops when its stdin reaches EOF | Shipped: `--exit-on-eof` |
| Ready line | Prints one JSON line, its **server record**, once its socket accepts connections, so a host polls nothing and a folder’s name can forge nothing | Planned (`mb-hhzd`, the moment; `mb-wpel`, the line) |
| Registry entry | Writes the same record, owner-only, and removes it at an orderly exit | Planned (`mb-baee`) |
| Sticky port | Binds the port its root had last, else one the OS chooses, which the ready line reports | Planned (`mb-e74k`) |
| Token | Reads a per-launch token from the first line of stdin and requires it in `Authorization` on every content route. The token appears nowhere else: no argument, variable, log, or record | Planned (`mb-qzny`) |
| Gates | Serves a first page that holds no root data, and an event stream that a streamed `fetch` reads with the header | Planned, with the token |
| Control socket | Serves the control routes on an owner-only Unix socket that the record names | Planned (`mb-1zyp`) |
| Idle exit | Stops after a window, defined in code, with no viewer’s stream held and no request | Planned (`mb-k3yz`) |

The ready line is a contract: the server record that [Discovery](#discovery) defines,
whose schema `metab` serves.
A host asks for each part with a flag ([HM-6](#decision-hm-6-how-a-host-asks)), and the
record says which parts a server has.
A server from the command line and one a host owns differ in who answers for each part:

|  | Started from the command line | Owned by a host |
| --- | --- | --- |
| Lifetime | Ctrl-C or `kill`; idle exit when detached | The lifeline, and the host’s warm policy |
| Readiness | The `Serving` line, for a person | The ready line |
| Port | A walk from `--port` | The root’s sticky port |
| Credential | None until [HM-5](#decision-hm-5-which-servers-are-gated) C gates every server, after the hosts | The host’s per-launch token |
| Privacy prompts name | The terminal, or the agent’s host | The host |
| The record’s owner | The command line | The host, by name |

### Three Ways a Server Exists

Reading a view state is `GET /api/ui/viewer`, and sending an intent is
`POST /api/ui/intents`, in every cell.
What changes is how the agent finds the server and which transport carries the request.

|  | The agent started it | The user started it | A host launched it |
| --- | --- | --- | --- |
| **How** | `metab ROOT --no-open`, or `--present --open-in browser`, which starts one detached | `metab ROOT` in a terminal | The host’s launch command |
| **Today** | Found by the `Serving` line or `--present`’s report. Reached only by a raw HTTP client, and no view state exists | Not found, unless the user gives the address | Not found: `--present` hands the app a target and learns nothing back |
| **In the view slice** | Found the same way; `--api --server URL`, loopback only, reads view states and sends intents | Reached with `--server` once the user gives the address; `/api/identity` confirms the root | Not found: an agent can present a page and cannot read what the reader sees |
| **After discovery** | Listed; `--live` resolves ROOT; view states and intents over loopback | The same | The same, with the host named as owner |
| **Under the token** | View states and intents over the server’s owner-only socket where it is gated; content in the agent’s own process, as now | The same | Through the socket alone, since only the host holds the token |

The owner’s requirement is the fourth row: full visibility in every column.
It needs discovery and the view slice, and nothing of the token.

### Discovery

The **server record** is one contract ([HM-2](#decision-hm-2-one-server-record)). It
holds a protocol number; the root, keyed as
[recent targets](../../architecture/arch-recent-targets.md) key an entry; the URL; the
control socket’s path, when there is one; the owner, as a kind, a name, and the
launcher’s process ID; the server’s process ID; a **boot ID**, a random value new at
each start; the `metab` version; and whether loopback is gated.
It never holds a credential.

- **Every server writes one,** whoever started it, through `metabrowser.home`’s
  owner-only helpers, once its socket accepts connections.
  Writing never fails or delays a serve, as recording a recent target does not.
- **Where they live.** Entries, a server’s control socket, and the find-or-start lock
  sit in one owner-only runtime directory, named in code, below the configuration
  directory that holds recent targets.
  `home.py` supplies every step: `configuration_directory` (`:793`) resolves the root,
  `ensure_storage_root` (`:810`) and `ensure_private_directory` (`:562`) create the
  directory for the owner alone, `write_private_file_atomic` (`:849`) publishes an
  entry, and `read_private_file_bounded` (`:615`) reads one.
  The lock is a file there held by `flock`, as the recent targets list’s writer lock is
  (`_writing`, `recent_targets.py:539`), so the kernel frees it when its holder dies.
  The directory is not in the cache, which a user may delete while servers run, and not
  in a temporary directory.
  [Durable Storage](../../../../AGENTS.md#durable-storage) forbids keeping what a later
  step or a lock depends on where a restart empties it.
  These files describe live processes alone, and a restart ends the processes they
  describe, so nothing durable depends on their surviving one: a reader drops an entry
  by the two tests below, and a lock left behind is free.
  A socket’s file name is short, so its path fits the platform’s limit for a socket
  address under an ordinary home; a server that cannot bind one serves without it, and
  its record names none.
- **A reader makes two tests.** It drops an entry whose process is gone.
  It then asks the entry’s address for `/api/identity` and requires the entry’s boot ID,
  which a reused process ID, or another program on the port, cannot give.
  `/api/identity` gains `pid`, `boot_id`, and `version` for this.
- **`metab` lists them.** A mode ([HM-3](#decision-hm-3-a-mode-or-a-route)), named here
  `--servers`, prints the live records.
  It imports no server and signals none.
- **`--live` resolves ROOT.** `metab ROOT --api ROUTE --live` issues the route to the
  most specific registered root that holds ROOT, the brief’s rule.
  It starts nothing, and fails with a distinct status when no server is live.
- **The find-or-start lock** (`mb-5xi4`) serializes “find this root’s server, else start
  one”, which keeps a root to one live server.
  `--present`’s browser delivery and a host’s start both take it.

### Reaching a Gated Server

Under the token, a loopback request for a content route is refused without the header,
and an agent never holds a host’s token.
It reaches the server through the owner-only socket of `mb-1zyp`, for the control routes
alone:

| The macOS plan’s verb | Route | Carries |
| --- | --- | --- |
| `identity` | `GET /api/identity` | The naming fields and `pid`, `boot_id`, `version` |
| `clients`, named `viewers` | `GET /api/ui/viewers`, the list, with the record route `GET /api/ui/viewer` beside it | `ViewState` records |
| `present` | `POST /api/ui/intents` | An `Intent`, whose field is `present` |
| `navigate`, an event | `ui.intent`, on the viewer’s stream | The intent, to the page |
| `close` | A route that stops the server, new | Nothing |

- **`metab` picks the transport.** `--live` reads the record: loopback where the server
  is open, the socket where it is gated.
  A content route asked of a gated server is refused with the command that reads it in
  process. An agent’s commands are the same whatever the server is.
- **What the owner check authenticates.** The socket sits in an owner-only directory,
  and the server also reads the peer’s user ID from the kernel and refuses any other.
  Both tests name a user, and neither says which program connected: an agent, a script
  an agent was steered into running, and the user’s own shell are the same peer.
  So the socket grants only what any process of the user may already do: read which page
  the reader is on, and present an address of a served root, under the `control`
  setting. It admits no root, serves no content, and hands out no token.
  For that setting’s default a request over the socket counts as local: the owner check
  stands in for the loopback-peer test of
  [VM-5](plan-2026-11-18-view-model-and-view-state.md#decision-vm-5-consent-and-trust),
  which such a request would fail, since it carries no client address (`loopback_peer`,
  `delivery.py:124`).
- **A sandbox needs a rule either way.** One that refuses loopback refuses a socket path
  too
  ([What Agents Can Reach](../../research/research-2026-11-10-native-app-server-topology.md#what-agents-can-reach)),
  so the agent interface plan’s narrow [rule](plan-2026-11-18-agent-interface.md#trust)
  still applies.

### Self-Description

An agent with `metab` and no document can learn everything above.

| An agent asks | `metab` answers with | On `main` |
| --- | --- | --- |
| What can I do? | `metab --help` | Exists. It names modes and not tasks, and of the host parts only `--exit-on-eof` (`cli/main.py:775`) |
| Which routes exist? | `GET /api/routes` | Exists (`server.py:5161`): path, methods, and kind, and not what a route answers or which transport serves it |
| Which servers are live? | The listing mode | Missing. `--recent` lists targets, not servers |
| What does a ready line or a listing row hold? | The server record’s schema, through `--api` | Missing: no record, and no route serves a schema |
| Which verbs reach a gated server? | A mark on each `/api/routes` entry the socket serves | Missing |

This plan owns four gaps: the listing mode, the record’s schema, the transport mark, and
the host flags in the help.
`GET /api/contracts` and `GET /api/contract` serve the schema; the agent interface
plan’s [Self-Description](plan-2026-11-18-agent-interface.md#self-description) adds
them, with the help’s paragraph of agent tasks.

### Safety Rules

These carry over as settled, the first three from the macOS plan’s
[Phase 3](plan-2026-11-10-native-macos-app.md#phase-3-host-mode-the-registry-and-the-agent-front-door)
and the last from the brief’s Recommendations, and hold for every host:

- **No root is admitted on an agent’s request alone.** A request through the front door,
  the socket, or a link may present a root the host has open or warm, or one with a live
  server.
- **Any other root needs the user’s confirmation in the host,** which then starts the
  server as its own child.
  A declined confirmation is reported as blocked.
- **A credential is bound to its origin.** It is never a cookie, never sent to another
  port or host name, and never printed by a listing.
- **Nothing signals a server it did not start.** A listing is read-only.

### Parity

Each surface arrives with its row in the
[Parity Registry](../../architecture/arch-parity-registry.md) and a golden, by
[the parity rule](../../../../AGENTS.md#cli-and-functional-ui-parity).

| Surface | `metab` equivalent | Evidence |
| --- | --- | --- |
| The server record and ready line | The serve flag that prints it | A golden of the line, and the reference-host test |
| The listing, and `--live` | The listing mode, an `owned-model` row as `--present`’s are; `metab ROOT --api ROUTE --live` | Goldens against a fixture runtime directory and a harness server |
| Identity’s process fields, and `close` | Their routes through `--api` | Goldens |
| `viewers`, `viewer`, and intents over the socket | The same routes through `--api --live` | The view model’s goldens, run again on a gated harness server |
| Lifeline, sticky port, token on stdin, idle exit | Serve flags | The reference-host test; `cli-serve-exit-on-eof.tryscript.md` exists |
| The shell’s credential helper, its streamed event reader, the reload on a new boot ID, and the refusal of a root mismatch | Browserless sessions on the production JavaScript | Golden sessions |
| Cross-port behavior of a real engine; a host’s consent sheet and token handoff | Exempt, each named | The Credentials check; each host’s own tests |

## Key Decisions

Decided. The owner took all six on 2026-11-19, each as this plan recommended; each
section below keeps the options weighed and the reasoning.

| Decision | Decided 2026-11-19 |
| --- | --- |
| **HM-1** When discovery lands | A: ahead of the token |
| **HM-2** One server record | A: one contract for the ready line, the entry, and the listing |
| **HM-3** A mode or a route | A: a mode, until the credential exists |
| **HM-4** What the control socket speaks | A: HTTP, on an allowlist of registered routes |
| **HM-5** Which servers are gated | C: hosts first, then every server |
| **HM-6** How a host asks | A: a flag for each part |

### Decision HM-1: When Discovery Lands

The view slice answers “what is the reader looking at?”, and the reader’s page is most
often in a server the agent did not start.
This is the agent interface plan’s
[AI-7](plan-2026-11-18-agent-interface.md#decision-ai-7-finding-a-server-the-agent-did-not-start),
which this plan now owns.
Until this decision, the beads recorded `mb-qzny`, host mode, as blocking `mb-5xi4`, the
registry.

- **A. Split the beads, and land discovery first.** The record, the entry, the listing,
  and `--live` land beside the view slice.
  The lock, the idle exit, and the sticky port follow, and the token comes last, after
  the socket. It costs a second kind of persisted state, with stale files, reused process
  IDs, and start races to test, and an entry read by another release of `metab`. It also
  lowers what a steered agent must do to reach a window it did not open, which the
  intent’s limits and `control` still bound.
- **B. Keep the macOS plan’s order.** No new state now.
  The user’s and a host’s servers stay invisible to an agent until the token work ends,
  the largest piece here.
- **C. Each host publishes its own servers.** It covers one launch mode with a mechanism
  the registry replaces.
- **D. The agent scans ports.** It is slow, and a sandbox blocks it.

**Decided 2026-11-19: A,** over keeping the macOS plan’s order (B), a publisher per host
(C), and port scans (D). From first principles the dependency is not real.
Discovery needs a moment after bind, a boot ID, an owner-only place, and a client mode.
None is the token, the sticky port, or the idle exit, which `mb-qzny` bundled with the
ready line. The real order runs the other way: gating a server before the socket and the
listing exist would remove agent access that the view slice gave.
So the token waits for discovery, and discovery waits for nothing.
The beads were split the same day, as the [Implementation Plan](#implementation-plan)
lists.

**Clarified 2026-11-19:** of the implementation map’s groundwork, discovery’s steps H1
to H3 need only T0.7, the contract check that takes a pair for each registry.
H2 brings the `metabrowser.host` family’s own registry, as V2 brings `metabrowser.ui`’s,
and the server record names no object, so it uses nothing of V2 or of the shared object
definitions.

### Decision HM-2: One Server Record

- **A. One contract,** in a `metabrowser.host` family beside `metabrowser.ui`, with a
  registry of its own: the ready line prints it, the registry entry stores it, the
  listing answers it, and `/api/contract` serves its schema.
  Its protocol number is a hard gate, as `PLUGIN_SDK_VERSION` is: a reader skips an
  entry it does not know and says so.
- **B. Three shapes,** each fitted to its reader, for one fact.
- **C. An internal envelope with a format string,** as recent targets has.
  It is simpler, and no route serves its schema.

**Decided 2026-11-19: A,** over three shapes (B) and an internal envelope (C). The
consumers that cannot update with the producer are named: a running server of another
release, and the macOS app, which is replaced by hand and reads `metab` through
[its contract](../../architecture/arch-app-contract.md).

**Clarified 2026-11-19:** the entry, the socket, and the find-or-start lock live in an
owner-only runtime directory below the configuration directory, as
[Discovery](#discovery) sets out with the helpers that create it.

### Decision HM-3: A Mode or a Route

The parity rule prefers a route.

- **A. A mode, like `--recent`.** The listing names every folder the user has open.
  A route would give those names to every page of every served root, over a port that
  asks for no credential, which is why the macOS plan holds back a recent-targets route
  (`mb-a5ru`).
- **B. A route on every server.** `--api` reaches it for free, and it leaks as above.
- **C. A route behind the credential,** added when a switcher in the page needs it
  (`mb-9lf4`).

**Decided 2026-11-19: A now, and C when the token lands.** B, a route on every server,
would leak every open folder’s name over a port that asks for no credential.

### Decision HM-4: What the Control Socket Speaks

- **A. HTTP over the Unix socket, on an allowlist of registered routes.** The verbs are
  the routes in [Reaching a Gated Server](#reaching-a-gated-server), `--api` is their
  client, and their goldens are the ones the routes already have.
- **B. A protocol of its own,** with named verbs: a second vocabulary to keep in step,
  which AI-1 ruled out.

**Decided 2026-11-19: A,** over a protocol of its own (B).

**Clarified 2026-11-19:** a request over the socket counts as local for the `control`
default, since the socket’s owner check stands in for the loopback-peer test
([Reaching a Gated Server](#reaching-a-gated-server)).

### Decision HM-5: Which Servers Are Gated

A loopback port is open to every local user’s processes, and to a sandboxed process
whose sandbox allows loopback, while the files behind it are protected by their
permissions.

- **A. Only a server whose host hands it a token.** A server from the command line stays
  open, as today.
- **B. Every server.** The command line makes a token and hands it to the browser by a
  one-time login address, as the brief sketches, which changes every tab’s first load.
- **C. Hosts first, then every server,** once the first-load gate is measured in each
  engine the Credentials check names.

**Decided 2026-11-19: C,** over gating hosts alone (A) or every server at once (B). The
socket serves an agent under any of them.

### Decision HM-6: How a Host Asks

- **A. A flag for each part,** beside the shipped `--exit-on-eof`. Parts land and are
  golden-pinned one at a time, as HM-1 A needs, and a host’s declared command line says
  exactly what it relies on.
- **B. One `--host-mode` flag** that implies every part.
  It is simpler to type, and no part can ship before the token.
- **C. Both,** with the one flag as an alias: two spellings to test.

**Decided 2026-11-19: A,** over one flag (B), which would hold every part until the
token, and both (C).

## Implementation Plan

The steps form a stack of their own, H, beside the stacks of the implementation map’s
[Ordering 2](plan-2026-11-18-object-model-implementation-map.md#orderings), whose
[Stack H](plan-2026-11-18-object-model-implementation-map.md#stack-h-host-mode) slots
them. Under HM-1 A, `mb-qzny` keeps the token and its gates, `mb-5xi4` keeps the lock,
and the rest of each became the new beads below on 2026-11-19, children of the native
macOS app epic like the beads they split from.

| Step | Work | Bead | Slot in Ordering 2 |
| --- | --- | --- | --- |
| H1 | The ready moment after bind; the boot ID; `pid`, `boot_id`, and `version` on `/api/identity` | `mb-hhzd`, from `mb-qzny` and `mb-1zyp` | Beside Tier 0: additive, and no page changes |
| H2 | The server record’s contract and the ready-line flag, which the app adopts through its `ServerLaunch` seam in place of the `serving` line [its contract](../../architecture/arch-app-contract.md) declares | `mb-wpel`, from `mb-qzny` | After T0.7, the one groundwork pull request discovery needs |
| H3 | The registry entry, the liveness tests, and the listing mode | `mb-baee`, from `mb-5xi4` | Beside Tier 1, before V5 |
| H4 | `--live` on `--api` | `mb-77x9` | Stack V, after V5 |
| H5 | The find-or-start lock; `--present` finds the root’s server, sends the `present` intent, and reports `confirmed` from the view state; idle exit for a detached server; the skill and the guide follow | `mb-5xi4`, `mb-idri`, `mb-ko5d`, and `mb-k3yz`, from `mb-qzny` | The later V slice, after V8, which adds the skill’s sections |
| H6 | The sticky port; pages reload once on a new boot ID and refuse a root mismatch | `mb-e74k`, from `mb-qzny`; `mb-54r1`, whose follow half is V4’s applier | After Stack V |
| H7 | The control socket, with `close` | `mb-1zyp` | After H3 |
| H8 | The token: a measurement first, then the stdin token, the shell’s helper, the first-load and event-stream gates, and the Credentials check | `mb-qzny` | Last, after H7 |
| H9 | The app’s link scheme, rendezvous, attach, and confirmation; the VS Code host on the same contract | `mb-rtgh`, `mb-x4y5` | After H8 |

- **Tier 0** keeps its cap, and **Tier 1** and **Stack P** need nothing here.
  H1 to H3 need T0.7 and nothing else of Tier 0.
- **H2’s registry, document, and check.** The `metabrowser.host` family builds its
  registry from its own specs, as the cache’s family does.
  A new `docs/project/architecture/arch-host-mode.md` holds its contract table, which
  `devtools/check_artifact_contracts.py` compares with that registry once T0.7 lets the
  check take a pair for each registry.
  The document is linked from [Architecture](../../../architecture.md) and
  `docs/project/README.md`, as `tests/test_docs_discipline.py` requires.
- **Stack V** gains `--live` after V5, and its later slice, H5, stops waiting on the
  token.
- **Beads outside Stack H** that waited on the old `mb-qzny` or `mb-5xi4` now wait on
  the part they use: the app’s relaunch on its root’s port (`mb-w4kd`) on the sticky
  port, the resident server (`mb-obgj`) on the control socket, the rootless spare
  (`mb-bbod`) on both, and the page’s folder switcher (`mb-9lf4`) on discovery and, as
  before, on the token (`mb-qzny`), since under HM-3 C the route that serves the listing
  to a page arrives behind the credential.

## Testing Strategy

- **A reference host:** one test plays a host through the whole contract against a real
  `metab`, as `tests/test_stdin_lifeline.py` does for the lifeline: start, read the
  ready line, find the entry, stop by EOF, and find the entry gone.
- **Discovery’s failures:** a fixture runtime directory holds a live entry, a dead
  process, a reused process ID, a boot ID that does not match, an unknown protocol, and
  a damaged file. Two starts for one root race under the lock.
- **Goldens** for every row under [Parity](#parity), and the Credentials check, in each
  engine it names, before any token is issued.
- **A measurement before H3 and H8:** what an entry adds to a server’s start, and what
  the first-load gate costs, each against the unchanged build.

## Open Questions

- **Where does a root’s sticky port live?** It must outlive its server, unlike the
  entries of [Discovery](#discovery): in its recent target, which can be turned off and
  forgotten, or in a file of its own?
  H6 decides it.
- **Does `metab ROOT` in a terminal join a live server for its root,** or start a
  second, as today?
- **Browsed content under the token.** An image, a sandboxed preview frame, and a
  download carry no header, and `/raw` serves the user’s files.
  The brief says that what such requests load must need no credential, and no design yet
  says how `/raw` meets that.

## References

- [Native macOS App](plan-2026-11-10-native-macos-app.md), whose Phase 3 this plan
  restates,
  [Opening Anything from the CLI and the App](plan-2026-11-17-open-anything-from-cli-and-app.md),
  and
  [Server Topology, Lifecycle, and Agent Handoff](../../research/research-2026-11-10-native-app-server-topology.md)
- [View Model and View State](plan-2026-11-18-view-model-and-view-state.md),
  [Agent Interface for Objects and View State](plan-2026-11-18-agent-interface.md), and
  the [implementation map](plan-2026-11-18-object-model-implementation-map.md)
- [macOS App](../../architecture/arch-macos-app.md#a-server-per-folder),
  [The macOS App’s Contract with metab](../../architecture/arch-app-contract.md),
  [Recent Targets](../../architecture/arch-recent-targets.md), and the
  [Parity Registry](../../architecture/arch-parity-registry.md)
- [The agent skill](../../../../skills/metabrowser/SKILL.md), and
  [Compatibility and Legacy Code](../../../development.md#compatibility-and-legacy-code)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
