# Feature: Archive Contents and Browsing Archives as Folders

**Date:** 2026-11-24

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Draft for the owner’s review.
The [Key Decisions](#key-decisions) carry recommendations the owner has not adopted yet.
The work is tracked under epic `mb-p7ts`, one stack per phase.

## Overview

A `.zip`, `.jar`, `.epub`, `.tar`, or `.tar.gz` opens in Metabrowser today as bytes: no
plugin claims it, so it falls through to the `binary` kind and its Bytes view.
This plan adds a built-in `archive` plugin in two phases:

1. **Contents.** An archive’s own file page lists its members as a tree, with sizes,
   dates, a summary line, and the problems a hostile or damaged archive carries (unsafe
   names, duplicates, links, encrypted members).
2. **Archives as folders.** The navigation tree expands an archive the way it expands a
   directory. Its directories expand in turn, and selecting a member opens it with its
   own kind’s views: a Markdown file renders, an image draws, a CSV is a table, and a
   `.jar` inside a `.zip` expands again.

The plugin claims the ZIP family by its bytes, so every format built on ZIP (`.jar`,
`.war`, `.apk`, `.whl`, `.epub`, `.docx`, `.xlsx`, `.odt`, and others) gets the same
treatment, and the tar family by its bytes or its name, compressed or not.

Everything archive-specific lives in `builtin_plugins/archive/`. Phase 2 needs two
surfaces the plugin framework does not have, and the plan adds them as generic ones:

- **Member sources:** a protocol for a file whose bytes hold other files, so a member
  reaches every route and view through the content reader, as a Git blob does.
- **Folder-like container children:** a container’s child rows can expand, so a
  container can hold a hierarchy.

A table source made “a file of tables” a protocol any plugin implements; a member source
makes “a file of files” one, so a plugin installed later for 7z, ISO images, or Electron
`.asar` files gets the same tree and views.

## Goals

- **Phase 1:** an `archive` kind whose default view, Contents, shows every member as a
  tree with a summary and problem counts, for ZIP-family files whatever their name, tar,
  and tar compressed with gzip, bzip2, or xz; on a served folder and on a Git pin.
- **Phase 2:** archives expand in the tree like folders; a member has an address
  (`/view/app.zip/docs/readme.md`), opens with its own kind’s views, is served by `/raw`
  under the same sandbox as any file, and follows its archive when the archive changes.
- **Safe on hostile input:** no member name ever becomes a path on disk; every read,
  scan, and decompression is bounded by a named, measured constant; and an unsafe name,
  a duplicate, a link, or an unreadable member is shown for what it is rather than
  hidden.
- **Generic surfaces:** member sources and folder-like children are plugin surfaces with
  documentation, doctor checks, and tests, not seams private to the archive plugin.
- **Parity:** every new route has a golden, the Contents view’s and the tree’s new
  states run browserlessly against production JavaScript, and nothing is exempt but
  paint.

## Non-Goals

- **Writing.** Extracting to disk, adding, deleting, or editing members.
  Archives are read-only.
- **Encrypted members.** They are listed and marked; Metabrowser never asks for a
  password.
- **Formats without a standard-library reader.** `.tar.zst` waits for a decision on
  Zstandard (see [Open Questions](#open-questions)); 7z, RAR, ISO, and disk images need
  native libraries, which belong in installed plugins
  ([Plugin System](../../architecture/arch-plugin-system.md#adding-a-file-type)), and
  Phase 2’s member sources are how such a plugin plugs in.
- **Single-file `.bz2` and `.xz`.** They stay on the compression roadmap in `TODO.md`;
  this plan reads bzip2 and xz only as the outer layer of a tar.
- **Indexing members.** Quick Search, the Files filter’s totals, the Overview’s type
  breakdown, and the Treemap count an archive as one file.
- **Comparing archives member by member.** A Git diff of a `.zip` stays a binary change.
- **Serving an archive as the root** (`metab app.zip`). That is the re-rooting proposal
  in
  [Navigation Containers](../../architecture/arch-plugin-system.md#what-stays-uniform),
  which this plan makes easier but does not build.
- **Format-specific readers.** An EPUB reader or an Office document view is its own
  plugin; Phase 1 exports the Contents view so such a plugin can keep it as a tab.
- **ZIP data after a prefix,** such as a self-extracting executable: the magic rule
  needs the ZIP signature at offset 0, so such a file stays binary.

## Background

### What Happens to an Archive Today

- **Classification ends at `binary`.** A NUL byte makes a file binary
  (`content_sniff.py`), and no `magic` or `binary = true` rule names an archive format,
  so a `.zip`, `.jar`, `.epub`, `.tar`, or `.tgz` gets the Bytes view.
  A `.tar.gz` is read through `gz_io.ArtifactPath`, whose logical extension is `.tar`,
  but a compressed file has no magic prefix (`content_sniff.py`), so it reaches
  `_binary_kind` with `.tar` and is `binary` too.
  On a pin `blob_logical_ext` (`git/tree_source.py`) strips nothing, so the same file is
  `.gz` there.
- **`.tgz` is not a compressed name.** `COMPRESSED_SUFFIXES` in `gz_io.py` lists `.gz`
  and `.zlib` only, so a `.tgz` file is read as its gzip bytes.
- **Containers exist, but flat.** A kind with `container = { children = "<route>" }`
  gets a chevron, and its children hook answers
  `{children: [{name, path, badge?, muted?}]}`
  ([Navigation Containers](../../architecture/arch-plugin-system.md#navigation-containers)).
  The tree draws every child as a leaf (`renderContainerChildren` in `static/app.js`),
  reads no pagination, and finds a container by the name’s last suffix only
  (`containerForNode`), so `x.tar.gz` would look up `.gz`. A deep link reveals its row
  by expanding `.tree-folder` rows only, so it never opens a container to reach a child.
- **A container child is always its container’s kind.** `_resolve_container_child` in
  `server.py` returns the container’s kind and views with `container` and
  `container_inner`, and an empty body; the diff and SQLite views draw the child
  themselves. No route reads a child’s bytes: `FilesystemContentSource._open_ref` in
  `source.py` answers nothing for a path that is not a file, `/raw` answers 404, and
  `/api/kpress/render` requires a file on disk.
  The inner path is bounded by `MAX_CONTAINER_INNER_DEPTH` in `source.py`.
- **A binary rule cannot be a container.** `validate_consistency` in
  `plugin_loader/manifest.py` refuses `binary = true` beside `container`, and a magic
  rule never sees a compressed file’s logical bytes, so no rule today can make a
  `.tar.gz` or `.tgz` a container.
- **Random access depends on the subject.** A plain file on a served folder seeks; a
  gzip file is read forward from its start, under `ARTIFACT_MAX_COMPRESSED_BYTES`,
  `ARTIFACT_MAX_DECOMPRESSED_BYTES`, and `ARTIFACT_MAX_CPU_SECONDS` in `gz_io.py`; a Git
  blob streams from its start on every window, and a whole-blob read stops at
  `TEXT_PREVIEW_REQUEST_MAX_BYTES` in `settings.py`. `TableHandle.local_path`
  (`table_source.py`) is the precedent for handing a reader the real file a served
  folder has.
- **Watches follow files.** A container’s rows follow its file (`followContainer` in
  `static/file-watches.js`), and a change to a file nudges a watch on any
  `<file>/<inner>` beneath it (`_touches` in `file_watches.py`), but a path that is
  neither a file nor a table source’s has no generation, so a watch on it never fires.
- **No archive reader exists.** Nothing in `src/` imports `zipfile` or `tarfile`. The
  file-type registry already groups archive extensions in the `archives` family
  (`src/metabrowser/data/file-rollup-format/recommended-file-types.toml`), and gives
  EPUB its own.
- **The requirements are written down.** `TODO.md` asks for safe member paths, symlink
  and traversal rejection, duplicate-name handling, nesting limits, and aggregate
  decompression limits before any container format ships.
  Bead `mb-p7ts` tracks that, and `mb-380k` sketched a ZIP container on the flat
  contract.
- **A Git blob is the nearest precedent for a member,** bytes with no file on disk, but
  the routes do not share one reader.
  On a folder, `api_file`, `raw_file`, and `api_kpress_render` (`server.py`) resolve
  through `resolve_session_identity` and `ArtifactPath`; on a pin, `git_revision_file`,
  `git_revision_raw`, and `git_revision_kpress_render` (`git/content_routes.py`) call
  the tree source’s `read_blob` and `read_blob_window`. Only sidekicks, such as the
  binary chunk and table hooks, read through `ContentRef` and `read_content_window`. A
  consumer that needs a file, as the SQLite reader does, copies the blob into a private
  folder named by its object ID (`reader_pool().blob` in `sqlite_readers.py` accepts
  only an alphanumeric ID).
- **Binary rules are folder-only.** `_binary_kind` (`server.py`) is consulted on a
  served folder; every pin classification site applies `magic` rules alone, so a file
  claimed by name is `binary` on a pin.
- **A magic rule’s `exts` never narrow it.** `classify_magic`
  (`plugin_loader/classify.py`) ignores them, and magic rules run before binary rules,
  so a second plugin cannot claim one ZIP-based extension by the ZIP signature without
  claiming every ZIP.
- **A large `.tar.gz` never reaches the binary rules.** Past
  `ARTIFACT_MAX_COMPRESSED_BYTES` it sniffs as unknown, takes the text path, and fails
  to a hard-coded `binary` in `api_file`; below it, every `/api/file` call decodes the
  whole gzip stream to validate it.

### Archive Formats in Brief

| Format | Found by | Index | Reading one member | Python reader |
| --- | --- | --- | --- | --- |
| ZIP and every format built on it | `PK\x03\x04` at offset 0 (`PK\x05\x06` for an empty archive) | A central directory at the end of the file, located through the end-of-central-directory record | Seek to its local header and decompress that member alone | `zipfile`: stored, deflate, bzip2, and LZMA members; ZIP64 |
| tar | `ustar` at offset 257; a pre-POSIX tar has no magic and is known only by name | None: a 512-byte header before each member’s data, with pax and GNU headers for long names and large sizes | Seek past every earlier member’s data | `tarfile` |
| Compressed tar (`.tar.gz`, `.tgz`, `.tar.bz2`, `.tbz2`, `.tar.xz`, `.txz`) | Its name; the tar magic is inside the compressed stream | None | Decompress the stream from its start up to that member | `tarfile` over `gzip`, `bz2`, or `lzma` |

Three properties of ZIP matter below:

- A member’s name is UTF-8 only when the archive sets the language-encoding flag;
  otherwise `zipfile` decodes it as code page 437.
- One archive can hold two entries with the same name.
- A Unix symlink is a member whose external attributes carry `S_IFLNK` and whose data is
  the link target.

The standard library’s readers are unsafe to point at hostile archives as they are:

- `zipfile` reads the whole central directory into memory, fails the whole archive on
  one member’s invalid UTF-8 name or corrupt Unicode-path field, cuts names at a NUL (so
  two NUL names become false duplicates), and checks for overlapping entries only when a
  member is opened.
- `tarfile` gathers a pax or GNU long-name header from many reads into one buffer,
  decompresses with no output bound, follows symlinks and hardlinks in `extractfile` (a
  hardlink through `getmembers()`, which loads the whole archive), and treats an invalid
  header after the first as the end of the archive, so a damaged listing looks complete.

Each of these was confirmed in the CPython 3.12 source and on crafted archives, and
their fixes vary by patch release within the supported range.
A wrapper cannot repair them, because the worst hide members that `unzip` and `bsdtar`
list.
So the plugin parses both formats’ directories itself, with every read bounded, and
uses the standard decompressors to decompress one member’s bytes
([Decision 11](#decision-11-how-archives-are-parsed)).

## Design

### Approach

1. **Formats in the plugin, protocols in core.** Core stays consumer-agnostic: the ZIP
   and tar readers, their safety rules, and their views are the `archive` plugin’s; core
   gains a member-source protocol and folder-like children, which name no format.
2. **A member is read through the content reader.** It has bytes, a size, a time, and an
   identity, and no file on disk.
   Phase 2 first moves the file, raw, and render handlers onto `ContentRef` on both
   subjects, then gives a member a `ContentRef`, so every route answers for it through
   one path, and a consumer that needs a file takes the copy path a pin takes.
3. **No member name is a filesystem path.** Bytes that must be kept are stored under a
   key derived from what they were computed from, never under a member’s name, so `..`,
   an absolute name, or a case collision cannot reach the disk.
4. **Bounds come from measurements.** Each constant below is set from a measurement
   taken in Phase 1 or Phase 2 and recorded beside it, as
   [Rendering Large Content](../../../large-content-rendering.md) requires.
   The plan names the constants and gives no values.

### The `archive` Plugin

`src/metabrowser/builtin_plugins/archive/`:

- **`manifest.toml`:** one `archive` kind, from rules that combine with OR:
  - a `magic` rule for `504b0304` at offset 0 and one for `504b0506`, with `exts` naming
    the ZIP-family extensions the tree should give a chevron (`.zip`, `.jar`, `.war`,
    `.ear`, `.aar`, `.apk`, `.ipa`, `.whl`, `.egg`, `.nupkg`, `.vsix`, `.xpi`, `.epub`,
    `.docx`, `.xlsx`, `.pptx`, `.odt`, `.ods`, `.odp`, `.kmz`);
  - a `magic` rule for `7573746172` (`ustar`) at offset 257, with `exts = [".tar"]`;
  - a `binary = true` rule by name for `.tar` (a pre-POSIX tar) and the compressed tar
    names (`.tar.gz`, `.tgz`, `.tar.bz2`, `.tbz2`, `.tar.xz`, `.txz`). Today a rule’s
    `exts` sees one logical extension, which is `.tar` for `x.tar.gz` on a folder, `.gz`
    for it on a pin, and `.bz2` for `x.tar.bz2` on both, and `path_glob` does not apply
    to a blob. So Phase 1 makes one classifier change: an `ext` or `exts` entry with an
    inner dot matches the name’s compound extension (`fs_paths.derive_ext`, which gives
    `archive.tar.gz` the extension `.tar.gz`), on a folder and on a pin alike.
  - **Three more classifier changes in Phase 1,** each generic:
    - binary rules apply at every pin classification site, against the blob’s display
      name and its compound extension;
    - a name-based binary rule for a compound extension is matched before the sniff, and
      a file it claims is not a transparent gzip artifact: `api_file` does not decode
      it, and its `ContentRef` carries its stored bytes on a folder as on a pin
      ([Decision 10](#decision-10-a-compressed-tar-is-an-archive-not-a-gzip-file));
    - a `magic` rule may set `restrict_exts = true`, so its `exts` narrow the match and
      a dedicated plugin can claim `.epub` by the ZIP signature at a higher priority
      without claiming every ZIP.
  - Views: Contents (`contents`, key `V`, the default, client-rendered) and Bytes
    (`bytes`, key `B`), the `binary` plugin’s view, which that plugin exports for a kind
    that keeps it.
  - Data hooks: `listing` in Phase 1; `children` in Phase 2.
  - `requires = ["binary"]`.
- **`names.py`:** member-name normalization and the safety rules below.
- **`reader.py`:** format detection from the stored bytes’ magic numbers (gzip, bzip2,
  xz, ZIP, ustar), never from what the content reader decompressed; the ZIP
  central-directory parser and the tar header parser; and member decompression with
  `zlib`, `bz2`, and `lzma`, always with `max_length`. It imports only the standard
  library and nothing from `metabrowser`: a file object and limits in, a plain index
  out, so it can be fuzzed on its own and later run unchanged in a child process.
- **`index_cache.py`:** the parsed indexes, kept by archive generation.
- **`sidekick.py`:** the data hooks.
- **`source.py`** and **`store.py`** (Phase 2): the member-source adapter and the
  materialization store.
- **`index.js`**, **`contents-model.js`**, **`contents-view.js`**, **`styles.css`:** the
  Contents view, split as the table plugin splits its model from its drawing.
  `index.js` exports `mountArchiveContents(container, {path})`, so a plugin that claims
  a ZIP-based format for itself can keep Contents as one of its tabs.

### The Archive Index

The reader parses an archive once per generation into an index the listing, the children
hook, and member reads all use.
Each entry holds:

| Field | Meaning |
| --- | --- |
| `path` | The normalized member path, or none when the name is unsafe |
| `stored_name` | The name as the archive spells it, shown when it is unsafe |
| `type` | `file`, `dir`, `symlink`, `hardlink`, or `other` (device, FIFO) |
| `size`, `compressed_size` | Declared sizes; ZIP alone has a per-member compressed size |
| `modified`, `mode` | Where the format records them |
| `link_target` | For a link |
| `method`, `encrypted` | ZIP compression method and encryption flag |
| `location` | Where the data starts: a ZIP local-header offset, or a tar data offset in the decompressed stream |
| `problems` | The safety rules’ findings |

Directories the archive implies but does not list, as ZIP files often do, are added.
The index records totals (members, files, directories, links, declared bytes, archive
bytes) and, when it stops early, why.

How each format is read:

- **ZIP:** the reader finds the end-of-central-directory record (and the ZIP64 locator),
  refuses a central directory past `CENTRAL_DIRECTORY_MAX_BYTES` or a member count past
  `LISTING_MAX_MEMBERS`, and parses each entry itself, so a bad name or extra field
  marks that member rather than failing the archive.
  It records each member’s data span and marks members whose spans overlap.
- **tar:** the reader parses each 512-byte header itself, checking its checksum, type
  flag, and size before reading anything the header announces; it refuses a pax or GNU
  long-name header past `EXTENDED_HEADER_MAX_BYTES` and stops at `LISTING_MAX_MEMBERS`.
  An invalid header after the first is a damaged archive, which the listing reports as
  stopped, not complete.
  An uncompressed tar on a seekable file seeks over member data.
- **Compressed tar:** the reader decompresses the archive’s on-disk bytes itself, with
  `gzip`, `bz2`, or `lzma`, rather than through `gz_io`, whose caps bound single-file
  previews, and stops at `TAR_SCAN_MAX_BYTES` of tar stream or `LISTING_DEADLINE`. A
  listing that stops says so and shows what it read.
- **On a served folder** the reader opens the resolved real file, as a table source does
  through `TableHandle.local_path`. **On a pin** the blob is copied once into the
  materialization store under its object ID, which never goes stale, within
  `ARCHIVE_COPY_MAX_BYTES`, since ZIP needs random access and a blob only streams.
  The copy streams from the object store into the file, never through memory.
  Phase 1 therefore builds the store, with its bounds; Phase 2 widens it to members.
- **Never extracted.** No code path calls `zipfile` or `tarfile` extraction; member data
  is read by the index’s offsets, and links resolve from the plugin’s own index.

The index cache is bounded by `INDEX_CACHE_MAX_ENTRIES` and an estimate of each index’s
memory, and keyed by the archive’s identity and generation: the stat generation on a
served folder, the object ID on a pin.

### Member Names and Safety Rules

| Case | In the listing | Addressable in Phase 2 |
| --- | --- | --- |
| An absolute name, a drive letter, a `..` segment, a NUL or control character, or an empty name | Listed under its stored name, escaped, with `unsafe_name` | No |
| `\` separators | Normalized to `/`, as Info-ZIP’s `unzip` does for archives made on Windows | Yes |
| `./a`, `a//b`, a trailing `/` | Normalized | Yes |
| Two entries with one path | Every entry listed; earlier ones marked `shadowed` | The last one, the one extraction leaves |
| A file and a directory at one path | Both listed; the file marked `shadowed` | The directory |
| A symlink | Listed with its target | Its page says it is a link and links to the target when the target, resolved lexically against the link’s directory, names a member; it is never followed |
| A tar hardlink | Listed with its target | Reads the earlier member it names, resolved from the index; a missing target is a problem |
| ZIP members whose data spans overlap (an overlap bomb) | Listed with `overlapping` | No |
| A name or extra field that cannot be decoded | Listed with `bad_name`; the rest of the archive lists | No |
| A device, FIFO, or other special member | Listed | Its page says what it is; no bytes |
| An encrypted ZIP member | Listed with `encrypted` | Its page says it is encrypted |
| A ZIP member neither stored nor deflated (bzip2, LZMA, Deflate64, Zstandard, PPMd, and others) | Listed with the method’s name | Its page names the method |
| A sparse tar member | Listed | Its page says it is sparse; no bytes |
| A name not valid UTF-8 | Shown decoded with replacement characters, escaped before JSON | By the inventory’s identity spelling (`canonical_inventory_path`), which is lossless |
| A segment that starts with `g1-` | Listed | Escaped as the SQLite plugin escapes table segments (`builtin_plugins/sqlite/database.py`), since a pin reads leading `g1-` segments as its own path |

Case differences (`A` and `a`) are distinct members: nothing is written under a name, so
nothing collides. A member’s declared size is shown as declared; Phase 2’s reads stop at
their bounds whatever the declaration says, and a stream whose length or CRC disagrees
with it is a problem on that member’s page.

### Bounds

Each is a constant in the plugin’s module that uses it, with the measurement that set it
in its docstring; the measurement task in each phase records the curves.

| Constant | Bounds | Set from |
| --- | --- | --- |
| `LISTING_MAX_MEMBERS` | Entries in one index | Index build time and memory per entry, for ZIP and tar, and the Contents view’s render cost in Chrome |
| `CENTRAL_DIRECTORY_MAX_BYTES` | A ZIP central directory `zipfile` reads whole | Bytes per entry at `LISTING_MAX_MEMBERS` |
| `EXTENDED_HEADER_MAX_BYTES` | One pax or GNU long-name header | The longest headers in real archives, such as source tarballs with deep trees |
| `TAR_SCAN_MAX_BYTES`, `LISTING_DEADLINE` | A compressed tar’s scan | gzip, bzip2, and xz decompression throughput |
| `INDEX_CACHE_MAX_ENTRIES` | Indexes held in memory | Memory per indexed entry |
| `ARCHIVE_COPY_MAX_BYTES` | A pin’s archive streamed into the store | Copy time from the object store |
| `STORE_MAX_BYTES`, `STORE_MAX_ENTRIES` | The store, from Phase 1’s pin copies on | As the PDF previews area is bounded (`builtin_plugins/pdf/preview_store.py`) |
| `MEMBER_WINDOW_MAX_BYTES` (Phase 2) | Decompressed bytes one windowed read may produce | The largest window a view asks for (`TEXT_PREVIEW_REQUEST_MAX_BYTES` and the binary plugin’s chunk ceiling) |
| `MEMBER_WHOLE_MAX_BYTES` (Phase 2) | A member read or materialized whole, for `/raw`, KPress, and the SQLite copy | Real members: images, PDFs, and databases inside archives |
| `TAR_MATERIALIZE_MAX_BYTES` (Phase 2) | A compressed tar decompressed into the store | Disk and time to decompress, against the store’s bound |
| `ARCHIVE_NESTING_MAX` (Phase 2) | Archives inside archives | The deepest nesting real artifacts carry (a `.jar` in a `.war` in an `.ear`) |
| `MAX_CONTAINER_INNER_DEPTH` (raised in Phase 2) | Segments in an inner path | Real archives, such as a packed `node_modules` tree; it stays one value, since a pin checks depth before it knows the kind |

`Budget` in `table_source.py` is a wall clock only, and `/api/file` and `/raw` run with
none. Phase 2 adds a member-read budget to `member_source.py` that counts decompressed
bytes, bytes written to the store, and time, across every member and nesting level one
request touches, so a bomb split across members or nested inside another archive stops
at one total, on disk as in memory.

### Phase 1: The Contents View

**The listing route.** `GET /api/plugin/archive/listing?path=<identity>` answers the
index in the collection envelope the
[object data model plan](plan-2026-11-14-object-data-model-and-views.md) proposes and
the table routes use:

```json
{
  "format": "zip",
  "compression": null,
  "generation": "…",
  "totals": {"members": 412, "files": 380, "dirs": 30, "links": 2,
             "bytes": 18234112, "archive_bytes": 6120448},
  "problems": {"unsafe_name": 1, "shadowed": 2, "encrypted": 0},
  "complete": true,
  "truncated": null,
  "rows": [{"path": "docs/readme.md", "type": "file", "size": 2310,
            "compressed_size": 1022, "modified": "…", "problems": []}]
}
```

Rows come in the order the tree lists a folder.
A file that is not a readable archive answers a typed error (`archive_unreadable`, with
what failed), which the view shows as one line with Bytes still a tab away.

**The view.** Contents draws:

- **A summary line:** the format (“ZIP”, “tar, gzip”), files and folders, total size,
  and, where there is one, the compressed size and ratio.
- **Problem chips:** one per problem with a count (“1 unsafe name”, “2 duplicates”, “3
  encrypted”), each a filter, and a line when the listing stopped early, saying where
  and why in a reader’s words, with no internals.
- **The tree:** directories collapsible, the first level open; each row the file-type
  icon (`mb.fileTypeIcon`), name, size, and modified time, with badges for links,
  encryption, and problems.
  Rows are not links in Phase 1.
- **Windowing,** only if the render measurement shows a full listing at
  `LISTING_MAX_MEMBERS` costs too much to draw at once; the structured tree’s row
  materialization is the first candidate to reuse.

`contents-model.js` holds what the view decides, as pure functions of the listing and
the expansion state: rows shown, chips, the filter, and the summary.
`contents-view.js` draws it.
The view watches the archive (`metabrowser.watchFile`) and fetches the listing again
when its generation moves, keeping expansion and filter.
It is not printable in Phase 1.

### Phase 2: Archives as Folders

#### Member Sources

A plugin declares a member source for one of its kinds, as it declares a table source:

```toml
[[member_source]]
kind = "archive"
adapter = "metabrowser.builtin_plugins.archive.source:adapter"
```

`src/metabrowser/member_source.py` holds the protocol, its wire, and the registry, and
`plugin_api.py` re-exports the protocol’s types and errors as SDK surface.
Registration follows the table source’s rules: one of the plugin’s own kinds, once;
Python only from a built-in or installed plugin; `metab --doctor` reports one that does
not import; a later declaration replaces an earlier one.

The adapter maps a `MemberHandle` (the archive’s `ContentRef`, its name, and its local
path on a served folder) to a `MemberSource`, whose methods are synchronous and run on
the route threadpool under the request’s `Budget`:

| Method | Answers |
| --- | --- |
| `generation()` | The archive’s generation, which every member shares |
| `entries(directory, after, limit)` | One page of a directory’s members, as children rows |
| `stat(inner)` | A member’s type, declared size, time, link target, and whether it can be read and why not; a member’s `ContentStat` says its size is declared, and a read that finds otherwise is an error the route reports |
| `read(inner, offset, max_bytes)` | A bounded window of a member’s bytes |

#### Members in the Content Reader

- **Moving the handlers first.** `api_file`, `raw_file`, and `api_kpress_render`, and
  their pin counterparts `git_revision_file`, `git_revision_raw`, and
  `git_revision_kpress_render`, read through `ContentRef` before any member exists, with
  their goldens unchanged; a member then needs no branch in any of them.
- **Resolution** is keyed on the member-source registry, not on `container`, so it works
  before the tree learns to expand archives.
  When the nearest file ancestor of a path has a kind with a member source, the source’s
  `stat` decides the inner path, and `ContentSource.open_ref`, on the served folder and
  on a pin, returns a member `ContentRef`: the archive’s identity and generation, the
  inner path, and a reader that calls the source’s `read`. `read_content_window` and
  every helper over it then work for a member.
- **Classification.** `/api/file` classifies a member file as a Git blob is classified:
  its logical name and sniffed prefix through the same steps, without `path_glob`, so
  `docs/readme.md` is `markdown` and a nested `.jar` is `archive`. A member directory is
  the archive’s own kind with `container_inner`, so Contents draws that directory, as
  the SQLite kind draws a database or one table at one address.
- **Raw bytes.** `/raw` answers for a member in both forms, through the same resolution,
  sandboxed and typed as any file.
  The path form matters for an HTML member, whose relative stylesheets and images then
  resolve inside the archive
  ([HTML Preview](../../architecture/arch-server-and-content.md#html-preview)).
- **Validators.** A member’s fingerprint is a hex SHA-256 of its archive’s generation
  and its path, so every member of a pinned archive is immutable to the cache and the
  fingerprint passes wherever an object ID is checked; no member name reaches a
  filename.
- **Consumers that need a file** take the copy path: the SQLite reader receives a member
  as it receives a blob, through a core helper that streams any `ContentRef` into a
  private file within a bound (see [Framework Surfaces](#framework-surfaces)), and
  `TableHandle.local_path` answers none unless its path is a file, so a member never
  takes the served-folder branch.
- **The depth bound.** `MAX_CONTAINER_INNER_DEPTH` rises from a measurement of real
  archives; it stays one value, since a pin checks depth before it knows the kind.

#### Folder-Like Children

- **The wire.** A children row may carry `folder: true`, and a children hook may take
  `?path=<container>/<directory>` and answer a page: `after` and `limit` in,
  `next_after` and `complete` out, as a directory’s lazy pages do.
- **The tree.** A folder-like child row gets a chevron and an empty child group, fetched
  on first expansion from its container’s children hook, with the keyboard, ARIA, and
  pagination a directory has.
  Selecting it opens its container kind’s overview at its address.
  A member whose name carries a container extension gets the chevron of its own kind,
  and expanding it calls that kind’s children hook with the member’s address.
- **The chevron lookup** matches a name’s compound extension (`.tar.gz`), as Phase 1’s
  classifier change does, not only its last suffix.
- **Binary rules may be containers.** The manifest check that refuses `binary = true`
  beside `container` goes, and the container walk applies binary rules on a folder and a
  pin, so a compressed tar is a container by name.
- **Deep links reveal members.** Revealing `/view/app.zip/docs/readme.md` expands the
  archive and its directories, as it expands folders today.
- **The archive’s children hook** reads its index through its own member source, so the
  tree, the listing, and member reads share one parse.

#### Reading Members

| Archive | Served folder | Pin |
| --- | --- | --- |
| ZIP, stored member | A seek and a read | The same, on the store’s copy |
| ZIP, compressed member | Decompress from the member’s start to the window’s end; materialize in the store when a consumer needs the whole member or windows far into it | The same, on the store’s copy |
| tar | A seek to the data offset | The same, on the store’s copy |
| Compressed tar | The first member read decompresses the whole tar once into the store as a plain tar, within `TAR_MATERIALIZE_MAX_BYTES`; later reads seek | The same |

A compressed tar too large to materialize keeps its listing, and its members’ pages say
the archive is too large to open members of.

#### The Materialization Store

The store holds bytes the plugin must keep to read members: a pin’s archive copy, a
decompressed tar, a member a consumer needs whole, a nested archive.
It is a plugin cache area (`plugin_api.plugin_cache_directory`), kept owner-only, each
entry written atomically and named by a SHA-256 of what it was computed from (the
archive’s identity key and generation, the member path, and the member’s CRC or size),
evicted least recently used past `STORE_MAX_BYTES` or `STORE_MAX_ENTRIES`, and answering
every filesystem failure as a miss, as the PDF previews area does.
No entry is named after a member.

#### Nested Archives

A member classified as an archive is itself a container.
Resolution splits the inner path at the deepest member that is an archive, up to
`ARCHIVE_NESTING_MAX` levels; the nested archive is materialized first, since it needs
random access, and its member source reads the copy.
Past the limit, the nested archive opens with its Contents view only, saying why.

#### Live Updates

A member’s watch generation is its archive’s, so `file_watches.py` answers a watch on
`<archive>/<inner>` with the archive’s generation, as it answers a table source’s. An
open member page reloads when its archive changes, and shows the missing page when the
member is gone; open directories in the tree read their pages again, as a container’s
children do today.

#### Trust

Every decision the server makes per response treats a member as untrusted content,
whatever its subject’s profile, because an archive is often a download its reader never
opened:

- **`/raw`** answers a member with the untrusted sandbox (no `allow-scripts`);
  `_RawTrustHeaderMiddleware` already sets the sandbox per response.
- **Markdown** members render through the inert path and its deadline, not in a server
  thread, which closes the T7 residual for them.
- **Server-side parsers:** a PDF member’s preview renders only in the sandboxed child,
  and a SQLite member is read with the untrusted source’s settings.
- **The page policy** stays the subject’s: it belongs to the shell a member is drawn in.
- **The macOS app’s Open** treats a member as a pin’s file: a quarantined, read-only
  copy, never a path under the folder.

The threat model gains the archive entries in T4 and T7.

### Framework Surfaces

| Surface | Phase | Where | Who else uses it |
| --- | --- | --- | --- |
| `mountArchiveContents` export | 1 | `archive/index.js` | A plugin that claims a ZIP-based format, such as an EPUB reader |
| Bytes view export | 1 | `binary/index.js` | Any binary-format plugin that keeps the Bytes tab |
| Compound extensions in kind rules | 1 | `plugin_loader/classify.py` | Any format named by a compound suffix, on a folder and a pin |
| Binary rules on a pin, and before the gzip sniff | 1 | `server.py`, `git/content_routes.py` | Any binary format claimed by name |
| `restrict_exts` on a magic rule | 1 | `plugin_loader/manifest.py`, `classify.py` | A plugin that claims one ZIP-based format, such as `.epub` |
| File, raw, and render handlers on `ContentRef` | 2 | `server.py`, `git/content_routes.py` | Every content kind, on either subject |
| Streaming a `ContentRef` into a private file | 2 | `source.py` | The SQLite reader and any consumer that needs a file |
| Member-read budget (bytes, store writes, time) | 2 | `member_source.py` | Any member source |
| `[[member_source]]` and `member_source.py` | 2 | Manifest, core, `plugin_api` | Installed plugins for 7z, ISO, `.asar`; a plugin that claims `.epub` reusing the ZIP source |
| Member `ContentRef` | 2 | `source.py`, `git/tree_source.py` | Every route and sidekick that reads through the content reader |
| Folder-like children and paged children | 2 | Container contract, `static/app.js` | Any container with a hierarchy |
| Compound-extension chevrons and binary-rule containers | 2 | `static/app.js`, `plugin_loader/manifest.py` | Any container claimed by name |

All are additive, so `PLUGIN_SDK_VERSION` stays where it is.

## Key Decisions

### Decision 1: Where Archive Reading Lives

- **A. A built-in plugin, with a generic member-source protocol in core.**
- **B. A core module, as `gz_io` is.**
- **C. The plugin alone, serving members through its own data hooks.**

**Recommendation: A.** Format readers are domain code, which `AGENTS.md` keeps out of
core. C cannot give a member its own kind’s views: every view reads through core routes
and the content reader, not through the archive’s hooks.

### Decision 2: How a Member Reaches Other Kinds’ Views

- **A. A member `ContentRef` in the content reader.**
- **B. Extract the archive into a temporary folder and serve that folder.**
- **C. A per-kind hook each plugin implements for members.**

**Recommendation: A.** B writes attacker-chosen names to disk (T4), pays for every
member to show one, and goes stale; C makes every plugin learn about archives.
A follows the pin, which already proves the content reader carries every view.

### Decision 3: How ZIP-Based Formats Are Claimed

- **A. By the ZIP signature, whatever the name, with `exts` for the chevron.**
- **B. By an extension list.**

**Recommendation: A.** It finds every ZIP-based format without a list to maintain, and a
dedicated plugin claims its own extension with a `restrict_exts` magic rule at a higher
priority when one exists.

### Decision 4: Reading Members of a Compressed Tar

- **A. Decompress once into the store as a plain tar, then seek.**
- **B. Decompress from the start on every read.**
- **C. A seek-point index into the compressed stream (as `zran` does for gzip).**

**Recommendation: A.** B costs the archive’s size on every window; C is gzip-only and
complex. A’s cost is bounded disk in a store that evicts.

### Decision 5: Duplicate Names

- **A. The last entry is the address; earlier ones are listed as shadowed.**
- **B. The first entry is the address.**
- **C. Each duplicate gets a synthetic address.**

**Recommendation: A.** It is what extraction leaves, for `tar` and for `unzip -o`, and
what `zipfile.getinfo` answers.
C invents names a reader cannot find in the archive.

### Decision 6: Symlinks

- **A. Shown, never followed; the page links to a lexically resolved target member.**
- **B. Followed within the archive.**
- **C. Hidden.**

**Recommendation: A.** Following needs loop and escape rules for no reading benefit, and
hiding a link misleads.

### Decision 7: A Member’s Trust

- **A. Untrusted in every per-response decision (`/raw`’s sandbox, inert Markdown,
  server-side parsers), with the shell’s page policy the subject’s.**
- **B. The subject’s profile everywhere.**
- **C. A page policy per file.**

**Recommendation: A.** B would run a downloaded archive’s HTML scripts, and render its
PDF and Markdown outside their sandboxes, because the archive sat in a trusted folder.
C needs a page policy the shell does not have, and A gets the same protection from the
places the server already decides per response.

### Decision 8: Nested Archives

- **A. Recurse to `ARCHIVE_NESTING_MAX`, through the store.**
- **B. No nesting: a nested archive shows Contents only.**

**Recommendation: A.** A `.jar` inside a `.war` or a wheel inside a release `.zip` is
the common case, and the request budget bounds the total.

### Decision 9: Office and EPUB Files

- **A. Archives until a dedicated plugin claims them.**
- **B. Left as bytes.**

**Recommendation: A,** as the owner asked for every ZIP-based format.
Contents of an `.epub` or `.docx` is more useful than its bytes.

### Decision 10: A Compressed Tar Is an Archive, Not a Gzip File

- **A. A name-based binary rule claims `.tar.gz` before the sniff, and the file keeps
  its stored bytes.**
- **B. Keep gzip transparency and read the logical tar stream.**

**Recommendation: A.** B classifies a large `.tar.gz` as `binary` without consulting any
rule, decodes the whole stream on every `/api/file`, hands a reader tar bytes on a
folder but gzip bytes on a pin and for `.tgz`, and caps an archive at single-file
preview limits. A gives one byte stream on both subjects, and the reader bounds its own
decompression.

### Decision 11: How Archives Are Parsed

- **A. Our own index parsers, with the standard decompressors for member bytes.**
- **B. `zipfile` and `tarfile` as they are, wrapped in checks and bounds.**
- **C. `zipfile` and `tarfile` in a bounded child process that returns a checked
  index.**
- **D. A third-party reader, such as libarchive bindings.**

**Recommendation: A,** as a hybrid with the standard library kept as the test oracle.
The owner asked whether our own parsers carry risks of their own; a review on 2026-11-24
weighed them against each option:

- **B and C keep the semantic faults.** One member with an invalid UTF-8 name makes
  `zipfile` refuse an archive that `unzip -l` lists whole, and a corrupt second tar
  header makes `tarfile` return one member with no error where `bsdtar` reports damage
  and lists the rest. A wrapper or a process boundary changes neither answer.
- **The standard readers differ by patch release.** The ZIP64 end-record check and
  `tarfile`’s chunked extended-header read are present in some releases in the supported
  range and absent in others, so goldens over hostile fixtures would differ by
  interpreter, and a guard on read sizes holds on one release and not another.
- **There is no memory-safety trade.** Both standard parsers are pure Python, as ours
  would be; the native code is `zlib`, `bz2`, and `lzma` in every option.
- **A is faster.** A minimal `struct` loop read central-directory entries in about a
  quarter of `zipfile`’s time and held less memory per entry.
- **C does not bound memory on macOS,** where the address-space limit does not apply
  (`render_child.py`, `sqlite_readers.py`), and a child’s start costs a large part of an
  instant listing. It remains an option for Phase 2’s whole-tar materialization.
- **D** is a native reader, which belongs in an installed plugin, and the pure-Python
  alternatives read local headers rather than the central directory, so they list
  different members than `unzip`.

The rules A implies:

- **What we parse,** with `struct` on fixed-size records: the ZIP end record (searched
  within its maximum comment length), the ZIP64 locator and record, central-directory
  entries, only the ZIP64 (`0x0001`) and Unicode-path (`0x7075`) extra fields, and the
  local header only to find the data; the tar header (checksum, octal and base-256
  numbers, type, ustar prefix), GNU `L` and `K`, and pax `x` and `g` records, keeping
  only `path`, `linkpath`, `size`, and `mtime`.
- **What we leave out:** sparse tar members and ZIP members neither stored nor deflated
  are listed and not read, so ZIP reads touch only `zlib`.
- **What we delegate:** decompression to `zlib.decompressobj`, `bz2.BZ2Decompressor`,
  and `lzma.LZMADecompressor` with a `memlimit`, always called with `max_length` on
  bounded input chunks, and the budget checked between calls, as `gz_io.py` does.
- **Invariants, each a counter a test can read:** every file read passes through one
  counting wrapper with a named maximum; an extended header’s size is checked before it
  is read; entries stop at `LISTING_MAX_MEMBERS`; every loop advances by at least one
  record; every offset and span lies inside the file and before the directory; only the
  plugin’s own error type leaves the reader; and links resolve from the index with a hop
  limit.
- **Data before the archive:** one explicit rule for a ZIP whose offsets are shifted by
  prepended bytes, pinned by a test.
- **`zipfile` and `tarfile` stay out of `src/`,** enforced by a check; tests use them as
  fixture writers and as the oracle.

Residual risks: an ambiguous archive can be read differently than by `unzip`, `bsdtar`,
or GNU `tar`, which already disagree with one another; `bz2` and `lzma` become native
decompressors of attacker bytes in the server, which the threat model records under T7
as it does gzip; a missed bound has no operating-system limit behind it on macOS; and
the oracle’s list of deviations needs upkeep as CPython changes.

## Implementation Plan

Each phase is one stack, its layers listed below; implementation beads may be finer.

### Phase 1: The Contents View

- [ ] **Reader, listing, and kind** (layer 1, `mb-7l96`): the four classifier changes
  (compound extensions, binary rules on a pin, binary rules before the gzip sniff, and
  `restrict_exts`); the plugin’s manifest and kind rules; `names.py`, `reader.py`, the
  index cache, and the store with its bounds; the `listing` hook; deterministic and
  hostile fixtures, unit tests for every safety rule and bound at its edge, and the
  measurements that set the Phase 1 constants.
  In the same layer, since the build checks a kind and a route where they land:
  `cli-api-archive-listing.tryscript.md`, `kind: archive` lines in
  `cli-show.tryscript.md` for each format on a folder and on a pin, the route’s parity
  row, the `archive` row in
  [Views, Models, and Routes](../../architecture/arch-views-models-routes.md), and the
  built-in plugin lists (`test_plugin_requirements.py`, `check_distribution.py`, the
  `cli-plugins` golden and the plugin counts in others)
- [ ] **Contents view** (layer 2, `mb-53xr`): the model and view, the Bytes view export
  and its reuse, `mountArchiveContents`, the watch, the render measurement in Chrome,
  `tests/dom/archive-contents-session.js` with `cli-ui-archive-contents.tryscript.md`,
  and its parity rows
- [ ] **Documents and verification** (with layer 2, `mb-54di`): the Archive row and
  status line in [Plugin System](../../architecture/arch-plugin-system.md), T4 and T7 in
  the [threat model](../../architecture/arch-threat-model.md), `TODO.md`,
  `docs/plugins.md` for the exports and `restrict_exts`,
  [Browsing Files](../../../browsing-files.md), and a changelog fragment; then Contents
  in Chrome, Safari, and the macOS app on a folder, a pin, and an `--untrusted` folder,
  with real archives (a wheel, a source tarball, an Android `.apk`, an `.epub`) and a
  hostile fixture

### Phase 2: Archives as Folders

- [ ] **Member sources and member content** (layer 1, `mb-xyz9`): first the six file,
  raw, and render handlers onto `ContentRef` with goldens unchanged; then
  `member_source.py` with its member-read budget, the manifest table and its checks,
  `plugin_api` re-exports, the doctor’s report, resolution keyed on member sources,
  member `ContentRef`s on both subjects, member classification, the trust rules, the
  `ContentRef`-to-file helper, `local_path` answering none for a member, the raised
  depth bound, the archive’s adapter, and `cli-api-archive-members.tryscript.md`
  (`--show` and `/api/file` on a Markdown, image, CSV, and HTML member, `/raw` in both
  forms with its sandbox, each unreadable case)
- [ ] **Folder-like children** (layer 2, `mb-0dja`): the children wire’s `folder` flag
  and pages, the tree’s folder-like rows, compound-extension chevrons, binary-rule
  containers on both subjects, deep links that reveal members, the archive’s `children`
  hook and `container` declaration, Contents rows that link to members, the tree session
  and golden for nested rows, and the parity rows
- [ ] **Nested archives, pins, and live members** (layer 3, `mb-tf53`): nesting through
  the store, compressed-tar materialization, member watch generations, the SQLite
  reader’s copy and the PDF preview’s untrusted rule for members, the app’s Open for a
  member, and their goldens
- [ ] **Documents and verification** (`mb-3ny3`): the container contract and member
  sources in [Plugin System](../../architecture/arch-plugin-system.md) and
  `docs/plugins.md`, the threat model’s Phase 2 entries, the URL grammar row, a
  changelog fragment, and the Phase 1 verification matrix again with members opened from
  each

## Testing Strategy

- **Fixtures** are built by a generator from the standard library’s writers with fixed
  times, so they are deterministic and no binary is committed.
  Hostile cases the writers refuse are assembled at the byte level: absolute and `..`
  names, duplicates, a file and directory at one path, overlapping ZIP entries, a
  high-ratio bomb, a nested bomb, a central directory that claims more than the file
  holds, a pax header that claims a huge size, symlinks pointing out of the archive, and
  truncated and corrupt files.
- **Unit tests:** every row of the safety table, every bound at its edge, cache and
  store keys, and the counting read wrapper.
- **Differential tests against the standard library:** a seeded corpus from its writers
  (stored and deflated, forced ZIP64, more than 65,535 entries, data descriptors, code
  page 437 and UTF-8 names; tar in ustar, GNU, and pax forms with long names, links, and
  devices). Wherever `zipfile` or `tarfile` reads an archive, our index and member bytes
  equal theirs, and every deviation is on an enumerated list.
- **Cross-checks against tools:** `unzip -Z1`, `bsdtar -tf`, and GNU `tar -tf` over the
  corpus and the pinned cases (the invalid-UTF-8 ZIP and the tar with a corrupt second
  header), skipped where a tool is absent and never in a golden.
- **Mutation fuzzing** with no new dependency, seeded and inside `make test`:
  truncations, bit flips, and maximized length fields, asserting only that the plugin’s
  error type leaves the reader, the guard counters, and a `tracemalloc` ceiling; a
  longer run lives in `devtools/`.
- **Identical hostile goldens on every supported interpreter.**
- **No name reaches the disk:** a test runs the listing and every member read over the
  hostile fixtures and checks that the store holds only key-named entries and nothing
  appeared anywhere else.
- **Bombs stop in budget:** the bomb fixtures stop within the request budget, asserted
  on the budget’s byte counters and `tracemalloc`, never on wall time, which a loaded
  machine varies tenfold.
- **Goldens:** `cli-api-archive-listing`, `cli-show`, `cli-api-archive-members`, and the
  route list in `cli-api-shell`.
- **Browserless sessions:** the Contents model (expansion, chips and filter, a stopped
  listing, refresh that keeps expansion, replacement, disposal), and the tree with
  folder-like children (expansion, paging, keyboard, deep-link reveal, a nested
  archive).
- **Pins:** the same fixtures committed in a test repository and served pinned.
- **Measurements:** recorded beside each constant, from real archives and generated ones
  at sizes that bracket each bound.

## Rollout Plan

Each phase ships in the next `metab` release after it lands.
Phase 1 changes no contract the macOS app reads.
If Phase 2’s member Open needs an app change, the app and `metab` change in one commit
and `MetabRequirement.minimumRelease` rises, as
[Compatibility and Legacy Code](../../../development.md#compatibility-and-legacy-code)
requires.

## Open Questions

1. **`.tar.zst`.** Python’s standard library reads Zstandard from 3.14
   (`compression.zstd`), which is above the floor `pyproject.toml` supports.
   Wait for 3.14 as the floor, or take a third-party reader under the cool-off with the
   single-file `.zst` roadmap item?
   Recommendation: decide with `.zst`, outside this plan.
2. **Printing Contents.** A listing is complete, so it could print with every directory
   open. Worth adding in Phase 1?
3. **Members in Quick Search.** A later phase could index members of archives the reader
   has opened. Wanted?
4. **The manifest table’s name.** `[[member_source]]` follows `[[table_source]]`.
   `[[folder_source]]` reads more plainly but collides with the `folder` kind.

## References

- Bead `mb-p7ts`, this effort’s epic; `mb-380k`, the flat-container sketch this plan
  replaces
- [Plugin System](../../architecture/arch-plugin-system.md), Navigation Containers and
  Table Sources
- [Tabular Data Browsing and Live SQLite](plan-2026-11-19-tabular-data-and-live-sqlite.md),
  the table-source precedent
- [PDF Plugin](plan-2026-11-24-pdf-plugin-and-open-in-default-app.md), the store and
  sandbox precedent
- [Threat Model](../../architecture/arch-threat-model.md), T4 and T7
- [Rendering Large Content](../../../large-content-rendering.md)
- `TODO.md`, Archive and Container Formats

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
