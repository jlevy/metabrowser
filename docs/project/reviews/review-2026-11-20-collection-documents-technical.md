# Review: Technical Review of the Collection Documents Brainstorm

**Date:** 2026-11-20

**Author:** Independent reviewer (LLM-assisted)

**Status:** Complete.
Findings are folded into the brief as options and constraints; nothing is decided.

**Scope:** The first draft of
[Collection Documents](../research/research-2026-11-20-collection-documents.md),
reviewed against the object model plans on `claude/object-model-plan-revision` and the
code they describe. That draft was rewritten in response and is not in the history.
The code claims were rechecked against `main` on 2026-11-22, after the table view, file
watches, declared plugin dependencies, and the plugin cache directory landed; the
findings below say where that changed the answer.

## How to Read This

The review is adversarial by brief: it says where the draft’s claims fail against the
plans and the code. It argues for a smaller first step than the draft did.
That is one reviewer’s position, and the brief presents it as one option among several.

Claims are cited by document and section, or by file and constant.
The reviewer ran one read-only KPress probe to check how the server tokenizes a link
list and what the inert path leaves of a fence.
The orchestrating session re-checked the quoted plan text and the named constants
against the files before recording them here.

Short names used below:

| Name | Document |
| --- | --- |
| Object Model | [Object Data Model and Views](../specs/active/plan-2026-11-14-object-data-model-and-views.md) |
| Plugin Authoring | [Plugin Authoring](../specs/active/plan-2026-11-18-plugin-authoring-objects-views.md) |
| View Model | [View Model and View State](../specs/active/plan-2026-11-18-view-model-and-view-state.md) |
| Recent | [The Recent Tab](../specs/active/plan-2026-11-18-recent-tab-updates-and-events.md) |
| Tabular | [Tabular Data and Live SQLite](../specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md) |

## Verdict

- **The Markdown face is right and cheap.** A list of links parses cleanly with the
  KPress MarkdownIt core the server already uses.
- **“Layouts are plugin-provided arrangements of host shapes” does not hold as
  written.** Arrangement is what Decision 11 reserves to the host: height, activation,
  windowing, keyboard, and the list facet.
- **Two factual errors.** A ````collection`fence does not survive the inert path,
  because only`mermaid` is allowlisted.
  Trusted local editing provides rename, move, and trash only, so board write-back has
  no substrate.
- **The item model was wrong in the plans’ vocabulary.** An item with a note, a done
  state, a group, and an overridden title is not a reference.
  A `url` type whose `href` has a host breaks the header’s meaning of `href` and the
  View Model’s intent rule.
- **The core additions were overstated.** No registry change is needed for `permissive`,
  no `softschema.contract` classifier field is needed, and a `document` facet on `file`
  is neither needed nor cheap at first.

## Findings

### 1. Layouts and Shapes

**What Decision 11 protects.** A shape is “a contract with the list host about height,
activation, and slots” (Object Model, Decision 11 A). The list host owns windowing, one
Tab stop with roving focus, disclosure, sections, and its state record (Object Model,
The List Host).

**Where a grid breaks.** Windowing is one-dimensional, and a grid needs row chunking.
Left and Right need a meaning, but Right already moves to a row’s facet line (Object
Model, The List Host), and Decision 21’s keyboard contract is arrows plus J and K.

**Where a board breaks.**

- Sections group consecutive items under headings, and `sectionOf` returns one string
  (Plugin Authoring, the `MetabrowserListOptions` type).
  Lanes are parallel scrollers.
- The list facet is the list host’s record, `collection`, `shape`, `focused`,
  `expanded`, `closed_sections`, and `window` (View Model, the facet table).
  It has no arrangement field and no window per lane.
- `pane.list` is one list.
  A page of several lists is deferred to Phase 2 (Object Model, Decision 17).

**Where a table breaks.**

- A `wide-row` is “leading mark, title line, metadata line, trailing columns” (Object
  Model, Shapes). It has no header row, no aligned or sortable columns, and no column
  chooser.
- The Tabular plan puts grids in a built-in `table` plugin fed by `[[table_source]]`,
  and says “Rows are not objects in the object model’s sense”.
  Its `{ref}` cell is a table-internal `{table, key, label}`, not an object reference.

**“The active layout is the list facet” is wrong.** It is `pane.view`, a tab, or a
`[[view.part]]` with `values`, as the diff’s `layout` part is (Plugin Authoring).

**A framing that needs no new registry term:**

| Layout | Framing |
| --- | --- |
| List | One `mountList` with `shape: wide-row` |
| Cards | One `mountList` with `shape: card` |
| Grid | A host-owned arrangement option of the `card` frame, decided when Recent’s R4 builds the frame, because it changes windowing and keys |
| Board | A Decision 17 A page view that mounts one list host per lane, each a collection reference with `params = {group}`; it waits for view state that covers several lists |
| Table | A `[[table_source]]` over the normalized items, with `requires = ["table"]`; this is built and needs no core change |

The draft’s true half is worth keeping: no type is asked to draw anything new, and the
header fallback covers every type.

### 2. Decisions 17 B and 18

**17 B.** The rejected option is a manifest-declared page that the host lays out with no
JavaScript.
A `collection` kind whose page view mounts lists in code is 17 A, so the kind
itself does not reopen 17 B.

It does reopen 17 B where the draft’s `views:` list carries `fields`, `columns`, and
`featured`, and where Principle 7 adds `:::` layout.
That is “a layout language to design before a second page exists”, moved into user
files.

A decision text the reviewer would write: “A collection document names one view by a
closed token and nothing else.
The page is an ordinary page view (17 A). Per-view options and layout are out of scope
until a second consumer exists.”

**18.** The draft complies only if membership, order, grouping, link resolution, and
glob expansion all run in the Python data hook, because “membership and order are data
semantics”.
A fence parsed in the browser, or a glob expanded in JavaScript, would be the
rejected option. Author order replaces `(updated_at, type, id)`; the cursor is the
position; `generation` is the document’s fingerprint.
A fence route must take `path` plus a block index and parse on the server, never a fence
body sent by the page.

**The item is a nested object, not a reference.** “A reference names an object” and
carries no context. Recent’s precedent is `Update`, which has a `subject` reference and
whose `href` is its subject’s page.
So the fit is a plugin type, `collection-item`, with `subject`, `note`, `group`, and
`done`, and an `id` unique within its parent.
The same file appearing twice, which is natural on a board, also breaks a store and a
`focused` field keyed by `{type, id}`.

**A gap in the plans this exposes.** A collection route’s `rows` are member summaries.
“No route answers a `File` or `Folder` object”: the adapters run in the browser from the
tree. `file` has no batch route, and its object route is `/api/file`, an envelope with
content. A list of N file references outside the tree therefore costs N `/api/file`
reads. A `collection-item` that carries what its card needs sidesteps this.

**“A collection document is the container-children case” overclaims.** That open
question concerns container kinds whose children are inner paths, not references to
sibling files.

### 3. Extracting Items from the Markdown Body

**Parser.** The KPress MarkdownIt core in the Python data hook.
`diff/markdown_projection.py` already builds one with `_markdown_it`, the navigation
plan forbids a second Markdown grammar, and Decision 18 requires the server.

**Probe results.**

- A task item tokenizes as an inline HTML checkbox, a space, then the link.
  The draft’s rule “a list item whose first child is a link” therefore fails on every
  checkbox item. The rule must be “an optional task marker, then a link”.
- Reference-style links and autolinks arrive with a resolved `href`.
- `[[wiki]]` is plain text on the server; wiki parsing lives in the browser
  (`wiki-parser.js`, `wiki-resolver.js`). A first version would report such items as
  unresolved.
- Tokens carry source line maps, which would help write-back later.

**Rules a specification would have to pin:**

- The first link is the subject; later links belong to the note.
- Links in paragraphs, blockquotes, and tables are prose.
- Groups are flat: the nearest preceding heading of level two or more.
  The host’s sections are flat, so “heading level sets nesting” has nowhere to go.
- Duplicate headings need numbered slugs, as `inert_html`’s anchors have.
- Items before the first heading have no group.

**The nested `key: value` grammar is the weak rule.** It is not YAML, and it collides
with nested link items.
The reviewer would keep properties in a YAML form.

**Resolution.** Relative to the document’s directory, through `resolve_content`, which
handles pins and compressed files.
A fragment stays as the inner location.
A missing target is an item state, since a reference does not promise the served source
can open it. A root-relative `/x` needs a stated meaning.

**Bounds.** `MARKDOWN_DIFF_MAX_BYTES` and `_MAX_LINK_OPENERS` in
`diff/markdown_projection.py` were measured for a different input.
`_MAX_LINK_OPENERS` counts `[`, and a checkbox link item uses two, so a link list
reaches it quickly.
The comment beside those constants records that a nested bracket pair
is MarkdownIt’s pathological case, which is this document type’s shape.
The collection parser needs its own measured constants beside its code.

### 4. A `document` Facet and a Batch Describe Route

**What the plans say.** `file` has no facets.
Facets are declared by the type’s owner, so a plugin cannot add one to `file`. A facet
loader is a bounded batch route answered from cache or memory.

**Why a core `document` facet is not small.**

- Title and description depend on the kind: frontmatter and H1 for Markdown, `<title>`
  for HTML. Core would need a describe hook per kind.
- A word count and a first paragraph need a body read and a Markdown parse.
- A `**Date:**` line is one repository’s convention, which the rule that core stays
  consumer-agnostic rules out.

**The cheaper answer.** The plugin’s own item rows carry a small `document` sub-object
that its hook reads.
It is promoted to core when a second consumer appears; the `/recent` cards and the
navigation plan’s frontmatter alias lookup, which is already “a lazy, bounded metadata
index”, are candidates.

**Bounds: name them, do not invent them.**

- `FRONTMATTER_MAX_BYTES` in `frontmatter_yaml.py` is generous for a batch; a comment in
  `server.py` records that parsing at that bound can take seconds.
- The classifier’s `_YAML_PREFIX_BYTES` in `plugin_loader/classify.py` is a closer
  precedent for a prefix read.
  (`CONTENT_PREDICATE_MAX_BYTES` there is the largest of the predicate bounds, which is
  `FRONTMATTER_MAX_BYTES`, so it is no smaller.)
- The transclusion budget in the Markdown plugin’s `transclusion.js` has the right
  dimensions for a batch: documents and aggregate bytes shared by one document, and a
  time bound per embed.
- An over-budget answer reports `truncated`; it does not fail.
- An in-memory cache keys by the content fingerprint.

**Built-in or installed.** `metabrowser.plugin_api` exports no bounded frontmatter
loader, so an installed plugin could not do this safely today.
That argues for a built-in plugin, or for exporting the loader.

### 5. A `url` Type

**The `href` conflict.** The header’s `href` is “the object’s address in the browser”.
A plugin cannot register an address.
`present` takes a reference and opens its `href`, and the View Model forbids “a URL with
a host” in an intent.
A `url` type would turn a `present` of it into the forbidden thing.

**A fit that avoids it.** A URL is a field of the item, not a registered type.
The item’s own address is the document plus a fragment.
The external address is the `web_url` the Object Model’s open question on a header web
address already proposes.
How a host-owned frame activates an external link is then the open design point; the
inert path’s new-tab, no-opener, no-referrer link is the model.

**The draft’s CSP claim is half right.** The restrictive policy applies only when active
content is off. A trusted page has none.
The reason to fetch on the server is privacy and consistency.

**Unfurl risks the draft omitted.**

- A server fetch of URLs a document names is server-side request forgery: loopback,
  intranet hosts, redirects, and DNS rebinding.
- It needs response size and time bounds.
- An `og:image` must honor the remote-images setting.
- “Rendering never fetches” is right and should stay.

**Where a cache would live.** It is keyed by URL, not by repository, so it belongs in
the application home with owner-only storage, per
[Repository Cache](../architecture/arch-repository-cache.md).
It is either a plugin-private versioned format validated on every read and write, in the
owner-only directory `metabrowser.plugin_api.plugin_cache_directory` gives a plugin, or
an `enforced` contract in `cache/contracts.py`. It is persisted state, so it needs a
`metab` equivalent, and the instruction to prefer a route means a POST route reached
with `--api`, not a new command.

The reviewer would cut unfurl from any first step: the link text is already the title,
and host plus path gives the rest.

### 6. SoftSchema

**The projection.** Projecting to a validated normalized record is right, and it does
not bend SoftSchema’s rule.
The items route answers contract-validated objects; the Markdown file is simply not a
SoftSchema artifact for its items.

**`permissive`.** In softschema 0.8.1, `soft` and `permissive` do not change validation
behavior; extra keys are a property of the model.
“`permissive` so view plugins can keep their own keys” is wrong as stated.

**No registry change is needed.** `cache/contracts.py` already validates the user-owned
`config.yml` permissively outside the registry, and a collection’s configuration can
follow it. Admitting `frontmatter-md` into `plugin_loader/artifact_contracts.py` would
touch its profile type, its parser, its root-key check, and its serializer; that
registry is for machine-written records.

**The trigger.** A `softschema.contract` classifier field adds a core predicate and
three lines of ceremony for an agent.
`frontmatter_has_key` already works on pins.
The existing `frontmatter_schema_prefix` reads a top-level `schema:` string, while
SoftSchema’s `schema` is a file pointer inside its block, so that predicate is not
SoftSchema-aware either way.

**The key.** `collection` is generic and may collide with other tools.
The draft made it both a scalar and a mapping; a scalar cannot validate as an object
contract.

**An alternative worth recording.** SoftSchema’s own direction is generated sections:
structured data is authoritative and the body list is regenerated between markers.
It conforms to the spec and costs the author a YAML list.

### 7. Fences

**The survival claim is false for the inert path.** `inert_html.py` keeps `lang` on a
`<pre>` only for `DIAGRAM_LANGUAGE`, which is `mermaid`, and `tests/test_inert_html.py`
pins that any other language is dropped.
The probe showed trusted output as a `language-collection` code block and hardened
output as a bare code block: the text survives, the identity does not.
Supporting it needs an allowlist change in `inert_html.py` and in its JavaScript twin.

**“Mermaid becomes its first client” overclaims.** KPress itself marks and draws Mermaid
figures. Metabrowser dispatches on no fence; the Markdown plugin’s `diagrams.js` only
hosts KPress’s Mermaid figures, turning `pre[lang="mermaid"]` back into figures.

**A browser-side `registerFence` conflicts with the load model.** Plugin code loads by
kind, or through `mb.plugins.load` for a plugin named in the caller’s `requires`, so the
collection plugin is not loaded when a plain `markdown` document renders.
`requires` points from consumer to provider: for a fence it would have the Markdown
plugin require the collection plugin, the inverted direction, so it does not solve fence
dispatch. The consistent alternative is a manifest declaration indexed like Plugin
Authoring’s type index.

**Security.**

- A `from:` pattern must match the inventory, not the filesystem, and must refuse `..`
  and absolute patterns.
- It must work without `path_glob`, which matches only on the filesystem.
- The real risk is amplification: one hostile README fence causing N reads, times
  fences, times documents.
  All fences in a document would share one budget, with an explicit `truncated`.
- A fence’s YAML is hostile input and is parsed on the server with the bounded loader.

### 8. Board Write-Back

**Not feasible on the cited plan.** The
[trusted local editing plan](../specs/active/plan-2026-07-16-trusted-local-file-editing.md)
says no built-in write route consumes the mutations capability, its goals are rename,
move, and trash, and its non-goals include in-browser text editing and plugin-defined
mutations.

**The editor contract does not help yet.** The
[editor plugin contract](../specs/active/plan-2026-07-17-editor-plugin-editing-contract.md)
is a draft with nothing implemented.
Its first save is whole-file replacement, and structural patches are an open question.

**Consequences.**

- A drag is a plugin-defined structural edit, the last thing those plans reach.
- “Moves one line” is untrue for an item with a nested list or a note paragraph.
- A checkbox toggle has the same dependency.
  Until then `done` is read-only and comes from the file.

### 9. Parity

The draft’s parity section is insufficient.
For a built-in plugin, `devtools/check_parity.py` requires:

- a route-table row for every `[[data_hook]]`, with a golden that successfully invokes
  that route;
- a `kind: collection` line in a successful `metab --show` golden;
- functional-table rows: a data row naming the route (membership, order, grouping, done
  state, missing targets, bounds, and errors), an interaction row whose browserless
  session runs the production `describe` and the group and keyboard state, and a paint
  exemption only with a specific reason and focused evidence.

[Agent Instructions](../../../AGENTS.md) also require the
[map](../architecture/arch-views-models-routes.md) in the same change, lazy-mount and
disposal tests, a loading tier for each asset, the strict `tsconfig.json` gate, and a
changelog fragment.

Wrong in the draft:

- “Before and after files are a golden pair” is not a `metab` equivalent.
  A move must be a server operation reached by a route.
- The unfurl “command” should be a route.
- Fence behavior on the inert path needs its own evidence.

### 10. Other Problems

- **A first phase would hand-draw cards.** The `card` frame does not exist until
  Recent’s R4. Drawing cards before it is the drift Decision 12 A names, and the move
  onto the object model then rewrites it.
  A first phase would say so, or draw rows.
- **Priority 100 does beat `markdown`,** but the new kind must declare its own Document
  and Source views, because views bind to a kind.
- **The board example mixed lanes and checkboxes.** One of them must be the source of
  status.

## The Smallest First Step the Reviewer Would Take

One built-in plugin, one route, one tab, and no core change:

1. **Kind.** `collection`, matched by one frontmatter key at priority 100, whose value
   is a closed token.
2. **Route.** `GET /api/plugin/collection/items?path=`: a KPress parse under new
   measured bounds; flat groups; items of
   `{id, subject | web_url, title, note, done, group, state}`; per-target
   `document {title, description, date}` from bounded frontmatter under a documents,
   bytes, and time budget; the collection convention’s keys.
3. **Views.** Rows by default, since cards before Recent’s R4 are the drift named under
   Other Problems; a Table through a `[[table_source]]` adapter over the items; Document
   and Source through the Markdown plugin’s exports (`requires = ["markdown"]`); a named
   pure `describe` per item; the Decision 21 A keyboard; a disposal path; refresh on
   `file.changed` through `mb.watchFile`.
4. **Evidence.** An `--api` golden covering groups, a checkbox, a reference link, a URL
   item, a missing target, an escape attempt, and an over-budget file; a `--show`
   golden; a browserless describe session; parity rows, the map, and a changelog
   fragment.

What it would defer, and on what:

| Deferred | Waits for |
| --- | --- |
| Fences and `from:` | An inert allowlist change and fence loading |
| Grid arrangement and `mb.objects` | Recent’s R4 and the manifest blocks |
| Board | View state for several lists, and the editor contract |
| Unfurl | Its own plan |

The same route internals with a different member source give a Documents view over a
folder’s or a pull request’s changed Markdown files, with no file to write.
On a folder, an `offer` predicate on the `[[view]]` limits it to folders that hold
documents.

## Open Questions the Review Adds

1. How does the store get N `file` summaries by reference outside the tree?
   Is a `file` batch route coming, and does `/recent` need it too?
2. Is a grid a host arrangement of `card`, decided in R4, and what do Left and Right
   mean there?
3. How is a page of several list hosts published in view state?
4. How does a host frame activate an external `web_url`?
5. What is an item’s stable `id` across edits: its subject plus an occurrence ordinal,
   or its source line?
6. Which frontmatter key, and does it collide with other tools?
7. Should a manifest-declared fence language extend the inert allowlist, letting
   untrusted documents invoke plugin renderers, or are fences for trusted folders only?
8. Should the bounded frontmatter loader join `metabrowser.plugin_api`?
9. Is `done` document state, read-only until structural edits exist, or a per-viewer
   read mark, which is persisted state with its own route and golden?
10. Should the document-metadata reader be shared with the frontmatter alias lookup from
    the start?

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
