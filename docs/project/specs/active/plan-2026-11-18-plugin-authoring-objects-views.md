# Feature: Plugin Authoring for Objects, Views, and View State

**Date:** 2026-11-18

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Decided, and nothing here is built.
The owner took every decision here, PS-1 to PS-7, on 2026-11-18, each at A, with the
decisions this document rests on: the parent plan’s Decisions 1 to 23 and the view model
plan’s VM-1 to VM-10. A companion to
[Object Data Model and Views](plan-2026-11-14-object-data-model-and-views.md), called
the parent plan below, and to
[View Model and View State](plan-2026-11-18-view-model-and-view-state.md), the view
model plan, which holds the view state and its Phase 4. Written against `main` at
`4a5b9e825`. Clarifications dated 2026-11-19, from an independent review, are marked at
the decisions they touch.

## Overview

The parent plan gives each thing Metabrowser shows one object model and several views of
it, and the view model plan gives each viewer a view state an agent can read and set.
This document is that design as a plugin author meets it: what `manifest.toml` declares,
what `index.js` registers, what the plugin’s Python ships, and which tests hold the
three together.

One rule shapes the surface:

- **The manifest declares structure.** Every type, facet, view, collection, and settable
  part of a page is a manifest key, because the server, `metab`, `--doctor`, and the
  parity check read manifests and run no plugin JavaScript.
- **Python supplies data:** a compiled contract schema, its corpus, a projection, and
  routes.
- **JavaScript supplies functions:** `normalize`, `describe`, and `paint`.

No fact is stated in two of the three, and a test binds each declaration to its function
([Decision PS-1](#decision-ps-1-where-structure-is-declared)).

Paths are under `src/metabrowser/` unless they start with `docs/`, `tests/`, or
`devtools/`; `static/` is the browser shell.

## Background

Four facts about today’s plugin contract constrain the design.

- **Unknown manifest keys are refused** (`plugin_loader/manifest.py:348`), so a new
  block is part of the SDK gate ([Versioning](#versioning)).
- **A plugin’s code loads by kind.** The shell indexes a plugin’s assets under the kinds
  its `[[kind]]` and `[[view]]` blocks name (`server.py:5057-5058`) and loads them when
  one is selected (`static/plugin-sdk.js:382`). A list drawn on another plugin’s page
  selects none of them
  ([Decision PS-6](#decision-ps-6-loading-the-plugins-a-list-needs)).
- **A plugin cannot register an address**
  ([Registration Surfaces Not Built](../../architecture/arch-plugin-system.md#registration-surfaces-not-built)).
  A plugin type’s page is therefore a kind’s page at a `/view/` address, or a place
  inside its parent’s page
  ([Decision PS-5](#decision-ps-5-a-type-whose-objects-are-files)).
- **Startup loads no schema library** (`tests/test_plugin_public_api.py:101`), so checks
  at load read text, and `metab --doctor` does the schema work.

## Design

### Manifest Blocks

There are four new blocks and one nested table.
Every name follows the plugin-name grammar (`plugin_loader/manifest.py:311`), and every
file key follows the plain-filename rule of `extra_scripts` (`:472`).

**`[[object_type]]`** declares a type this plugin owns.

| Key | Type | Meaning | Refused at load when |
| --- | --- | --- | --- |
| `id` | string, required | The type token, an object’s `type` | Core or another plugin declares it |
| `contract` | string, required | The contract identifier | It is outside the registry’s grammar (`plugin_loader/artifact_contracts.py:31`), or its namespace does not end with the plugin’s name, `_` written `-` |
| `schema` | string, required | The compiled schema, a file in the plugin directory | The file is absent |
| `corpus` | string, required | The conformance corpus, a JSON file there | The file is absent |
| `model` | string | `module:Class`, read only by the drift check | The plugin’s Python does not run in the server |
| `page_kind` | string | The kind whose `[[view]]` tabs are this type’s page | No loaded plugin declares or draws that kind |
| `route` | string | The type’s object route, where a reference leads: a GET data hook answering one object by `?id=<id>`, with `?facets=` naming the facets wanted | This plugin has no such `[[data_hook]]` |
| `batch_route` | string | Optional. A GET data hook answering many objects by `?ids=` and `?facets=` in the collection convention. The store’s default loader uses it where it is declared, and otherwise asks `route` once for each reference | This plugin has no such `[[data_hook]]`, or the type declares no `route` |
| `facets` | list of strings | The type’s facets | A name repeats |

**`[[object_view]]`** declares a drawing of a type, its own or another’s, in a row
shape.

| Key | Type | Meaning | Refused at load when |
| --- | --- | --- | --- |
| `type` | string, required | The type drawn | Neither core nor a loaded plugin declares it |
| `shape` | `nav-row`, `wide-row`, or `card`, required | The shape | It is any other value; `page` is refused with a message naming `[[view]]` |
| `facets` | list of strings | The facets its `describe` reads, which the list host requests for the rows in view | The type declares no such facet |

One manifest may not repeat a type and shape.
`card` is in the set by the parent plan’s
[Decision 11](plan-2026-11-14-object-data-model-and-views.md#decision-11-the-set-of-shapes),
and its frame is built with its first real use, so a `card` view draws from then.
Across plugins the later one in discovery order replaces the earlier, as a `[[view]]`
does, and `metab --doctor` names both.

**`[[collection]]`** declares a list of objects.

| Key | Type | Meaning | Refused at load when |
| --- | --- | --- | --- |
| `name` | string, required | The `name` of its collection reference | Another declaration has the same `name` and `parent` |
| `members` | list of strings, required | The types its rows may hold | It is empty, or names an undeclared type |
| `route` | string, required | A GET data hook answering the collection convention: `rows`, `next_after`, `complete`, `truncated`, `generation` | This plugin has no such `[[data_hook]]` |
| `params` | list of strings | The query parameters that select a list; `after` is the cursor | It names `after` |
| `parent` | string | The type a collection sits on; its reference then carries `parent`, that object’s reference | The type is undeclared |

**`[[collection_source]]`** joins a core mixed collection.
The first is `recent`, the Recent tab’s list, and
[The Recent Tab](plan-2026-11-18-recent-tab-updates-and-events.md#updates-and-events)
defines what a source answers: changes, not objects.

| Key | Type | Meaning | Refused at load when |
| --- | --- | --- | --- |
| `collection` | string, required | The core collection joined | It admits no sources |
| `type` | string, required | The type of the subjects this source’s changes name | This plugin does not own it |
| `route` | string, required | A GET data hook answering this source’s changes in time order, each `{subject, at, kind}`, from memory or cache alone | This plugin has no such `[[data_hook]]` |
| `kinds` | table, required | Each kind token this source answers, mapped to `clumping` or `standalone`, as in `kinds = { opened = "standalone", comment = "clumping" }` | It is empty, or a value is neither word |

**`[[view.part]]`**, nested under a `[[view]]`, declares a part of that page which a
view state reports and `present` may set: an entry of the view model plan’s `pane.parts`
facet ([The View State](plan-2026-11-18-view-model-and-view-state.md#the-view-state)).

| Key | Type | Meaning | Refused at load when |
| --- | --- | --- | --- |
| `id` | string, required | The part’s name in `pane.parts` | It repeats within the view |
| `values` | list of strings | Its values; omitted, the part is open or closed | It has fewer than two |

`[[kind]]`, `[[view]]`, and `[[data_hook]]` are unchanged.
A type is not a kind (the parent plan’s Decision 4), and `page_kind` joins the two; a
`[[view]]` is the `page` shape; and every `route` and `batch_route` above names a
`[[data_hook]]`, still the only Python a manifest mounts, so `--api` reaches each by
construction. An operator-directory plugin is JavaScript-only
([Discovery](../../architecture/arch-plugin-system.md#discovery)), so it may declare
`[[object_view]]` and `[[view.part]]` and is refused the three blocks that name routes.

`metab --doctor` repeats the load checks and adds those that read a schema:

- The schema declares `contract`, its digest matches, and it is enforceable, as the
  registry requires (`plugin_loader/artifact_contracts.py:352`).
- Its header and shared sub-object definitions equal the host’s.
- The corpus has valid and invalid cases, and each behaves as it says
  (`plugin_loader/artifact_inventory.py:375-377`, `:415`).
- Each `facets` name is an optional top-level property, and every other property outside
  the header is required.
- A declared `model` compiles to the packaged schema.

Problems print as they do now (`cli/plugins.py:421`):

```text
metab --doctor: 1 problem(s):
  • plugin 'agent-log': object_view (agent-session, card) reads facet 'usage', which
    object_type 'agent-session' does not declare
```

`metab --plugin NAME --json` gains the four lists (`cli/plugins.py:103`), and
`GET /api/object-types` answers the merged registry with each schema’s digest.

### JavaScript SDK

`MetabrowserSdk` (`static/types.d.ts:1527`) gains `objects` and `ui`:

```typescript
type MetabrowserObjectRef = Readonly<{ type: string; id: string; parent?: MetabrowserObjectRef }>;
type MetabrowserParams = Readonly<Record<string, string>>;
type MetabrowserCollectionRef = Readonly<{
  name: string; params?: MetabrowserParams; parent?: MetabrowserObjectRef;
}>;
type MetabrowserRowShape = "nav-row" | "wide-row" | "card";
type MetabrowserObject = Readonly<{
  type: string; id: string; href: string; title: string;
  updated_at: string | null; actor?: MetabrowserActor; [field: string]: unknown;
}>;

type MetabrowserObjectsApi = Readonly<{
  // Read.
  get(ref: MetabrowserObjectRef): MetabrowserObject | undefined;
  subscribe(ref: MetabrowserObjectRef, listener: (object?: MetabrowserObject) => void): () => void;
  ensure(ref: MetabrowserObjectRef, options?: { facets?: ReadonlyArray<string>; signal?: AbortSignal }):
    Promise<MetabrowserObject | undefined>;
  collection(ref: MetabrowserCollectionRef): MetabrowserCollectionHandle;
  // Register and write: the declaring plugin.
  registerType<T extends MetabrowserObject>(type: string, spec: Readonly<{
    normalize(value: unknown): T; // strict: throws outside the contract
    load?(refs: ReadonlyArray<MetabrowserObjectRef>,
      request: { facets: ReadonlyArray<string>; signal: AbortSignal }): Promise<ReadonlyArray<unknown>>;
  }>): void;
  registerCollection(name: string, open: (ref: MetabrowserCollectionRef) => MetabrowserCollectionHandle): void;
  // A generation is opaque: the store compares two for equality, never for order.
  put(value: unknown, origin: { feed: string; generation: string | number }): void;
  // Draw.
  registerView<T extends MetabrowserObject, D>(type: string, shape: MetabrowserRowShape, spec: Readonly<{
    describe(object: T, context: MetabrowserDescribeContext): D; // pure and named
    paint(frame: MetabrowserFrame, description: D): Readonly<{ update(next: D): void; dispose(): void }>;
  }>): void;
  mountList(container: HTMLElement, options: MetabrowserListOptions): MetabrowserListHandle;
}>;

type MetabrowserCollectionHandle = Readonly<{
  ref: MetabrowserCollectionRef;
  rows(): ReadonlyArray<MetabrowserObjectRef>;
  freshness(): Readonly<{ state: "absent" | "pending" | "current" | "stale";
    refreshing: boolean; complete: boolean; truncated: boolean; error: Error | null }>;
  more(): Promise<void>;
  subscribe(listener: () => void): () => void;
}>;
type MetabrowserDescribeContext = Readonly<{
  shape: MetabrowserRowShape; collection: MetabrowserCollectionRef | null;
  position?: unknown; // collection context, such as graph lanes
}>;
type MetabrowserFrame = Readonly<{ shape: MetabrowserRowShape; slots: Readonly<Record<string, HTMLElement>> }>;
type MetabrowserListOptions = Readonly<{
  collection: MetabrowserCollectionRef;
  shape: MetabrowserRowShape;
  activation?: "enter" | "move"; // what opens a row; "enter" in the pane
  history?: "push" | "replace";
  sectionOf?(object: MetabrowserObject): string | null; // pure
  state?: MetabrowserListState; // a list facet to restore
}>;
type MetabrowserListHandle = Readonly<{ ready: Promise<void>; state(): MetabrowserListState; dispose(): void }>;

type MetabrowserParts = Readonly<Record<string, { open: boolean } | { value: string }>>;
type MetabrowserUiApi = Readonly<{
  registerParts<S>(kind: string, view: string, spec: Readonly<{ describe(state: S): MetabrowserParts }>): void;
  bind<S>(container: HTMLElement, binding: Readonly<{
    state(): S;
    present?(request: Readonly<{ parts: MetabrowserParts }>, options: { signal: AbortSignal }): void | Promise<void>;
  }>): Readonly<{ changed(): void; dispose(): void }>;
}>;
```

`MetabrowserActor` is the header’s `actor`, and `MetabrowserListState` the parent plan’s
list facet: `collection`, `shape`, `focused`, `expanded`, `closed_sections`, and
`window`. A frame’s slots follow its shape’s frame in that plan, `lead`, `title`,
`meta`, and `trail` for a `wide-row` and `title`, `byline`, and `body` for a `card`; the
design-system section for each shape settles the names.

**What needs no JavaScript.** A type with a manifest `route` gets a default loader,
which asks its `batch_route` for the references wanted where one is declared and
otherwise its `route` once for each, and a `[[collection]]` is read from its route by
the collection convention
([Decision PS-2](#decision-ps-2-default-loaders-and-collections)). `load` and
`registerCollection` are for a controller of the plugin’s own, as the Pulls panel’s is.
A minimal type registers `normalize` and its views.

**View state.** The list host publishes each list’s facet, so a plugin that calls
`mountList` writes no view-state code, and a page view with no parts writes none.
One with parts registers a pure `describe` from its own state to its declared parts and
binds each mount: `state()` gives that state, `changed()` asks the publisher to describe
again, and `present` applies a request.
The server refuses an intent naming an undeclared part as `unsupported_field`, and a
value outside `values` as `invalid`, before it reaches the page.
`pane.view` and `pane.inner` need no call: the shell switches to a registered view, and
`pane.inner` is the item the address names, so the host opens that address and the view
receives it in its render context, as any open.

**Lifecycle.**

- **Registration** (`registerType`, `registerCollection`, `registerView`,
  `registerParts`) runs once, synchronously, while the plugin’s module evaluates.
  It records, loads nothing, and has no disposer.
  The host evaluates one plugin at a time (`static/plugin-sdk.js:391-393`), so it knows
  whose registration each is, and it checks each against the declarations the shell
  injects beside the asset index (`server.py:5029`).
- **A mount owns what it starts.** `mountList` returns at once with `ready` and an
  idempotent `dispose`, the form a view handle has
  ([Registration and Lifecycle](../../../plugins.md#registration-and-lifecycle)). A
  view’s `dispose` calls the list’s, each `subscribe`’s unsubscribe, and each binding’s,
  and aborts the signals it gave `ensure`.
- **A row’s `paint` handle** is disposed when its row leaves the window or its list is
  disposed, so `paint` keeps nothing outside its frame.
- **Lazy mounting.** A nondefault tab mounts on first activation, and a list reads its
  collection only while its container is active (`static/view-state.js:36`).

**Loading tier.**

| Code | Tier |
| --- | --- |
| The store, and every `mb.objects` call but the list host | The `sdk-views` on-demand bundle, in place before any plugin code runs (`static/plugin-sdk-views.js:11-16`) |
| The list host | Its own on-demand bundle, fetched by the first `mountList` and prefetched in idle time |
| `mb.ui` | Recording stubs in `sdk-views`; the publisher takes them when the deferred `static/ui-state.js` loads, as plugin shortcuts are queued (`static/plugin-sdk.js:185`) |
| A plugin’s functions | With the plugin, when a kind it names is selected, or a list mounts whose types it declares or draws ([Decision PS-6](#decision-ps-6-loading-the-plugins-a-list-needs)) |

**Errors.**

| Where | Failure | Result |
| --- | --- | --- |
| Any registration | A malformed argument | Throws, as `registerView` does (`static/plugin-sdk.js:483`); the e2e test reports a load error |
| Any registration | No loaded manifest declares it, it repeats, or a later plugin’s `[[object_view]]` replaces it | Ignored, with one console warning |
| `put` | `normalize` throws | Nothing is held, and the caller gets the error |
| A default loader or collection | A failed request, a `plugin_error` body, or a row `normalize` refuses | `ensure` rejects, or the handle’s `error` is set; the list keeps its rows and shows a local failure |
| `describe` or `paint` | Throws | That row draws the header fallback, with one console error per type and shape |
| A binding’s `present` | Throws | Logged. The outcome stays `applied`, and the view state it carries reports each part’s real value |

### Python: Contracts and Projections

A type’s Python is a contract, a projection, and routes.

- **The contract** is a Pydantic model that forbids unknown fields and extends the
  host’s header, reusing its shared sub-objects.
  `softschema` compiles it, as `compile_contracts` does for the cache
  (`cache/contracts.py:238`), into the `schema` file, with every definition inlined,
  since the registry admits only local references
  (`plugin_loader/artifact_contracts.py:286`). The file ships in the wheel beside the
  manifest, and `/plugin-static/` serves it as it serves any plugin file.
  `--api` issues `/api/` routes alone, so an agent reads a schema through the contracts
  route of the agent interface plan’s
  [Self-Description](plan-2026-11-18-agent-interface.md#self-description), which answers
  the parent plan’s question of whether schemas are served.
- **The packaged schema is the authority, for every plugin**
  ([Decision PS-7](#decision-ps-7-one-validation-path)). The host builds the type’s
  registry entry from the packaged bytes and imports no plugin model.
  The entry’s `validate_record` and `dump_record` callables
  (`plugin_loader/artifact_contracts.py:73-74`) pass the record through, so the JSON
  Schema pass (`:447`) is the whole check, and a rule no schema can state belongs in the
  projection’s tests.
- **Validation runs** in `--doctor`, in tests, and in `--api` over a declared route,
  which validates `rows` before normalizing them.
  A running server validates no response (the parent plan’s Decision 16).
- **The projection** is one function from the plugin’s record to the object, with every
  branch driven by a test.
  The summary holds only what the collection’s route can answer for every row from
  memory or cache; whatever costs a read per object is a facet.
- **The corpus** is JSON in the registry’s case form: `name`, `record`, `changes`, and
  `expect` (`plugin_loader/artifact_inventory.py:178`). It needs a summary-only base
  record, a valid case for each facet, and invalid cases for a missing summary field, an
  unknown field, a partial facet, and a wrong `type`. Its data is synthetic.
- **Under #380,** a third-party plugin’s Python runs in a worker whose `metabrowser` is
  a standard-library runtime.
  Its routes return JSON, its model compiles at build time, where `softschema` and the
  host’s header are development dependencies, and nothing above changes.

### A Worked Example

A hypothetical extension of the built-in `agent-log` plugin, a candidate type in the
parent plan: an agent session, listed under a folder.

**Manifest**, added to `builtin_plugins/agent_log/manifest.toml`, with three
`[[data_hook]]` routes: `sessions`, the collection; `session`, one session by its `id`;
and `session-batch`, many by `?ids=`:

```toml
[[object_type]]
id = "agent-session"
contract = "metabrowser.agent-log:AgentSession/v1"
schema = "agent-session-v1.schema.yaml"
corpus = "agent-session-conformance.json"
model = "metabrowser.builtin_plugins.agent_log.objects:AgentSession"
page_kind = "agent-log"
route = "session"
batch_route = "session-batch"
facets = ["tally"]

[[collection]]
name = "agent-sessions"
members = ["agent-session"]
route = "sessions"
params = ["path"]

[[object_view]]
type = "agent-session"
shape = "wide-row"

[[object_view]]
type = "agent-session"
shape = "card"
facets = ["tally"]

[[view]]            # the Log view that exists, which gains one part
kind = "agent-log"
id = "log"
label = "Log"
key = "v"
default = true

[[view.part]]       # open or closed
id = "tool-output"

[[view]]            # a tab on the folder kind, which mounts the list
kind = "folder"
id = "agent-sessions"
label = "Sessions"
key = "n"
```

The compiled schema and the corpus sit beside the manifest, in
`builtin_plugins/agent_log/`.

**Contract and projection**, in `builtin_plugins/agent_log/objects.py`:

```python
class SessionTally(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str | None
    events: int
    counts: dict[str, int]


class AgentSession(ObjectHeader):  # type, id, href, title, updated_at, actor
    type: Literal["agent-session"]
    agent: Literal["claude", "gemini", "pi"]
    size: int
    tally: SessionTally | None = None  # a facet: whole or absent
```

An object’s `id` is the log’s inventory path, its `href` `/view/<id>`, its `title` the
file name, and its `updated_at` the modification time.
The summary is what a folder listing holds, plus the adapter, sniffed from each log’s
first records as the Charts projection sniffs it (`charts.py:131`); `sessions` bounds
how many logs it sniffs for one answer and records the measurement.
The `tally` facet is what a full parse yields: the `summary` that projection builds
(`charts.py:168-173`), read through its fingerprint memo (`charts.py:43`) by `session`
for one object and by `session-batch` for the rows in view.
`project_session` and `project_tally` are the projections.
The corpus has a `claude` base record, a valid case for each agent and for a `tally`,
and the four invalid cases.

**JavaScript**, in `index.js`:

```javascript
function normalizeAgentSession(value) { /* returns the object, or throws outside the contract */ }
mb.objects.registerType("agent-session", { normalize: normalizeAgentSession });

function describeSessionWideRow(session) {
  return { title: session.title, agent: session.agent, size: session.size };
}
function paintSessionWideRow(frame, description) {
  const apply = (d) => {
    frame.slots.title.textContent = d.title;
    frame.slots.meta.textContent = d.agent;
    frame.slots.trail.textContent = mb.formatSize(d.size);
  };
  apply(description);
  return { update: apply, dispose() {} };
}
mb.objects.registerView("agent-session", "wide-row", {
  describe: describeSessionWideRow, paint: paintSessionWideRow });

function describeSessionCard(session) {
  const tally = session.tally ?? null; // absent: the body keeps its reserved box
  return { title: session.title, byline: session.agent, events: tally && tally.events };
}
mb.objects.registerView("agent-session", "card", {
  describe: describeSessionCard, paint: paintSessionCard }); // paints as the row does

mb.registerView("folder", "agent-sessions", {
  render(container, ctx) {
    const list = mb.objects.mountList(container, {
      collection: { name: "agent-sessions", params: { path: ctx.path } },
      shape: "wide-row",
    });
    return { ready: list.ready, dispose: () => list.dispose() };
  },
});

function describeLogParts(state) {
  return { "tool-output": { open: state.toolOutputOpen } };
}
mb.ui.registerParts("agent-log", "log", { describe: describeLogParts });
// In the Log view's render; its dispose calls parts.dispose().
const parts = mb.ui.bind(container, {
  state: () => state,
  present(request) {
    const part = request.parts["tool-output"];
    if (part && "open" in part) setToolOutput(part.open);
  },
});
```

It registers no collection and no loader: the store reads `sessions` and
`session-batch`, and a reference leads to `session`. With the Log view open, the view
state’s `pane` holds `kind: agent-log`, `view: log`, and
`parts: {tool-output: {open: true}}`.

**The evidence it needs:**

| Evidence | Form |
| --- | --- |
| The routes `sessions`, `session`, and `session-batch` | Route rows in the [Parity Registry](../../architecture/arch-parity-registry.md), with `--api` goldens in `cli-api-plugins.tryscript.md`, where the plugin’s `charts` route is pinned |
| The type | Validated rows in the `sessions` golden, the parent plan’s rule for a type `--show` does not report ([Decision PS-5](#decision-ps-5-a-type-whose-objects-are-files)) |
| `agent-log.session-views` | An interaction row naming `describeSessionWideRow` and `describeSessionCard`; its session prints each description of each corpus object, pinned as `cli-ui-agent-log-session-views.tryscript.md` |
| `agent-log.log-parts` | An interaction row naming `describeLogParts`; its session ends by printing the view state |
| The Sessions tab | A `--show` case for a folder that lists the view, and a row in [Views, Models, and Routes](../../architecture/arch-views-models-routes.md) |
| Paint | A paint-exempt row for the wide row’s grid, measured in headless Chrome |

### Versioning

`PLUGIN_SDK_VERSION` covers the blocks, `mb.objects`, `mb.ui`, the frames’ slots, the
collection convention, and the core contracts a plugin reads.
A plugin’s own contract carries its own version.

| Change | Today’s rule, an exact match (`plugin_loader/manifest.py:369`) | #380’s caret rule |
| --- | --- | --- |
| Landing the blocks, `mb.objects`, and `mb.ui` | No bump, under the parent plan’s Decision 20 A; an older host refuses a manifest that uses them, as an unknown key | A patch bump and an `sdk-changes.toml` entry; an older host refuses by version, read before the keys |
| An added optional key, call, shape, slot, or optional contract field | No bump | Patch |
| A removed or renamed key, call, slot, or convention key; a changed `describe`, `paint`, or `present` signature | A bump, with every built-in manifest in the commit | Minor |
| A break in the header, a shared sub-object, or a core contract | The same | Minor |
| A break in a plugin’s own contract | None; another plugin’s view of that type breaks unguarded ([Open Questions](#open-questions)) | None |

### Testing Helpers

- **The binding test.** `tests/dom/load-plugins.js` reports each declared type, object
  view, and part beside what was registered, and
  `test_every_declared_view_has_a_registration` (`tests/test_plugin_e2e_render.py:77`)
  gains three siblings: a type with no `registerType`, an `[[object_view]]` with no
  `mb.objects.registerView`, and a `[[view.part]]` its registered `describe` does not
  return. A registration with no declaration fails too.
- **A describe session with no code per plugin.** One runner,
  `tests/dom/object-views-session.js <plugin>`, loads the plugin through that shim, puts
  each valid corpus case through `normalize`, and prints every registered `describe` of
  it. A plugin gets the golden by declaring a corpus and naming the session in its parity
  row.
- **Normalizer against contract.** The same session requires `normalize` to accept every
  valid case and throw on every invalid one, which holds the JavaScript normalizer to
  the Python contract.
- **The corpus runner.** `metab --doctor` runs any discovered plugin’s corpus, and
  `devtools/check_artifact_contracts.py`, extended as the parent plan asks, runs the
  built-ins' in `make lint-check`.
- **Route validation.** `--api` validates a declared route’s rows, so its golden is
  contract evidence.

### Migrating the Built-In Plugins

Phases 1 to 3 are the parent plan’s, and Phase 4 is the view model plan’s. Core types
are declared by `objects/registry.py`, not a manifest, and the shell registers their
sources through its internal seam.
Core’s sources of the Recent tab’s list are declared in that Python registry too, and
never through `[[collection_source]]`, which is a plugin’s block.

| Phase | `github` | `folder` | `diff` |
| --- | --- | --- | --- |
| 1 | `[[object_type]]` for the pull request, with `changes` among its `facets`; `[[collection]]` `pulls`; a `wide-row` view; `registerCollection` from the Pulls controller, and a `load` over the `pull-files-summary` lane. By the parent plan’s Decision 22 D the blocks wait for Phase 2, the registrations do not, and the check of one against the other starts with the blocks | Nothing | Nothing |
| 2 | A `card`, once the frame’s first real use builds it; a `[[collection_source]]` for the Recent tab, in that plan’s R3; the comment types once a comment is listed outside its pull request, each with a `[[collection]]` whose `parent` is the pull request | `wide-row` views of the core `file` and `folder` types; the Files tab, a `[[view]]` that mounts a list | Nothing |
| 3 | A `nav-row` view as the Pulls panel moves to the list host; `pull` becomes the type’s `route`, its object route, taking the number as `id` | A `nav-row` view of `file` and `folder` in place of the tree’s two builders | If its rows converge: a `changed-file` type, its `nav-row` view, and a `[[collection]]` |
| 4 | `[[view.part]]` `tab`, with the page’s three tabs as its `values`, and the page’s `describe` | Parts for Overview and Treemap, where a control is worth setting | `[[view.part]]` `layout`, with `values`, and `diff-summary`, with their `describe` |

## Key Decisions

Each gives the phase that needs it, the options it weighed, and the decision.
The owner took all seven on 2026-11-18, each at A.

### Decision PS-1: Where Structure Is Declared

**Needed for:** Phase 2, where the parent plan’s Decision 22 D puts the manifest blocks.

- **A. The manifest declares every structure,** facets and parts included, and
  JavaScript supplies functions only.
- **B. The split the parent plan first drew.** The manifest names types, views, and
  collections; `registerView` states `facets`, and a page declares its parts through
  `mb.ui`. The server, `--doctor`, and an intent’s refusal see neither.
- **C. JavaScript only,** the parent plan’s Decision 20 C.

**Decided 2026-11-18: A.**

### Decision PS-2: Default Loaders and Collections

**Needed for:** Phase 1.

- **A. The store reads a declared route by the collection convention,** and
  `registerCollection` and `load` are for a controller of the plugin’s own.
- **B. Every type and collection is registered in JavaScript,** as the parent plan first
  wrote it. Each plugin restates paging and freshness.

**Decided 2026-11-18: A.** The Pulls panel still registers its own.

**Clarified 2026-11-19:** a type’s object route and its batch route are separate
declarations. Its object route, `route`, answers one object by its `id` and is where a
reference leads, for an agent and in `/api/object-types`, by the parent plan’s
[Decision 15](plan-2026-11-14-object-data-model-and-views.md#decision-15-routes).
Its optional `batch_route` answers many by `?ids=` and `?facets=` in the collection
convention. The default loader uses the batch route where one is declared, and otherwise
asks the object route once for each reference.

### Decision PS-3: What a Collection Source Names

**Needed for:** Phase 2.

- **A. A data-hook route.** `--api` reaches it, a golden pins it, and #380’s worker
  hooks cover it with no new call.
- **B. A sidekick callable:** a second Python registration surface, which that plan’s
  Decision 15 declines for a dispatcher.

**Decided 2026-11-18: A.**

**Clarified 2026-11-19:** the block also carries `kinds`, a table that maps each kind
token the source answers to `clumping` or `standalone`
([Manifest Blocks](#manifest-blocks)).

### Decision PS-4: How a Page Declares Its Parts

**Needed for:** Phase 4, the later slice that adds `pane.parts`.

- **A. `[[view.part]]`, a registered `describe`, and a binding per mount.**
- **B. JavaScript only.** A part exists once a view reports it, and nothing can refuse
  an intent for an unknown one without asking the page.
- **C. Functions on the view’s handle,** with no `mb.ui`: one namespace fewer, and no
  named function for the parity check to credit before a mount exists.

**Decided 2026-11-18: A.**

### Decision PS-5: A Type Whose Objects Are Files

**Needed for:** Phase 2, before a plugin outside core gives a type a page.

An agent session’s address is its file’s, and one address parses to one type.

- **A. The address stays a `file`.** A view state reports `object: {type: file, …}` with
  `pane.kind: agent-log`, and `/api/object-types` names the types whose `page_kind` that
  is. `present` takes the session’s reference and opens its `href`.
- **B. The most specific type wins the parse.** What an agent reads would change with
  the plugins installed.
- **C. No file-backed plugin types,** which leaves a plugin type no page at all.

**Decided 2026-11-18: A.**

### Decision PS-6: Loading the Plugins a List Needs

**Needed for:** Phase 2, the first list drawn outside its type’s own page.

- **A. Index assets by type as well as kind,** and have `mountList` load the plugins
  that declare or draw its collection’s `members` before first paint.
- **B. Draw the header fallback, then repaint.** Rows change under the reader.
- **C. Load every plugin with an object view eagerly,** against the loading tiers.

**Decided 2026-11-18: A.**

### Decision PS-7: One Validation Path

**Needed for:** Phase 2, where the parent plan’s Decision 22 D puts the manifest blocks.

- **A. The packaged schema validates every plugin’s type,** and `model` serves the drift
  check alone.
- **B. The model for in-process plugins and the schema for workers,** as the parent plan
  first had it: two kinds of evidence for one declaration.
- **C. Ask the worker to validate,** a call on every check.

**Decided 2026-11-18: A.** Its cost is the model’s semantic layer, which moves to the
projection’s tests.

## Open Questions

- **Two functions named `registerView`.** `mb.registerView(kind, view, …)` and
  `mb.objects.registerView(type, shape, …)` take different arguments.
- **A view of another plugin’s type.** Nothing gates it when that contract breaks.
  An `[[object_view]]` could name the contract version it was written for.
- **A type’s scope.** The store drops a type’s objects when its scope changes.
  Does a plugin type declare whether the served root, the served revision, or a
  repository scopes it?
- **Parts of an embedded view.** The pull request page mounts the diff view, and the
  view model plan’s example reports the diff’s `layout` under that page.
  Does the host page declare an embedded view’s parts, or inherit them?
- **Sections.** A section has a `describe` of its own in the parent plan.
  Whether and where it is declared waits for the stack headings in Phase 3.
- **Tools for an author outside the repository.** `metab --doctor` is Python; the
  binding test and the describe session need Node.
- **A container’s children.** A container kind could declare them as a `[[collection]]`
  whose `parent` is the file, which would answer the parent plan’s question.

## References

- [Object Data Model and Views](plan-2026-11-14-object-data-model-and-views.md), the
  parent plan;
  [View Model and View State](plan-2026-11-18-view-model-and-view-state.md); and
  [The Recent Tab](plan-2026-11-18-recent-tab-updates-and-events.md)
- [Plugin Authoring](../../../plugins.md),
  [Plugin System](../../architecture/arch-plugin-system.md), and
  [AGENTS.md](../../../../AGENTS.md#cli-and-functional-ui-parity)
- [#380](https://github.com/jlevy/metabrowser/pull/380), plugin sources and
  out-of-process environments: its Decision 8 and Plugin API Compatibility

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
