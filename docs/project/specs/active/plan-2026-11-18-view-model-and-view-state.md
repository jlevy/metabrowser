# Feature: View Model and View State

**Date:** 2026-11-18

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Decided, and nothing here is built.
The owner took every decision under [Key Decisions](#key-decisions), VM-1 to VM-10, on
2026-11-18, with the parent plan’s Decisions 1 to 23. A companion to
[Object Data Model and Views](plan-2026-11-14-object-data-model-and-views.md), the
parent plan below, which defines the objects, references, collections, and shapes this
plan names. Written against `main` at `a1100bca6`.

## Overview

The parent plan gives each thing Metabrowser shows one model, an object, which says what
the thing is. This plan adds a second model, the **view model**, which says what each
window shows: which object, in which page view, beside which list, with which rows
current and open. Each viewer publishes a **view state** that refers to objects and
collections by reference and never copies them, so an agent can read what the reader is
looking at; and an agent can send an **intent**, a partial view state such as “show this
pull request”, which the page applies as the reader’s own open would be.
Objects, view states, and intents are SoftSchema contracts, so everything the UI shows,
and every change an agent may ask of it, has a named structure an agent can read and
write.

The view model’s first step, the **view slice**, is small on purpose: what the reader
sees, and opening a file or a pull request.
The rest of the UI’s state is mapped ([The View State](#the-view-state)) so each later
part is a facet or a settable field added to the same contracts.

[Agent Interface for Objects and View State](plan-2026-11-18-agent-interface.md) says
how an agent uses these records end to end, and
[Plugin Authoring for Objects, Views, and View State](plan-2026-11-18-plugin-authoring-objects-views.md)
how a plugin’s page declares its parts.

## Goals

- One view state per viewer, built from the objects’ references and the UI’s own state,
  that an agent can read through `metab` and a route, and one intent, `present`, by
  which an agent asks a viewer to show something, applied through the reader’s own paths
  and answered with the view state that results.
- One vocabulary with the object model: a reference, a collection reference, a shape, a
  summary and facets, and a `generation`, each defined once, in the parent plan’s
  [Approach](plan-2026-11-14-object-data-model-and-views.md#approach).

## Non-Goals

- A server that owns the UI. The page stays the authority for what it shows, and the
  server holds the latest view state each page publishes
  ([Decision VM-1](#decision-vm-1-where-the-view-state-lives)).
- Pixels, the DOM, or content in a view state.
  It names what is shown; an agent reads the content through the object’s own route.

## Background

Paths below are under `src/metabrowser/` unless they start with `docs/`, `tests/`,
`devtools/`, or `explorations/`; `github/` abbreviates `builtin_plugins/github/`, and
`static/` is the browser shell.
A decision cited by number alone, such as Decision 5, is the parent plan’s, and Phases 1
to 3 are its phases.

### UI State Today

Only the address is serialized and shared.
Everything else is module state or DOM, in the page alone.

| State | Held in |
| --- | --- |
| What is selected | The address ([URL grammar](../../architecture/arch-views-models-routes.md#browser-url-grammar)) |
| The revision a page was drawn for | The pin token its data requests name (`static/source-pin-guard.js:1-12`) |
| Main tab, and each tab’s last destination | `activeNavPanelId`, `mainTabDestinations` (`static/main-tabs.js:115`, `:120`) |
| Files filter, Group by, expansion, and current row | A snapshot reset on every page (`static/filter-state.js:5-21`); DOM classes (`static/tree-expansion.js:125`); `setSelectedPath` (`static/app.js:4153`) |
| Pulls filter, closed stacks, and current row | `setFilter`, `closedStacks`, `setCurrent` (`github/pulls-panel.js:2871`, `:863`, `:3027`) |
| Active page view | A flag per view container (`static/view-state.js:18`) |
| Display preferences | Host-only cookies, not `localStorage` (`static/app.js:534`, `static/plugin-sdk.js:675`) |
| Windows, tabs, and each tab’s page | The macOS app’s `session.json` ([Session Restore](../../architecture/arch-macos-app.md#session-restore)) |

Four facts shape the design.

- **Nothing sees a running page.** The server knows a page only as an event-stream
  connection, and `metab --api` runs its own application in process
  (`docs/project/architecture/arch-cli.md:106`), so it reaches every route and no page.
- **`--present` cannot confirm.** It reports `confirmed: false` (`cli/present.py:795`),
  because the app cannot reply and the page “never calls into the app”
  (`docs/project/architecture/arch-macos-app.md:15`).
- **Showing an item is already one rule.**
  [Navigation Reveals the Item](../../../design-system.md#navigation-reveals-the-item)
  lists the routes by which a reader reaches an item, and `revealPlan` applies one rule
  to them (`static/main-tabs.js:63`).
- **The verbs are planned without payloads.** The
  [native macOS app plan](plan-2026-11-10-native-macos-app.md#phase-3-host-mode-the-registry-and-the-agent-front-door)
  lists `present` and `clients` (`mb-1zyp`), pages that follow `navigate` (`mb-54r1`),
  and the front door (`mb-idri`); its brief asks for a front door “that carries intents,
  not content”
  (`docs/project/research/research-2026-11-10-native-app-server-topology.md:471`). This
  plan defines what those verbs carry, once, for both plans.

## Design

The object model says what each thing is.
The view model says what a viewer shows: which object, in which page view, beside which
list, with which rows current and open.
An agent reads it to learn what the reader is looking at, and writes to it to show the
reader something.

### Components

| Component | Where | Job |
| --- | --- | --- |
| View model contracts | `ui/` (new package), compiled under `data/ui-format/` | `ViewState` and `Intent`, the viewer registry, the `control` setting, and the routes `/api/ui/viewers`, `/api/ui/viewer`, and `/api/ui/intents` |
| View state publisher | `static/ui-state.js`, deferred | The `describe` function of each summary field and facet, the publisher, `openAddress`, and the applier for `present` |
| View state SDK surface | `mb.ui`, in a later slice | A page view declares its named parts and reports their values, which the publisher prints as `pane.parts` |

### Terms and Rules

| Term | Meaning |
| --- | --- |
| **Viewer** | One tab showing a served root: a browser tab, or an app tab’s web view |
| **View state** | The record of what one viewer shows now |
| **Surface** | A part of the UI with state to publish. Most are a **list** (a collection in a row shape) or a **page** (an object in the `page` shape); the overlay layer, the display preferences, and the command registry are the rest |
| **Intent** | A request to change a view state |
| **Outcome** | The answer to an intent: a status, and the view state after it |

A surface’s part of a view state is a **facet**, as an object’s optional part is.
“Slice” is not a word for it: a slice is a step of delivery
([Approach](plan-2026-11-14-object-data-model-and-views.md#approach)).

“View” already means three things here: the served view of
[Open Modes](../../architecture/arch-open-modes.md#vocabulary), a page view, and a
drawing in a shape. “View state” and “viewer” add no fourth, which is also why the route
that lists viewers is `/api/ui/viewers` and not `/api/ui/views`. Since
`static/view-state.js` exists and tracks only which page view is active, the new module
is `static/ui-state.js`.

The view model adds no vocabulary of its own where the object model has one:

| Object model | View model |
| --- | --- |
| Object and reference | A page shows one; every part of a view state names things by reference |
| Collection and collection reference | A list shows one, and its facet names it |
| Shape | A field of each list facet |
| Summary and facets | A view state’s summary, and its facets by surface |
| `href` and its inverse | `address` and `object` |
| Collection envelope | The list of viewers |
| `generation` | A view state’s counter |
| Contract registry | A second family, `metabrowser.ui` |

1. **The page is the authority, and the server is where it is read.** A page publishes
   its view state; the server keeps the latest per viewer, in memory, and relays intents
   back.
2. **A view state refers and never copies.** Content, titles, typed text, the DOM, and
   pixels are absent; an agent follows a reference through the object’s own route.
3. **Most surfaces are a list or a page.** The list host publishes every list’s facet
   and the page-view lifecycle every page’s, so a surface that converges onto them is
   modeled with no code of its own.
   The three that are neither each publish one facet from the module that owns them.
4. **A summary and facets.** The summary is small and always published; a facet is whole
   or absent, and published while a reader asks for it.
5. **A write has a read’s shape.** `present` takes a view state’s settable fields under
   the same names, so an agent reads, changes a field, and writes it back.
6. **An applied intent has the standing of the reader’s own open,** and runs the code a
   click or Quick Search runs.

### Hosts

The shell is host-agnostic, and the view state’s publisher and applier are part of the
shell.
They behave the same in a standalone browser tab, in the macOS app’s web view, and
in a later host such as the VS Code host design (`mb-x4y5`). The page talks to its
server over HTTP and server-sent events and never calls into the app
(`docs/project/architecture/arch-macos-app.md:14-15`), and the view model keeps that
rule: a view state is published to the server, and an intent arrives on the server’s
stream.

- **Nothing in the view slice requires the app.** A browser tab on a server started in a
  terminal is a complete viewer.
- **A host is one more reader and writer of the same routes.** The app may read
  `/api/ui/viewers` to save a session as view states, or send an intent where it now
  loads an address, and it gets no route or event of its own.
  What a host alone knows, its windows and their order, stays out of a view state
  ([Reading](#reading)).

Two parts of the design are new to WebKit’s web view, and the view slice’s first item
verifies both there before either ships:

- **Viewer identity.** No shell module reads `sessionStorage` today, so
  [Decision VM-6](#decision-vm-6-viewer-identity) is its first use.
  To verify in the app’s `WKWebView`, which uses the persistent default data store
  (`docs/project/architecture/arch-macos-app.md:77-78`): that `sessionStorage` is
  available; that it survives a full load in one web view; that a tab the app discarded
  comes back with none, since it gave up its web view, and so is a new viewer; and that
  a window opened from a page copies its opener’s, which is the duplicated-tab case that
  decision already handles.
  A server restarted after a failure returns on a new port, a new origin with empty
  storage, and its registry is new as well.
- **The event stream.** The app’s pages hold the stream today.
  What is new is a stream on a pinned revision’s page, which is every GitHub repository
  the app opens, and so one more held connection for each such tab against WebKit’s
  limit for a host. The measurement counts connections in WebKit with several tabs open,
  with the
  [WKWebView probe](../../../../explorations/performance-loop/README.md#wkwebview-probe).
  It also records whether a background tab’s page still receives an intent and
  publishes: WebKit throttles a hidden web view, and suspends one removed from its
  window, which stops its stream
  (`docs/project/research/research-2026-11-10-native-app-server-topology.md:260-264`).

The [host mode plan](plan-2026-11-18-host-mode.md#hosts) holds the contract every host
meets, and lists these two checks among those each host makes before it relies on the
part they cover.

### The View State

A view state is identified by `viewer` and versioned by `generation`; the contract’s own
version changes only on a break.

| Summary field | Meaning | From |
| --- | --- | --- |
| `viewer` | The tab’s identifier ([Decision VM-6](#decision-vm-6-viewer-identity)) | `sessionStorage` |
| `generation` | A count of changes to what is shown | Assigned by the server on publish, and returned to the page |
| `attention` | `focused`, `visible`, or `hidden`; it does not move `generation` | `document.hasFocus()`, `visibilityState` |
| `served` | `{revision, ref}`: `working-tree` or a commit, and the ref it was resolved from | The pin token, or `working-tree` where a page names none |
| `address` | Path, query, and fragment | `location` |
| `object` | The reference the address selects; null at a list’s address | `parse`, `parseCommit`, `parsePull` |
| `nav` | `{tab, current}`: the main tab in front, and the row it marks current, null when the item is outside the list or its filter | `static/main-tabs.js`, each panel |
| `pane` | `{kind, view, views, status}`: the kind, the registered page view in front, the registered page views offered, and `loading`, `ready`, `idle`, `not_found`, or `failed` | The pane’s claim lifecycle (`static/navigation.js:1077`) |

`pane.kind` and `pane.views` are what `--show` prints today as `kind:` and `views:` for
the same address, and `object` is what its new `object:` line prints
([Routes and the CLI](plan-2026-11-14-object-data-model-and-views.md#routes-and-the-cli)).

[The Recent Tab](plan-2026-11-18-recent-tab-updates-and-events.md#routes-the-cli-and-the-view-model)
adds a fourth main tab.
There `nav.tab` is `recent`, and `nav.current` is the row’s reference, an `update` or an
`event`, while `object` stays what the address selects.

`pane.view` and `pane.views` hold registered `[[view]]` identifiers and nothing else.
A page that draws tabs of its own has one registered view.
The pull request page is `pull-request` at all three of its addresses
(`github/manifest.toml:149-150`), and `--show` prints `views: pull-request (default)`
for it, with the tab in its model line as `tab=conversation`
(`tests/golden/cli-github-checkout.txt:346-350`). The tab stays in `address`
(`PULL_ROUTE_TABS`, `view_routes.py:24`) and later becomes a `pane.parts` value, so the
page and `--show` agree at every pull request address.

`pane.status` is read from the pane’s lifecycle, whose phases are `starting`, `idle`,
`loading`, `content`, `error`, `unreachable`, and `external` (`PreviewPanePhase`,
`static/navigation.js:947`):

| Phase | `pane.status` |
| --- | --- |
| `starting`, `loading` | `loading` |
| `content` | `ready` |
| `error` | `failed`, or `not_found` where the answer was a 404 |
| `idle` | `idle`: nothing is selected, and `object` is null |
| `external` | The owner’s own status. The pull request page and the commit page claim the pane and paint for themselves (`static/app.js:9295`, `static/git-panel.js:2707`), so each reports `loading`, `ready`, `not_found`, or `failed` |
| `unreachable` | Never published. A page that cannot reach the server cannot publish, so the server holds the last state through the grace period of [Decision VM-7](#decision-vm-7-persistence) |

Two of these rows are work for the view slice.
The lifecycle records a 404 as `error`, and only an open’s result tells the two apart
today (`settleFileSelectionFailure`, `static/navigation.js:1236`;
`QuickFileOpenOutcome`, `static/app.js:976`), so the lifecycle must keep that fact.
An `external` owner reports nothing to the lifecycle now, so the lifecycle gains a call
by which the owner settles its claim.

| Facet | Holds | Published by |
| --- | --- | --- |
| `nav.list` | The front panel’s list facet, which is the list host’s state record ([The List Host](plan-2026-11-14-object-data-model-and-views.md#the-list-host)): `collection`, a collection reference; `shape`; `focused`; `expanded`; `closed_sections`; and `window`, the first and last rows in view | The list host; an adapter per panel until it converges |
| `pane.list` | The same facet for a page that is a list: `/pulls`, a folder’s Files view | The list host |
| `pane.inner` | The item inside the object that the address names, as a nested reference: a changed file, a container’s entry | The address parsers. It is left out of the view slice: the address already carries it, and its types have no contract yet |
| `pane.parts` | Named parts of a page, each open or closed, or one of a set of values: a table of contents, the Diff summary, the diff layout, the pull request page’s tab | The page view, through `mb.ui` |
| `overlay` | The modal or menu that is open | The overlay controller (`createModal`, `static/overlay-layer.js:177`) |
| `display` | Theme, reading font, and width | The preference cookies |
| `commands` | The registered commands available now, by identifier | The shortcut registry (`create`, `static/keyboard-shortcuts.js:651`) |

- **Bounds.** A view state grows with the rows in view, never with a collection:
  `expanded` and `closed_sections` are capped and say `truncated`, and `window` names
  two rows. `MAX_VIEWERS`, `MAX_VIEW_STATE_BYTES`, and the list caps are constants in
  `ui/`, each set by a measurement recorded beside it.
- **Publishing.** Every summary field and every facet is computed by a pure `describe`
  function registered under its path in the view state, as `describeRow` is for a row.
  The publisher composes them after the view settles, debounced, with one request in
  flight and the newest state winning, the rule `createRootSummaryRefresh` adopted after
  identical requests took every connection in WebKit (`static/navigation.js:642`). Its
  module loads with the deferred shell tools, and no click waits on it.
- **The publish route.** A publish is `POST /api/ui/viewers`, the route that lists
  viewers. Its answer gives the `generation` the state was assigned.
  The page keeps that number, and whether anything it shows has changed since, for the
  `stale` check under [Writing](#writing).

### Reading

- **Routes.** `GET /api/ui/viewers` answers the view states in the
  [collection convention](plan-2026-11-14-object-data-model-and-views.md#decision-3-the-collection-envelope),
  most recently attended first, so `rows[0]` is the viewer the reader looked at last.
  `GET /api/ui/viewer` answers one view state as a record, as `pull` sits beside
  `pulls`: the viewer attended last, or the one `?viewer=<id>` names, and `no_viewer`
  when there is none, by the agent interface plan’s
  [Decision AI-5](plan-2026-11-18-agent-interface.md#decision-ai-5-reading-one-viewer).
  A later slice adds `?facets=`; a bounded wait on the record route, `since` and `wait`,
  for an agent that follows a viewer
  ([Decision AI-6](plan-2026-11-18-agent-interface.md#decision-ai-6-following)); and a
  stream of states for an observer ([Writing](#writing)).
- **`metab`.** `--api` reaches these routes in process, where no page is connected, so
  its goldens pin the empty collection, the contracts, a publish accepted and a publish
  refused, and the refusals a server makes without a page
  ([Parity for the View Model](#parity-for-the-view-model)). Reaching a running server
  is new: `--api ROUTE --server URL` issues the route to it as a client that starts no
  server, as `--present` is.
  `--live`, which finds ROOT’s server, waits for the host mode plan’s
  [Discovery](plan-2026-11-18-host-mode.md#discovery).
- **`--format yaml`.** An answer that is one contract record, which `/api/ui/viewer`
  gives, prints as a SoftSchema artifact: a `softschema:` header and the record under
  its envelope key, the form `serialize_artifact` writes
  (`plugin_loader/artifact_contracts.py:479-502`). That form holds one record.
  So a multi-row answer, and the answer to an intent, print as `--format yaml` prints
  any route today: the envelope as plain YAML, with no header (`cli/api_cli.py:95-102`).
- **Several viewers.** Each tab is a viewer, in a browser or in the app.
  A tab the app has discarded (`docs/project/architecture/arch-macos-app.md:442`) has no
  viewer until it is shown.
  Windows and their order are the shell’s, platform behavior the parity rule exempts; a
  viewer reports only its own `attention`.
- **Privacy.** A view state holds paths, numbers, and commit IDs that the same port
  already serves through `/api/tree`. What it adds is which one the reader is on, and
  whether the tab has focus.
  Any process that reaches the port can read it, as it can read the files; host mode’s
  credential (`mb-qzny`) closes both together.
- **The macOS plan’s names.** That plan lists the control verbs `present` and `clients`
  and a `navigate` event that pages follow, in its
  [Phase 3](plan-2026-11-10-native-macos-app.md#phase-3-host-mode-the-registry-and-the-agent-front-door).
  They take this plan’s names and payloads, as the host mode plan’s
  [Reaching a Gated Server](plan-2026-11-18-host-mode.md#reaching-a-gated-server) maps
  them. `clients` answers the list of viewers, and is named `viewers`. `navigate` is an
  event there and not a verb, and it is the `ui.intent` event below.
  `present`, which pushes that event to the most recently visible page
  (`docs/project/research/research-2026-11-10-native-app-server-topology.md:507-508`),
  carries an intent to `rows[0]`, and the intent’s own field has the verb’s name,
  `present`.

**Following a reference.** A view state names things and holds none of them, so an agent
needs the route each type’s reference leads to:

| `type` | Route | Answers |
| --- | --- | --- |
| `file`, `folder` | `GET /api/file?path=<id>` | The file or folder envelope, for a working tree and for a pin (`server.py:3375-3380`). No route answers a `File` or `Folder` object: the tree and Recent stay compact, and their adapters run in the browser |
| `commit` | `GET /api/git/commit/<id>` | `GitCommitDetail` today; a `Commit` object once the parent plan’s Phase 2 conforms the Git routes |
| `pull-request` | `GET /api/plugin/github/pull?number=<id>` | The pull record today; the object with its facets in the parent plan’s Phase 3 |

In the view slice the table is a constant in `ui/`, beside the list of types an intent
may name. `/api/object-types` serves it once the registry exists
([Decision 15](plan-2026-11-14-object-data-model-and-views.md#decision-15-routes)). The
Recent tab plan adds a row for each of its three types, `update`, `event`, and
`working-tree-changes`
([Routes, the CLI, and the View Model](plan-2026-11-18-recent-tab-updates-and-events.md#routes-the-cli-and-the-view-model)).

### Writing

```text
agent ── POST /api/ui/intents ──► server ── ui.intent, on the viewer's stream ──► page applies it
agent ◄── outcome: a status and the view state ── server ◄── a publish naming the intent ──┘
```

- **One verb.** `present` carries a partial view state.
  The view slice accepts exactly one of `object` or `address`. Later slices add
  `pane.view`, `nav.tab`, a list’s `params` and `expanded`, and `pane.inner`, applied in
  that order. The name is the agent interface plan’s
  [Decision AI-4](plan-2026-11-18-agent-interface.md#decision-ai-4-one-word-for-the-act):
  one word for the act, from the `--present` flag to the control verb to this field.
  `metab --show` is a different thing, a report of a selection that changes nothing.
- **The viewer.** An intent names the `viewer` it is for, or names none and goes to
  `rows[0]`, the viewer the reader attended last.
  A viewer the server does not hold is refused as `unknown_viewer`, and an intent with
  no viewer connected as `no_viewer`. An intent that sends `if_generation` must name its
  `viewer`, and one that does not is refused as `invalid`: a generation is one viewer’s
  counter, so without the viewer it could be compared with another viewer’s count.
- **Sent through `--api`.** The view slice’s write is
  `metab --api /api/ui/intents --server URL --data FILE`, where `--data` makes the
  request a `POST` (`cli/main.py:598-604`). `--data` sends a file’s bytes today, and the
  route takes JSON, so the agent interface plan’s
  [Output Forms](plan-2026-11-18-agent-interface.md#output-forms) says how an intent
  written as a YAML artifact becomes that body.
  `--present` sends no intent in this slice, for the reasons the last item of this list
  gives.
- **The stream.** A page’s event stream names its viewer, `/api/events?viewer=<id>`, and
  the server sends that viewer’s `ui.intent` events on it.
  The parameter is not a `scope`: the stream’s `scope` is one value that sets its depth
  (`events_route.py:625-629`). The stream is refused today for a subject without the
  `watcher` capability (`events_route.py:773`), which a pinned revision lacks, so for
  such a subject it is served with `ui` events alone.
  A later slice adds `?ui=states`, which sends each published state as a `ui.state`
  event to an agent that follows the UI without polling.
  The plan calls that client an observer, since “watcher” is the capability’s name.
- **Applied as an open.** The page turns the target into an address and opens it through
  one `openAddress`, which dispatches to the openers that exist: `navigateToPath`,
  `openQuickSearchPull`, and the Git panel’s `selectCommit` (`static/app.js:9850`,
  `:9234`, `static/git-panel.js:2519`). Where none applies it loads the address, as a
  followed link does. What it loads is the address rebuilt from the parse through the
  encoders, never the caller’s string.
  The reveal rule then does what it does for Quick Search: the tab comes forward, the
  row is revealed, focus stays, and no filter changes (`docs/design-system.md:4103`,
  `:4154`). The Recent tab plan adds a case to that rule, for an item two tabs hold
  ([The Tab](plan-2026-11-18-recent-tab-updates-and-events.md#the-tab)): `present` with
  an `update` or an `event` reveals it in Recent, and `present` with the subject in the
  subject’s own tab.
- **History.** One pushed entry, so Back undoes it; none when the address is already
  shown (`static/navigation.js:1410`).
- **The reader wins.** An intent is applied at once, offered, or refused, and never
  queues behind input.
  A click that lands while it loads cancels it, by the guard every open uses
  (`static/navigation.js:1340`). While a modal is open, where the reader could not
  follow a link either, it is refused as `busy`.
- **A base.** `if_generation` refuses as `stale` when the viewer changed after the agent
  read it, and the page enforces it, not the server.
  It is sent with the `viewer` it was read from, as the rule above requires.
  A `generation` is assigned on a debounced publish, so the server’s copy trails the
  page, and a check there would pass after the reader moved and before the page said so.
  The page refuses when `if_generation` is not the generation its last publish was
  given, and when anything it shows has changed since that publish: an unpublished
  change is stale.
- **Announced.** A notice says that a local command opened the page.
- **The answer.** The page’s publish after an intent names the intent it answers and
  what became of it, so the server pairs the two by identifier and never by order.
  The next publish after an intent may be the reader’s own click, the one that cancelled
  it. An outcome is the intent’s identifier, a status, and the viewer’s view state once
  the pane settles. The status says what became of the intent: `applied`, `offered`,
  `cancelled`, `refused` with a code, or `pending` when the bounded wait ran out, with a
  `status_route`. `--api` follows a `status_route` today only in process, once and with
  no wait, after a `POST` that answered 202 (`cli/api_cli.py:132`, `:138`), so following
  one through `--server` is new client code.
  What the pane then shows is not repeated in the status: an applied open of a path that
  is gone is `applied`, and `view_state.pane.status` says `not_found`. An offered intent
  stays `offered` until the reader accepts or dismisses it, which its `status_route`
  then reports as `applied` or `cancelled`.
- **Refusals.** The server gives six codes without a page: `invalid`, `control_off`,
  `not_an_address`, `unsupported_field`, `unknown_viewer`, and `no_viewer`. Only a page
  can give the other two, `busy` and `stale`. `invalid` is the code for whatever the
  `Intent` contract’s model refuses, an `if_generation` with no `viewer` included, so
  that rule adds no code.
- **`--present`, later.** The flag and the intent’s field share a word and are two
  things: `metab --present` is the command that hands a target to a viewer, and
  `present` is what an intent carries.
  Today the command sends no intent.
  It starts no server and hands its target to the app through `open -b`
  (`cli/present.py:4-6`, `:38-40`), so it has no server address to send an intent to
  until the live-server registry (`mb-5xi4`) exists.
  An intent also admits no root, and opening a root is most of what `--present`
  delivers. So every change to `--present` waits for the slice that has the registry.
  There, where it resolves a `page` (`cli/present.py`, `cli/selection_href.py:16`) and
  finds the root’s server with a viewer, it sends `present: {address: page}` and reports
  `confirmed: true` with the outcome.
  Confirmation becomes an observation of the view state, whichever channel delivered the
  target, so the app never has to reply.
  On `main` after the `a1100bca6` these citations name, #582 gave `--present` a second
  delivery, to a browser on a detached server it starts and whose address it reports.
  The app handoff still learns no address, so the wait for the registry stands; the host
  mode plan’s
  [Three Ways a Server Exists](plan-2026-11-18-host-mode.md#three-ways-a-server-exists)
  counts the browser delivery as a server the agent started.

What untrusted content cannot do:

- A write is a `POST` with `Content-Type: application/json` and origin proof, which a
  sandboxed preview’s `Origin: null`, a form, and an image cannot produce
  (`server.py:781`, `:829`). A `GET` changes nothing.
- An intent names only an object of one of
  [Decision 5](plan-2026-11-14-object-data-model-and-views.md#decision-5-identity)’s
  types, or an address the route parsers accept: never a URL with a host, `/raw`, or
  `/api`. Until the object registry exists, those types are a fixed list in `ui/`.
- The applier listens to the server’s stream alone.
  No `postMessage`, DOM event, or link scheme reaches it.
- An agent can still be steered by text it read.
  Three things bound what that can do: the rule above, that an intent names only an
  object or a parsed address of the served root; the notice; and Back.
  [Decision VM-5](#decision-vm-5-consent-and-trust) adds a fourth, that an applied
  intent does not run a file’s scripts.

### UI Contracts

Two SoftSchema contracts form a `metabrowser.ui` family, with a registry built from its
own specs as the cache’s is (`cache/contracts.py:231`): `metabrowser.ui:ViewState/v1`
and `metabrowser.ui:Intent/v1`, under the envelope keys `view_state` and `intent`. An
outcome is not a third contract.
It is the intents route’s envelope around a view state, internal as every route envelope
is.

A repository folder, the Pulls tab filtered to open, and pull request 561 on Changes
with a file selected.
The summary is what the view slice publishes, and the three facets belong to later
slices:

```yaml
softschema:
  contract: metabrowser.ui:ViewState/v1
  envelope: view_state
  status: enforced
view_state:
  viewer: t-4f2a
  generation: 42
  attention: focused
  served: {revision: working-tree, ref: null}
  address: /pull/561/files/src/metabrowser/static/app.js
  object: {type: pull-request, id: "561"}
  nav:
    tab: pulls
    current: {type: pull-request, id: "561"}
    list:                               # facet
      collection: {name: pulls, params: {state: open}}
      shape: nav-row
      focused: null
      expanded: [{type: pull-request, id: "561"}]
      closed_sections: []
      window:
        first: {type: pull-request, id: "563"}
        last: {type: pull-request, id: "548"}
      truncated: false
  pane:
    kind: pull-request
    view: pull-request
    views: [pull-request]
    status: ready
    inner:                              # facet
      type: changed-file
      id: src/metabrowser/static/app.js
      parent: {type: pull-request, id: "561"}
    parts:                              # facet
      tab: {value: files}
      diff-summary: {open: true}
      layout: {value: split}
```

An intent, and the route’s answer to it:

```yaml
softschema: {contract: "metabrowser.ui:Intent/v1", envelope: intent, status: enforced}
intent:
  viewer: t-4f2a
  present:
    object: {type: pull-request, id: "562"}
  if_generation: 42
```

```json
{
  "intent": "i-7",
  "status": "applied",
  "view_state": {
    "viewer": "t-4f2a",
    "generation": 43,
    "attention": "focused",
    "served": {"revision": "working-tree", "ref": null},
    "address": "/pull/562",
    "object": {"type": "pull-request", "id": "562"},
    "nav": {"tab": "pulls", "current": {"type": "pull-request", "id": "562"}},
    "pane": {"kind": "pull-request", "view": "pull-request", "views": ["pull-request"], "status": "ready"}
  }
}
```

| What | Standing |
| --- | --- |
| `ViewState`, `Intent` | SoftSchema contracts: models in `ui/`, compiled schemas and a corpus under `data/ui-format/`, checked as object contracts are |
| The reference, the collection reference, and the shape names | The object model’s definitions, which both families include |
| The outcome | Internal: the intents route’s envelope, `intent`, `status`, `code`, and `status_route` around a `view_state` |
| The other route envelopes | The internal collection convention |
| The stream’s event names, and the publish request, which carries a view state and the intent it answers | Internal, changed with the shell in one commit |
| Facet paths and `describe` functions | An internal registry, held by the parity rule below |

A running server validates a published state and an intent with the contract’s Pydantic
model alone, not through `validate_record`, whose first pass is a JSON Schema validator
(`plugin_loader/artifact_contracts.py:447`), so serving loads no schema library and the
startup gate holds (`devtools/check_distribution.py:62`). The full check,
`validate_record`, runs in the tests, the corpus, and the CLI, which validates the
artifacts it reads and prints.
The browser runs a strict normalizer over the same corpus.

### Parity for the View Model

| Row | Tier | Evidence |
| --- | --- | --- |
| `/api/ui/viewers` | Route, covered | A new golden. `--api` reads the empty collection, and `--api --data` publishes: once accepted, printing the `generation` it is given, and twice refused, as `invalid` and as over `MAX_VIEW_STATE_BYTES` |
| `/api/ui/viewer` | Route, covered | The same golden. `--api` in process answers `no_viewer`; the harness transcript of `ui.viewer-order` reads the viewer attended last and one named by `?viewer=<id>` |
| `/api/ui/intents` | Route, covered | A new golden. `--api --data` in process, where no page is connected, pins the six codes a server gives without a page, `control_off` under `--ui-control off`, and `invalid` for an `if_generation` that names no `viewer` |
| `ui.view-state` | Interaction | `tests/dom/ui-view-state-session.js` runs the production `describe` functions and publisher through a session and prints the view state after each step |
| `ui.intent-apply` | Interaction | The same session applies intents: applied and found, applied and not found, offered, cancelled by input, and the two codes only a page gives, `busy` and `stale`, with an unpublished change among the stale cases. It prints each publish with the intent it names, the history length, and the focused element, which an applied intent leaves where it was |
| `ui.viewer-order` | Data, owned by `/api/ui/viewers` | A transcript through `--api --server` against a harness server with stub viewers: order by attention, the default viewer, the caps, and a `pending` outcome followed through its `status_route` |
| `ui.intent-notice-paint` | Paint-exempt | Where the notice sits, in headless Chrome, as `tests/test_nav_reveal_chrome.py` checks a reveal |

`ui.present-confirmation`, data owned by `cli/present.py`, is a later row.
It waits for the live-server registry with every other change to `--present`, and then
`tests/golden/cli-present-delivery.txt` gains the confirmed and refused reports.

Three checks make the parity rule stronger than it is today.

- **Any interaction session can end by printing the view state.** One observable for
  every session, in place of a report written by hand for each.
- **`--show` and the page must agree.** For each address in the `--show` goldens, a test
  compares the `object`, the `kind`, and the identifiers of the `views` printed with the
  `object`, `pane.kind`, and `pane.views` the browserless page publishes.
  A pull request’s addresses pass because `pane.views` holds registered views alone:
  `[pull-request]` beside `views: pull-request (default)`. An address with a fragment
  joins the test once `--show` splits the fragment off, which the agent interface plan
  lists with [the view slice](plan-2026-11-18-agent-interface.md#with-the-view-slice).
- **Coverage is a table.** `devtools/check_parity.py` gains a rule: every registered
  navigation panel and every kind’s page views has a facet whose `describe` ran in a
  session, or a row that says why it is not yet modeled.

## Key Decisions

Each decision gives the options it weighed, their trade-offs, and the decision.
All ten belong to [Phase 4](#phase-4-the-view-model).

| Standing, as of 2026-11-18 | Decisions |
| --- | --- |
| Taken by the owner on 2026-11-18 | **VM-1** A: the page publishes, and the server holds the latest. **VM-2** B: a summary and a facet per surface. **VM-3** C: one verb, `present`. **VM-4** is folded into VM-5. **VM-5** A: one `control` setting, whose default follows the caller and not `--untrusted`. **VM-6** B: a viewer per tab, in `sessionStorage`. **VM-7** A: no persistence. **VM-8** A, with the parent plan’s Decision 1: SoftSchema contracts. **VM-9** A: the tab’s one stream, and a `POST`. **VM-10** A: the summary and `present`, with the view slice first or beside the object slice |
| Open | None |

These were the parent plan’s Decisions 24 to 33 until this plan was split from it on
2026-11-18:

| The parent plan’s number | Here | Decision |
| --- | --- | --- |
| 24 | VM-1 | Where the View State Lives |
| 25 | VM-2 | What a View State Holds |
| 26 | VM-3 | The Write Model |
| 27 | VM-4 | The Standing of an Applied Intent |
| 28 | VM-5 | Consent and Trust |
| 29 | VM-6 | Viewer Identity |
| 30 | VM-7 | Persistence |
| 31 | VM-8 | The Schema Form |
| 32 | VM-9 | How Intents and States Travel |
| 33 | VM-10 | The View Model’s First Slice |

The two plans each have a first step, and name them.
The **view slice** is this plan’s, chosen in
[Decision VM-10](#decision-vm-10-the-view-models-first-slice), and the **object slice**
is the parent plan’s, chosen in its
[Decision 22](plan-2026-11-14-object-data-model-and-views.md#decision-22-the-first-slice).
Neither needs the other’s code.
What the view slice needs of the object half is a set of definitions and decisions,
listed under [Phase 4](#phase-4-the-view-model), and Decision VM-10 sets the order of
the two.

### Decision VM-1: Where the View State Lives

**Needed for:** Phase 4, the view slice.

- **A. The page publishes; the server holds the latest per viewer in memory and relays
  intents.** One place to read, for any shell, at one small request per settled change.
- **B. The server owns UI state, and pages render from it.** Every expansion would cross
  the network, against the instant-transition rules, and the shell would be rewritten.
- **C. On demand: the server holds nothing and asks the page.** No request per change;
  every read waits on a page, and a watch needs a second mechanism.
- **D. Browser automation.** An agent reads the DOM through a debugging protocol: no
  contract, no stable names, and it breaks with the markup.
- **E. The macOS app owns it.** One shell would have it, and the page would have to call
  into the app.

**Decided 2026-11-18: A,** with C’s mechanism for facets.

### Decision VM-2: What a View State Holds

**Needed for:** Phase 4, the view slice.

- **A. The address alone.** It exists and restores a selection.
  It cannot say the tab in front, a filter, or what is open.
- **B. A summary and a facet per surface, by reference.** Bounded, and each surface is
  added alone.
- **C. A component or accessibility tree.** Complete by construction.
  It is the DOM under another name, unbounded, with no vocabulary an agent can rely on.

**Decided 2026-11-18: B,** with A as its spine.

### Decision VM-3: The Write Model

**Needed for:** Phase 4, the view slice.

- **A. Navigate to an address.** It exists, and it cannot set what an address does not
  carry.
- **B. Verbs:** open, select, expand, set a filter, run a command.
  Each maps to one input; an agent must learn and order them, and nothing ties them to
  what it read.
- **C. `present`, a partial view state applied through the reader’s paths.** One verb,
  whose settable fields grow by slice.
  It needs a stated settable set and a fixed order of application.
- **D. A generic patch over the view state.** Most fields are derived, and a patch
  cannot be applied as input.

**Decided 2026-11-18: C.** In the view slice it equals A. B’s one verb worth keeping is
`run`, a registered command by identifier, deferred until a use appears.

### Decision VM-4: The Standing of an Applied Intent

Folded into [Decision VM-5](#decision-vm-5-consent-and-trust).
What an intent does when it arrives is a value of the setting that decision chooses, so
the two are one question, decided there.

### Decision VM-5: Consent and Trust

**Needed for:** Phase 4, the view slice.

This decision answers two questions together: what an intent does when it arrives, and
who may send one. The pin guard’s rule is that nothing changes under a reader
(`docs/project/architecture/arch-source-sessions-and-pins.md:235`). That rule is about
changes nobody asked for.

- **A. One setting, `control`, on by default where the server and the caller are
  local.** It has three values.
  `apply` applies an intent at once as an open, pushed to history and announced, which
  is the standing `--present` has.
  `offer` shows a notice that names the target, and the reader accepts it: nothing moves
  unasked, and the main use takes two steps.
  `off` stops pages publishing, and both routes refuse with `control_off`.
- **B. Off unless a flag allows it,** as `--allow-edits` is.
- **C. The reader allows it in the page,** per viewer.
- **D. Applied silently.** The reader cannot tell why the page changed.

**Decided 2026-11-18: A** for showing an address of the served root, which grants
nothing that `--present` and `open -b` do not already grant to any local process; **B**
for whatever is not showing, such as `run` or a switch of the served revision, which
stays off unless a flag allows it.
Under host mode the routes sit behind its credential, and no intent admits a root, as
that plan’s [Safety Rules](plan-2026-11-18-host-mode.md#safety-rules) require.

These points state A exactly.

- **`control` is trust in the caller, and is held outside `Capabilities`.** That block
  is content trust. Each of its switches is a boolean (`as_wire() -> dict[str, bool]`,
  `capabilities.py:72`), and a pinned revision is always answered under
  `UNTRUSTED_CAPABILITIES` (`capabilities.py:79-82`, `:92-105`). A `control` switch
  there would be off on every pin, and the mirror a GitHub pull request URL opens is a
  pin, which is the case the view slice exists for.
  So `control` is a setting of its own in `ui/`: three-valued, resolved once per
  process, and the same for a working tree and a pin.
- **Its flag is `--ui-control apply|offer|off`.** `METAB_UI_CONTROL` sets it from the
  process environment only.
  It joins the names the import guard keeps out of the `.env` allowlist
  (`dotenv.py:124`), so a browsed repository’s `.env` cannot set it.
  An explicit `--ui-control offer` or `off`, or `METAB_UI_CONTROL`, sets it whatever the
  default would be.
- **`--untrusted` does not decide `control`.** `--untrusted` is trust in content, and
  `control` is trust in the caller, so the default is the same under either content
  profile. A GitHub pull request URL implies `--untrusted`
  (`cli/git_pin_cli.py:114-124`), so a default that followed that flag would leave the
  view slice’s main case offer-only.
  Content trust does not change the harm either: an applied intent runs no file’s
  scripts, since it opens an HTML file on Source, as the last point here says.
- **“Local” is tested, not assumed.** The origin check accepts any request that sends
  neither `Origin` nor `Sec-Fetch-Site` (`server.py:840-841`), so the server cannot tell
  a local command from any other peer that sends neither.
  With a non-loopback `--host`, or a remote server reached through a forwarded port,
  local is whoever reaches the port.
  `delivery.py` already makes the tests that matter, and the default is `apply` only
  where all three hold, and `offer` anywhere else.
  Two are the server’s, made once as it starts: its bind host is loopback
  (`loopback_host`, `:107`), and its environment names no remote session
  (`remote_session`, `:97`). The third is the request’s: it came from a loopback peer
  that names no proxy (`loopback_peer`, `:124`). The default does not read
  `serving_locally()` (`:102`). `cli/serve.py:385-387` sets that flag from the same two
  server tests and `local_client`, which `cli/main.py:1009` sets to `--exit-on-eof`, so
  it holds only for a server the macOS app starts, and a server started with
  `metab ROOT`, by the user or an agent, would default to `offer`. This corrects the
  plan’s reading of the code to fit the decided intent, that the default follows whether
  the server and its caller are local, and is not a new decision.
- **It departs from the `mutations` precedent, on purpose.** The one write switch in
  `capabilities.py` is off by default (`DEFAULT_CAPABILITIES`, `:79`), and
  `--allow-edits` turns it on.
  An edit changes the reader’s files, and the page cannot undo it.
  A `present` changes what one tab shows; it is announced; Back undoes it; and it
  reaches nothing a local process cannot already reach through `--present`. Whatever is
  not showing keeps the precedent, which is the B half of the decision.
- **An applied intent does not run a file’s scripts.** An HTML file opens on Preview,
  its default view (`builtin_plugins/html/manifest.toml:15-20`), which loads the file in
  a sandboxed frame where its scripts run while active content is on
  ([HTML Preview](../../architecture/arch-server-and-content.md#html-preview)). A
  reader’s click is a gesture for that, and an intent is not.
  So an applied intent opens such a file on Source, as a line anchor already does
  ([URL grammar](../../architecture/arch-views-models-routes.md#browser-url-grammar)),
  and the reader’s own switch to Preview runs it.
  An offered intent opens on the default view, since the reader accepted it.
  Browsed content never executes in the application page
  ([Rendering Browsed Content](../../architecture/arch-server-and-content.md#rendering-browsed-content)),
  so Preview’s frame is where a file’s own scripts run today; a second such view would
  need a manifest flag the applier reads.

### Decision VM-6: Viewer Identity

**Needed for:** Phase 4, the view slice.

- **A. Per document, in memory.** No storage.
  Every load is a new viewer, and controls in four modules load a page in full
  (`static/source-freshness.js:886`, `static/source-ref-selector.js:814`,
  `builtin_plugins/diff/index.js:301`, `github/pull-page.js:7003`).
- **B. Per tab, in `sessionStorage`.** It survives a load, and the applier keeps the
  intent it is applying beside it, so the publish after a full load still names that
  intent. A duplicated tab copies it, so the server reassigns a second live claim.
- **C. Per connection, assigned by the server.** A reconnect is a new viewer.
- **D. The app’s window and tab identifiers.** The app alone has them.

**Decided 2026-11-18: B.** [Hosts](#hosts) lists what is verified in the app’s web view
before it ships.

### Decision VM-7: Persistence

**Needed for:** Phase 4, the view slice.

- **A. None.** The server holds a view state while its viewer is connected, and a short
  grace after. A shell that restores a session saves the view states it read and shows
  them again.
- **B. The server persists the last state per root.** It adds a record of what the
  reader looked at to the application home.
- **C. The page persists its own.** Filters reset on every page by design
  (`static/filter-state.js:19-21`).

**Decided 2026-11-18: A.**

### Decision VM-8: The Schema Form

**Needed for:** Phase 4, the view slice.
It was decided with the parent plan’s
[Decision 1](plan-2026-11-14-object-data-model-and-views.md#decision-1-what-describes-an-object).

- **A. SoftSchema contracts in the registry, in the `pure-yaml` profile.**
- **B. A YAML convention held by tests.** Nothing an agent or the CLI can name or
  validate.
- **C. JSON Schema without SoftSchema.** It rebuilds the identifier, digest, and corpus
  machinery.

**Decided 2026-11-18: A.** The owner chose SoftSchema contracts for this family and, in
that Decision 1, for objects, so both families take one form.
An intent is an artifact another program writes, and a view state is one an agent reads
and a shell may save, which are the YAML stage and the durability that Decision 1’s weak
points say objects lack.
That is this family’s own case.
It does not carry over to objects by itself, since an intent crosses a program boundary
and an object does not, so Decision 1 records those two weak points as costs it accepts,
and the question of the CLI printing an object as an artifact stays under the parent
plan’s [Open Questions](plan-2026-11-14-object-data-model-and-views.md#open-questions).

The registry needs no JSON profile, and the validation path is one story for both
families. A running server validates no response.
It checks what a client sends it, a published state and an intent, with the contract’s
Pydantic model alone.
`validate_record` (`plugin_loader/artifact_contracts.py:434`), a JSON Schema pass and
then the model, runs in the tests, the corpus, and the CLI
([UI Contracts](#ui-contracts)). Only printed or saved artifacts use `pure-yaml`.

This family brings its own registry, so the view slice waits for nothing that
[Decision 22](plan-2026-11-14-object-data-model-and-views.md#decision-22-the-first-slice)
D defers: the object contracts, the manifest blocks, the registry route, `--api`
validation of objects, and the two parity rules.

### Decision VM-9: How Intents and States Travel

**Needed for:** Phase 4, the view slice.

- **A. The tab’s one event stream carries intents, and a `POST` carries states.** The
  stream names its viewer, `?viewer=<id>`, and is served for every subject, with `ui`
  events alone where the subject has no `watcher` capability ([Writing](#writing)).
- **B. A second stream per tab.** A browser opens six connections to a host
  (`static/navigation.js:541`), so three tabs would take them all.
- **C. A WebSocket.** Nothing here uses one, and the origin checks would be written
  again.
- **D. Polling.** A delay on every intent, or a held request, which is B.

**Decided 2026-11-18: A.** Under host mode the same payloads move to its owner-only
socket and credential with the control verbs; what that socket speaks is the host mode
plan’s open
[HM-4](plan-2026-11-18-host-mode.md#decision-hm-4-what-the-control-socket-speaks).

### Decision VM-10: The View Model’s First Slice

**Needed for:** Phase 4, before anything else.

This decision chooses the **view slice**, the view model’s first step, and its order
with the object slice of
[Decision 22](plan-2026-11-14-object-data-model-and-views.md#decision-22-the-first-slice).

- **A. The summary, and `present` with an object or an address.** What the reader sees
  and “open this file or pull request”, the owner’s scope.
  An agent writes through `--api --server`.
- **B. Reading only.** An agent can see what the reader sees and can show nothing.
- **C. Wait for the list host, and ship lists with it.** Nothing until the parent plan’s
  Phase 1 list host lands, and nothing for a navigation panel until its Phase 3 moves it
  onto the host.
- **D. Confirmation for `--present` alone.** It waits for the live-server registry
  (`mb-5xi4`), builds the relay, and leaves it with one caller.

**Decided 2026-11-18: A.** Every later slice is a facet or a settable field added to
these contracts, which is not a break.

**Decided 2026-11-18, on order: the view slice first, or beside the object slice.** The
owner’s stated initial core is the view slice: knowing what the reader sees, and opening
files and pull requests.
It needs no code from Phases 1 to 3, and what it needs of the object half is a short
list of definitions and decisions ([Phase 4](#phase-4-the-view-model)). The two slices
meet in two places, the reference definitions and `--show`’s `object:` line, and
whichever lands first adds them.
Nothing else orders them, so they can also be built in parallel.

## Implementation Plan

The phases are numbered with the parent plan’s, which holds Phases 1 to 3. The
[implementation map](plan-2026-11-18-object-model-implementation-map.md) orders this
phase’s items among them, as its Stack V.

### Phase 4: The View Model

Phase 4 is listed last, and its first step, the view slice, waits for no other phase’s
code.
By [Decision VM-10](#decision-vm-10-the-view-models-first-slice) it lands first, or
beside the object slice.

**The view slice: what the reader sees, and “open this”.** It needs no code from Phases
1 to 3: an address and a reference convert both ways through parsers that exist and that
`navigation.route-identity` pins.
It does need four things of the object half: two decisions that are taken, and two
pieces of code that its second item writes.

- [Decision 5](plan-2026-11-14-object-data-model-and-views.md#decision-5-identity)’s
  type names and identifiers, which are decided: `file`, `folder`, `commit`, and
  `pull-request`.
- [Decision 3](plan-2026-11-14-object-data-model-and-views.md#decision-3-the-collection-envelope)’s
  convention, which the list of viewers answers in, and which is also decided.
- The shared definitions of a reference and a collection reference
  ([Approach](plan-2026-11-14-object-data-model-and-views.md#approach)), which both
  contract families include.
- `--show`’s `object:` line, which the agreement test compares.
  It is a Phase 2 item under
  [Decision 22](plan-2026-11-14-object-data-model-and-views.md#decision-22-the-first-slice)
  D, so the view slice adds it when it lands first.

No object registry exists yet, so an intent’s `object.type` is checked against a fixed
list, one of Decision 5’s types, which becomes the registry’s when the registry is
built.
[Decision 2](plan-2026-11-14-object-data-model-and-views.md#decision-2-standing-of-the-contracts)
says what an outside writer of an intent is promised.

- [ ] Measure the publish and the pinned page’s stream in Chrome and WebKit before
  either ships. The measurement comes first, because it sets `MAX_VIEWERS`,
  `MAX_VIEW_STATE_BYTES`, and the publisher’s debounce.
  With it, verify viewer identity and the stream in the app’s web view, as
  [Hosts](#hosts) lists.
- [ ] Add the reference and collection reference definitions in `objects/`, and the
  `object:` line in `--show`, each unless the object slice has landed it.
  The implementation map lands both as groundwork, before either slice.
- [ ] Add `ui/` with the two contracts, their schemas and corpus under
  `data/ui-format/`, the family’s registry, the fixed list of types with the route each
  one’s reference leads to, the model’s rule that `if_generation` names its `viewer`,
  and the `control` setting with its `--ui-control` flag and its default by caller; have
  `devtools/check_artifact_contracts.py` compare that registry with a contract table in
  a new `docs/project/architecture/arch-view-model.md`. The check compares one registry
  with one document today, and the parent plan’s Phase 2 adds a pair too, so it is
  changed once, to take a list of pairs.
- [ ] Add the viewer registry, `GET` and `POST /api/ui/viewers`, the record route
  `GET /api/ui/viewer`, and `/api/ui/intents` with its outcome envelope; give the event
  stream `?viewer=<id>`, and serve it for every subject, with `ui` events alone where
  the subject has no `watcher` capability, since a pinned revision’s page has no stream
  today (`events_route.py:773`, `static/app.js:9109`).
- [ ] Teach the pane’s lifecycle the two facts `pane.status` needs: a 404 apart from
  another failure, and the status of an owner that paints for itself
  ([The View State](#the-view-state)).
- [ ] Add `static/ui-state.js` in the deferred tier: the registry of `describe`
  functions and the summary’s functions, with an adapter in each navigation panel for
  `nav.current`, the publisher, `openAddress`, the applier for `present` with `object`
  or `address`, which enforces `if_generation` and names the intent in its publish, and
  the notice.
- [ ] Add `--api --server URL` and the artifact form of `--format yaml`. `--present`
  does not change in this slice.
- [ ] Add the parity rows, the browserless session, the agreement test, a design-system
  entry naming a local command as a route of Navigation Reveals the Item, and the rows
  of [Views, Models, and Routes](../../architecture/arch-views-models-routes.md).

**Later slices,** each mapped above, independent, and added as a facet or a settable
field:

| Slice | Waits for |
| --- | --- |
| The bounded wait on `/api/ui/viewer`, `since` and `wait` | Nothing more; a measured cap on the wait, in `ui/` |
| `pane.list` for `/pulls`; facets on request; an observer’s stream of states | The parent plan’s Phase 1 list host |
| `--live`; every change to `--present`: the intent it sends after the handoff, its confirmed report, and the `ui.present-confirmation` row | The host mode plan’s steps H3 to H5 ([Implementation Plan](plan-2026-11-18-host-mode.md#implementation-plan)): the listing of live servers, `--live`, and the find-or-start lock |
| `nav.list` for Pulls, Commits, and Files, and for Recent, which is on the list host from the start; `present` sets `nav.tab`, `params`, and `expanded` | Each panel’s move to the list host in the parent plan’s Phase 3, until which the view slice’s adapter publishes `nav.current` alone; the Recent tab plan’s R4 |
| `pane.parts` and `mb.ui`; `pane.inner`; `present` sets `pane.view` and `pane.inner` | A page view’s declaration of its parts through `mb.ui`; a contract for the nested types `pane.inner` names |
| `overlay`, `display`, `commands`; a `run` verb; the app’s session saved as view states | A need for each |

## Testing Strategy

[Parity for the View Model](#parity-for-the-view-model) lists the rows.
The evidence is:

- a browserless session that prints the view state after each step and applies intents
  through the production publisher and applier;
- a test that `--show` and the browserless page agree on `object`, `kind`, and `views`
  for every address in the `--show` goldens;
- `--api` goldens for a publish and for the six refusals a server gives without a page;
- the session for the two refusals only a page gives, `busy` and `stale`.

## Rollout Plan

The view slice can ship before the parent plan’s Phase 1: it needs the decisions and
definitions listed under [Phase 4](#phase-4-the-view-model) and the address parsers that
exist.
Its later slices ship as the surfaces they read move onto the list host, and every
change to `--present` ships with the live-server registry.
Agent control ships under the `control` setting of
[Decision VM-5](#decision-vm-5-consent-and-trust), so an operator can lower it to
`offer` or turn it off.

## Open Questions

- **Finding a running server.** Reading from ROOT, and every change to `--present`, need
  the listing of live servers, which is planned and not built.
  Until it lands, the view slice serves a caller that knows the server’s address,
  through `--api --server`. The host mode plan’s open
  [Decision HM-1](plan-2026-11-18-host-mode.md#decision-hm-1-when-discovery-lands) asks
  whether discovery lands ahead of host mode’s credential.

- **What publishing costs.** One request per settled change, and one held stream on a
  pinned page that has none today.
  Neither is measured, and connection starvation has happened twice here
  (`explorations/page-connections/`, `explorations/tree-summary-storm/`).

- **What counts as busy?** A modal, by the overlay controller; an unsaved edit, once
  editing is built.

- **A hidden viewer.** A page cannot raise its window
  (`docs/project/research/research-2026-11-10-native-app-server-topology.md:668`). The
  outcome’s view state carries `attention`, and `--present` keeps the app handoff for
  fronting.

- **The pull request page’s tabs.** One registered view draws all three, so `pane.view`
  is `pull-request` at each, as `--show` prints, and the tab is read from `address` and
  later from `pane.parts`. Registering three page views instead would make the tab a
  `pane.view`. It is a prerequisite the plan does not take: it changes what `--show`
  prints for every pull request address, and their goldens.

- **A reference to a type with no contract.** `changed-file` and a container’s entry
  have identities and no contract yet, which is why `pane.inner` is left out of the view
  slice.

- **The served revision.** A `/view/` address names no revision, and a switch moves
  every tab, so `present` leaves `served` read-only.

- **Forged publishes.** Any process that reaches the port can publish a state for a
  viewer, as it can call any route; host mode’s credential is the answer.

- **Which routes answer a contract record?** `--format yaml` prints an artifact for an
  answer that is one contract record ([Reading](#reading)), and nothing yet tells the
  command which routes those are.
  The family’s registry is the likely place, and the agent interface plan’s
  [Self-Description](plan-2026-11-18-agent-interface.md#self-description) asks the route
  listing to say it.

- **Parts of an embedded view.** The example under [UI Contracts](#ui-contracts) reports
  `diff-summary` and `layout` under the pull request page, which embeds the diff view.
  Which view declares an embedded view’s parts is an
  [open question](plan-2026-11-18-plugin-authoring-objects-views.md#open-questions) of
  the plugin authoring plan.

## References

- [Object Data Model and Views](plan-2026-11-14-object-data-model-and-views.md), the
  parent plan, and its other companions:
  [Agent Interface for Objects and View State](plan-2026-11-18-agent-interface.md),
  [Plugin Authoring for Objects, Views, and View State](plan-2026-11-18-plugin-authoring-objects-views.md),
  [The Recent Tab](plan-2026-11-18-recent-tab-updates-and-events.md), and the
  [implementation map](plan-2026-11-18-object-model-implementation-map.md)
- [Views, Models, and Routes](../../architecture/arch-views-models-routes.md),
  [Parity Registry](../../architecture/arch-parity-registry.md),
  [Open Modes](../../architecture/arch-open-modes.md),
  [Command Line](../../architecture/arch-cli.md),
  [Source Sessions and Pins](../../architecture/arch-source-sessions-and-pins.md),
  [Server and Content](../../architecture/arch-server-and-content.md#api-origin-proof),
  and [macOS App](../../architecture/arch-macos-app.md)
- [Native macOS App](plan-2026-11-10-native-macos-app.md), whose Phase 3 plans
  `present`, `clients`, and `navigate`; this plan defines what they carry, and
  [the app and server topology research](../../research/research-2026-11-10-native-app-server-topology.md)
- [Host Mode](plan-2026-11-18-host-mode.md): how any host launches and owns a server,
  and how an agent finds and reaches one
- [Design System](../../../design-system.md): Navigation Reveals the Item
- [SoftSchema](https://github.com/jlevy/softschema): its guide and specification

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
