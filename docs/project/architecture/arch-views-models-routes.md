# Views, Models, and Routes

**Status:** Implemented, except where a row says otherwise.

The map of what Metabrowser shows, what it shows it from, and how each thing is
addressed. Every other architecture document explains one of these in depth; this one is
the index that says how they fit together, and the place to look first when adding a
kind, a view, a data format, or a route.

## The four layers

A selection travels the same four layers no matter what it is:

```text
address  ──►  resource kind  ──►  contract/model  ──►  view
what is      what the thing      the validated       how it
selected     can do              data                 is drawn
```

- **Address** names the address space and the resource within it.
  Core routes are owned by the shell; installed domain plugins may own validated mounted
  sub-routes through the same route map.
  See [Browser URL Grammar](../../architecture.md#browser-url-grammar).
- **Resource kind** is the semantic classification a plugin claims.
  Filesystem `[[kind]]` blocks use `FileContext` (including content predicates).
  Git blobs use extension, basename, sniffed adapter, and bounded JSON/YAML/frontmatter
  mappings parsed from blob bytes.
  `path_glob` stays filesystem-only.
  Planned `ResourceKindSpec` declarations cover route-backed resources without
  fabricating a file matcher.
  One kind, many views.
- **Contract/model** is the validated data a view receives.
  Simple kinds take the `/api/file` envelope; richer kinds have their own documented
  format with a schema and a conformance corpus.
- **View** is a registered renderer (`[[view]]` plus `mb.registerView`), shown as a tab.
  A kind’s `default = true` view is what a selection opens.

The layers are deliberately decoupled: a view never learns which source produced its
model, and a model never learns which route reached it.
That is what lets one diff renderer serve a patch file, a commit, and later a pull
request without knowing the difference.

Artifact contracts, resource publication profiles, and resource kinds are separate
trusted registries. Their ownership and the mapping workflow for external APIs are
defined in
[External Resources, Artifact Contracts, and Views](arch-external-resources-and-views.md).

Filesystem-backed models reach these layers through the
[Inventory Provider Contract](arch-inventory-provider.md).
That boundary keeps routes, wire serializers, and views independent of the Python or fdu
engine selected for the served-root session.
The planned source boundary for attached filesystems and immutable Git revisions is in
[Repository Sources and Provider Mirrors](arch-repository-sources-and-provider-mirrors.md).
It keeps a session’s selected root independent of the shared Git object and provider
stores.

## Kinds and their views

Built-in kinds, as registered by the manifests in `src/metabrowser/builtin_plugins/`:

| Kind | Matches | Views (default first) | Model |
| --- | --- | --- | --- |
| `folder` | Directories | Overview, Treemap | Folder envelope + [File Rollup Format](file-rollup-format/file-rollup-format.md) |
| `markdown` | `.md` | Document, Source | File envelope; KPress render |
| `html` | `.html`, `.htm` | Preview, Source | File envelope; sandboxed raw document |
| `text` | Text files | Source | File envelope |
| `structured` | `.json`, `.yaml`, `.yml` | Tree, Source | File envelope, parsed hook |
| `diff` | `.patch`, `.diff` | Diff | [File Diff Format](file-diff-format/file-diff-format.md) |
| `agent-log` | `.jsonl` sniffed as an agent log | Log, Charts, Raw JSON | File envelope, charts hook |
| `unknown-jsonl` | Other `.jsonl` | Log, Raw JSON | File envelope |
| `image` | Browser image extensions | Image | File envelope; raw asset |
| `binary` | Non-text files | Bytes | Bounded byte-chunk hook |
| `pull-request` | No file; the shell selects it for `/pull/<n>[/files]` | Pull request | `github/pull` envelope; `github/pull-markdown` per text; `diff/comparison` for Files changed |

Two kinds are also **containers** — folder-like entries whose children are addressable
(see [nav containers](arch-nav-containers.md)): `folder` (children are files and
folders) and `diff` (children are the files a patch changes).

The proposed v0.12 hosted-review plugin adds one route-backed kind only when its model,
view, address, and parity evidence land together:

| Planned kind | Matches | Views (default first) | Model | Bead |
| --- | --- | --- | --- | --- |
| `change-request` | A selected `/hosted/.../change-request/...` resource | Review, Diff, Source | `ChangeRequest/v1` plus a selected bundle of validated companions and File Diff Format by reference | `mb-83w0`, `mb-81p5` |

It is item-like as a document and folder-like as a changed-file container.
Repository summaries and PR index rows are route models and virtual-navigation data, not
synthetic filesystem kinds.

### Shared Source rendering

`text`, `structured`, `markdown`, and `html` all expose raw source from the file
envelope. Generic text and structured views use the SDK’s shared Source renderer;
Markdown keeps its custom frontmatter split but follows the same language and size
decisions.
A source view never embeds another kind’s renderer, because nondefault plugins
mount on demand and may not be loaded.

The server owns the logical-extension and basename grammar maps plus the syntax byte
bound and injects them with the file envelope settings.
A renderer emits exact escaped text and a host language class.
The shell enhances the mounted subtree after the renderer settles and after first paint,
whether the tab was initially visible or mounted later.
Diff views need tokens in their semantic line model rather than markup, so they call the
bounded SDK token service but use the same injected registry, prefetched grammars, and
palette. Diff intraline ranges follow the same ownership rule: they are browser-local
enrichment over exact line text, composed with syntax runs in the renderer and shared by
unified and split projections.
Neither enrichment extends File Diff Format v1.

The registry-to-vendored-grammar and registry-to-text-routing checks live in
`test_plugin_sdk_syntax_token_contracts` and
`test_syntax_language_extensions_are_always_browser_text`.

## Documented data formats

Complete formats have a schema, a conformance corpus, and implementations bound by it;
in-progress rows name the narrower authority already present.
These formats are tool-neutral: nothing in a document references Metabrowser.

| Format | Describes | Authority | Implementations |
| --- | --- | --- | --- |
| [File Diff Format v1](file-diff-format/file-diff-format.md) | A change set between two snapshots | `data/file-diff-format/file-diff.schema.json` | `metabrowser.diff.format` (Pydantic), `builtin_plugins/diff/diff-model.js` |
| [File Rollup Format](file-rollup-format/file-rollup-format.md) | File classification and directory totals | `data/file-rollup-format/` | Python inventory, browser rollup projection |
| [Hosted Review Format](arch-hosted-review-model.md) (in progress) | Provider-neutral repositories, change requests, reviews, threads, checks, status, freshness, and activity projections | Installed enforced SoftSchema contracts and resource profiles; Pydantic record validators; packaged conformance corpora; mechanically closed scrubbed GitHub coverage oracle with exact reduced-response shapes, field/value evidence, and executable identity recipes | Python registry, validators, and codecs plus registry-driven browser parsers for every browser-consumed contract; the generic installed inventory/evidence and isolated-wheel gates are implemented, while browser plugin registration and the GitHub adapter remain planned |

The registry and composition rules that let later release, issue, or other external
contracts reuse these layers are specified in
[External Resources, Artifact Contracts, and Views](arch-external-resources-and-views.md).
Its installed contract and profile tables are maintained by
`devtools/check_artifact_contracts.py`; this map does not register a route, resource
kind, or view for format-only capability declarations.
A planned resource kind is added to the table above only when its model, route, views,
CLI parity, and functional evidence land together.

Everything else travels as an envelope on `/api/*`, versioned with the shell and the
built-in plugins as one artifact — an internal contract, not a standard.
[Where diff documents come from](file-diff-format/diff-sources-and-anchoring.md) maps
the sources that produce them.

## Routes

### Browser routes: one per address space

| Route | Selects | Status |
| --- | --- | --- |
| `/view/<path>` | Content in the active source session; `/view/` is the root | Implemented. A filesystem session uses a served-root-relative path. A `GitRevisionSubject` uses a `GitPath` wire identity and refuses a filesystem spelling |
| `/view/<container>/<inner>` | One entry inside a container file | Implemented. On a Git pin the container address is a `GitPath` prefix and the inner is a host path |
| `/commit/<rev>` | A commit’s change set against its first parent | Implemented |
| `/commit/<rev>/<inner>` | One file’s diff inside that change set | Route parses; the panel restores the commit, not yet the file |
| `/pull/<n>[/files]` | The served pull request’s page: its conversation, or its Files changed | Implemented. The shell mounts the view a plugin registers for the `pull-request` kind (the GitHub plugin’s); a number other than the served pull request’s shows why it has nothing |
| `/compare/<base>..<head>[/<inner>]` | An explicit comparison (`...` for merge base) | Specified, not built |
| `/hosted/<provider-kind>/<instance-key>/<repository-key>/<resource-kind>/<resource-key>[/<inner>]` | A provider-neutral hosted resource and optional addressed child; typed atom keys encode the instance and opaque IDs canonically | Proposed for v0.12.0 in `mb-xzj3`, `mb-6mle`, `mb-83w0`, and `mb-81p5`; the first kind is `change-request` |

The shape after the route is always `<container address>/<inner path>`, which is the
container contract written as a URL. The full grammar, including the `_mb_` query
reservation and its invariants, is in
[Browser URL Grammar](../../architecture.md#browser-url-grammar).

### Data routes

| Route | Serves |
| --- | --- |
| `/api/file` | The file or folder envelope: kind, views, capability envelope, and bounded content window. A `GitRevisionSubject` uses `GitPath` wire identities and Git object facts; it does not invent mtime or ignore state. A Git tree envelope is SPA `folder` chrome (`git_kind` stays `tree`) with recursive blob `total_files` / `total_size` and no mtime. A complete blob-size tally mounts Overview and treemap; a direct-child README blob sets `readme_path` to its GitPath wire. SPA path chrome and copy-path decode GitPath wires to display names (C0 and invalid UTF-8 become U+FFFD); navigation identities stay wires. Omitted mtime leaves tally chrome empty rather than pending. File Overview mounts when `dir` carries inventory `mtime` or Git `total_size`. Blob kinds use extension, basename, sniffed adapter, and bounded JSON/YAML/frontmatter mappings. Git blob envelopes include `ext` from the same bounded compound-tail helper as filesystem inventory so plugin-sdk `langForPath` and `ctx.ext` do not fall back to a GitPath wire; they omit compressed `logical_ext` because blobs are stored bytes with no gzip smudge. Git markdown envelopes include parsed YAML `frontmatter` and `frontmatter_error`; KPress on a pin uses that parse rather than an empty mapping. Git text envelopes use the same first-window and highlight bound as filesystem listings (`bytes_read`, `content_preview_limit`, `content_max_preview_limit`, `highlight_disabled`). `/api/file`, `/raw`, KPress, and plugin sidekicks follow in-tree relative symlink blobs; the requested GitPath stays the route identity, and kind checks use the leaf path. A Git image blob is SPA `image` chrome; `/raw` serves the stored bytes. A Git `.jsonl` blob is a parsed JSONL envelope. A patch-file container inner is a `GitPath` `g1-` prefix plus a host inner path. An LFS pointer is stored pointer bytes; a missing blob is `object_unavailable`. Markdown and wiki links on that pin resolve to `GitPath` wires |
| `/api/tree` | Navigation subtrees. `types` and `min_size` work for every source that supplies them. Git blob listings carry `cat-file` info sizes so `min_size` can filter; trees and gitlinks stay unsized as blobs. `recency` requires that declared source capability and otherwise returns `unsupported_for_subject`. The SPA hides Modified within on a Git pin because there is no honest mtime. `include_ignored=0` on a Git pin is a no-op because ignore is absent (unignored equals total), not `unsupported_for_subject`. On a Git pin the payload keeps Git-native `entries` and also projects a SPA `tree` array (`dir`/`file`/`symlink`, `GitPath` wires, blob sizes, recursive dir `total_files`/`total_size`, no mtime/ignore); gitlinks are files, not directories. `depth` nests children the way filesystem listings do (default 2) and emits a lazy sentinel past the cap; `depth=0` returns chrome without a listing. File nodes include `ext` from the same bounded compound-tail helper as filesystem inventory; `logical_ext` is only the inner extension of a compressed name. Whole-tree `extensions`, `canonical_extensions`, `type_families`, and `type_presets` rows, `tally_cache_status`, and `summary` (`files`, `size`, ignored 0/0) come from the recursive blob index; ignored counts are 0 because ignore is absent. Incomplete blob sizes omit `summary` rather than inventing 0. `types` and `min_size` keep ancestor trees of matching blobs and emit subtree `filtered` totals; empty filter dirs are omitted. Git `logical_ext` and type matching use the same bounded compound-tail helper as filesystem inventory. Omitted mtime leaves tally chrome empty rather than pending |
| `/api/rollup` | Bounded directory rollups over the facts the active source truthfully supplies; a requested unavailable dimension returns `unsupported_for_subject`. A `GitRevisionSubject` answers from recursive blob names and sizes, omits mtime, and treats ignore as absent so unignored equals total. A missing blob size is `object_unavailable` rather than a partial sum |
| `/api/catalog` | One-shot Quick File universe. A `GitRevisionSubject` lists recursive blob names (`p` GitPath wire, `e` logical compound-tail extension, `n` display basename) and is already complete; a truncated index is an empty truncated snapshot |
| `/api/index/progress`, `/api/index/meta`, `/api/capabilities` | Index status. A `GitRevisionSubject` answers from recursive blob names, omits mtime and watcher facts, and reports `events.stream` off. The JSONL stream still refuses a Git pin |
| `/api/recent` | Flat newest-first matching leaves for sources with recency; unavailable for immutable Git trees rather than populated with fake mtimes |
| `/api/activity`, `/api/stream` | Live inventory and JSONL tail for sources with a filesystem root; unavailable for immutable Git trees rather than the lifespan folder |
| `/api/git/repo`, `/api/git/refs`, `/api/git/summary`, `/api/git/log`, `/api/git/commit/<rev>` | Read-only Git history for the Git panel; log pages use bounded, replayable server sessions, opaque page cursors, and versioned graph-boundary checkpoints. The boundary and its rules are in [Git and comparison sources](arch-git-and-comparison-sources.md) |
| `/api/cache/layout`, `/api/cache/sources`, `/api/cache/source/<slug>`, `/api/cache/stores` | Read-only logical state of the repository cache: layout and config formats, abandoned staging entries, source identity with alias generation and publication, and store records with the aliases that name them. They resolve `METABROWSER_HOME` per request without creating it, read without locks and without repairing a shared entry, page in key order, and never report a cache path, pack file, or Git internal. Wire shapes are in `cache/wire.py`. A server serving a Git pin answers them with `unsupported_for_subject` (409), so nothing about other cached sources is served beside acquired content |
| `/api/source/status` | What this server serves: the subject kind and session generation, and on a `GitRevisionSubject` the full commit it is pinned to (`pin`), the store ref that commit was resolved from (`ref`), and the name the origin knows that ref by (`ref_name`); all three are null on a folder. On a served mirror it also reports freshness from server memory, so polling it runs no Git and reads no store: `refreshable`, the commit the pinned ref names in the mirror now (`latest`), whether the origin still had that ref at the last fetch (`ref_on_origin`: false when it deleted it, null for a pin by commit ID or a ref not yet observed), `last_fetch_at`, `last_outcome` (operation, typed outcome by name, time, from this process or the store’s record, whichever is newer), `refreshing`, and `stale` (older than the one-minute freshness window), both of which cover a served pull request’s record as well as the mirror, plus `pull_request`, the number a served pull-request URL named, `selection_state`, which follows a URL selection the mirror lacked when serving began (`pending` until a fetch for it ends, then `found` and served, `not_found`, or `fetch_failed` when that fetch did not run; `superseded` after a pin switch), and `selection_href`, where a found selection opens. `cli-github-url-waits.txt` pins the pending, found, not-found, and fetch-failed sequence through `metab <url> --api /api/source/refresh --data …`, the one-shot request that fetches; `tests/test_github_serve.py` covers a server, a superseding switch, and the retry after a failed fetch. It sends an ETag and answers `If-None-Match` with 304. The navigation heading on a pin renders from the same envelope. Its checked evidence includes a pin: `cli-api-source.tryscript.md` opens a cached mirror, which needs no acquisition floor, so it runs on CI’s Git; acquiring and serving one are pinned in-process by `cli-git-pin.txt` and `tests/test_serve_pin.py` |
| `/api/source/refresh` | `POST` with a JSON body: start a background refresh of the served mirror, or join the one running, and answer 202 at once with `refresh` (`started` or `joined`) and the status. The refresh is one `fetch --prune --atomic` under the store’s fetch side lock; its typed outcome appears in the status, never as a request error. A folder, or a pin with no mirror, answers `unsupported_for_subject` (409). A one-shot `--api` waits for the refresh it started, prints the status after it, and exits 1 unless the fetch ran or another process’s refresh is running; nothing else in a one-shot command fetches. A page on a pin sends the commit it shows in `x-metabrowser-pin` on every other `/api/` request, and a request for a commit the server does not serve, after a switch or a restart onto another pin, answers `pin_changed` (409); loads that are not `fetch` calls, such as `/raw` images, are not checked |
| `/api/source/refs` | `GET` with `kind` (`branch` or `tag`), `q`, and `limit`: the served mirror’s branches or tags, for the ref selector, read from the mirror alone with one `for-each-ref`. Branches list the default first, then by name; tags newest first. Each row has `name`, the store `ref` a pin request names it with, the `commit` it names (an annotated tag peeled), `default`, and `current`, which marks the ref the server serves now. `q` is a case-insensitive name fragment of at most 256 characters; `limit` is clamped to 1–1000 (default 100), and `total` and `truncated` say how many matched. A tag of a tree or of another tag is not listed. An unknown `kind` or an overlong `q` answers `invalid_request` (400); a folder, or a pin with no mirror, `unsupported_for_subject` (409) |
| `/api/source/pin` | `POST` with `{"ref": …}` or `{"oid": …}`: resolve a branch, then a tag, then a commit ID in the mirror alone, never through revision syntax, and serve it: the old tree source is closed and the new one attached under a new generation. Answers `changed` and the new status, and, when the body also names the page’s `/view/` address as `view`, `view_href`: that entry’s canonical address when the new pin has it, else `/view/`; `invalid_selection` (400), `selection_not_found` (404), `ambiguous_selection` (409), or `unsupported_for_subject` (409) otherwise. `HEAD` is the default branch, and a name the mirror holds that is not a commit answers `not_a_commit` (409) at once, as URL opening does. In a server, a selection the mirror lacks answers `selection_pending` (202) with `refresh` and the status, and starts one background fetch; asked again after it ends, it switches, answers 404, or answers `selection_fetch_failed` (502) when that fetch did not run. `--api` never fetches for it, so the transcripts pin the 404; the 202 path is asserted by `tests/test_source_refresh.py` |
| `/api/kpress/render`, `/api/kpress/export` | Document rendering and export. On a `GitRevisionSubject`, render reads a `GitPath` blob, uses the object id as the cache key, and passes the GitPath wire as `source_path`; export stays mutation-gated and unavailable. With active content off (every served mirror, and a folder served with `--untrusted`), render answers the HTML reduced to the inert allowlist of `src/metabrowser/inert_html.py`, marks it `inert`, and keeps only stylesheets in its assets |
| `/api/plugin/<plugin>/<route>` | Plugin data hooks (`[[data_hook]]`). On a `GitRevisionSubject`, diff document/children, binary chunk, structured parsed, and agent-log charts honor `GitPath` and follow in-tree relative symlink blobs using the leaf kind |
| A plugin-declared mounted prefix (proposed) | Domain resource routes with path parameters and honest HTTP responses; `mb-xzj3` adds this for hosted review |
| `/raw`, `/raw/<path>` | Bounded raw bytes through the active source’s content reader, and the document the sandboxed html Preview frames; oversized content is refused before an unbounded object read. Both shapes share one resolver and send the same sandbox headers; the path form exists so relative references inside a browsed document resolve. A Git subject reads blobs by `GitPath` and follows in-tree relative symlink blobs. Image blobs use an image media type from the leaf display name. LFS pointers are stored pointer bytes; a missing blob is 404. On a Git subject only the query form answers: the path form’s one consumer, the HTML preview frame, is never offered under the forced untrusted profile, so it answers `unsupported_for_subject` (409) rather than a 404 that would misreport a present file, and Markdown images resolve to `GitPath` wires through the query form |
| `/kpress-static/<path>`, `/static/<path>`, `/plugin-static/<plugin>/<path>` | Shell, renderer, and plugin assets |
| `/_debug/tasks`, `/_debug/inventory` | Opt-in local task and inventory-provider diagnostics when `METABROWSER_DEBUG=1` |

Plugin hooks currently registered: `diff/document`, `diff/children`, `diff/comparison`,
`folder/*`, `binary/chunk`, `agent-log/charts`, `structured/parsed`, `github/pull`,
`github/pull-refresh`, `github/pull-markdown`. On a `GitRevisionSubject`,
`diff/comparison` honors the pin through `GitLocation` and `GitDiffSource.content` reads
blobs through the shared cat-file pool; patch `document`/`children`, `binary/chunk`,
`structured/parsed`, and `agent-log/charts` honor `GitPath` and follow in-tree relative
symlink blobs.
`diff/comparison?left=&right=` takes `base_policy=direct` (the default) or
`merge_base`, and reports it in the document.

`github/pull` answers the served pull request’s cached record from the cache alone:
`absent` (with `no_pull_request`, `not_cached`, `schema_mismatch`, or `unreadable`),
`pending` (no record yet, and a refresh is running), `current`, or `stale`, plus the
pin, `refreshing`, how this server’s last refresh of it ended (`last_refresh`), and
`comparison_route`, the `diff/comparison` of the record’s merge-base endpoints.
The pin is the served commit and can differ from the record’s head: a commit URL inside
the pull request pins that commit, and a refresh can find a newer head than the pin.
A record is fetched only by a refresh.
`POST github/pull-refresh` starts or joins that refresh in the refresh coordinator and
answers `202` at once, naming `github/pull` as its `status_route`, which a one-shot
`--api` prints after the refresh ends, exiting 1 when it failed; it is a POST with a
JSON object body for the same reason `/api/source/refresh` is, and plugin data routes
are one path segment, hence the name.
`github/pull` also sends an entity tag over everything but the record, which changes
only with `fetched_at`, and answers a matching `If-None-Match` with `304`, so the
pull-request page polls it as cheaply as the status route.
`github/pull-markdown?part=<part>` renders one text of the cached record through KPress
in its sanitized mode and answers only the resulting HTML, with the record’s
`fetched_at` and the part: `body`, or `issue_comment/<id>`, `review/<id>`, or
`review_comment/<id>`. It never fetches; a part the record lacks is `unknown_part`.
KPress keeps what a document of its own may use, so the hook reduces that HTML to an
allowlist (`src/metabrowser/inert_html.py`, with links made absolute against the pull
request’s page): plain text markup (paragraphs, headings, emphasis, code, quotes, lists,
tables, details, `div`, `span`) with no attributes but a link’s `href` (http or https,
absolute against the pull request’s github.com page, in a new tab), `ol[start]`, a table
cell’s `colspan`, `rowspan`, and `align`, and `details[open]`. Scripts, styles, SVG,
MathML, media, frames, forms, and stylesheets go with their content; an image becomes a
link to it; any other tag is unwrapped to its text.
KPress’s asset list is not sent, so no script KPress adds for a text’s content loads.
The page applies the same allowlist again, rebuilding the nodes it inserts.
See
[Pull-request records](arch-repository-sources-and-provider-mirrors.md#pull-request-records).

The hosted-review slice registers these exact proposed resource routes with the browser
address in the same implementation changes:

| Planned route | Model | CLI evidence | Bead |
| --- | --- | --- | --- |
| `/api/hosted-review/<provider-kind>/<instance-key>/<repository-key>/repository` | `HostedRepository/v1` plus retrieval and manifest references | `metab --api`; `cli-github-repository.tryscript.md` | `mb-2oxp` |
| `/api/hosted-review/<provider-kind>/<instance-key>/<repository-key>/change-requests?query_key=<key>` | One `ChangeRequestIndex/v1` observation | `metab --api`; `cli-github-pr-index.tryscript.md` | `mb-lnkl` |
| `/api/hosted-review/<provider-kind>/<instance-key>/<repository-key>/change-requests/<resource-key>` | Selected `ChangeRequest/v1` bundle, including distinct top-level and review comments | `metab --api`; `cli-github-pr-open.tryscript.md` | `mb-h64t` |
| `/api/hosted-review/<provider-kind>/<instance-key>/<repository-key>/change-requests/<resource-key>/comparison` | File Diff Format resolved from immutable base/head object IDs | `metab --api`; `cli-github-pr-open.tryscript.md` | `mb-81p5` |

### Planned plugin registration surfaces

Browser and route declarations are additive installed-plugin capabilities only if
existing SDK 0.6 manifests and JavaScript calls keep their signatures and behavior.
They still require plugin-author documentation and a changelog entry.
An existing browser-contract change instead bumps `PLUGIN_SDK_VERSION` and every
built-in manifest in one commit, with no compatibility layer.
Artifact contracts and resource profiles use the separately versioned
`metabrowser.capabilities.v1` installed-Python entry-point group and never enter browser
plugin discovery or static asset loading.

| Declaration or SDK call | Owns | Arbitration and lifecycle | Bead |
| --- | --- | --- | --- |
| `SourceSession` / `SourceCapabilities`; `resolve_content`, `resolve_content_container`, `stat_content`, `read_content_window` | One active subject generation and opaque bounded content access | Every read takes an explicit byte maximum and there is no unbounded variant; failures share one catchable family with a `code` and the `http_status` the pinned routes answer with. Session replacement joins the old generation; legacy `Path` helpers and hooks run only with `filesystem_path`; absent semantics return typed unsupported states. `InventoryCoordinator.open_subject` accepts a `GitRevisionSubject` without a filesystem walk. `metab file://… --show`, non-cache `--api`, and `--check-api` open that pin in-process, and an `https://` or GitHub URL opens the commit it selects; serve mode opens it through the application lifespan, in the serving event loop, and closes it at shutdown. `POST /api/source/pin` replaces it within one mirror: the new subject is attached under a new generation, then the old one is closed, and a request still reading the old pin finishes on the store’s shared readers | `mb-3bna`, `mb-tsdc`, `mb-z335` |
| `RouterSpec` | Mounted HTTP prefix and trusted router factory | Reserved/duplicate prefixes fail; application lifespan awaits shutdown | `mb-xzj3` |
| `AddressSpaceSpec` / `registerAddressSpace` | Browser prefix, parse, format, apply, preview claim, startup, popstate, root replacement, disposal | Exactly one owner per address; browser and `metab --show` share the registration | `mb-6mle` |
| `ProviderUrlReducerSpec` | Declared schemes/hosts and `NotApplicable`/`Reduced`/terminal `Rejected` reducer | Overlapping claims fail discovery; claimed rejection never falls through. Superseded for the alpha by the thin-mirror plan: the built-in GitHub reducer reaches `classify_root_argument(reducers=)` through `cache/providers.py`, with no public declaration | `mb-12cz` |
| `ProviderAdapterSpec` | Provider/instance capability and trusted adapter factory | Duplicate claims fail; lifespan injects neutral ports and awaits cancellation/close | `mb-ji83` |
| `ArtifactContractSpec` / `ResourceProfileSpec` via `metabrowser.capabilities.v1` | Packaged schema, parser, corpus, producer/consumer inventory, and publication bundle shape | Only installed Python distributions contribute; duplicate IDs, malformed declaration structure, invalid schemas, broken profile references, missing evidence, and architecture-table drift fail the build. Artifact content cannot register declarations. The installed capability, generic inventory, and isolated-wheel gates are implemented without registering a browser plugin or static asset | `mb-52iz`, `mb-vors` |
| `ResourceKindSpec` | Route-backed semantic kind, item/container capabilities, primary contract, and views | Duplicate kind or view claims fail; route, browser, and CLI resolve the same selection | `mb-83w0` before `mb-81p5` |
| `registerNavPanel` | Repository-scoped bounded virtual collection | Generation-checked loading, restoration, root replacement, and disposal | `mb-uh6p` |

## CLI and functional UI parity

Every data surface the browser consumes is reachable from `metab` without a browser or a
listening port and is pinned by a golden transcript.
`--api` makes route reachability true by construction, while `--show` records the kind,
views, and model selected for a path.
`devtools/check_parity.py` fails the build when this table drifts from registered routes
or when any kind declared or consumed by a built-in manifest is absent from exact
`kind: <id>` output inside an executable golden console block.
`cli-show.tryscript.md` currently exercises every built-in kind in one small fixture.

Status values: **covered** names the goldens that pin it and **exempt** gives the reason
it has no model to pin.
There is no third value: `check_parity.py` rejects a `gap` row outright, so a new route
or kind arrives with transcript evidence or the build fails.

| Surface | Status | CLI | Golden or reason |
| --- | --- | --- | --- |
| `/api/file` | covered | `--show PATH`, `--api` | `cli-show.tryscript.md`, `cli-api.tryscript.md` |
| `/api/tree` | covered | `--walk`, `--api` | `cli-api.tryscript.md` |
| `/api/rollup` | covered | `--api` | `cli-api-nav.tryscript.md` |
| `/api/recent` | covered | `--api` | `cli-api-nav.tryscript.md` |
| `/api/activity` | covered | `--api` | `cli-api-nav.tryscript.md` |
| `/api/catalog` | covered | `--api` | `cli-api-shell.tryscript.md` |
| `/api/routes` | covered | `--api` | `cli-api-shell.tryscript.md` |
| `/api/diagnostics/pending-tallies` | covered | `--api --data` | `cli-api-shell.tryscript.md` |
| `/api/capabilities` | covered | `--api` | `cli-api-shell.tryscript.md` |
| `/api/index/progress` | covered | `--api` | `cli-api-shell.tryscript.md` |
| `/api/index/meta` | covered | `--api` | `cli-api-shell.tryscript.md` |
| `/api/cache/layout` | covered | `--api` | `cli-api-cache.tryscript.md` |
| `/api/cache/sources` | covered | `--api` | `cli-api-cache.tryscript.md` |
| `/api/cache/source` | covered | `--api` | `cli-api-cache.tryscript.md` |
| `/api/cache/stores` | covered | `--api` | `cli-api-cache.tryscript.md` |
| `/api/source/status` | covered | `--api` | `cli-api-shell.tryscript.md`, `cli-api-source.tryscript.md` |
| `/api/source/refresh` | covered | `--api --data` | `cli-api-source.tryscript.md`, `cli-api-shell.tryscript.md` |
| `/api/source/pin` | covered | `--api --data` | `cli-api-source.tryscript.md`, `cli-api-shell.tryscript.md` |
| `/api/source/refs` | covered | `--api` | `cli-api-source.tryscript.md`, `cli-api-shell.tryscript.md` |
| `/api/git/repo` | covered | `--api` | `cli-api-git.tryscript.md` |
| `/api/git/refs` | covered | `--api` | `cli-api-git.tryscript.md` |
| `/api/git/summary` | covered | `--api` | `cli-api-git.tryscript.md` |
| `/api/git/log` | covered | `--api` | `cli-api-git.tryscript.md` |
| `/api/git/commit` | covered | `--api` | `cli-api-git.tryscript.md` |
| `/api/kpress/render` | covered | `--api`, `--api --data` | `cli-api-shell.tryscript.md`, `cli-api-untrusted-markdown.tryscript.md` |
| `/api/kpress/export` | covered | `--api --data` | `cli-api-shell.tryscript.md` |
| `/api/plugin/agent-log/charts` | covered | `--api` | `cli-api-plugins.tryscript.md` |
| `/api/plugin/binary/chunk` | covered | `--api` | `cli-api-plugins.tryscript.md` |
| `/api/plugin/diff/document` | covered | `--api` | `cli-api-plugins.tryscript.md` |
| `/api/plugin/diff/children` | covered | `--api` | `cli-api-plugins.tryscript.md` |
| `/api/plugin/diff/comparison` | covered | `--api` | `cli-api-plugins.tryscript.md`, `cli-api-git.tryscript.md`, `cli-github-pull.tryscript.md` |
| `/api/plugin/github/pull` | covered | `--api` | `cli-github-pull.tryscript.md` |
| `/api/plugin/github/pull-refresh` | covered | `--api` | `cli-github-pull.tryscript.md` |
| `/api/plugin/github/pull-markdown` | covered | `--api` | `cli-github-pull.tryscript.md` |
| `/api/plugin/structured/parsed` | covered | `--api` | `cli-api-plugins.tryscript.md` |
| `/view` | covered | `--show PATH`, `--show /view/...` | `cli-show.tryscript.md` |
| `/commit` | covered | `--show /commit/<rev>[/<inner>]` | `cli-api-git.tryscript.md` |
| `/pull` | covered | `--show /pull/<n>[/files]` | `cli-github-pull.tryscript.md` |
| `/api/events` | exempt | — | streaming; the response never terminates, so there is no envelope to pin |
| `/raw` | exempt | — | asset serving; the query form and `/raw/{path}` share one resolver and send the file’s bytes plus sandbox headers, covered by `tests/test_raw_passthrough.py`, `tests/test_content_trust.py`, `tests/test_raw_path_route.py`, and, on a served Git pin, `tests/test_serve_pin.py` |
| `/_debug/tasks` | exempt | — | opt-in diagnostic, not a surface the browser reads |
| `/_debug/inventory` | exempt | — | opt-in diagnostic; its work counters carry wall and CPU times, which no transcript can pin. Its payload shape is asserted by `tests/test_inventory_debug_route.py`, because the performance harness and `devtools/bench_serving.py` both parse it. On a Git pin, which runs no inventory provider, it answers `unsupported_for_subject`, asserted by `tests/test_serve_pin.py` |
| `/api/stream` | exempt | — | streaming; the response never terminates, so there is no envelope to pin |

`/api/kpress/export` is the one surface whose golden writes a file, and the rule it
settles is worth stating: a golden may write, into the tryscript sandbox, which is
created per run and discarded after it.
That is safe here because the export report’s paths normalize to `<ROOT>` and its
content hash is identical across runs and across sandbox paths, so the write is
deterministic evidence rather than a source of churn.
The test runs last in its file so no earlier test observes the written file.

The `/api/cache/` rows are the persisted-state clause of the parity rule: cache state is
read through routes like any other model, not through an inspection command.
Their transcript builds each application home in the sandbox with the production cache
writers, and each command names its home with a leading `METABROWSER_HOME=$PWD/<home>`
assignment, because tryscript frontmatter cannot name the sandbox path.
`check_parity.py` skips leading environment assignments and nothing else, so the command
must still be `metab`. Sessions that write the cache through `--no-serve` — acquisition,
reuse, interruption recovery, fetch failure, and refusal — also read state through these
routes, but they run in-process as `.txt` goldens from
`tests/test_cli_cache_acquire_golden.py` and `tests/test_cli_cache_recovery_golden.py`,
because CI’s Git is below the acquisition floor.
`check_parity.py` reads only tryscript console blocks, so those sessions are not counted
as the rows’ evidence.

The exempt rows are the honest boundary.
A server-sent-event response has no terminating envelope, so `--api` bounds the request
and fails rather than hanging — which is behavior worth having, but not a model a
transcript can assert.
Their content is covered by `tests/dom/` and the event tests instead.

One covered row pins less than the others.
`/api/activity` marks a file active only after the tracker sees it change between two
polls, and a one-shot `metab` process ends first, so its transcript can pin the envelope
with an empty `active_files` and nothing more.
The nonempty case is asserted by `tests/test_browser_active_tracker.py`.

### User-visible functional aspects

Route reachability is necessary and insufficient.
A view can combine two correct models incorrectly, as Recent did when its tally counted
the complete response while its folder visibility depended on descendants mounted in the
DOM.

Every user-visible functional aspect belongs to one of three checked tiers:

- **data** — membership, ordering, grouping inputs, counts, bounds, persisted state,
  actions, and errors belong to a route or model reached through `metab`;
- **interaction** — browser-owned state machines run from a command line against the
  exact production JavaScript, with a golden transcript;
- **paint-exempt** — geometry, animation, real paint timing, or browser platform
  behavior may require a browser, but the row must give a specific reason and focused
  evidence.

There is no blanket exemption for the view layer.
The functional table is seeded with the navigation-filter composition that exposed the
old gap; subsequent user-visible work adds or refines rows at the level of the
observable contract it changes.
`devtools/check_parity.py` rejects missing evidence, prose-only mentions, commands a
golden never runs, data behavior that bypasses `metab`, and unexplained paint
exemptions. For an interaction row, it also runs the session and compares the declared
owners with checker-controlled V8 coverage.
Only a canonical path contained beneath the production source root whose executed
top-level range spans the file’s exact UTF-16 length receives credit.
An interaction owner must also name one unique function whose primary V8 range executed,
so a transitive import, stdout claim, comment, or relabeled snippet is not evidence.
The Recent session enters through the same production filter transition, request launch,
response settlement, complete-leaf projection, and live-change batch APIs as `app.js`;
the shell retains only transport and paint glue around those decisions.
KPress owns TOC disclosure; Metabrowser’s disclosure row proves that the installed
control remains wired through the production Markdown mount, including collapsed-row
state, accessible labels, and disposal.
The Markdown catalog itself remains the data model exposed by `/api/catalog` and its CLI
golden. Resolution, pinned-revision reconciliation, published-route adaptation, and
transclusion are browser-owned state machines over that immutable model; their
browserless session calls the exact production exports rather than adding a second
server algorithm that the browser does not consume.
Graph analysis is not an SDK surface: duplicating KPress parsing in the browser could
disagree with the document a reader sees.
A future graph belongs in a server route backed by a KPress-owned intent manifest.
It cannot infer an undeclared product behavior from source code; review is the gate that
requires a row whenever a change adds or alters an observable contract.
The **Data inputs** column makes provenance executable: a data row declares
`owned-route`; an interaction names only registered, route-parity-covered inputs or the
canonical `local-only` marker.
`transport-exempt:/api/events` is the narrow exception for the standing nonterminating
SSE transport whose emitted snapshot is already owned by its data routes.

| Aspect | Tier | Owner | Data inputs | CLI command | Golden or reason |
| --- | --- | --- | --- | --- | --- |
| `navigation.recent-filter-membership` | data | `/api/recent` | `owned-route` | `metab navroot --api '/api/recent?window=all&types=.md&min_size=7&include_ignored=0'` | `cli-api-nav.tryscript.md` |
| `navigation.recent-tree` | interaction | `static/filter-state.js#rowMatches`, `static/tree-filter-model.js#renderRecentView`, `static/tree-expansion.js#chooseDefaultExpandedPaths` | `/api/recent` | `node tests/dom/recent-filter-session.js` | `cli-ui-navigation.tryscript.md` |
| `navigation.recent-continuity` | interaction | `static/tree-filter-model.js#createRecentContinuity` | `/api/recent`, `transport-exempt:/api/events` | `node tests/dom/recent-filter-session.js` | `cli-ui-navigation.tryscript.md` |
| `navigation.file-type-replacement` | interaction | `static/tree-filter-model.js#applyRecentChangeBatch`, `static/known-file-catalog.js#applyCatalogChange` | `/api/recent`, `/api/catalog`, `transport-exempt:/api/events` | `node tests/dom/recent-filter-session.js` | `cli-ui-navigation.tryscript.md` |
| `navigation.known-file-catalog-order` | interaction | `static/known-file-catalog.js#create` | `/api/catalog` | `node tests/dom/catalog-unicode-order-session.js` | `cli-ui-navigation.tryscript.md` |
| `navigation.catalog-delivery-bounds` | interaction | `static/known-file-catalog.js#beginBulkSnapshot`, `static/catalog-feed.js#create` | `/api/catalog`, `transport-exempt:/api/events` | `node tests/dom/catalog-feed-large-session.js` | `cli-ui-navigation.tryscript.md` |
| `navigation.file-preview-ownership` | interaction | `static/navigation.js#createFileRevalidationTracker`, `static/navigation.js#settleFileSelectionFailure`, `static/navigation.js#commitFreshFileResponse` | `/api/file` | `node tests/dom/file-navigation-lazy-asset-session.js` | `cli-ui-file-lifecycle.tryscript.md` |
| `navigation.preview-pane-states` | interaction | `static/navigation.js#createPreviewPaneLifecycle`, `static/navigation.js#requestFailure`, `static/navigation.js#responseBodyFailure`, `static/navigation.js#settleFileSelectionFailure`, `static/navigation.js#openFailureOutcome`, `static/navigation.js#createController` | `/api/file`, `transport-exempt:/api/events` | `node tests/dom/preview-pane-state-session.js` | `cli-ui-file-lifecycle.tryscript.md` |
| `navigation.inventory-snapshot-replacement` | interaction | `static/navigation.js#replaceFileSnapshot` | `transport-exempt:/api/events` | `node tests/dom/file-navigation-lazy-asset-session.js` | `cli-ui-file-lifecycle.tryscript.md` |
| `navigation.catalog-continuity` | interaction | `static/catalog-feed.js#create` | `/api/catalog`, `transport-exempt:/api/events` | `node tests/dom/catalog-feed-behavior.js` | `cli-ui-navigation.tryscript.md` |
| `navigation.route-identity` | interaction | `static/navigation.js#href`, `static/navigation.js#parse`, `static/navigation.js#commitHref`, `static/navigation.js#parseCommit`, `static/navigation.js#pullHref`, `static/navigation.js#parsePull`, `static/navigation.js#displayPath` | `/api/file`, `/api/plugin/diff/comparison` | `node tests/dom/navigation-route-behavior.js` | `cli-ui-navigation.tryscript.md` |
| `navigation.served-source-kind` | interaction | `static/plugin-sdk.js#sourceKind`, `static/navigation.js#displayPath` | `/view`, `/api/tree` | `node tests/dom/source-kind-session.js` | `cli-ui-source-kind.tryscript.md` |
| `source.pinned-revision` | data | `/api/source/status` | `owned-route` | `metab shellroot --api /api/source/status` | `cli-api-shell.tryscript.md` |
| `source.mirror-freshness` | interaction | `static/source-freshness.js#createController`, `static/source-freshness.js#describe` | `/api/source/status`, `/api/source/refresh` | `node tests/dom/source-freshness-session.js` | `cli-ui-source-freshness.tryscript.md` |
| `source.selection-arrival` | interaction | `static/source-freshness.js#selectionToOpen`, `static/source-freshness.js#describe`, `static/source-freshness.js#createController` | `/api/source/status`, `/api/source/refresh` | `node tests/dom/source-freshness-session.js` | `cli-ui-source-freshness.tryscript.md` |
| `source.newer-revision-offer` | interaction | `static/source-freshness.js#describe`, `static/source-freshness.js#acceptOffer` | `/api/source/status`, `/api/source/pin` | `node tests/dom/source-freshness-session.js` | `cli-ui-source-freshness.tryscript.md` |
| `source.stale-pin-guard` | interaction | `static/source-pin-guard.js#guardFetch`, `static/source-pin-guard.js#guardedRequest` | `/api/file`, `/api/tree`, `/api/source/status` | `node tests/dom/source-freshness-session.js` | `cli-ui-source-freshness.tryscript.md` |
| `source.ref-selector` | interaction | `static/source-ref-selector.js#createSelector`, `static/source-ref-selector.js#describe` | `/api/source/refs`, `/api/source/pin` | `node tests/dom/source-ref-selector-session.js` | `cli-ui-source-ref-selector.tryscript.md` |
| `git.history-stale-cursor` | interaction | `static/git-history-window.js#classifyPageFailure` | `/api/git/log` | `node tests/dom/source-freshness-session.js` | `cli-ui-source-freshness.tryscript.md` |
| `github.pull-page` | interaction | `builtin_plugins/github/pull-page.js#describePull`, `builtin_plugins/github/pull-page.js#createPullController` | `/api/plugin/github/pull`, `/api/plugin/github/pull-refresh`, `/api/plugin/github/pull-markdown`, `/api/source/pin` | `node tests/dom/github-pull-page-session.js` | `cli-ui-github-pull-page.tryscript.md` |
| `github.pull-page-inert-markup` | interaction | `static/inert-html.js#sanitizeNodes`, `static/inert-html.js#allowedAttributes`, `static/inert-html.js#imageLink`, `builtin_plugins/github/pull-page.js#safeLink`, `builtin_plugins/github/pull-page.js#gitPathWire` | `/api/plugin/github/pull-markdown` | `node tests/dom/github-pull-page-session.js` | `cli-ui-github-pull-page.tryscript.md` |
| `github.pull-page-paint-decisions` | interaction | `builtin_plugins/github/pull-page.js#conversationAction`, `builtin_plugins/github/pull-page.js#conversationKey`, `builtin_plugins/github/pull-page.js#filesAction` | `/api/plugin/github/pull` | `node tests/dom/github-pull-page-session.js` | `cli-ui-github-pull-page.tryscript.md` |
| `navigation.pull-page-history` | interaction | `static/navigation.js#pullHistoryAction` | `local-only` | `node tests/dom/navigation-route-behavior.js` | `cli-ui-navigation.tryscript.md` |
| `assets.on-demand-load-recovery` | interaction | `static/asset-loader.js#ensureAsset`, `static/asset-loader.js#ensureScript` | `local-only` | `node tests/dom/asset-loader-behavior.js` | `cli-ui-navigation.tryscript.md` |
| `source.incremental-cache-transaction` | interaction | `static/source-append.js#requestOwnsPreview`, `static/source-append.js#commitChunkCache` | `/api/file` | `node tests/dom/source-append-navigation-session.js` | `cli-ui-file-lifecycle.tryscript.md` |
| `agent-log.chart-request-ownership` | interaction | `builtin_plugins/agent_log/index.js#renderCharts` | `/api/file`, `/api/plugin/agent-log/charts` | `node tests/dom/agent-log-plugin-behavior.js` | `cli-ui-agent-log-charts.tryscript.md` |
| `charts.theme-and-replacement-lifecycle` | interaction | `static/charts.js#renderPayload`, `static/charts.js#repaintForTheme`, `static/view-composition.js#createLifecycle` | `/api/plugin/agent-log/charts` | `node tests/dom/chart-theme-behavior.js` | `cli-ui-agent-log-charts.tryscript.md` |
| `markdown.primary-fragment-links` | interaction | `builtin_plugins/markdown/rendered.js#mountRenderedMarkdown`, `builtin_plugins/markdown/link-enhancer.js#enhanceRenderedLinks` | `/api/kpress/render` | `node tests/dom/markdown-toc-scrollspy-session.js` | `cli-ui-markdown-scrollspy.tryscript.md` |
| `markdown.embedded-fragment-links` | interaction | `builtin_plugins/markdown/link-enhancer.js#enhanceRenderedLinks` | `/api/kpress/render` | `node tests/dom/markdown-toc-scrollspy-session.js` | `cli-ui-markdown-scrollspy.tryscript.md` |
| `markdown.toc-scrollspy` | interaction | `builtin_plugins/markdown/rendered.js#mountRenderedMarkdown`, `builtin_plugins/markdown/toc-intersection-fallback.js#initTocWithIntersectionFallback`, `builtin_plugins/markdown/toc-intersection-fallback.js#selectTocTargetAtReadingLine` | `/api/kpress/render` | `node tests/dom/markdown-toc-scrollspy-session.js` | `cli-ui-markdown-scrollspy.tryscript.md` |
| `markdown.toc-disclosure` | interaction | `builtin_plugins/markdown/rendered.js#mountRenderedMarkdown` | `/api/kpress/render` | `node tests/dom/markdown-toc-scrollspy-session.js` | `cli-ui-markdown-scrollspy.tryscript.md` |
| `markdown.wiki-resolution` | interaction | `builtin_plugins/markdown/wiki-resolver.js#createWikiResolutionContext` | `/api/catalog` | `node tests/dom/markdown-functional-session.js` | `cli-ui-markdown-functional.tryscript.md` |
| `markdown.catalog-reconciliation` | interaction | `builtin_plugins/markdown/reconciliation-coordinator.js#createMarkdownReconciliationCoordinator` | `/api/catalog`, `transport-exempt:/api/events` | `node tests/dom/markdown-functional-session.js` | `cli-ui-markdown-functional.tryscript.md` |
| `markdown.published-route-adaptation` | interaction | `builtin_plugins/markdown/project-adapters.js#createPublishedRouteResolutionContext` | `/api/catalog` | `node tests/dom/markdown-functional-session.js` | `cli-ui-markdown-functional.tryscript.md` |
| `markdown.standard-link-semantics` | interaction | `builtin_plugins/markdown/links.js#createTrustedStandardLinkResolutionContext`, `builtin_plugins/markdown/link-enhancer.js#enhanceRenderedLinks` | `/api/kpress/render` | `node tests/dom/markdown-functional-session.js` | `cli-ui-markdown-functional.tryscript.md` |
| `markdown.worker-preprocessing` | interaction | `builtin_plugins/markdown/markdown-worker-client.js#acquireMarkdownWorkerClient`, `builtin_plugins/markdown/markdown-worker-client.js#createMarkdownWorkerClient`, `builtin_plugins/markdown/wiki-parser.js#preprocessObsidianWiki`, `builtin_plugins/markdown/rendered.js#mountRenderedMarkdown` | `/api/file`, `/api/kpress/render` | `node tests/dom/markdown-functional-session.js` | `cli-ui-markdown-functional.tryscript.md` |
| `markdown.transclusion-lifecycle` | interaction | `builtin_plugins/markdown/transclusion.js#createTransclusionBudget`, `builtin_plugins/markdown/transclusion.js#mountWikiTransclusion` | `/api/catalog`, `/api/file`, `/api/kpress/render` | `node tests/dom/markdown-functional-session.js` | `cli-ui-markdown-functional.tryscript.md` |
| `markdown.untrusted-inert-render` | interaction | `static/inert-html.js#sanitizeNodes`, `static/inert-html.js#allowedAttributes`, `static/inert-html.js#keepsImage`, `builtin_plugins/markdown/inert-render.js#isInertRender` | `/api/kpress/render` | `node tests/dom/inert-html-session.js` | `cli-ui-inert-markdown.tryscript.md` |
| `markdown.aggregate-root-budget` | interaction | `builtin_plugins/markdown/reconciliation-coordinator.js#createMarkdownEnhancementBudget`, `builtin_plugins/markdown/dom-traversal.js#matchingDescendants`, `builtin_plugins/markdown/link-enhancer.js#enhanceRenderedLinks` | `/api/catalog`, `/api/kpress/render` | `node tests/dom/markdown-functional-session.js` | `cli-ui-markdown-functional.tryscript.md` |
| `image.raw-preview` | interaction | `static/view-composition.js#createLifecycle`, `builtin_plugins/image/index.js#renderImage` | `/api/file` | `node tests/dom/image-preview-session.js` | `cli-ui-image-preview.tryscript.md` |
| `html.sandboxed-preview` | interaction | `static/view-composition.js#createLifecycle`, `builtin_plugins/html/index.js#renderPreview` | `/api/file` | `node tests/dom/html-preview-session.js` | `cli-ui-html-preview.tryscript.md` |
| `html.full-page-escape` | interaction | `builtin_plugins/html/index.js#createFullPageBar` | `/api/file` | `node tests/dom/html-preview-session.js` | `cli-ui-html-preview.tryscript.md` |
| `document.reading-width` | interaction | `static/document-width.js#apply` | `local-only` | `node tests/dom/document-width-session.js` | `cli-ui-document-width.tryscript.md` |
| `navigation.filter-layout` | paint-exempt | `static/styles.css` | `local-only` | — | CSS geometry and disclosure motion require rendered layout; focused selectors and accessibility state are pinned in `tests/test_browser_filter_ui.py` and `tests/test_tree_keyboard_integration.py` |
| `github.pull-page-paint` | paint-exempt | `builtin_plugins/github/pull-page.js#mountPullPage` | `local-only` | — | Building the page’s DOM, observing which texts scroll into view, loading KPress’s stylesheets, mounting the diff view, and the shell’s `app.js` calls that claim the pane and call `history.pushState` need a rendered page. Every decision they act on is a session owner above: the history action (`navigation.pull-page-history`), whether the conversation repaints or asks again and what Files changed keeps (`github.pull-page-paint-decisions`), and what of a text’s HTML is inserted (`github.pull-page-inert-markup`). The route grammar, the shell and plugin wiring for the `pull-request` kind, and that only an inert template is parsed are pinned in `tests/test_pull_page_route.py`; the browser walkthrough is in the v0.12 QA runbook |

### Planned v0.12 hosted-review functional rows

These rows move into the enforced table in the same changes that add their production
functions. All interaction rows enter through `node tests/dom/hosted-review-session.js`
and are pinned together by `tests/golden/cli-ui-hosted-review.tryscript.md`; focused
unit sessions may supplement but cannot replace that exact production path.

| Aspect | Tier | Planned owner | Data inputs | Required production session |
| --- | --- | --- | --- | --- |
| `hosted-review.direct-lifecycle` | interaction | `static/plugin-address-spaces.js#parseAddress`, `static/plugin-address-spaces.js#applyAddress`, `builtin_plugins/hosted_review/hosted-review-view.js#prepareChangeRequestView`, `#mountChangeRequestView`, `#disposeChangeRequestView` | selected change-request and comparison routes above | direct `/hosted/.../change-request/...` startup, popstate, replacement, and failed-load recovery |
| `hosted-review.panel-window` | interaction | `builtin_plugins/hosted_review/hosted-review-panel.js#createPullRequestPanel`, `#loadIndexPage` | change-request index route | bounded page load, virtualization window shift, stale and partial indicators |
| `hosted-review.panel-selection` | interaction | `builtin_plugins/hosted_review/hosted-review-panel.js#openChangeRequest` | index and selected change-request routes | row selection opens the same direct address and changed-file container |
| `hosted-review.panel-restoration` | interaction | `builtin_plugins/hosted_review/hosted-review-panel.js#restorePullRequestSelection` | index route | selection and expansion restore only for the same repository and query key |
| `hosted-review.root-replacement` | interaction | `static/plugin-address-spaces.js#replaceRoot`, `builtin_plugins/hosted_review/hosted-review-panel.js#replaceRoot` | `local-only` | old requests, previews, index pages, and snapshot leases settle before the new root owns state |
| `hosted-review.disposal` | interaction | `static/plugin-address-spaces.js#disposeAddress`, `builtin_plugins/hosted_review/hosted-review-view.js#disposeChangeRequestView`, `builtin_plugins/hosted_review/hosted-review-panel.js#dispose` | `local-only` | navigation away, failed replacement, root replacement, and shutdown dispose once |

Every browser-consumed Hosted Review Format record has a named parser in
`builtin_plugins/hosted_review/hosted-review-model.js` and runs the same valid/invalid
corpus as Python: repository, index, change request, top-level comment, review, thread,
review comment, check, status, and activity page.
Provider binding, retrieval, resource-set, sync-manifest, pointer, and tombstone records
remain server-only publication evidence and have no browser parser.
No server aggregate may bypass those record validators.

## Adding something

- **A filesystem-backed kind**: add a `[[kind]]` block with a match predicate and at
  least one `[[view]]`, then add a representative `--show` case to the golden
  transcript.
- **A route-backed resource kind**: add one `ResourceKindSpec` with its primary
  contract/model, item/container capabilities, address owner, and views; add the route,
  `--show`, `--api`, browser parser, and functional golden evidence in the same change.
  Do not invent a file matcher.
- **A view on an existing kind**: add a `[[view]]` block and `mb.registerView`; give it
  a disposal path, then register each new observable behavior in the functional table.
- **A container**: add `container = { children = "<data_hook route>" }` to the kind and
  serve child rows from that hook.
  The tree, keyboard, ARIA, and URL behavior follow.
- **A data format**: it needs a schema, a conformance corpus both implementations run,
  and a normative doc — the bar the two formats above meet.
- **A route**: only when a genuinely new address space appears.
  A new kind of thing *within* an existing space extends that space’s path instead.

`tests/test_views_models_routes.py` checks the tables above against the manifests and
route table. `devtools/check_parity.py` binds the registered routes and kinds to their
CLI transcript evidence, so the map and executable coverage fail together rather than
drifting.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
