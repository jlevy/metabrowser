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
  Core routes are owned by the shell; a plugin adds data routes as `[[data_hook]]`
  entries under `/api/plugin/<plugin>/`. See
  [Browser URL Grammar](../../architecture.md#browser-url-grammar).
- **Resource kind** is the semantic classification a plugin claims.
  Filesystem `[[kind]]` blocks use `FileContext` (including content predicates).
  Git blobs use extension, basename, sniffed adapter, and bounded JSON/YAML/frontmatter
  mappings parsed from blob bytes.
  `path_glob` stays filesystem-only.
  A route-backed kind has no file matcher: the shell selects it for its route, as it
  does `pull-request` for `/pull/<n>`. One kind, many views.
- **Contract/model** is the validated data a view receives.
  Simple kinds take the `/api/file` envelope; richer kinds have their own documented
  format with a schema and a conformance corpus.
- **View** is a registered renderer (`[[view]]` plus `mb.registerView`), shown as a tab.
  A kind’s `default = true` view is what a selection opens.

The layers are deliberately decoupled: a view never learns which source produced its
model, and a model never learns which route reached it.
That is what lets one diff renderer serve a patch file, a commit, and a pull request
without knowing the difference.

The repository cache validates its own records against installed artifact contracts; see
[Cache record contracts](arch-repository-sources-and-provider-mirrors.md#cache-record-contracts).
Resource publication profiles and resource kinds belong to the retired design in
[External Resources, Artifact Contracts, and Views](arch-external-resources-and-views.md)
and are not built.

Filesystem-backed models reach these layers through the
[Inventory Provider Contract](arch-inventory-provider.md).
That boundary keeps routes, wire serializers, and views independent of the Python or fdu
engine selected for the served-root session.
The source boundary for attached filesystems and immutable Git revisions is in
[Repository Sources and Provider Mirrors](arch-repository-sources-and-provider-mirrors.md).
It keeps a session’s selected root independent of the shared Git object store.

## Kinds and their views

Built-in kinds, as registered by the manifests in `src/metabrowser/builtin_plugins/`:

| Kind | Matches | Views (default first) and keys | Model |
| --- | --- | --- | --- |
| `folder` | Directories | Overview `O`, Treemap `M` | Folder envelope + [File Rollup Format](file-rollup-format/file-rollup-format.md) |
| `markdown` | `.md` | Document `D`, Source `S` | File envelope; KPress render |
| `html` | `.html`, `.htm` | Preview `P`, Source `S` | File envelope; sandboxed raw document |
| `text` | Text files | Source | File envelope |
| `structured` | `.json`, `.yaml`, `.yml` | Tree `R`, Source `S` | File envelope, parsed hook |
| `diff` | `.patch`, `.diff` | Diff | [File Diff Format](file-diff-format/file-diff-format.md) |
| `agent-log` | `.jsonl` sniffed as an agent log | Log `L`, Charts `C`, Raw JSON `R` | File envelope, charts hook |
| `unknown-jsonl` | Other `.jsonl` | Log `L`, Raw JSON `R` | File envelope |
| `image` | Browser image extensions | Image | File envelope; raw asset |
| `binary` | Non-text files | Bytes | Bounded byte-chunk hook |
| `pull-request` | No file; the shell selects it for `/pull/<n>[/files[/<path>]]` | Pull request, which draws its own Conversation, Changes, and Checks tabs | `github/pull` envelope; `github/pull-markdown` per text; `github/pull-timeline` for Conversation commits; `github/pull-comparison` for Changes, at one changed file for `/pull/<n>/files/<path>`; `github/pull-rendered-diff` per changed Markdown file |
| `pull-request-list` | No file; the shell mounts it in the Pulls tab, and in the pane at `/pulls` | Pull requests | `github/pulls` envelope; `github/pulls-refresh` for resumable catalog warming; `github/pull` for a row’s record |

A view’s key is its manifest `[[view]] key`, written here uppercase as the keyboard
shows it and served lowercase as the envelope’s `views[].key`; a single-view kind
declares none, and a list left with one view, as HTML without active content or a Git
folder with Overview alone, serves none.
`tests/test_keymap.py` fails when two views of a kind share a key or a view takes a key
the shell reserves for that kind, which `src/metabrowser/keymap.py` lists, and
`cli-show.tryscript.md` prints each kind’s views with their keys.

Two kinds are also **containers** — folder-like entries whose children are addressable
(see [nav containers](arch-nav-containers.md)): `folder` (children are files and
folders) and `diff` (children are the files a patch changes).

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

Complete formats have a schema, a conformance corpus, and implementations bound by it.
These formats are tool-neutral: nothing in a document references Metabrowser.

| Format | Describes | Authority | Implementations |
| --- | --- | --- | --- |
| [File Diff Format v1](file-diff-format/file-diff-format.md) | A change set between two snapshots | `data/file-diff-format/file-diff.schema.json` | `metabrowser.diff.format` (Pydantic), `builtin_plugins/diff/diff-model.js` |
| [File Rollup Format](file-rollup-format/file-rollup-format.md) | File classification and directory totals | `data/file-rollup-format/` | Python inventory, browser rollup projection |

The repository cache’s record contracts are an internal format, not one of these: their
installed inventory is maintained by `devtools/check_artifact_contracts.py` in
[Cache record contracts](arch-repository-sources-and-provider-mirrors.md#cache-record-contracts),
and this map registers no route, kind, or view for them.

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
| `/commit/<rev>` | A commit’s change set against its first parent | Implemented, for a full commit ID; anything else says it needs one (`revision_not_full`). Back or Forward onto the entry restores the commit |
| `/commit/<rev>/<inner>` | One file’s diff inside that change set | Route parses; the panel restores the commit, not yet the file |
| `/pull/<n>[/files or /checks]` | A pull request’s Conversation, Changes, or Checks tab | Implemented. The GitHub plugin renders all three tabs from the same PR record. The initial read uses the cache, and a visible first visit can fill an empty cache with a separate request |
| `/pull/<n>/files/<path>` | One changed file of that page: Files changed, with the diff at that file | Implemented. The path is one in the pull request’s comparison, a segment at a time, never looked up on disk. A file row in the Pulls tab links to it; `--show` reports the page and whether the cached list of changed files holds the path |
| `/pulls` | A repository’s list of pull requests with none selected; `?state=` names its filter | Implemented. The pane says what is listed, and the Pulls tab shows the list. A server with no GitHub repository answers the shell, and the page’s own request says there is nothing to list |
| `/compare/<base>..<head>[/<inner>]` | An explicit comparison (`...` for merge base) | Specified, not built |

The shape after the route is always `<container address>/<inner path>`, which is the
container contract written as a URL. The full grammar, including the `_mb_` query
reservation and its invariants, is in
[Browser URL Grammar](../../architecture.md#browser-url-grammar).

### Data routes

| Route | Serves |
| --- | --- |
| `/api/file` | The file or folder envelope: kind, views, capability envelope, and bounded content window. Each `views[]` entry carries its manifest’s one-letter `key`, lowercase, when it declares one; within a kind’s merged views the first view keeps a shared key and a key the shell reserves for the kind is dropped, the view still served, and `metab --doctor` reports either, naming both plugins for a shared key (`keymap.check_view_keys`; `cli-plugins-view-keys.tryscript.md`). A list that keeps fewer than two views serves no key, since one view has no other tab to switch to (`keymap.live_view_keys`). A folder the inventory’s scope leaves out still gets its envelope, with `dir.not_indexed` saying which it is: `hidden` for a hidden path component, and `symlink` for one reached through a symbolic link. Its aggregates stay null and `state` pending, and `/api/tree` and `/api/rollup` answer 404, so the page states why it has no totals instead of waiting for them. A `GitRevisionSubject` uses `GitPath` wire identities and Git object facts; it does not invent mtime or ignore state. A Git tree envelope is SPA `folder` chrome (`git_kind` stays `tree`) with recursive blob `total_files` / `total_size` and no mtime. A complete blob-size tally mounts Overview and treemap; a direct-child README blob sets `readme_path` to its GitPath wire. SPA path chrome and copy-path decode GitPath wires to display names (C0 and invalid UTF-8 become U+FFFD); navigation identities stay wires. Omitted mtime leaves tally chrome empty rather than pending. File Overview mounts when `dir` carries inventory `mtime` or Git `total_size`. Blob kinds use extension, basename, sniffed adapter, and bounded JSON/YAML/frontmatter mappings. Git blob envelopes carry the name’s last extension as `ext`, as a folder’s do, and choose the kind from it, so plugin-sdk `langForPath` and `ctx.ext` do not fall back to a GitPath wire; they omit compressed `logical_ext` because blobs are stored bytes with no gzip smudge. Git markdown envelopes include parsed YAML `frontmatter` and `frontmatter_error`; KPress on a pin uses that parse rather than an empty mapping. Git text envelopes use the same first-window and highlight bound as filesystem listings (`bytes_read`, `content_preview_limit`, `content_max_preview_limit`, `highlight_disabled`), and a later window’s `bytes_read` is the cursor past it, as on the filesystem, which Load more reads as its next offset. `/api/file`, `/raw`, KPress, and plugin sidekicks follow in-tree relative symlink blobs; the requested GitPath stays the route identity, and kind checks use the leaf path. A Git image blob is SPA `image` chrome; `/raw` serves the stored bytes. A Git `.jsonl` blob is a parsed JSONL envelope. A patch-file container inner is a `GitPath` `g1-` prefix plus a host inner path. An LFS pointer is stored pointer bytes; a missing blob is `object_unavailable`. Markdown and wiki links on that pin resolve to `GitPath` wires |
| `/api/tree` | Navigation subtrees. `types` and `min_size` work for every source that supplies them. Git blob listings carry `cat-file` info sizes so `min_size` can filter; trees and gitlinks stay unsized as blobs. `recency` requires that declared source capability and otherwise returns `unsupported_for_subject`. The SPA hides Modified within on a Git pin because there is no honest mtime. `include_ignored=0` on a Git pin is a no-op because ignore is absent (unignored equals total), not `unsupported_for_subject`. On a Git pin the payload keeps Git-native `entries` and also projects a SPA `tree` array (`dir`/`file`/`symlink`, `GitPath` wires, blob sizes, recursive dir `total_files`/`total_size`, no mtime/ignore); gitlinks are files, not directories. `depth` nests children the way filesystem listings do (default 2) and emits a lazy sentinel past the cap; `depth=0` returns chrome without a listing. File nodes include `ext` from the same bounded compound-tail helper as filesystem inventory; `logical_ext` is only the inner extension of a compressed name. Whole-tree `extensions`, `canonical_extensions`, `type_families`, and `type_presets` rows, `tally_cache_status`, and `summary` (`files`, `size`, ignored 0/0) come from the recursive blob index; ignored counts are 0 because ignore is absent. Incomplete blob sizes omit `summary` rather than inventing 0. `types` and `min_size` keep ancestor trees of matching blobs and emit subtree `filtered` totals; empty filter dirs are omitted. Git `logical_ext` and type matching use the same bounded compound-tail helper as filesystem inventory. Omitted mtime leaves tally chrome empty rather than pending |
| `/api/rollup` | Bounded directory rollups over the facts the active source truthfully supplies; a requested unavailable dimension returns `unsupported_for_subject`. A `GitRevisionSubject` answers from recursive blob names and sizes, omits mtime, and treats ignore as absent so unignored equals total. A missing blob size is `object_unavailable` rather than a partial sum. Beside `file_type_breakdown`, `file_type_legend` names what File Overview’s compact legend shows for each measure and population: at most five families above the 1% share floor at which the type table folds a row into “N more”, ranked across groups, and `other` for the rest; No extension and Other types are never named. It is null exactly when the breakdown is. The rule is `file_type_legend.py` |
| `/api/catalog` | One-shot file universe for Quick Search. A `GitRevisionSubject` lists recursive blob names (`p` GitPath wire, `e` logical compound-tail extension, `n` display basename) and is already complete; a truncated index is an empty truncated snapshot |
| `/api/index/progress`, `/api/index/meta`, `/api/capabilities` | Index status. A `GitRevisionSubject` answers from recursive blob names, omits mtime and watcher facts, and reports `events.stream` off. The JSONL stream still refuses a Git pin |
| `/api/recent` | Flat newest-first matching leaves for sources with recency; unavailable for immutable Git trees rather than populated with fake mtimes |
| `/api/activity`, `/api/stream` | Live inventory and JSONL tail for sources with a filesystem root; unavailable for immutable Git trees rather than the lifespan folder |
| `/api/git/repo`, `/api/git/refs`, `/api/git/summary`, `/api/git/log`, `/api/git/commit/<rev>` | Read-only Git history for the Git panel; log pages use bounded, replayable server sessions, opaque page cursors, and versioned graph-boundary checkpoints. The boundary and its rules are in [Git and comparison sources](arch-git-and-comparison-sources.md) |
| `/api/cache/layout`, `/api/cache/sources`, `/api/cache/source/<slug>`, `/api/cache/stores` | Read-only logical state of the repository cache: layout and config formats, abandoned staging entries, source identity with alias generation and publication, and store records with the aliases that name them, including a store’s `mode` (`full`, or `overlay` when it borrows from a checkout) and `lender` (`present` or `lender_missing`, and no path). They resolve cache and configuration independently per request using the storage precedence rules without creating either root, read without locks and without repairing a shared entry, page in key order, and never report a cache path, pack file, or Git internal. Wire shapes are in `cache/wire.py`. A server serving a Git pin answers them with `unsupported_for_subject` (409), so nothing about other cached sources is served beside acquired content |
| `/api/identity` | What the served subject is called, for a window’s title: `short_name`, `full_name`, `kind` (`folder` or `mirror`), `kind_label` (`Local folder` or `Cached mirror`), and `title`, `<short_name> • Metabrowser` with U+2022, which the shell writes, escaped as HTML, as its `<title>`. A folder is called by its own name, `/` for the file system’s root and `~` for the home directory itself, and its full name is its absolute path with the home directory as `~`; `metab <file>` serves the file’s folder, and the pull-request pages a checkout opens keep the folder’s name. A mirror is called by its repository’s name, the `name` `/api/source/status` reports, and its full name is its origin without the scheme, the user, a leading `www.`, or a trailing `.git` (`git@host:owner/repo` reads `host/owner/repo`, and a `file://` origin is its path with the home directory as `~`), then `@<ref>` for a branch or tag, `@<first 12 hex>` for a commit, or `#<n>` for a pull request’s head, whose short name is `<repository> #<n>`. It never names the cache. Every name passes through `display_segment`. A page changes subject only by loading again, so no page asks for this route: it is for a native window and `--api`. It is answered from memory and runs no Git. `RootIdentity` in `root_identity.py` maps every subject kind; `tests/test_root_identity.py` covers each origin form and pin, and `tests/test_serve_pin.py` a served mirror and its switch |
| `/api/source/status` | What this server serves: the subject kind and session generation, and on a `GitRevisionSubject` the full commit it is pinned to (`pin`), the store ref that commit was resolved from (`ref`), and the name the origin knows that ref by (`ref_name`); all three are null on a folder. On a served mirror it names what the page is headed by: the repository’s `name` as a checkout would have it, the `origin` it mirrors, and the `location` of the mirror, the store’s bare repository; a `file://` origin and the location have the home directory as `~` when they are under it, and all three are null for a folder and for a pin with no mirror. `location` is the one field of any route’s answer that names a path in the cache, and [What a mirror’s page is called](arch-repository-sources-and-provider-mirrors.md#what-a-mirrors-page-is-called-and-where-it-says-it-is-kept) holds its bounds; `--api` prints it as answered, the one field a pin’s output does not rewrite to `<ROOT>`. Beside it, under the same exception, `borrows` is the checkout an overlay store borrows objects from, null for a store that holds its own, and `shallow` is whether the store’s history stops at a shallow boundary. On a served mirror it also reports freshness from server memory, so polling it runs no Git and reads no store: `refreshable`, the commit the pinned ref names in the mirror now (`latest`), whether the origin still had that ref at the last fetch (`ref_on_origin`: false when it deleted it, null for a pin by commit ID, a ref not yet observed, or a ref the store swept because the checkout it borrows from collected its commits, until a fetch names it again), `last_fetch_at`, `last_outcome` (operation, typed outcome by name, time, from this process or the store’s record, whichever is newer), `refreshing`, and `stale` (older than the one-minute freshness window), both of which cover the attended pull request’s record as well as the mirror, plus `pull_request`, the attended pull request: the number a URL named, replaced whenever a pin switch serves another’s `refs/pull/<n>/head`, `selection_state`, which follows a URL selection the mirror lacked when serving began (`pending` until a fetch for it ends, then `found` and served, `not_found`, or `fetch_failed` when that fetch did not run; `superseded` after a pin switch), and `selection_href`, where a found selection opens. `cli-github-url-waits.txt` pins the pending, found, not-found, and fetch-failed sequence through `metab <url> --api /api/source/refresh --data …`, the one-shot request that fetches; `tests/test_github_serve.py` covers a server, a superseding switch, and the retry after a failed fetch. It sends an ETag and answers `If-None-Match` with 304. The navigation heading on a pin renders from the same envelope. Its checked evidence includes a pin: `cli-api-source.tryscript.md` opens a cached mirror, which needs no acquisition floor, so it runs on any Git; acquiring and serving one are pinned in-process by `cli-git-pin-index.txt` and `tests/test_serve_pin.py` |
| `/api/source/refresh` | `POST` with a JSON body: start a background refresh of the served mirror, or join the one running, and answer 202 at once with `refresh` (`started` or `joined`) and the status, or 429 `too_many` when only the attended pull request is stale and the pull-request queue has no room. The refresh is one `fetch --prune --atomic` under the store’s fetch side lock; its typed outcome appears in the status, never as a request error. A body of `{"for": "commit"}` asks for the fetch a commit the mirror lacks waits for: the mirror’s branches and tags, as a pin by commit ID asks for, and the refresh of the data served beside it. A page sends it by itself when it opens a commit’s address, which a link in served content can cause, so it fetches the mirror only when the last fetch is older than the freshness window and joins a fetch that is running; inside the window `refresh` is `fresh`, no mirror fetch starts, and the answer is 200 unless the data beside the mirror is refreshing. `"retry": true` is a reader’s own click and always fetches. That answer also carries `pull_refresh`, how the attended pull request’s refresh was answered (`started`, `joined`, or `too_many` when the queue had no room for it) or null when none was asked for, so a commit page does not say the origin lacks a commit only that refresh would bring; `cli-ui-source-freshness.tryscript.md` pins the refusal. Any other key is `invalid_request` (400). `tests/test_mirror_companion.py` and `tests/test_source_refresh.py` cover both sides of the window; `cli-api-source.tryscript.md` pins the request on a stale mirror and `cli-git-refresh.txt` on a fresh one, with the retry. A folder, or a pin with no mirror, answers `unsupported_for_subject` (409). A one-shot `--api` waits for the refresh it started, prints the status after it, and exits 1 unless the fetch ran or another process’s refresh is running; nothing else in a one-shot command fetches. A page on a pin sends the commit it shows in `x-metabrowser-pin` on every other `/api/` request, and a request for a commit the server does not serve, after a switch or a restart onto another pin, answers `pin_changed` (409); loads that are not `fetch` calls, such as `/raw` images, are not checked |
| `/api/source/refs` | `GET` with `kind` (`branch` or `tag`), `q`, and `limit`: the served mirror’s branches or tags, for the ref selector, read from the mirror alone with one `for-each-ref`. Branches list the default first, then by name; tags newest first. Each row has `name`, the store `ref` a pin request names it with, the `commit` it names (an annotated tag peeled), `default`, and `current`, which marks the ref the server serves now. `q` is a case-insensitive name fragment of at most 256 characters; `limit` is clamped to 1–1000 (default 100), and `total` and `truncated` say how many matched. A tag is listed when it names a commit, directly or as an annotated tag whose own target (`%(object)`, one level on every Git version) is a commit; a tag of a tree, a blob, or another tag is not listed and still pins by name. An unknown `kind` or an overlong `q` answers `invalid_request` (400); a folder, or a pin with no mirror, `unsupported_for_subject` (409) |
| `/api/source/pin` | `POST` with `{"ref": …}` or `{"oid": …}`: resolve a branch, then a tag, then a commit ID in the mirror alone, never through revision syntax, and serve it: the old tree source is closed and the new one attached under a new generation. Answers `changed` and the new status, and, when the body also names the page’s `/view/` address as `view`, `view_href`: that entry’s canonical address when the new pin has it, an inner address kept when the new pin has its container file, else `/view/`; `view` is checked before the switch, so one that is not percent-encoded ASCII is `invalid_selection` with nothing changed, and a query or fragment is dropped; `invalid_selection` (400), `selection_not_found` (404), `ambiguous_selection` (409), or `unsupported_for_subject` (409) otherwise. `HEAD` is the default branch, and a name the mirror holds that is not a commit answers `not_a_commit` (409) at once, as URL opening does. A commit pinned by `oid` has no ref, unless it is the tip, in the mirror now, of the ref this server last served or of the attended pull request’s `refs/pull/<n>/head`: it is then served under that ref, so a reader who went to another commit and came back by ID, as View file on a diff does, is on the branch or the pull request again. Otherwise a commit that is the tip of any fetched `refs/pull/<n>/head` is served under it, the highest number when it heads several, which makes that pull request the attended one. In a server, a selection the mirror lacks answers `selection_pending` (202) with `refresh` and the status, and starts one background fetch; asked again after it ends, it switches, answers 404, or answers `selection_fetch_failed` (502) when that fetch did not run. `--api` never fetches for it, so the transcripts pin the 404; the 202 path is asserted by `tests/test_source_refresh.py` |
| `/api/kpress/render`, `/api/kpress/export` | Document rendering and export. On a `GitRevisionSubject`, render reads a `GitPath` blob, uses the object id as the cache key, and passes the GitPath wire as `source_path`; export stays mutation-gated and unavailable. With active content off (every served mirror, and a folder served with `--untrusted`), render answers the HTML reduced to the inert allowlist of `src/metabrowser/inert_html.py`, with GitHub’s `user-content-` heading anchors, marks it `inert`, and keeps only stylesheets in its assets; KPress’s table of contents leaves the HTML, `toc` says whether KPress drew one, and the model’s `headings` point at the anchors |
| `/api/plugin/<plugin>/<route>` | Plugin data hooks (`[[data_hook]]`). On a `GitRevisionSubject`, diff document/children, binary chunk, structured parsed, and agent-log charts honor `GitPath` and follow in-tree relative symlink blobs using the leaf kind |
| `/raw`, `/raw/<path>` | Bounded raw bytes through the active source’s content reader, and the document the sandboxed html Preview frames; oversized content is refused before an unbounded object read. Both shapes share one resolver and send the same sandbox headers; the path form exists so relative references inside a browsed document resolve. A Git subject reads blobs by `GitPath` and follows in-tree relative symlink blobs. Image blobs use an image media type from the leaf display name. LFS pointers are stored pointer bytes; a missing blob is 404. On a Git subject only the query form answers: the path form’s one consumer, the HTML preview frame, is never offered under the forced untrusted profile, so it answers `unsupported_for_subject` (409) rather than a 404 that would misreport a present file, and Markdown images resolve to `GitPath` wires through the query form |
| `/kpress-static/<path>`, `/static/<path>`, `/plugin-static/<plugin>/<path>` | Shell, renderer, and plugin assets |
| `/_debug/tasks`, `/_debug/inventory` | Opt-in local task and inventory-provider diagnostics when `METABROWSER_DEBUG=1` |

Plugin hooks currently registered: `diff/document`, `diff/children`, `diff/comparison`,
`folder/*`, `binary/chunk`, `agent-log/charts`, `structured/parsed`, and `github/*`. On
a `GitRevisionSubject`, `diff/comparison` honors the pin through `GitLocation` and
`GitDiffSource.content` reads blobs through the shared cat-file pool; patch
`document`/`children`, `binary/chunk`, `structured/parsed`, and `agent-log/charts` honor
`GitPath` and follow in-tree relative symlink blobs.
`diff/comparison?left=&right=` takes `base_policy=direct` (the default) or `merge_base`,
and reports it in the document.

On a page that shows a pinned revision, the diff view’s file bars offer **View file** at
each side of a change that exists, for a commit’s diff and a pull request’s Changes.
For a commit’s diff it adds no route.
The comparison document already says everything it needs: `resolved.left` and
`resolved.right` are the two commits (the parent and the commit, or the merge base and
the head), and each change’s `old` and `new` are the path at each and its `entry_type`,
so a deleted file has only its old side, an added file only its new side, and a renamed
file’s old side is its old path.
Only a regular file’s side is offered: a submodule’s side is a commit of another
repository, and a symbolic link’s would open its target, not the link text the diff
shows. A file at a commit is its `/view/` address while the server’s pin is that commit.
A side at the commit the page shows is therefore a link to that address, which the
browser follows, and a side at any other commit is a button that sends
`POST /api/source/pin` with the commit ID and the address and goes to the answer’s
`view_href`, as the ref selector does.
There is no address for a file at a commit the server does not serve, so those sides
have no link to copy.
A switch the server does not make (`selection_pending`, `selection_not_found`,
`selection_fetch_failed`, or any other refusal) is said under the file bar and the page
stays.
A patch file’s snapshots are not commits and a served folder’s page has no pin, so
neither carries the control on a commit’s diff: its working-tree file is not that file.

A pull request’s Changes never switches the pin, on a mirror or beside a checkout.
Its comparison carries the envelope’s `snapshot_route`, the `GET github/pull-snapshot`
address of that base and head, and the diff plugin appends only `side` and `path`; it
names no GitHub route of its own.
Its `rendered_route` is likewise the server’s, to which the plugin appends only `file`.
A side at the commit a pinned page shows keeps its `/view/` link, so the file opens in
the app’s own viewer.
Every other side is a link to its revision page, including both sides beside a checkout,
whose page has no pin and which then imports `/static/git-path.js` on demand.
A side whose commit is not the end the route itself names has no control, and a route
that is not a same-origin plugin route gives no revision links while the diff still
shows.

Back and forward bring a pin’s page back without asking the server for it, from the
back/forward cache or the HTTP cache, so after a pin switch the page can name a commit
the server no longer serves.
The page stays cacheable, and `static/source-pin-guard.js` handles the landing instead:
on a restore from the back/forward cache, or a load whose navigation type is
`back_forward`, it asks `/api/source/status` once and reloads if another commit is
served, at most once, and a data request refused as `pin_changed` meanwhile reloads at
once. A reload is not a history landing, so it cannot loop, and a page that stayed open
while another tab switched is left to the freshness row’s offer.
A landing on an unchanged pin costs one status request and keeps its scroll position;
`explorations/history-landing/README.md` records the measurement in Chrome.

`github/pull?number=<n>` answers any pull request’s cached record from the cache alone,
and the number is required: `absent` (with `not_github` on a server with no GitHub
repository, or `not_cached`, `schema_mismatch`, or `unreadable`), `pending` (no record
yet, and a refresh is running), `current`, or `stale`, plus the pin and the ref it came
from (`pin_ref`), `refreshing`, how its last refresh ended (`last_refresh`), and
`comparison_route`, the `github/pull-comparison` of the record’s merge-base endpoints.
The record is checked against the catalog’s row of its number, by the same source and
reader: it is `current` while a scan within the window, or the next one running for at
most `SCAN_GRACE_S` past it, has not seen it change, and `stale` when the row is newer
or names another head at the same time, with `head_moved` when the row names another
head; otherwise the one-minute window decides.
An open pull request’s record read longer ago than the window is `stale` though the
catalog vouches for it, since `updated_at` does not move for checks, statuses, or
mergeability; its automatic refresh reads those alone.
`verified_at` is the newest moment it was known to describe GitHub’s pull request and
`verified_by` says how (`catalog` or `fetch`); `checks_pending` says its checks,
statuses, or mergeability are still settling, for the page to say.
`cli-github-pulls-prefetch.txt` pins each verdict.
The entity tag leaves out `verified_at` and `verified_by`, which move with every scan;
`x-metabrowser-verified: <verified_by> <verified_at>` carries them on a `200` and a
`304` alike, followed by ` scanning` on a catalog verdict while the next scan runs,
which the page polls fast for.
That route names a cached pull request and requires two full commit IDs with
`merge_base`, then forwards to the diff comparison implementation with the PR’s prepared
manifest. It acquires nothing; its build and store parameters identify the same answer
for the page’s prefetch, mount, and deferred-file reads.
The pin is the served commit and can differ from the record’s head: a pull request
opened from a branch moves no pin, a commit URL inside the pull request pins that
commit, and a refresh can find a newer head than the pin.
A record is fetched only by a refresh.
`POST github/pull-refresh` with `{"number": n}` starts or joins that refresh in the
refresh coordinator and answers `202` at once, naming `github/pull?number=<n>` as its
`status_route`, which a one-shot `--api` prints after the refresh ends, exiting 1 when
it failed; it is a POST with a JSON object body for the same reason
`/api/source/refresh` is, and plugin data routes are one path segment, hence the name.
On a served checkout, `{"number": n, "retry": true, "comparison": true}` also acquires
the store its Files changed needs.
The page sends it once when **Changes** opens at its own address on a record without a
store, and shows progress only while that request is on its way or still to be sent.
Because `retry` bypasses the server’s window, the page itself holds that request after a
recorded failure newer than the record that another attempt would repeat (the store’s
acquisition, or an origin that cannot be read), and until a rate limit’s `reset_at`,
when the page reads again and asks.
**Retry changes** overrides a hold.
A Pulls-tab file walk that will settle on Changes, at a file the route can address,
shows progress until its address moves there; the route’s confirmation, too, wakes the
page at a hold’s lift.
Changes shown while the address names another tab, as a cancelled walk leaves it, sends
nothing and offers **Fetch changes**. Neither button is shown while another refresh of
the page is on its way.
`comparison: true` without `retry: true` is refused.
Acquisition leaves the source folder and its pin unchanged, and a request joining a
metadata refresh retains the comparison action for that job.
The comparison request prepares the cached record without reading GitHub only while that
record is current, was read by the account this server observed, and has no failed
refresh recorded since; otherwise it refreshes the record first, as before.
It writes a refresh stamp only when it fails.
On a checkout whose store is already attached,
`{"number": n, "prepare_comparison": "<record_revision>"}` asks for that exact cached
record’s comparison as optional work.
It stands alone: no other field may accompany it.
It starts only while no other pull job of the checkout runs, the record is current and
was written with no store, and its revision is the one named, and otherwise answers
`200` with `refresh: "not_due"`. It fetches only the pull request’s head and base, never
deepens a shallow store, holds no network slot, and records no outcome; a failed
revision is not tried again.
While it runs, the envelope carries `"preparing_comparison": true`, and the page polls
at the slow rate on Conversation.
A reader’s comparison request for the same pull request promotes it: a failure is then
the reader’s, without a second fetch, and a merge base that needs deepening is deepened.
A metadata refresh of it, automatic or not, cancels the idle part, and a refresh of
another pull request cancels it.
The page sends it once per record revision, from a visible Conversation at its own
address, after `REFRESH_ASK_MS` and an idle callback, and only for a `stale` envelope of
a fresh record without a store, which only a server with a store answers.
For an explicitly selected missing record, `retry: true` may include `wait_core: true`,
which is refused with comparison or recovery arguments.
The POST waits at most two seconds for a verified core or terminal outcome; one waiter
per PR may hold this lease, and cancelling or timing out the waiter leaves the producer
running. An ephemeral `core_preview` contains the validated header and description,
reader, source, observed time and content revision.
Discussion and checks remain pending, and comparison is `pending` for a managed store or
`no_store` for a metadata-only checkout.
It is never a synthetic full record.
For an initially missing selected record, a GraphQL core names its actual response
viewer, which must match the initial account check before the preview is staged.
The existing five part reads then overlap; the final account and Git-head checks still
guard full publication.
Detected account changes, source binding changes, head retries, failure or cancellation
revoke the preview. Existing full-record refreshes retain conditional REST reads.
A core obtained through GraphQL carries no invented REST ETag: its first later REST
refresh reads the core and stores its ETag, and subsequent refreshes may answer 304. GET
reads cache and memory only, captures the preview on the event loop, and rejects a
revoked snapshot after the bounded worker read.
The entity tag carries preview identity and removal as well as full-record identity.
Existing full records take precedence.
Batch preparation also persists lightweight cores separately from full records.
The existing GET can serve an identity-validated core after the preparation window ends
or the server restarts, while the full discussion remains absent.
A ready `github/pull-cores-prepare` receipt includes `ready_numbers` and
`skipped_numbers`; a partial receipt also names `retry_numbers` and `retry_at`. Failed
batches and source holds include a failure outcome and reset time.
See
[lightweight cores](arch-repository-sources-and-provider-mirrors.md#lightweight-pull-request-cores)
for cache identity, stale display, publication, and retry rules.
A page that started a selected refresh may give the displayed preview’s revision in
`GET github/pull?number=<n>&wait_full_after=<revision>`. If that exact preview is still
pending and the full record is absent, one request can wait up to 900 ms for completion
or revocation.
The wait shares the POST’s single lease, holds no network slot, and cannot
cancel or start provider work.
The route reads a fresh envelope before applying normal ETag handling.
A pin claim is checked again after the wait, using the same `pin_changed` refusal as
other data reads. A waiting read spends part of the regular poll interval; the client
counts that interval from the read’s start.

The envelope’s `comparison_route` names `GET github/pull-comparison` with the pull
number, immutable endpoints, and build and store tokens.
This route reads only the managed store and uses the diff plugin’s comparison service;
it never acquires one.
The envelope’s `rendered_route` names `GET github/pull-rendered-diff` for the same
endpoints and store token; a page appends `file`, one manifest file ID, and `prefetch=1`
on a request it sends before the reader asks, which also starts the projection process.
After the same admission check as `github/pull-snapshot` it answers `markdown-diff-v1`
(`diff/markdown_projection.py`): `ready` with rendered blocks, each `context`, `removed`
or `added` with changed words marked and a `source_only` flag when its source says more
than its render, and the file’s own `source_only`; or `unsupported` or `too_large` with
no blocks. Refusals have their own codes: `invalid_rendered_diff` (400),
`snapshot_expired` (410), `snapshot_unavailable` and `rendered_objects_unavailable`
(409), and `rendered_diff_busy` (429) past four loads waiting for its one projection at
a time. Projections run in one child process once it is ready
(`diff/markdown_projection_worker.py`), which stops after ten idle minutes, and the
answers of the last 32 files are kept.
The page loads `diff-markdown.js` beside the comparison and falls back to the source
diff when a projection is unsupported or over budget.
The envelope’s `snapshot_route` names `GET github/pull-snapshot` for the same endpoints
and store token; a page appends `side` and `path`. It opens a full file from the exact
displayed base or head without changing the served pin or checkout, and never fetches.
A pair opens when it is the local record’s current comparison, or one of the 16 most
recent earlier pairs retained in `<n>.snapshots.json` for the record’s reader and for
the store that computed it (see
[Repository Sources](arch-repository-sources-and-provider-mirrors.md)). A Markdown
document of at most 64 KiB renders inert, its code blocks unhighlighted, while its
estimated render work is within 400 ms (`_DOCUMENT_WORK_MS` in `pull_snapshot.py`, which
records the measurement), one render at a time per server, with its relative links and
up to 64 images in the same Git tree and the rest as links; otherwise, and for Source,
it opens in 2 MiB windows that end on a line or a character.
The page applies the reader’s theme, interface font, reading font, and reading width
with the shell’s own first-paint scripts and the width default they read, allowed by
hash, and runs no other script.
A Markdown document sits in the in-app inert render’s KPress frame, which carries the
width and reading font to its text, and gets its prose classes on the server
(`inert_html.kpress_prose`, the browser’s `kpressProse`), so tables and code blocks are
styled as in the app.
A `<details>` chevron is the shell’s glyph served from this origin, since the page
admits no `data:` image.
Each outcome has its own code: `snapshot_expired` (410) for a pair not admitted,
`snapshot_unavailable` (409) when admission cannot be decided now,
`snapshot_objects_unavailable` (409) and `snapshot_objects_expired` (410) for objects
the store lacks on the current or an earlier pair, `file_not_found` and `not_a_file`
(404), `invalid_snapshot` (400), `download_too_large` (413), `unsupported_image` (415),
and `invalid_offset` (416). A request with `"retry": true` is a reader’s own action, a
press of **Fetch**, **Refresh**, **Retry changes**, or **Fetch changes**, or the one
comparison request a page on **Changes** sends by itself for a record without a store.
Only those can add a pull request to the cache.
Any other is the page’s own, sent when it is visible and its record is stale: with no
record it answers `200` with `refresh: "not_cached"`, inside the window or before a rate
limit’s `reset_at` it answers `200` with `not_due`, and each starts nothing.
Past `MAX_PULL_JOBS` queued or running, a request is refused `429` with `refresh` and
`code` of `too_many`, and starts nothing; the attended pull request may run one over.
`github/pull` carries `record_revision`, a content identity for the validated record,
and sends an entity tag over the envelope without repeating the record body in the tag
input.
The revision is a SHA-256 digest of the record excluding `fetched_at` and provider
`etags`; it is reused with the parsed record while the cached file is unchanged.
A matching `If-None-Match` answers `304`. Refresh time describes freshness, while the
revision distinguishes changed content even when two refreshes have the same timestamp.
`diff/comparison` on a store, for a request whose endpoints are all full commit IDs,
sends an entity tag that names the build and the store, answers a matching
`If-None-Match` with `304` once the store is known to hold the commits, and keeps its
manifest and its encoded answer in memory, so a repeat whose answer is kept runs no Git,
and one otherwise, a deferred file among them, runs one path-limited diff.
A request that also names this build with `&build=` and this store with `&store=`, as
`window.METABROWSER_SETTINGS.BUILD_TAG` and `STORE_TAG` give them to the diff plugin,
which spells the address for its own requests and for the pull-request page’s prefetch,
is `immutable`, so the browser’s Back makes no request at all; with either missing or
different it is `no-cache`, because a browser’s copy has to meet an upgrade, and because
the browser’s cache is keyed by the address, which has to name the subject or one
store’s answer would stand for another’s, or for a folder’s, on the same origin.
A folder’s comparison, and a request naming a ref, carries neither header and keeps
nothing, and a folder’s page has no `STORE_TAG`. A store’s reads see no attributes but
the store’s own `info/attributes`: not the reader’s files, and not the `.gitattributes`
of any commit, since Git 2.43 reads a bare repository’s from `HEAD` and 2.50 reads none,
so the attributes source is pinned to the store’s empty tree and the same two commits
answer the same on every Git the floor admits.
A folder’s comparison honors its working tree’s `.gitattributes`, its
`.git/info/attributes`, and the reader’s own attributes files and configuration, diff
drivers among them, as `git diff` in that folder would: a folder is the reader’s, and
its answer is not kept.
`builtin_plugins/diff/comparison_cache.py` says what an answer depends on besides the
two commit IDs, and `cli-diff-comparison-cache.txt` pins each case.
`github/pull-markdown?number=<n>&part=<part>` renders one text of the cached record
through KPress in its sanitized mode and answers the resulting HTML, with the same
parsed record’s `record_revision`, its `fetched_at`, and the part: `body`, or
`issue_comment/<id>`, `review/<id>`, or `review_comment/<id>`. It also answers the
manifest of KPress’s stylesheets, the same for every text, so the page sets a text in
the rules a Markdown file reads under.
The page accepts a reply only for its current record revision and text selection, and
checks that ownership again after awaiting stylesheets.
Superseded work cannot publish HTML or populate the current text cache.
A timestamp-only refresh keeps the rendered text and its cached Markdown.
It never fetches; a part the record lacks is `unknown_part`. KPress keeps what a
document of its own may use, so the hook reduces that HTML to an allowlist
(`src/metabrowser/inert_html.py`, with links made absolute against the pull request’s
page): plain text markup (paragraphs, headings, emphasis, code, quotes, lists, tables,
details, `div`, `span`) with no attributes but a link’s `href` (http or https, absolute
against the pull request’s github.com page, in a new tab), `ol[start]`, a table cell’s
`colspan`, `rowspan`, and `align`, and `details[open]`. Scripts, styles, SVG, MathML,
media, frames, forms, and stylesheets go with their content; an image becomes a link to
it; any other tag is unwrapped to its text.
KPress’s asset list is not sent, so no script KPress adds for a text’s content loads.
The page applies the same allowlist again, rebuilding the nodes it inserts.
See
[Pull-request records](arch-repository-sources-and-provider-mirrors.md#pull-request-records).

`POST github/pull-timeline` accepts `number` and the visible pull record’s
`record_revision`. It returns the revision, a `complete`, `partial`, or `unavailable`
state, and ordered commit, comment, and review identifiers.
Commit events carry a subject and optional commit date.
Discussion IDs are decimal strings.
The browser asks after the selected Conversation paints; its first paint waits for no
projection. A projection that answers after that paint moves nothing painted: its new
commit rows go after everything the Conversation shows, in its order.
A later first paint with the projection held, such as the Conversation shown again after
another tab, places its commit rows among the discussion cards.
During metadata refresh it can set `cached_only: true` to read the held projection.
Provider work uses a separate slot after that refresh settles.
A transient provider failure can return a verified prefix with `retryable: true`. The
active Conversation can retry once.
The bounded projection has its own cache entry.

`github/pulls?state=&limit=&after=` reads an indexed window of the served repository’s
metadata catalog. `state` is `open` by default, `closed` (including merged), or `all`.
The envelope is `absent` (`not_github` or `not_cached`), `pending`, `current`, or
`stale`, with the labelled `reader`, `refreshing`, and `last_refresh`. `total` and
`repository_total` are GitHub’s selected-filter and all-PR counts, nullable before a
page arrives. `filter_totals` carries the open, closed, and all counts from the same
checkpoint, or null before one is available.
`count_at` dates the counts.
`fetched` and `catalog_fetched` count cached matching and all rows independently.
`complete` means the all-PR backfill reached its end; `truncated` says a row field was
bounded.

`rows` is newest first by number, with at most `limit` rows (default 100, maximum 1,000,
zero for status alone), below `after`. `next_after` continues cached rows only.
Each row carries `head_oid`, the head commit GitHub reported with it, which records and
changed-files lists are checked against, or null for a row written before the catalog
read heads.
A per-filter `generation` changes when existing content or the leading prefix
changes; older appends and count-only changes preserve it.
A client replaces a held window only after it has collected that window under one
source, reader, and generation.
The ETag covers the bounded envelope and rows.
GET opens SQLite read-only and runs neither Git nor `gh`.

`POST github/pulls-refresh` takes `state`, `target` (default 500), and `retry`. It
starts or joins one repository catalog job, returning `202` with a filter-specific
`status_route`; the one-shot CLI waits for its outcome.
`target` prioritizes a display prefix, while background work continues through all
lightweight metadata.
A higher target on a complete, fresh catalog needs no provider request.
Joining a job updates its requested filter and target; an explicit retry is retained
until the worker consumes it.
Automatic refresh waits one freshness window after completion or failure.
Explicit retry checks changed metadata even while fresh, but neither bypasses a known
`rate_limited` reset.
A held request returns `200` with `refresh: "not_due"`. Unknown fields or invalid values
return `invalid_request` (400); no GitHub repository returns `not_github` (409). See
[Lists of pull requests](arch-repository-sources-and-provider-mirrors.md#lists-of-pull-requests).

`POST github/cache-clear` takes an empty JSON object and discards everything the plugin
caches for the served repository: the catalog, records, changed-file lists, timelines,
previews, the stack snapshot, and every refresh outcome, each fetched again when next
wanted. The source and its Git store stay.
It answers `200` with `cleared`, the number of files removed, and `source`; a cache that
refuses answers `cache_unwritable` (409) with why, and no GitHub repository `not_github`
(409). It holds the source’s alias lock, which every writer of those files takes.
The `cache_unwritable` message of the pull-request list, a record, a changed-file list,
the lightweight previews, or stack metadata, and the list’s `newer_cache` and
`unknown_cache`, name this route as the command to paste:
`echo '{}' | metab <address> --api /api/plugin/github/cache-clear --data -`, with
`metab .` in a checkout instead, where the address would clone a repository that has no
store.

`POST github/pull-cores-prepare` takes `state`, `window` with its `id` and catalog
`generation`, and at most eight `numbers` per transport batch.
A started or joined preparation returns `202` with a cache-only `status_route`. Other
outcomes return `200`: `ready`, `partial`, `busy`, `not_owner`, `released`, `failed`, or
`held`. A ready response lists `ready_numbers` and `skipped_numbers`, covering the batch
with validated cores or readable full records.
A partial response adds `retry_numbers` and `retry_at`; its three disjoint member lists
cover the batch while callers continue later cohorts and defer unfinished members.
A failed owner batch and later source holds carry `failure` with `outcome`, `message`,
and optional `reset_at`. An empty `numbers` list releases only the window matching its
state, ID, and generation; it retains useful persisted metadata.

Admission checks the exact cohort and generation.
Each publication rechecks its indexed fingerprint under the same source, reader,
repository, and catalog epoch, so a change to another row does not discard a stable
description. The 256-entry transient attempt budget governs outstanding cooldowns, and
successful durable writes release their entries.
It does not limit total prepared coverage.
A prepared description appears in the pull envelope as a reader-labelled `core_preview`
with its original observation time and `comparison_state: "not_started"`. It remains
readable after the freshness window or a process restart.
Selecting a pull with no complete record starts its own acquisition.

`GET github/stacks` reads one optional repository stack snapshot with no query
parameters. Its envelope has `state` (`absent`, `current`, `stale`), `reason`, `source`,
`reader`, `fetched_at`, remaining `fresh_for_s`, `refreshing`, `last_refresh`,
`complete`, and `stacks`. Each stack has its native `number`, `base_ref`, `open`, and
ordered bottom-to-top PR numbers in `pulls`. Only matching source/reader membership
enriches a PR. An incomplete snapshot supports positive membership only.
The entity tag excludes the ticking freshness countdown; expiry still changes `state`
and the tag. `POST github/stacks-refresh` accepts only optional boolean `retry`, and
returns `refresh`, `stacks`, and `status_route`; `202` starts/joins a job and `200` is
`not_due`. GET remains cache-only.
Optional failure retains known metadata without changing core PR/catalog outcomes.
See
[optional native stack metadata](arch-repository-sources-and-provider-mirrors.md#optional-native-stack-metadata).

`GET github/pull-files?number=<n>&offset=&limit=` answers one pull request’s changed
files from the cache alone, with the same `state` values.
A list is from the local comparison (`listed_from: "comparison"`, current while the
record’s head is its `head`) when the store holds both of the record’s comparison
commits, and otherwise from GitHub’s list (`"github"`, current while the `head` and
`base_ref` it names, observed before its first page, are the pull request’s as last
known from the newer of its record and cached list row; a list or source that names no
head is current while the pull request’s `updated_at` is no newer than `fetched_at`, or
within the window when neither knows).
A GitHub list read for a head that has since moved is due again at once after a success.
`fetched` is the rows held; `complete` is false while GitHub’s list fills or after it
stopped part-way, `last_page` is the page count GitHub’s `Link` gave, `capped` says
GitHub stopped at its 3,000 files, and `truncated` that an item was left out.
A row keeps `path`, its identity, `previous_path`, GitHub’s `status`, and the line
counts, with `display` and `previous_display` through the pinned tree’s display rule;
`rows` is the window from `offset`, all by default and none with `limit=0`. The
envelope’s `generation` identifies one admitted logical refresh and is shared by all of
its progressive publications; it is null when no list is held.
A held tree that receives a different generation rereads from offset zero; more rows
under the same generation extend that tree.
`fetched_at` remains freshness data.
The entity tag covers everything but the rows, including generation and progress.
`POST github/pull-files-refresh` with `{"number": n, "retry": false}` starts or joins
that list’s refresh and answers `202`, naming `github/pull-files` with `limit=0` as its
`status_route`. GitHub’s pages are published progressively after checking that the
active account still matches the list’s reader, never as fewer rows than the file holds.
The complete list receives the same account check; a held list is reread conditionally.
An observed account change stops publication and marks previously checked prefixes
stale. `"retry": true` is a reader’s own action; any other request starts a list that is
not held, not complete, or stale, and not tried within the window.
Past `rate_limited` nothing reads GitHub until `reset_at`, though the local comparison
may still list. A request held answers `not_due` with `200`. A file-list job takes no
turn at the store and holds a network slot for each `gh` request alone; past
`MAX_PULL_JOBS` of them queued or running, a request is refused 429 `too_many`. If
source admission refuses the application cache, `last_refresh` still reports
`cache_unwritable` and automatic retries back off in bounded server memory.
That rejected worker starts no GitHub request and attempts no lock, directory creation,
or file write in the refused home.
The envelope keeps the newest refresh outcome and message independently of the strongest
active provider reset deadline, so an older shared hold cannot hide a newer refusal or
shorten the network backoff.
Workers admitted before the refusal can still publish later; admission does not drain
those jobs. This fallback does not promise persistence across server restarts or memory
eviction. See
[Changed files of a pull request](arch-repository-sources-and-provider-mirrors.md#changed-files-of-a-pull-request).

`POST github/pulls-prefetch` takes `records` and `files`, each at most 16 distinct
pull-request numbers in a visible page’s order of priority, and `changed`, which adds
the numbers this server most recently answered `github/pull` for.
It replaces the repository’s background lane queue and starts or joins the lane, `202`
with `prefetch: "started"` or `"joined"` and `github/pulls-prefetch` as its
`status_route`; `200` with `"not_due"` when nothing was named, or `"deferred"` with a
`reason` (`below_floor` or `rate_hold`) when the rate-limit governor admits no
background work. The lane runs one item at a time and reads each again before it runs: a
record that is missing (named only) or that the catalog says changed, and a files list
the files route would refresh automatically.
It stops at the governor, at 8 record refreshes per catalog publication or 40 an hour,
at 20 GitHub file lists an hour, or when a reader’s job preempts its job, which gives
its place in the caps back; it does not stop merely because a reader’s work runs, which
it cannot delay. `GET github/pulls-prefetch` reports the lane from server memory:
`running`, `queued`, the `records` and `files` caps with their use, the `governor`
(`floor`, `admits`, `reason`, `held_until`, and each resource `observed` from GitHub’s
rate-limit headers), and the outcomes of the last 16 items (`recent`). A background job
takes no network slot, waits at a store turn behind every other job and is cancelled
when one starts waiting, and a reader’s request for its pull request joins and promotes
it. `cli-github-pulls-prefetch.txt` pins a run that refreshes, skips, and defers, with
the `gh` calls each made.
See
[Background prefetch](arch-repository-sources-and-provider-mirrors.md#background-prefetch-and-the-rate-limit-governor).

### Planned plugin registration surfaces

Browser and route declarations are additive installed-plugin capabilities only if
existing SDK 0.7 manifests and JavaScript calls keep their signatures and behavior.
They still require plugin-author documentation and a changelog entry.
An existing browser-contract change instead bumps `PLUGIN_SDK_VERSION` and every
built-in manifest in one commit, with no compatibility layer.
The thin-mirror plan retired the router, address-space, provider-adapter, resource-kind,
and nav-panel declarations for the alpha; their rows remain as design background.

| Declaration or SDK call | Owns | Arbitration and lifecycle | Bead |
| --- | --- | --- | --- |
| `SourceSession` / `SourceCapabilities`; `resolve_content`, `resolve_content_container`, `stat_content`, `read_content_window` | One active subject generation and opaque bounded content access | Every read takes an explicit byte maximum and there is no unbounded variant; failures share one catchable family with a `code` and the `http_status` the pinned routes answer with. Session replacement joins the old generation; legacy `Path` helpers and hooks run only with `filesystem_path`; absent semantics return typed unsupported states. `InventoryCoordinator.open_subject` accepts a `GitRevisionSubject` without a filesystem walk. `metab file://… --show`, non-cache `--api`, and `--check-api` open that pin in-process, and an `https://` or GitHub URL opens the commit it selects; serve mode opens it through the application lifespan, in the serving event loop, and closes it at shutdown. `POST /api/source/pin` replaces it within one mirror: the new subject is attached under a new generation, then the old one is closed, and a request still reading the old pin finishes on the store’s shared readers | `mb-3bna`, `mb-tsdc`, `mb-z335` |
| `RouterSpec` | Mounted HTTP prefix and trusted router factory | Reserved/duplicate prefixes fail; application lifespan awaits shutdown | `mb-xzj3` |
| `AddressSpaceSpec` / `registerAddressSpace` | Browser prefix, parse, format, apply, preview claim, startup, popstate, root replacement, disposal | Exactly one owner per address; browser and `metab --show` share the registration | `mb-6mle` |
| `ProviderUrlReducerSpec` | Declared schemes/hosts and `NotApplicable`/`Reduced`/terminal `Rejected` reducer | Overlapping claims fail discovery; claimed rejection never falls through. Superseded for the alpha by the thin-mirror plan: the built-in GitHub reducer reaches `classify_root_argument(reducers=)` through `cache/providers.py`, with no public declaration | `mb-12cz` |
| `ProviderAdapterSpec` | Provider/instance capability and trusted adapter factory | Duplicate claims fail; lifespan injects neutral ports and awaits cancellation/close | `mb-ji83` |
| `ResourceKindSpec` | Route-backed semantic kind, item/container capabilities, primary contract, and views | Duplicate kind or view claims fail; route, browser, and CLI resolve the same selection | `mb-83w0` before `mb-81p5` |
| `registerNavPanel` | Repository-scoped bounded virtual collection | Generation-checked loading, restoration, root replacement, and disposal | `mb-uh6p` |
| `shortcuts.attach(element, spec)` (SDK 0.7, additive) | A plugin view control’s letter key, its Help entry, and its Shift badge | Malformed input throws `shortcuts.attach:`; a letter in the reserved table that `METABROWSER_SETTINGS` serves from `keymap.py` is refused with one warning per id. Each letter is one command in the registry’s permanent `plugin` scope, below every shell key; a live shell key beats a plugin key and the earlier plugin attachment beats a later one, at dispatch and in the reveal. `plugin-sdk.js` queues attachments until `static/plugin-shortcuts.js` loads with `shell-tools` and replays them onto each registry the shell attaches; an attachment ends by its handle, its abort signal, or view composition disposing its container | `mb-v4u1` |

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
| `/api/file` | covered | `--show PATH`, `--api` | `cli-show.tryscript.md`, `cli-api.tryscript.md`, `cli-api-hidden-folder.tryscript.md` |
| `/api/tree` | covered | `--walk`, `--api` | `cli-api.tryscript.md` |
| `/api/rollup` | covered | `--api` | `cli-api-nav.tryscript.md`, `cli-api-file-type-legend.tryscript.md` |
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
| `/api/cache/stores` | covered | `--api` | `cli-api-cache.tryscript.md`, `cli-checkout-overlay.tryscript.md`, `cli-checkout-overlay.txt` |
| `/api/identity` | covered | `--api` | `cli-api-shell.tryscript.md`, `cli-api-source.tryscript.md`, `cli-github-pull.tryscript.md` |
| `/api/source/status` | covered | `--api` | `cli-api-shell.tryscript.md`, `cli-api-source.tryscript.md`, `cli-checkout-overlay.tryscript.md`, `cli-checkout-overlay.txt` |
| `/api/source/refresh` | covered | `--api --data` | `cli-api-source.tryscript.md`, `cli-api-shell.tryscript.md` |
| `/api/source/pin` | covered | `--api --data` | `cli-api-source.tryscript.md`, `cli-api-shell.tryscript.md`, `cli-api-diff-view-file.tryscript.md` |
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
| `/api/plugin/diff/children` | covered | `--api` | `cli-api-plugins.tryscript.md`, `cli-api-diff-no-hunks.tryscript.md` |
| `/api/plugin/diff/comparison` | covered | `--api` | `cli-api-plugins.tryscript.md`, `cli-api-git.tryscript.md`, `cli-github-pull.tryscript.md`, `cli-api-diff-view-file.tryscript.md`, `cli-api-diff-no-hunks.tryscript.md`, `cli-checkout-overlay.txt` |
| `/api/plugin/github/pull` | covered | `--api` | `cli-github-pull.tryscript.md`, `cli-checkout-overlay.txt`, `cli-github-pulls-prefetch.txt` |
| `/api/plugin/github/pull-refresh` | covered | `--api` | `cli-github-pull.tryscript.md`, `cli-github-pull-refresh.txt`, `cli-github-checkout-idle.txt` |
| `/api/plugin/github/pull-markdown` | covered | `--api` | `cli-github-pull.tryscript.md` |
| `/api/plugin/github/pull-timeline` | covered | `--api --data` | `cli-github-pull-timeline.txt` |
| `/api/plugin/github/pull-snapshot` | covered | `--api` | `cli-github-pull-snapshot.txt` |
| `/api/plugin/github/pull-rendered-diff` | covered | `--api` | `cli-github-pull-rendered.txt` |
| `/api/plugin/github/pull-comparison` | covered | `--api` | `cli-github-pull.tryscript.md`, `cli-github-checkout.txt` |
| `/api/plugin/github/pulls` | covered | `--api` | `cli-github-pulls.tryscript.md`, `cli-github-pulls-refresh.txt` |
| `/api/plugin/github/pulls-refresh` | covered | `--api` | `cli-github-pulls.tryscript.md`, `cli-github-pulls-refresh.txt`, `cli-github-pulls-failures.txt` |
| `/api/plugin/github/pull-cores-prepare` | covered | `--api` | `cli-github-pulls-refresh.txt` |
| `/api/plugin/github/stacks` | covered | `--api` | `cli-github-stacks.txt` |
| `/api/plugin/github/stacks-refresh` | covered | `--api` | `cli-github-stacks.txt` |
| `/api/plugin/github/pull-files` | covered | `--api` | `cli-github-pull-files.tryscript.md`, `cli-github-pull-files-refresh.txt` |
| `/api/plugin/github/pull-files-refresh` | covered | `--api` | `cli-github-pull-files.tryscript.md`, `cli-github-pull-files-refresh.txt`, `cli-github-pull-files-failures.txt` |
| `/api/plugin/github/pulls-prefetch` | covered | `--api` | `cli-github-pulls-prefetch.txt` |
| `/api/plugin/github/cache-clear` | covered | `--api --data` | `cli-github-pulls-refresh.txt`, `cli-github-pulls-failures.txt` |
| `/api/plugin/structured/parsed` | covered | `--api` | `cli-api-plugins.tryscript.md` |
| `/view` | covered | `--show PATH`, `--show /view/...` | `cli-show.tryscript.md` |
| `/commit` | covered | `--show /commit/<rev>[/<inner>]` | `cli-api-git.tryscript.md` |
| `/pull` | covered | `--show /pull/<n>[/files[/<path>] or /checks]` | `cli-github-pull.tryscript.md`, `cli-github-pull-files.tryscript.md` |
| `/pulls` | covered | `--show /pulls` | `cli-github-pulls.tryscript.md` |
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
writers, and each command names its home with a leading
`METABROWSER_CACHE_DIR=$PWD/<home>` assignment, because tryscript frontmatter cannot
name the sandbox path.
`check_parity.py` skips leading environment assignments and nothing else, so the command
must still be `metab`. Sessions that write the cache through `--no-serve` — acquisition,
reuse, interruption recovery, fetch failure, and refusal — also read state through these
routes, but they run in-process as `.txt` goldens from
`tests/test_cli_cache_acquire_golden.py` and `tests/test_cli_cache_recovery_golden.py`,
with the acquisition floor substituted, because a transcript must pass on a Git the
floor refuses. The rows do not name those goldens, so `check_parity.py` does not count
those sessions as the rows’ evidence.

What these routes answer on a Git pin is pinned the same way, one transcript per
scenario, by `tests/test_cli_git_pin_golden.py`: `cli-git-pin-index.txt` holds
`/api/index/progress`, `/api/index/meta`, `/api/capabilities`, `/api/source/status`, and
`--check-api`; `cli-git-pin-tree.txt` holds `/api/tree`; `cli-git-pin-rollup.txt` holds
`/api/rollup` and `/api/catalog`; `cli-git-pin-files.txt` holds `/api/file`,
`/api/plugin/structured/parsed`, and `/api/plugin/binary/chunk`;
`cli-git-pin-refusals.txt` holds each refusal `--api` can reach, `/api/recent` among
them; and `cli-git-pin-show.txt` holds `/view` through `--show`. Its docstring says why
they stay in-process.
They are evidence a reader can check, and the rows do not name them, so the gate does
not count them.

A command is successful evidence for a route when it exits 0. A row may name an
in-process `.txt` golden as well as a tryscript transcript, and `check_parity.py`
applies the same exact-route and exit-status rules to its `# command` and `exit:` lines.
`check_goldens.py` fails a `.txt` golden that no test compares, and the harness’s
`block` refuses output holding those lines, so what a command printed cannot read as a
command that ran. `/api/plugin/github/pull-refresh` needs this: a refresh that completes
needs `gh` and a fetch from the origin, and a subprocess transcript has neither.
`cli-github-pull-refresh.txt` records
`metab …/pull/7 --api /api/plugin/github/pull-refresh --data reader.json` exiting 0,
with the `202`, the `current` record after it, and the `gh` calls it made.
`cli-github-pull.tryscript.md` pins the same route with no `gh`: the `202`, the
`gh_failed` status after it, and the exit status 1.
`cli-ui-github-pull-page.tryscript.md` replays the route’s recorded answers through a
refresh that completes.
`/api/plugin/github/pulls-refresh` is the same: `cli-github-pulls-refresh.txt` records
refreshes that complete with the `gh` calls each made, `cli-github-pulls-failures.txt`
each typed failure, and `cli-github-pulls.tryscript.md` the same route with no `gh`.
`/api/plugin/github/pull-files-refresh` is too: `cli-github-pull-files-refresh.txt`
records lists that complete, from GitHub’s pages and from the local comparison, and a
force-push; `cli-github-pull-files-failures.txt` each typed failure and a list that
stopped part-way; and `cli-github-pull-files.tryscript.md` the route with no `gh`.

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
| `navigation.route-identity` | interaction | `static/navigation.js#href`, `static/navigation.js#parse`, `static/navigation.js#commitHref`, `static/navigation.js#parseCommit`, `static/pull-route.js#pullHref`, `static/pull-route.js#parsePull`, `static/navigation.js#displayPath` | `/api/file`, `/api/plugin/diff/comparison` | `node tests/dom/navigation-route-behavior.js` | `cli-ui-navigation.tryscript.md` |
| `navigation.served-source-kind` | interaction | `static/plugin-sdk.js#sourceKind`, `static/navigation.js#displayPath` | `/view`, `/api/tree` | `node tests/dom/source-kind-session.js` | `cli-ui-source-kind.tryscript.md` |
| `source.pinned-revision` | data | `/api/source/status` | `owned-route` | `metab shellroot --api /api/source/status` | `cli-api-shell.tryscript.md` |
| `shell.window-title` | data | `/api/identity` | `owned-route` | `metab shellroot --api /api/identity` | `cli-api-shell.tryscript.md` |
| `shell.page-connections` | interaction | `static/navigation.js#createPageConnections` | `/api/catalog`, `transport-exempt:/api/events` | `node tests/dom/page-connections-session.js` | `cli-ui-page-connections.tryscript.md` |
| `shell.key-reveal` | interaction | `static/key-reveal.js#createKeyReveal`, `static/keyboard-shortcuts.js#attachTarget`, `static/shell-keymap.js#createShellKeymap` | `/api/file`, `/api/git/repo`, `/api/source/status` | `node tests/dom/key-reveal-session.js` | `cli-ui-key-reveal.tryscript.md` |
| `navigation.failed-expanded-folder-recovery` | interaction | `static/navigation.js#recoverFailedExpandedFolders` | `/api/tree`, `transport-exempt:/api/events` | `node tests/dom/page-reconnect-behavior.js` | `cli-ui-page-connections.tryscript.md` |
| `source.mirror-heading` | interaction | `static/mirror-heading.js#note`, `static/mirror-heading.js#tip`, `static/mirror-heading.js#mountCommitCopy` | `/view`, `/api/source/status` | `node tests/dom/mirror-heading-session.js` | `cli-ui-mirror-heading.tryscript.md` |
| `source.mirror-freshness` | interaction | `static/source-freshness.js#createController`, `static/source-freshness.js#describe` | `/api/source/status`, `/api/source/refresh` | `node tests/dom/source-freshness-session.js` | `cli-ui-source-freshness.tryscript.md` |
| `source.selection-arrival` | interaction | `static/source-freshness.js#selectionToOpen`, `static/source-freshness.js#describe`, `static/source-freshness.js#createController` | `/api/source/status`, `/api/source/refresh` | `node tests/dom/source-freshness-session.js` | `cli-ui-source-freshness.tryscript.md` |
| `source.newer-revision-offer` | interaction | `static/source-freshness.js#describe`, `static/source-freshness.js#acceptOffer` | `/api/source/status`, `/api/source/pin` | `node tests/dom/source-freshness-session.js` | `cli-ui-source-freshness.tryscript.md` |
| `source.history-landing` | interaction | `static/source-pin-guard.js#createHistoryGuard`, `static/source-pin-guard.js#servesAnother` | `/api/source/status`, `/api/tree` | `node tests/dom/source-freshness-session.js` | `cli-ui-source-freshness.tryscript.md` |
| `source.stale-pin-guard` | interaction | `static/source-pin-guard.js#guardFetch`, `static/source-pin-guard.js#guardedRequest` | `/api/file`, `/api/tree`, `/api/source/status` | `node tests/dom/source-freshness-session.js` | `cli-ui-source-freshness.tryscript.md` |
| `source.ref-selector` | interaction | `static/source-ref-selector.js#createSelector`, `static/source-ref-selector.js#describe`, `static/source-ref-selector.js#moveRow` | `/api/source/refs`, `/api/source/pin` | `node tests/dom/source-ref-selector-session.js` | `cli-ui-source-ref-selector.tryscript.md` |
| `git.commit-history-landing` | interaction | `static/git-panel.js#restoreCommitLanding`, `static/git-panel.js#selectCommit`, `static/navigation.js#createController` | `/api/git/repo`, `/api/git/commit` | `node tests/dom/git-commit-history-session.js` | `cli-ui-git-commit-history.tryscript.md` |
| `git.history-stale-cursor` | interaction | `static/git-history-window.js#classifyPageFailure` | `/api/git/log` | `node tests/dom/source-freshness-session.js` | `cli-ui-source-freshness.tryscript.md` |
| `git.unfetched-commit` | interaction | `static/source-freshness.js#openMissingCommit`, `static/source-freshness.js#describeMissingCommit`, `static/source-freshness.js#fetchMissing` | `/api/git/commit`, `/api/source/status`, `/api/source/refresh` | `node tests/dom/source-freshness-session.js` | `cli-ui-source-freshness.tryscript.md` |
| `github.pull-page` | interaction | `builtin_plugins/github/pull-page.js#describePull`, `builtin_plugins/github/pull-page.js#hunkView`, `builtin_plugins/github/pull-page.js#tintOnFirstOpen`, `builtin_plugins/github/pull-page.js#createPullController` | `/api/plugin/github/pull`, `/api/plugin/github/pull-refresh`, `/api/plugin/github/pull-markdown`, `/api/source/pin` | `node tests/dom/github-pull-page-session.js` | `cli-ui-github-pull-page.tryscript.md` |
| `github.pull-timeline-data` | data | `/api/plugin/github/pull-timeline` | `owned-route` | `metab https://github.com/octo/demo/pull/7 --api /api/plugin/github/pull-timeline --data timeline.json` | `cli-github-pull-timeline.txt` |
| `github.pull-checks-tab` | interaction | `builtin_plugins/github/pull-page.js#mountPullPage` | `/api/plugin/github/pull` | `node tests/dom/github-pull-page-mount-behavior.js` | `cli-ui-github-pull-page.tryscript.md` |
| `github.pull-page-tab-keys` | interaction | `builtin_plugins/github/pull-page.js#attachTabKeys` | `/api/plugin/github/pull` | `node tests/dom/github-pull-page-mount-behavior.js` | `cli-ui-github-pull-page.tryscript.md` |
| `github.pull-timeline` | interaction | `builtin_plugins/github/pull-page.js#mountPullPage` | `/api/plugin/github/pull-timeline` | `node tests/dom/github-pull-timeline-session.js` | `cli-ui-github-pull-page.tryscript.md` |
| `github.selected-core-preview` | interaction | `builtin_plugins/github/pull-page.js#describePull`, `builtin_plugins/github/pull-page.js#createPullController` | `/api/plugin/github/pull`, `/api/plugin/github/pull-refresh` | `node tests/dom/github-pull-core-preview-behavior.js` | `cli-ui-github-pull-page.tryscript.md` |
| `github.checkout-comparison-fetch` | interaction | `builtin_plugins/github/pull-page.js#createPullController`, `builtin_plugins/github/pull-page.js#describePull` | `/api/plugin/github/pull`, `/api/plugin/github/pull-refresh` | `node tests/dom/github-checkout-comparison-session.js` | `cli-ui-github-checkout-comparison.tryscript.md` |
| `github.idle-comparison-preparation` | interaction | `builtin_plugins/github/pull-page.js#createPullController` | `/api/plugin/github/pull`, `/api/plugin/github/pull-refresh` | `node tests/dom/github-pull-idle-comparison-behavior.js` | `cli-ui-github-checkout-comparison.tryscript.md` |
| `github.displayed-comparison-repair` | interaction | `builtin_plugins/github/pull-page.js#mountPullPage`, `builtin_plugins/github/pull-page.js#createPullController` | `/api/plugin/github/pull`, `/api/plugin/github/pull-refresh` | `node tests/dom/github-pull-page-mount-behavior.js` | `cli-ui-github-pull-page.tryscript.md` |
| `github.pull-prefetch` | interaction | `builtin_plugins/github/comparison-prefetch.js#createComparisonPrefetch` | `/api/plugin/diff/comparison` | `node tests/dom/github-pull-prefetch-session.js` | `cli-ui-github-pull-prefetch.tryscript.md` |
| `github.pull-page-inert-markup` | interaction | `static/inert-html.js#sanitizeNodes`, `static/inert-html.js#allowedAttributes`, `static/inert-html.js#imageLink`, `builtin_plugins/github/pull-page.js#safeLink`, `builtin_plugins/github/pull-page.js#gitPathWire` | `/api/plugin/github/pull-markdown` | `node tests/dom/github-pull-page-session.js` | `cli-ui-github-pull-page.tryscript.md` |
| `source.checkout-overlay` | data | `/api/source/status` | `owned-route` | `metab --cache-dir home --config-dir config https://github.com/octo/demo/pull/1 --api /api/source/status` | `cli-checkout-overlay.tryscript.md` |
| `cache.store-borrowing` | data | `/api/cache/stores` | `owned-route` | `metab --cache-dir home --config-dir config root --api /api/cache/stores` | `cli-checkout-overlay.tryscript.md` |
| `github.pull-base-uncertain` | data | `/api/plugin/github/pull` | `owned-route` | `metab --cache-dir home-shallow --config-dir config https://github.com/octo/demo/pull/1 --api '/api/plugin/github/pull?number=1'` | `cli-checkout-overlay.tryscript.md` |
| `github.pull-page-paint-decisions` | interaction | `builtin_plugins/github/pull-page.js#conversationAction`, `builtin_plugins/github/pull-page.js#conversationKey`, `builtin_plugins/github/pull-page.js#filesAction`, `builtin_plugins/github/pull-page.js#filesUnavailableText` | `/api/plugin/github/pull` | `node tests/dom/github-pull-page-second-session.js` | `cli-ui-github-pull-page.tryscript.md` |
| `github.pull-page-place` | interaction | `builtin_plugins/github/pull-page.js#createScrollKeeper`, `builtin_plugins/github/pull-page.js#placeAt`, `builtin_plugins/github/pull-page.js#scrollTopOf`, `builtin_plugins/github/pull-page.js#keyMovesPane` | `local-only` | `node tests/dom/github-pull-page-second-session.js` | `cli-ui-github-pull-page.tryscript.md` |
| `diff.layout-fit` | interaction | `builtin_plugins/diff/diff-view.js#tooNarrowForSplit`, `builtin_plugins/diff/diff-view.js#opensTooNarrowForSplit`, `builtin_plugins/diff/diff-view.js#drawnLayout`, `builtin_plugins/diff/diff-view.js#setLayout`, `builtin_plugins/diff/diff-view.js#mountDiffView` | `local-only` | `node tests/dom/diff-layout-fit-session.js` | `cli-ui-diff-layout-fit.tryscript.md` |
| `diff.layout-key` | interaction | `builtin_plugins/diff/diff-view.js#toggleLayout`, `builtin_plugins/diff/diff-view.js#setLayout` | `local-only` | `node tests/dom/diff-layout-fit-session.js` | `cli-ui-diff-layout-fit.tryscript.md` |
| `diff.file-jump` | interaction | `builtin_plugins/diff/diff-view.js#jumpToFile`, `builtin_plugins/diff/diff-view.js#jumpPlacement`, `builtin_plugins/diff/diff-view.js#reservedRows`, `builtin_plugins/diff/diff-view.js#failDeferred`, `builtin_plugins/diff/diff-view.js#observeHydration`, `builtin_plugins/diff/diff-view.js#createHydrationScheduler`, `builtin_plugins/diff/diff-view.js#patchRows`, `builtin_plugins/diff/diff-view.js#firstScreenBudget` | `/api/plugin/diff/comparison` | `node tests/dom/diff-file-jump-session.js` | `cli-ui-diff-file-jump.tryscript.md` |
| `diff.view-file-sides` | data | `/api/plugin/diff/comparison` | `owned-route` | `metab changesroot --api '/api/plugin/diff/comparison?revision=6ac4c8b5eb94eecbdb621d629b31066f050c75f1&file=src/new_name.py'` | `cli-api-diff-view-file.tryscript.md` |
| `diff.view-file` | interaction | `builtin_plugins/diff/diff-view-file.js#viewFileSides`, `builtin_plugins/diff/diff-view-file.js#sidePathForAddress`, `builtin_plugins/diff/diff-view-file.js#describeViewFile`, `builtin_plugins/diff/diff-view-file.js#createViewFileOpener`, `builtin_plugins/diff/diff-view-file.js#switchRefusal`, `builtin_plugins/diff/diff-view.js#renderViewFileControl`, `builtin_plugins/diff/index.js#viewFileHost`, `builtin_plugins/diff/index.js#viewFileOpener`, `builtin_plugins/diff/index.js#snapshotHost`, `static/git-path.js#gitPathWire` | `/api/plugin/diff/comparison`, `/api/plugin/diff/document`, `/api/source/pin`, `/api/plugin/github/pull-comparison`, `/api/plugin/github/pull-snapshot` | `node tests/dom/diff-view-file-session.js` | `cli-ui-diff-view-file.tryscript.md` |
| `github.pull-rendered-diff` | data | `/api/plugin/github/pull-rendered-diff` | `owned-route` | `metab <PATH>/pull/7 --api '/api/plugin/github/pull-rendered-diff?number=7&left=f92fd713acd521d4ebb62fb9f345ec927b8b6d1b&right=33e7810f4188efa2734a80a37188f67877ace69d&store=<STORE>&file=f3'` | `cli-github-pull-rendered.txt` |
| `diff.markdown-rendered-view` | interaction | `builtin_plugins/diff/diff-markdown.js#createMarkdownViews`, `builtin_plugins/diff/diff-markdown.js#supportsMarkdownChange`, `builtin_plugins/diff/diff-markdown.js#firstScreenMarkdown`, `builtin_plugins/diff/diff-markdown.js#snapshotTargets`, `builtin_plugins/diff/diff-markdown.js#sanitizeBlock`, `builtin_plugins/diff/diff-markdown.js#appendBlocks` | `/api/plugin/github/pull-rendered-diff`, `/api/plugin/github/pull-snapshot` | `node tests/dom/diff-markdown-session.js` | `cli-ui-diff-markdown.tryscript.md` |
| `navigation.pull-page-history` | interaction | `static/pull-route.js#pullHistoryAction`, `static/pull-route.js#createPullPageHost`, `static/pull-route.js#parsePulls`, `static/pull-route.js#pullsHref` | `local-only` | `node tests/dom/navigation-route-behavior.js` | `cli-ui-navigation.tryscript.md` |
| `navigation.main-tab-destinations` | interaction | `static/main-tabs.js#openMainTab`, `static/main-tabs.js#bindShortcuts`, `static/navigation.js#createController` | `local-only` | `node tests/dom/preview-pane-state-session.js` | `cli-ui-file-lifecycle.tryscript.md` |
| `navigation.tree-key-walk` | interaction | `static/tree-keyboard-navigation.js#createWalk` | `local-only` | `node tests/dom/preview-pane-state-session.js` | `cli-ui-file-lifecycle.tryscript.md` |
| `navigation.quick-search-pulls` | interaction | `static/search-controller.js#createPullProvider`, `static/search-palette.js#create` | `/api/plugin/github/pulls`, `/api/plugin/github/pulls-refresh` | `node tests/dom/quick-search-pulls-session.js` | `cli-ui-quick-search.tryscript.md` |
| `navigation.quick-search-pull-landing` | interaction | `static/pull-route.js#createPullPageHost` | local-only | `node tests/dom/preview-pane-state-session.js` | `cli-ui-file-lifecycle.tryscript.md` |
| `github.pulls-tab-host` | interaction | `static/pulls-nav.js#createPullsNav`, `static/pulls-nav.js#tabForAddress`, `static/pulls-nav.js#pullAddress`, `static/pulls-nav.js#registerKeys` | `local-only` | `node tests/dom/pulls-nav-session.js` | `cli-ui-pulls-nav.tryscript.md` |
| `github.pulls-panel` | interaction | `builtin_plugins/github/pulls-panel.js#describePulls`, `builtin_plugins/github/pulls-panel.js#describeRow`, `builtin_plugins/github/pulls-panel.js#refreshFailure`, `builtin_plugins/github/pulls-panel.js#createPullsController`, `builtin_plugins/github/pull-state.js#displayState`, `static/plugin-sdk-views.js#mergeRefs` | `/api/plugin/github/pulls`, `/api/plugin/github/pulls-refresh`, `/api/plugin/github/pull` | `node tests/dom/github-pulls-panel-session.js` | `cli-ui-github-pulls-panel.tryscript.md` |
| `github.pulls-watch` | interaction | `builtin_plugins/github/pulls-panel.js#createPullsController` | `/api/plugin/github/pulls`, `/api/plugin/github/pulls-refresh` | `node tests/dom/github-pulls-catalog-behavior.js` | `cli-ui-github-pulls-panel.tryscript.md` |
| `github.background-freshness` | interaction | `builtin_plugins/github/pulls-panel.js#createPullsController`, `builtin_plugins/github/pull-page.js#createPullController`, `builtin_plugins/github/pull-page.js#describePull` | `/api/plugin/github/pulls`, `/api/plugin/github/pulls-prefetch`, `/api/plugin/github/pulls-refresh`, `/api/plugin/github/pull`, `/api/plugin/github/pull-refresh` | `node tests/dom/github-pulls-prefetch-behavior.js` | `cli-ui-github-pulls-prefetch.tryscript.md` |
| `github.visible-core-window` | interaction | `builtin_plugins/github/pulls-panel.js#mountPullsPanel` | `/api/plugin/github/pulls`, `/api/plugin/github/pull-cores-prepare`, `/api/plugin/github/pull` | `node tests/dom/github-pulls-viewport-behavior.js` | `cli-ui-github-pulls-panel.tryscript.md` |
| `github.pulls-file-selection` | interaction | `builtin_plugins/github/pulls-panel.js#mountPullsPanel` | `/api/plugin/github/pulls`, `/api/plugin/github/pull-files` | `node tests/dom/github-pulls-file-selection-session.js` | `cli-ui-github-pulls-panel.tryscript.md` |
| `github.native-stack-ui` | interaction | `builtin_plugins/github/pull-stacks.js#createStackController`, `builtin_plugins/github/pull-stacks.js#createStackIndex`, `builtin_plugins/github/pull-stacks.js#stackMembership`, `builtin_plugins/github/pull-stacks.js#memberRoute` | `/api/plugin/github/stacks`, `/api/plugin/github/stacks-refresh` | `node tests/dom/github-pull-stacks-behavior.js` | `cli-ui-github-pulls-panel.tryscript.md` |
| `github.pull-stack-loading` | interaction | `builtin_plugins/github/pull-page.js#mountPullPage` | `/api/plugin/github/pull`, `/api/plugin/github/stacks` | `node tests/dom/github-pull-stack-mount-behavior.js` | `cli-ui-github-pulls-panel.tryscript.md` |
| `github.pull-files-tree` | interaction | `builtin_plugins/github/pull-files-tree.js#buildFileTree`, `builtin_plugins/github/pull-files-tree.js#visibleRows`, `builtin_plugins/github/pull-files-tree.js#initialExpansion`, `builtin_plugins/github/pull-files-tree.js#toggleFolder`, `builtin_plugins/github/pull-files-tree.js#revealPath`, `builtin_plugins/github/pull-files-tree.js#holdFileList`, `builtin_plugins/github/pull-files-tree.js#describeFileList`, `builtin_plugins/github/pull-files-tree.js#createFileTreeController`, `builtin_plugins/github/pull-files-tree.js#createRowExpansion`, `builtin_plugins/github/pull-files-tree.js#windowRange`, `builtin_plugins/github/pull-files-tree.js#describeFileTree` | `/api/plugin/github/pull-files`, `/api/plugin/github/pull-files-refresh` | `node tests/dom/github-pull-files-tree-session.js` | `cli-ui-github-pull-files-tree.tryscript.md` |
| `github.pulls-reader-fetch` | interaction | `builtin_plugins/github/pull-page.js#createPullController`, `builtin_plugins/github/pull-page.js#describePull` | `/api/plugin/github/pull`, `/api/plugin/github/pull-refresh` | `node tests/dom/github-pulls-panel-session.js` | `cli-ui-github-pulls-panel.tryscript.md` |
| `github.selection-first-read` | interaction | `builtin_plugins/github/pulls-panel.js#createPullsController`, `builtin_plugins/github/pull-page.js#createPullController` | `/api/plugin/github/pull` | `node tests/dom/github-pull-selection-read-behavior.js` | `cli-ui-github-pulls-panel.tryscript.md` |
| `github.conversation-first-paint` | interaction | `builtin_plugins/github/pull-page.js#mountPullPage`, `builtin_plugins/github/pull-page.js#rememberRendered`, `builtin_plugins/github/pull-page.js#renderedText`, `builtin_plugins/github/pull-state.js#noteListed`, `builtin_plugins/github/pull-state.js#withListedState` | `/api/plugin/github/pull`, `/api/plugin/github/pull-markdown` | `node tests/dom/github-pull-first-paint-behavior.js` | `cli-ui-github-pull-page.tryscript.md` |
| `github.pull-files-opening` | interaction | `builtin_plugins/github/pull-files-tree.js#createFileTreeController`, `builtin_plugins/github/pull-files-tree.js#describeFileTree` | `/api/plugin/github/pull-files`, `/api/plugin/github/pull-files-refresh` | `node tests/dom/github-pull-files-opening-behavior.js` | `cli-ui-github-pull-files-tree.tryscript.md` |
| `assets.on-demand-load-recovery` | interaction | `static/asset-loader.js#ensureAsset`, `static/asset-loader.js#ensureScript` | `local-only` | `node tests/dom/asset-loader-behavior.js` | `cli-ui-navigation.tryscript.md` |
| `links.external-github` | interaction | `static/plugin-sdk-views.js#decorateExternalLink` | `local-only` | `node tests/dom/external-links-session.js` | `cli-ui-external-links.tryscript.md` |
| `plugins.view-helpers-before-plugin-code` | interaction | `static/plugin-sdk.js#loadPluginsForKind`, `static/plugin-sdk.js#_ensureViewHelpers`, `static/plugin-sdk.js#_startPluginAssets`, `static/plugin-sdk-views.js#renderSourceView`, `static/asset-loader.js#ensureAsset` | `local-only` | `node tests/dom/plugin-view-helpers-session.js` | `cli-ui-plugin-view-helpers.tryscript.md` |
| `plugins.shortcut-surface` | interaction | `static/plugin-shortcuts.js#attachShortcut`, `static/plugin-shortcuts.js#attachShortcutRegistry` | `local-only` | `node tests/dom/plugin-shortcuts-session.js` | `cli-ui-plugin-shortcuts.tryscript.md` |
| `source.incremental-cache-transaction` | interaction | `static/source-append.js#requestOwnsPreview`, `static/source-append.js#commitChunkCache` | `/api/file` | `node tests/dom/source-append-navigation-session.js` | `cli-ui-file-lifecycle.tryscript.md` |
| `source.line-anchors` | interaction | `static/plugin-sdk-views.js#describe`, `static/plugin-sdk-views.js#nextFragment`, `static/plugin-sdk-views.js#keyStep`, `static/plugin-sdk-views.js#preferredView`, `static/plugin-sdk-views.js#mount`, `static/plugin-sdk-views.js#refresh`, `static/plugin-sdk-views.js#renderSourceView`, `builtin_plugins/markdown/source.js#renderMarkdownSource` | `/api/file` | `node tests/dom/source-line-anchors-session.js` | `cli-ui-source-line-anchors.tryscript.md` |
| `agent-log.event-row-controls` | interaction | `builtin_plugins/agent_log/index.js#renderLogEventHtml`, `builtin_plugins/agent_log/index.js#renderLog`, `builtin_plugins/agent_log/index.js#toggleFromKey` | `/api/file` | `node tests/dom/log-event-row-session.js` | `cli-ui-log-event-rows.tryscript.md` |
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
| `markdown.untrusted-inert-render` | interaction | `static/inert-html.js#sanitizeNodes`, `static/inert-html.js#kpressProse`, `static/inert-html.js#allowedAttributes`, `static/inert-html.js#keepsImage`, `builtin_plugins/markdown/inert-render.js#isInertRender` | `/api/kpress/render` | `node tests/dom/inert-html-session.js` | `cli-ui-inert-markdown.tryscript.md` |
| `markdown.untrusted-inert-toc` | interaction | `builtin_plugins/markdown/inert-toc.js#inertTocEntries`, `builtin_plugins/markdown/inert-toc.js#buildInertToc`, `builtin_plugins/markdown/inert-toc.js#wireInertToc`, `builtin_plugins/markdown/inert-render.js#placeRendered`, `builtin_plugins/markdown/inert-render.js#inertArticle` | `/api/kpress/render` | `node tests/dom/markdown-inert-toc-session.js` | `cli-ui-inert-toc.tryscript.md` |
| `markdown.aggregate-root-budget` | interaction | `builtin_plugins/markdown/reconciliation-coordinator.js#createMarkdownEnhancementBudget`, `builtin_plugins/markdown/dom-traversal.js#matchingDescendants`, `builtin_plugins/markdown/link-enhancer.js#enhanceRenderedLinks` | `/api/catalog`, `/api/kpress/render` | `node tests/dom/markdown-functional-session.js` | `cli-ui-markdown-functional.tryscript.md` |
| `image.raw-preview` | interaction | `static/view-composition.js#createLifecycle`, `builtin_plugins/image/index.js#renderImage` | `/api/file` | `node tests/dom/image-preview-session.js` | `cli-ui-image-preview.tryscript.md` |
| `html.sandboxed-preview` | interaction | `static/view-composition.js#createLifecycle`, `builtin_plugins/html/index.js#renderPreview` | `/api/file` | `node tests/dom/html-preview-session.js` | `cli-ui-html-preview.tryscript.md` |
| `html.full-page-escape` | interaction | `builtin_plugins/html/index.js#createFullPageBar` | `/api/file` | `node tests/dom/html-preview-session.js` | `cli-ui-html-preview.tryscript.md` |
| `document.reading-width` | interaction | `static/document-width.js#apply` | `local-only` | `node tests/dom/document-width-session.js` | `cli-ui-document-width.tryscript.md` |
| `folder.file-overview-states` | interaction | `builtin_plugins/folder/file-overview-panel.js#mountFileOverviewPanel`, `builtin_plugins/folder/file-type-summary.js#mountFileTypeSummary`, `builtin_plugins/folder/folder-totals.js#mountFolderTotalsView`, `builtin_plugins/folder/file-type-summary-model.js#buildFileTypeSummaryModel`, `builtin_plugins/folder/distribution-view.js#updateDistributionView` | `/api/rollup` | `node tests/dom/file-overview-session.js` | `cli-ui-file-overview.tryscript.md` |
| `folder.file-type-legend` | data | `/api/rollup` | `owned-route` | `metab legendroot --api '/api/rollup?path=.&depth=0'` | `cli-api-file-type-legend.tryscript.md` |
| `folder.file-overview-details` | interaction | `builtin_plugins/folder/file-type-summary-model.js#buildFileTypeLegend`, `builtin_plugins/folder/distribution-view.js#updateLegend`, `builtin_plugins/folder/distribution-view.js#toggleDetails`, `builtin_plugins/folder/distribution-view.js#disposeDistributionView` | `/api/rollup` | `node tests/dom/file-overview-session.js` | `cli-ui-file-overview.tryscript.md` |
| `folder.treemap-not-indexed` | interaction | `builtin_plugins/folder/treemap.js#registerTreemap`, `builtin_plugins/folder/folder-totals.js#notIndexedStatement` | `/api/file` | `node tests/dom/treemap-not-indexed-session.js` | `cli-ui-treemap-not-indexed.tryscript.md` |
| `navigation.filter-layout` | paint-exempt | `static/styles.css` | `local-only` | — | CSS geometry and disclosure motion require rendered layout; focused selectors and accessibility state are pinned in `tests/test_browser_filter_ui.py` and `tests/test_tree_keyboard_integration.py` |
| `shell.reserved-chrome` | paint-exempt | `static/styles.css` | `local-only` | — | Whether a region keeps its box when its content is absent or arrives late is layout: line heights, struts, and gutters in a real engine. Which rows and slots exist in every state, the Pulls lines, and the File Overview first-paint hold are browserless in `tests/dom/github-pull-page-mount-behavior.js`, `tests/dom/github-pulls-panel-session.js`, and `tests/dom/file-overview-session.js`; the rules that size them are pinned in `tests/test_reserved_chrome.py`; the heights themselves are judged in a browser |
| `document.floating-ui-frame` | paint-exempt | `static/styles.css` | `local-only` | — | Where the `position: fixed` TOC drawer, its toggle, and its backdrop land while the preview pane scrolls is browser layout, and the repository has no browser harness to measure it. `tests/test_preview_frame_contract.py` pins by stylesheet text what places them: the shell wraps the scrolling `#preview-pane` in a non-scrolling `.preview-frame.kpress-frame` that declares a transform, and no rule in the shell’s, a built-in plugin’s, or KPress’s stylesheet gives the pane or an element between it and the TOC a property that makes a containing block for fixed descendants. Computed styles and rules a script adds are not checked. That the toggle stays in view at any scroll depth, in a trusted folder and a served mirror, is step 5 of section 5.9 of the v0.12 QA runbook |
| `diff.layout-fit-browser` | paint-exempt | `builtin_plugins/diff/styles.css` | `local-only` | — | At what width Split’s columns overflow a file’s body is layout, and when a `ResizeObserver` reports a width is the browser’s. Which layout each width draws is a session owner above (`diff.layout-fit`). The width measured in Chrome is recorded beside `SPLIT_MIN_WIDTH_EM` in `builtin_plugins/diff/diff-view.js`, and `tests/test_diff_browser_js.py` pins that constant to the `min-width` in the stylesheet |
| `diff.view-file-browser` | paint-exempt | `builtin_plugins/diff/styles.css` | `local-only` | — | What the browser does with a View file link is the browser’s: following it, opening it in a new tab, and copying its address. Where the controls sit in the bar, and that their text shares the path’s baseline, is layout. Every decision they act on is a session owner above (`diff.view-file`): which sides a bar offers, each link’s address, a pull request’s revision-page links and that its Changes never switches the pin, and that no handler takes a link’s click. `tests/test_diff_view_file_session.py` asks Git whether each address the session offers, a revision page’s included, is a file at its commit, and `tests/test_design_vocabulary.py` pins the size that puts the text on the baseline; the browser walkthrough is section 5.11 of the v0.12 QA runbook |
| `source.mirror-heading-layout` | paint-exempt | `static/styles.css` | `local-only` | — | Which part of a heading gives up its width as a pane narrows, that the note is whole or absent and takes nothing from the address, where it and the commit’s copy control sit, that a long name is cut at its end in both headings, and how a tooltip wraps a path and a commit ID are layout, which needs a rendered page. So is where any tooltip lands: only a mirror’s line of one wraps, and a folder’s tooltips are placed as before. What the headings and tooltips say, and what the copy control copies, is a session owner above (`source.mirror-heading`), and the name, origin, and location are `/api/source/status`. `tests/test_browser_client_filestore.py` pins by stylesheet text what orders it: the note’s zero flex basis, its margin against the breadcrumb’s gap, the basis its text must fit, the direction a mirror’s name is cut in, and that the one tooltip every page uses declares nothing about wrapping. The widths measured in Chrome, for a mirror’s heading and for a folder’s tooltips against the branch below, are recorded beside the note’s rule and the tooltip’s in `static/styles.css` |
| `shell.page-connections-browser` | paint-exempt | `static/navigation.js` | `local-only` | — | Whether a browser keeps a page for Back, the `persisted` it reports on `pagehide` and `pageshow`, how long it keeps a kept page’s open requests, and how many connections it opens to a host are the browser’s. The decision made on them is a session owner above (`shell.page-connections`), and `tests/test_page_connections_session.py` holds each behavior of it. `explorations/page-connections/README.md` records the Chrome run: before, the sixth page opened in a tab waited 55 to 56 s for a connection and a page left for a minute was loaded again on Back; after, no request waited behind an event stream, and every landing was restored with `persisted` true at its scroll position |
| `source.line-pitch` | paint-exempt | `static/styles.css` | `local-only` | — | How tall a line of a Source view is drawn is layout: the line height the browser gives the code’s box, which is the parent’s for an inline box in a block and the box’s own for a block. Code that is not highlighted, which is a file or a loaded window past the highlight bound, is drawn 21px to a line at the default sizes, as it was before the gutter made it a grid item, and highlighted code 18px; the gutter’s numbers take the line height of the code beside them. `tests/test_source_line_anchors.py` pins by stylesheet text the one property both columns take their line height from and the rule that sets it to the `<pre>`’s for unhighlighted code, and `tests/dom/syntax-token-sdk-behavior.js` pins that the production renderer writes the class that rule selects on unhighlighted code and on no other. Computed styles are not checked. The heights measured in Chrome against 0.11.0, and the rounding that differs under zoom, are recorded beside the rule in `static/styles.css` |
| `source.history-landing-browser` | paint-exempt | `static/source-pin-guard.js` | `local-only` | — | Whether Back restores a page from the back/forward cache or loads it again, when `pageshow` fires and with what `persisted`, the navigation type a document reports, and what a reload fetches are the browser’s. The decision made on them is a session owner above (`source.history-landing`), which also loads the module as the server writes it into a page. `tests/test_source_freshness_session.py` pins the statuses that decision reads against a real server, and `explorations/history-landing/README.md` records the Chrome run: a restore with `persisted` true that keeps its scroll position when nothing switched, and one reload after a switch |
| `github.pull-page-hunk-paint` | paint-exempt | `builtin_plugins/github/styles.css` | `local-only` | — | Opening and closing the native `details` that holds a review comment’s earlier hunk lines, and firing `toggle`, are the browser’s, and how far a line’s tint reaches in a hunk scrolled sideways, and that its label stays put, are layout. Which lines are shown, what each line is, and that a first open makes them a line each, once, are a session owner above (`github.pull-page`). That the tints are the diff view’s, that a hunk’s lines are painted as text, that the disclosure is native, and that one box scrolls all of a hunk are pinned in `tests/test_pull_page_route.py`; how it looks is judged in a browser |
| `github.pull-page-text-spacing` | paint-exempt | `builtin_plugins/github/styles.css` | `local-only` | — | The active system sans’s measured advance and resulting message width, and how much space a text’s paragraphs, headings, lists, code, quotes, tables, and details take in their card, and where a list’s markers fall, is layout: margins collapsing through KPress’s wrappers under the shell’s reset, in a browser’s line boxes, with nothing but the stylesheet’s text for a browserless session to run. Whether a table overflows its text and how it scrolls, and where a long word breaks, are layout too. That every block of the allowlist has a margin, that lists have room for their markers, that a wide table scrolls inside its text, that a long word breaks by the rule that leaves that table scrolling, that the first and last block are trimmed as deep as the Markdown route’s answer nests, and that no selector reaches outside the page are pinned in `tests/test_pull_page_route.py`; how it looks is judged in a browser |
| `github.pull-files-tree-paint` | paint-exempt | `builtin_plugins/github/pull-files-view.js#mountFileTree` | `local-only` | — | DOM geometry, actual focus, and the viewport window need a browser. The exact controller and window calculation run in `github.pull-files-tree`; its session covers keys, progressive windows, retries, selection, and disposal. Chrome 152 measured the production tree on the first 1,183 and all 2,003 filenames of django/django#15387 and 3,000 stress files: 67 rows at the top, 111 mid-list, one tabbable anchor, and a 4.1 ms maximum key update. The keyboard registry and roving anchor are pinned by `tests/test_design_vocabulary.py` and `tests/dom/github-pull-files-tree-session.js`. These are navigation-paint measurements; diff hydration is the diff view’s separate evidence. |
| `github.pulls-panel-paint` | paint-exempt | `builtin_plugins/github/pulls-panel.js#mountPullsPanel`, `builtin_plugins/github/pulls-panel.js#mountPullsLanding`, `builtin_plugins/github/pull-state.js#pullStateIcon` | `local-only` | — | Building the list’s DOM, moving focus, bringing a row into view, what a sticky header covers, truncating a title, an author, or a merge’s branch names and wrapping its line, and when an `IntersectionObserver` says the list’s end is near need a rendered page. Every decision they act on is a session owner above: which rows, marks, and notices (`github.pulls-panel`), which tab and when the view is told (`github.pulls-tab-host`), and what a row’s open asks for (`github.pulls-reader-fetch`). The panel session builds the list in a stand-in for the DOM and pins its tree roles with each row’s place and the list’s size, a title written as markup painted as one text node, an append that builds and keys only the rows it adds, and ages told again as time passes (`tests/dom/github-pulls-panel-session.js`, its `paint`); `tests/test_pulls_nav.py` pins that a folder’s shell draws nothing, and `tests/test_design_vocabulary.py` the design system’s primitives in the markup, among them the rules by which a row’s line wraps so that its merge is always whole (`test_merges_read_source_to_target_in_one_notation`), which was measured and judged in headless Chrome at every pane width from the 180px minimum to 340px, with a five-digit number, a 39-character login, an avatar that loads or fails, a stack badge, and the list’s scrollbar, in both themes. The list at its cap, a held key, and how it looks in both themes were measured and judged in Chrome; the numbers are beside `WINDOW_ROWS` in `builtin_plugins/github/pulls-panel.js` |
| `shell.nav-panel-scroll` | paint-exempt | `static/main-tabs.js#activateNavPanel` | `local-only` | — | The main panels share a scroller. The deferred tab controller keeps each panel’s offset and tells the panel that leaves. `tests/dom/preview-pane-state-session.js` checks that switching saves and restores the offset and notifies the panel that leaves. See `navigation.main-tab-destinations` and `github.pulls-tab-host`. |
| `github.pull-page-paint` | paint-exempt | `builtin_plugins/github/pull-page.js#mountPullPage` | `local-only` | — | Building the page’s DOM, observing which texts scroll into view, reading where a block sits and setting the pane’s scroll, loading the diff plugin and mounting its view, and the shell’s `app.js` callbacks the page host calls (load the plugin, render into the pane, `history.pushState`) need a rendered page. Every decision they act on is a session owner above: what a route, a tab link, the link to the served pull request, or a history landing does to the pane, and which superseded page is disposed (`navigation.pull-page-history`), whether the conversation repaints or asks again and what Files changed keeps (`github.pull-page-paint-decisions`), what of a text’s HTML is inserted (`github.pull-page-inert-markup`), and where a landing puts the pane and for how long (`github.pull-page-place`). The route grammar, the shell and plugin wiring for the `pull-request` kind, that only an inert template is parsed, that a text is asked for one pane ahead of the pane that scrolls, and what a reader’s place is wired to are pinned in `tests/test_pull_page_route.py`; the browser walkthrough is in the v0.12 QA runbook |
| `shell.refreshing-text-motion` | paint-exempt | `static/styles.css` | `local-only` | — | How text that a refresh is checking breathes is paint: the opacity the compositor draws each frame, that it draws it with no style, layout, or paint work on the main thread, and what starting it costs, none of which a browserless session can run. Which text breathes, and which status text is marked `aria-busy`, are decisions pinned browserlessly against the production code: the page’s age line (`github.pull-page`, `github.selected-core-preview`, `github.pull-timeline`) in `tests/dom/github-pull-core-preview-behavior.js`, `tests/dom/github-pull-stack-mount-behavior.js`, and `tests/dom/github-pull-timeline-session.js`; a changed-files tree’s names (`github.pull-files-tree`) in `tests/dom/github-pull-files-focus-behavior.js`, run by `tests/test_github_pull_files_tree_session.py`, and `tests/dom/github-pull-files-tree-session.js`; the Pulls connection row (`github.pulls-panel`, `github.pulls-watch`) in `tests/dom/github-pulls-panel-session.js` and `tests/dom/github-pulls-catalog-behavior.js`; and which Pulls titles breathe — an admitted core batch’s, until it settles, is replaced, or the panel goes offline — and the beat they are aligned to (`github.visible-core-window`) in `tests/dom/github-pulls-viewport-behavior.js`. `tests/test_design_vocabulary.py` pins that the keyframes change opacity alone, after the loading quiet period, with a reduced-motion override, that primary ink keeps 4.5:1 at its dimmest and a muted line rests at muted’s contrast in both themes, that no usable row or tree group is marked busy, and that no pull-request surface says “may be out of date”. The headless Chrome 152 run (no compositing failure; no main-thread style, layout, or paint for 2.7 s while the compositor drew 165 frames; 2.5 ms to start 120 breathing elements) is recorded beside the tokens in `static/styles.css` |
| `shell.key-badge-paint` | paint-exempt | `static/styles.css` | `local-only` | — | Where a badge lands in its target, how much of the label shows through it, whether a scroll container clips it, its contrast as composited in each theme, and that the revealed strip overlays the tree without moving it are layout and paint. Which badges mount, and the strip’s contents, are a session owner above (`shell.key-reveal`). The tokens, the host rule, the reveal-on-hover override, reduced motion, and print are pinned by stylesheet text in `tests/test_design_vocabulary.py` and `tests/test_chrome_typography.py`, which also pin the strip layer’s out-of-flow placement and recompute, from the tokens, the contrast of the reveal’s text on the yellow and over each surface a badge is composited on; the browser walkthrough is in the v0.12 QA runbook |
| `shell.disclosure-toggle-selection` | paint-exempt | `static/styles.css` | `local-only` | — | Whether a click, a double click, or a triple click on a control selects text is the browser’s: its selection engine reading the cascade, which no browserless session has, and the engines read it differently, Chrome honoring `user-select` and WebKit, the macOS app’s engine, only `-webkit-user-select`. `tests/test_design_vocabulary.py` pins the one rule for `.disclosure-toggle` and `summary`, both halves of every `user-select` in a shipped stylesheet, that no stylesheet makes a toggle or anything inside it selectable, though content it reveals beside it may be, that every registered toggle builder carries the class, that every chevron and `summary` a source builds is listed with the builder of the element it goes into, and that any other source that sets `aria-expanded` is registered with why it builds no toggle; it reads source text, so which element a listed chevron lands in is left to review. Real double and triple clicks, in headless Chrome on a folder row and a rendered Markdown diff’s fold and in a `WKWebView` on a folder row and a section trigger, selected nothing, with or without a `mousedown` handler, as [Disclosure Toggles Never Select Text](../../design-system.md#disclosure-toggles-never-select-text) records |

## Adding something

- **A filesystem-backed kind**: add a `[[kind]]` block with a match predicate and at
  least one `[[view]]`, then add a representative `--show` case to the golden
  transcript.
- **A route-backed kind**: declare a `[[view]]` for a kind no `[[kind]]` matches and
  have the shell select it for its route, as the GitHub plugin’s `pull-request` kind
  does for `/pull/<n>`; add the route, its `--api` golden, and its functional rows in
  the same change. Do not invent a file matcher.
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
