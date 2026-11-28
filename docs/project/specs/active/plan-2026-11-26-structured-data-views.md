# Shared Values, Tree, and Source Views for Structured Data

**Status:** In progress, November 2026. This is follow-up work to
[SoftSchema Collection Tables](plan-2026-11-26-softschema-collection-tables.md).
The collection preview can ship independently.

## What a Reader Can Do

Open a JSON or YAML file in Values.
Open a nested value, switch to Tree to inspect its shape, and choose Source to see
exactly how the author wrote it.
A Frontmatter disclosure in a rendered Markdown document offers the same views in place.
A structured excerpt in a diff keeps the comparison and the surrounding prose in view.
A record cell in a collection uses the same controls.

For example, a Markdown file begins with this frontmatter:

```yaml
---
title: Workshop
speakers:
  - name: Ada
    roles: [host, editor]
  - name: Bo
---
```

Values shows `title` and `speakers` with the first few levels already expanded.
Ada’s `roles` can be expanded in place to show two indexed values.
The speaker rows and `title` stay visible.
Tree in the frontmatter disclosure shows the same sequence.
Source selects `[host, editor]` within the original file.
Copy on the `roles` row includes the field and both roles.
The equivalent JSON object, a YAML flow mapping, and a YAML block mapping produce the
same rows and interactions.
Source exposes differences in spelling and layout.

## Current Implementation

- Standalone files open in Values, with Tree and Source on the same tab strip.
  A schema-free projection shows ordered children and supplies exact UTF-8 byte ranges.
  The Table plugin supplies the record grid for lists of mappings.
  The node table supports paging, document selection, and in-place expansion and copy.
  [Structured manifest](../../../../src/metabrowser/builtin_plugins/structured/manifest.toml),
  [node model](../../../../src/metabrowser/structured_nodes.py), and
  [core table renderer](../../../../src/metabrowser/static/structured-node-table.js).
- Metabrowser enhances the closed KPress Frontmatter disclosure with Values, Tree, and
  Source when a Markdown file provides frontmatter.
  Opening it requests the bounded projection.
  Switching to Tree or Source retains the selected value.
  The main app provides the Values, Tree and Source renderers and the revision-aware
  page reader. The Markdown plugin connects them to the disclosure and file envelope.
  Source preserves the selected text in the clipboard and numbers the displayed excerpt
  from its first line.
  Its source range retains the coordinates in the enclosing file.
  KPress supplies its definition list to hosts that lack the Metabrowser file envelope.
  [KPress adapter](../../../../src/metabrowser/kpress_adapter.py) and
  [Markdown placement](../../../../src/metabrowser/builtin_plugins/markdown/place-rendered.js).
- Closed top-level YAML and JSON code fences can open the same views through an Explore
  disclosure. KPress identifies genuine fences in the rendered document and matches their
  opening line and content to the exact file revision.
  The code remains visible while the disclosure is closed.
  Each opened excerpt reads data on demand from its original Markdown file.
- The rendered Markdown diff constructs its own disclosure from key, text and change
  entries. The structured diff builds changed rows from a merged tree and shares the
  structured plugin’s Tree internals.
  A removed row’s position in that merged tree can differ from its position on either
  side.
  [Markdown diff](../../../../src/metabrowser/builtin_plugins/diff/diff-markdown.js) and
  [structured diff](../../../../src/metabrowser/builtin_plugins/diff/diff-structured.js).
- The SoftSchema collection currently supplies the table plugin with an inline Tree
  renderer for nested values.
  A projected or conformed value can differ from the document it came from.
  [Collection view](../../../../src/metabrowser/builtin_plugins/softschema/index.js).

## One Projection for Both Formats

The main app owns an ordered, typed node model.
Each node describes its kind, child count, identity within a document or diff side, and
available source location.
Children are requested by page.
An object key and an array index have distinct address segments.
Encode segments losslessly, including empty keys, Unicode, punctuation and strings such
as `"0"`. Preserve document order through parsing and transport, including
numeric-looking object keys.
The model distinguishes an absent field, an explicit null, an empty string and an empty
container.

| Selected value | Values at that position | Open a value |
| --- | --- | --- |
| Mapping | Field and Value rows in source order | Expand a nested mapping or sequence below its row |
| Sequence of mappings | One row per item, with columns in first-seen field order; integrate the existing record grid and its paging | A cell opens its value; the row detail exposes the complete mapping, including fields outside the visible columns |
| Scalar or mixed sequence | Index and Value rows in sequence order | Each container opens according to its own shape; scalars retain their type |
| Scalar root | One typed Value cell | Tree and Source address the same scalar |
| Empty mapping or sequence | Empty-state text identifies the container kind | Tree and Source remain available |
| Multi-document YAML | A document index with ordered, individually addressable roots | Open a document using the same shape rules |

The node table renders the initial preview at `PREVIEW_DEPTH` in
`structured-node-table.js`. Each page reserves its root rows first and shares the
remaining `PAGE_MAX` rows among sibling containers.
A disclosure chevron expands the rows below its field in place.
It keeps focus on that control and leaves the surrounding rows visible.
A compact JSON preview identifies the value in the disclosure.
A condensed preview uses an ellipsis and gives the total number of keys or items.
The chevron follows the text, and the control fits the existing row height.
Use More to page through a branch beyond its preview.
Tree keeps its disclosure, expansion and virtualization behavior.

Three levels show the useful nested fields in the Universe People sample without
reaching the inline row cap.
On November 26, 2026, 24 People frontmatter records in filename order produced a median
of 26 rows at depth two, 34 at depth three, and 63 at depth four.
The largest depth-three page had 47 rows.
At depth four, the largest page reached the cap.
These counts come from `project_structured` and include all descendant rows sent in the
first page.

Source uses the core Source surface with its gutter, syntax highlighting and wrapping.
Standalone Source numbers the file.
Embedded Source numbers the displayed excerpt from one while keeping its exact position
in the file. Switching tabs retains the selected node.
Source shows original quotes, whitespace, comments, anchors, delimiters, line endings
and trailing newlines as present in the selected range; exact copy reads that range from
the original input. Visual wrapping or highlighting never changes the copy.

The copy button at the end of each Values row reads a single fragment on demand at the
displayed revision. Mapping rows include the field key and complete value.
Sequence items copy their value, including descendants beyond the visible page.
The shared record grid uses the item’s source position even when rows are sorted or
filtered. Row copy produces a standalone fragment, adding enclosing syntax or restoring
indentation where needed.
The Source tab remains available for an exact excerpt.
The record grid can still browse some files outside the ordered projection’s budgets.
It also reads standalone JSON5 record lists and YAML record lists with aliases when a
bounded validation confirms the values fit the grid.
It omits row copy when the projection cannot read the file.
Copy controls appear on row hover or keyboard focus and stay visible on touch screens.

Equivalent JSON and supported YAML values must have identical table rows, types,
expansion, Tree behavior and keyboard navigation.
Use the same equivalence fixtures for standalone documents, Markdown frontmatter and
code fences, diff sides, and collection cells.
Assert the shared presentation and interaction transcript across formats and the
original text separately for each Source range.
Include nested record lists, scalar roots, empty values, numeric-looking keys, and
Unicode escapes that parse to the same string.
Keep parser semantics explicit for format-specific values, multiline scalars, multiple
documents, numeric precision and permitted JSON extensions.
Preserve the source spelling of values that a browser number cannot represent
faithfully. Handle duplicate or non-string keys, unresolved tags and cyclic aliases
explicitly: preserve a distinguishable node and location where supported, or return a
diagnostic and exact Source.
Never silently overwrite keys, coerce distinct keys into one row or recursively expand
an alias cycle.

## Source Identity and Embedding

The core source descriptor identifies the host document, format or dialect, optional
document index, exact revision, side of a comparison, and the selected range.
Record how ranges are measured, including encoding, byte boundaries and the mapping to
original file lines.
Distinguish a complete value from an excerpt that starts or ends inside one.
A value-only embedding advertises that exact source is unavailable.
It may present a clearly labeled generated representation as a separate action.
It cannot claim reconstructed text as Source.

| Host | How the shared surface appears | What Source opens |
| --- | --- | --- |
| Standalone YAML or JSON | The existing file tab bar offers Values first, then Tree and Source, across all supported root shapes | Original file at the active filesystem version or pinned Git blob |
| Rendered Markdown | Keep the Frontmatter summary and surrounding document. Mount the shared layout when the disclosure opens. Both YAML and JSON frontmatter use this placement. Document the recognized frontmatter delimiters and parser selection in the KPress contract. Explicit YAML or JSON code fences show an excerpt without changing page metadata | Authored YAML or JSON inside the selected region, with the original source coordinates available to the reader |
| Rendered structured or Markdown diff | Keep change marks, current-side filtering, folds, side labels and the enclosing comparison. Values, Tree and Source act on the selected side or paired entries; unchanged context may remain collapsed | Exact base or head range, including deleted values from base and added values from head; a merged projection alone cannot supply either side’s original text |
| Embedded value or collection cell | Use the same tabs and recursive layout inside the host’s detail surface. A plugin can add validation, references and field descriptions around it | Original backing file and field range when reliably identified. A repaired, inferred or projected value identifies its provenance and any difference from the original |

A malformed fenced region shows a scoped diagnostic and its source while the readable
Markdown body remains available.
Recognize frontmatter only at the host’s document boundary.
If KPress needs a distinct JSON delimiter, define it in the placement contract and test
that existing prose and code fences keep their meaning.
A broken standalone document opens Source with its parser location.
A partial diff hunk can expose exact excerpt text even when it cannot form a complete
table or tree. If a working file changes between parse and source lookup, invalidate the
old range and refresh the model or report the version change.
A Git comparison resolves each side against its repository identity, blob path and
revision, including a rename.
Never recover a missing pinned value by reading the working tree.
[Git architecture](../../architecture/arch-git.md).

## Large YAML Previews

Values can open the beginning of an oversized block YAML mapping within the existing
`projection_byte_limit` in `structured_nodes.py`. YAML parser events must establish a
sibling boundary before the window ends.
Each page keeps the file revision and uses the same preview window.

The open mapping or sequence gives a lower-bound count.
A completed entry can still copy its authored source range.
The preview notice offers Source for the full file.
Full Values paging will need a bounded parser or position index that can address later
entries without loading the complete document into memory.

## Tabs, Arrows, and Browser History

The main app supplies the tab strip, current path, Back and Forward controls, empty and
error states, and content panel.
Use Values for document data and Table for collections and database tables.
Standalone views reuse the file tab bar.
Embedded views use the same visual and keyboard conventions at the disclosure or detail
boundary. The shared chooser uses design-system spacing between the host label, tabs and
content. A failure notice names the available reason and offers a Source action at the
affected excerpt or file.
Use the existing design-system icon registry, icon-button sizing, focus rings and
tooltips for left and right arrows.
Their accessible names are “Back” and “Forward”.
Keep disabled controls visible at history boundaries.
Disclosure chevrons only expand or collapse a branch.
Label a link to the parent container by its destination.
[Design system](../../../design-system.md) and [icons](../../../design-system-icons.md).

Make the selected host, revision or comparison side, embedded occurrence, node path and
active tab part of the canonical address.
Extend the existing navigation codec and its meaningful query fields so opening an
embedded value preserves the file view, table selection, filters and comparison
identity. Stable host and side-specific node identity must outlive rerenders; a virtual
DOM row index is insufficient.
An explicit node visit or tab switch creates one entry.
Expanding or collapsing a Values branch only updates that view’s state.
Repeated selection is a no-op.
Startup normalization and invalid-path recovery replace the current entry.
A new branch of navigation clears Forward.
Popstate restores the recorded surface, disclosure, focus and scroll without adding an
entry. Reopening a deep link directly requires no invented Back destination.

The arrows traverse the same recorded history as browser Back and Forward, within
entries the app can identify.
Never infer Forward availability from browser history length.
Keep focus restoration and transient expansion state in entry state where appropriate.
A stale path resolves to the nearest surviving ancestor with a short status; a missing
historical side remains missing.
Use real links for copy-link and modified clicks.
Give tabs one active panel, roving keyboard focus and the existing tab-strip key
behavior. Multiple excerpts on a page have independently labeled controls and unique DOM
IDs.

## Ownership, Loading, and Limits

Core owns the parser-facing projection contract, source addressing, tab and history
model, shared renderer, and shared layout and icons.
Publish a typed SDK mount accepting a value/source descriptor, initial address, and
optional host change decorations, with update and disposal.
The structured plugin registers the standalone file kind.
KPress exposes a stable host placement and source metadata for enhancement, while its
standalone HTML remains readable.
Metabrowser’s Markdown adapter supplies the core mount to that placement.
Diff adapters supply change identities and sides.
SoftSchema alone owns schema resolution, validation, repaired values, collection
identity and domain layouts.
Consumers use the public SDK and do not maintain their own general YAML/JSON layouts or
history stacks.

Reuse the implemented record grid, virtual Tree, Source gutter and navigation codec.
Extract the reusable pieces behind the SDK before migrating callers.
Load the shared implementation on demand at first use, respecting the
[browser loading tiers](../../architecture/arch-browser-shell.md#asset-loading-tiers).
A closed disclosure must add no parse, full-source fetch or view mount to the Markdown
first paint. Cancel stale requests and dispose listeners, virtualizers and source
observers on replacement.
Route bounded work through existing safe path, content and Git readers.
Render data as text; parsing must not execute tags, follow external references or
hydrate untrusted HTML.

Measure mapping width, depth, alias expansion, sequence size, source bytes and rendered
rows against actual documents before choosing new limits.
Publish truncation and continuation in route responses and the UI. Use bounded samples
or paging for column discovery and distinguish missing data from data outside the page.
The original Source remains reachable within existing content limits.
Benchmark cold file mounts, opening a disclosure, first visible rows, nested expansion
and moving between excerpts.
[Rendering large content](../../../large-content-rendering.md).

## Delivery and Acceptance

1. **Core data and source contract.** Introduce a route or extend an existing model
   reachable through `metab --api`. Add route goldens covering equivalent YAML block,
   YAML flow and JSON inputs, mixed and empty values, a nested record list,
   multi-document boundaries, exact ranges, losses in projection and malformed inputs.
2. **Core controls and standalone files.** Extract the SDK mount, shared controls and
   address transitions.
   Register Values, Tree and Source on the structured kind and retire its
   record-list-only offer.
   Preserve explicit Tree and Source links.
   Run production JavaScript browserlessly against nested tab changes, Back/Forward,
   branching, stale paths, modified clicks, reload and disposal.
   Pin the session with a golden.
3. **Markdown and KPress.** Add the placement and range contract.
   Cover equivalent fenced JSON and block and flow YAML frontmatter, YAML and JSON code
   fences, an empty disclosure, malformed frontmatter in each format, a working file and
   a Git pin. Verify exact copy, correct original lines, readable prose after an error,
   lazy mounting and multiple independent excerpts.
4. **Diffs and excerpts.** Adapt the Markdown and structured projections.
   Exercise added, removed, modified and moved-position entries, a rename, partial
   source, unavailable sides, preserved folds and Source defaulting to the correct side.
   Keep existing rendered-diff and Current behavior goldens.
5. **Cells and downstream plugins.** Migrate the SoftSchema cell and other
   structured-value consumers to the core SDK. Check nested expansion, projected versus
   original values, domain references, and Back to the same collection row.
   Audit remaining consumers and remove duplicated general layout, icons and navigation
   when each consumer migrates.

Each phase updates the [parity registry](../../architecture/arch-parity-registry.md),
surface registrations and applicable user documentation alongside its implementation.
Share fixtures for equivalent values across hosts.
Browser tests cover keyboard access, focus and scroll restoration, delayed mounts,
browser history integration, readable narrow layouts, visual alignment, clipboard
behavior and measured rendering cost.
Require the repository verification gate for each independently shippable phase.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
