# Research: File Patch Formats

**Date:** 2026-08-19 (last updated 2026-08-25)

**Author:** Claude (research agent), directed by Joshua Levy

**Status:** Complete

## Overview

Metabrowser has shipped
[File Diff Format v1](../architecture/file-diff-format/file-diff-format.md), a JSON
change-set document that wraps parsed unified diffs in resolved snapshot identity, a
manifest of file changes, and per-file hunk patches, validated by
[a schema](../../../src/metabrowser/data/file-diff-format/file-diff.schema.json) and an
[apply oracle](../../../src/metabrowser/diff/apply.py).
The stated goal is maximal backward compatibility with existing patch formats plus full
support for our own features, GitHub pull requests, and agent workflows.

This survey maps the existing formats against that goal.
The short answer: git’s extended unified format is the lingua franca — GitHub serves it,
Mercurial and Jujutsu adopt it, agents are trained near it — so it is the one format we
must both read and write.
Classic POSIX formats matter only as unified-diff variants (`patch(1)` itself accepts
more than we ever need to).
JSON-native patch formats (RFC 6902 family) are not competitors but teach identity and
validation lessons v1 already applies.
Agent edit formats diverge from all of the above in one consistent direction: they
anchor by content, not line numbers.
File Diff Format v1 captures nearly everything git’s text format captures, adds
identity, availability, and machine validation that no text format has, and currently
lacks exactly two things this research makes concrete: a git-applyable emitter, and
ingestion of a few real-world patch shapes (format-patch framing, GIT binary payloads,
GitHub REST bare hunks, `index`-line anchors).

## Questions to Answer

1. Which existing formats should Metabrowser treat as the compatibility surface, for
   ingest and for emit?
2. What does each format family capture, and what does it structurally miss?
3. What does File Diff Format v1 add over each, and what does it still lack?
4. Which git-patch features does our unified-patch parser
   ([`patch_file.py`](../../../src/metabrowser/diff/adapters/patch_file.py)) not yet
   ingest?
5. What do agent workflows need that classic patches lack?
6. Does any existing format make part of our model redundant?

## Scope

Surveyed: POSIX diff/patch and GNU diffutils; git’s extended unified format including
binary patches, combined diffs, `git apply` acceptance, and `git format-patch` framing;
GitHub’s pull-request diff representations and documented limits; RFC 6902 JSON Patch,
RFC 7386 JSON Merge Patch, and jsondiffpatch as JSON-native contrast cases; LSP and VS
Code workspace edits; OpenAI `apply_patch` (V4A), aider’s edit formats, Anthropic’s
text-editor tool, and Morph fast-apply; brief notes on Mercurial, darcs, and Jujutsu.
An appendix covers syntax highlighting architecture in diff viewers.

Out of scope: three-way merge file formats (`.orig`/`.rej`, conflict markers) beyond
their role in apply semantics, VCS storage internals, word-processor tracked changes,
and semantic/AST diff interchange beyond the difftastic note.

### Methodology and verification

Six parallel sub-surveys fetched primary sources (POSIX specs, GNU manuals, git
documentation and source, docs.github.com, RFCs, vendor docs); their reports carry the
URLs cited in References.
Local claims about Metabrowser were verified by reading the schema, contract docs,
parser, and apply oracle, and by executing probe inputs against `parse_unified_patch` on
this branch. Four defects those probes surfaced were fixed during the research in commit
`dbe4a7e` (see Findings); the remaining ingest gaps are open.
One gap in coverage: the POSIX/GNU sub-survey delivered its format sections in full but
was cut off partway through the `patch(1)` application details; statements below about
GNU patch defaults (fuzz, `-p` handling, create/delete heuristics) follow the GNU and
POSIX manuals as generally known and are marked UNVERIFIED where this research did not
re-confirm them against a fetched page.

## Findings

### POSIX diff/patch and GNU diffutils

POSIX `diff` defines four output forms.
Normal format (the default) emits `RcT`/`RaT`/`RdT` hunks with `<` old lines, `>` new
lines, and `---` separating the halves of a change.
Ed scripts (`-e`) are line-addressed `a`/`c`/`d` commands terminated by a lone `.`, and
POSIX notes they cannot represent some inputs (a line consisting of a single `.`) and
carry no context. Context format (`-c`) uses `*** file1 timestamp` /
`--- file2 timestamp` headers, a 15-asterisk hunk separator, per-side ranges
(`*** 1,4 ****`, `--- 1,4 ----`), and two-column markers: unchanged, `- ` deleted, `+ `
added, `! ` changed; a side with no changes may omit its body entirely.
Unified format (`-u`) is the familiar `---`/`+++` header pair and
`@@ -start,count +start,count @@` hunks with ` `/`-`/`+` markers; a count of 1 may be
omitted; POSIX defers the detailed description to the GNU manual.
Headers are `"--- %s\t%s\n"` — path, one tab, then a timestamp; GNU diff writes a
full-resolution ISO timestamp, and `--label` replaces the whole field with an arbitrary
label.
This tab-plus-timestamp form is a mandatory part of classic unified headers, which
any git-header-oriented parser must strip.

`patch(1)` is deliberately liberal: it skips leading garbage, auto-detects the diff
form, selects file names from the headers (only the final pathname component unless
`-p num` says how many leading components to strip), applies hunks at an offset when
exact positions have drifted, and — for context forms — drops context lines down to a
maximum “fuzz”, with GNU patch documenting a default maximum fuzz factor of 2
(UNVERIFIED this session; see Methodology).
Reversed-patch detection prompts to apply with `-R`. Creation and deletion are
conventions, not structure: `/dev/null` names or epoch timestamps signal them
(UNVERIFIED for exact GNU heuristics), and GNU `-N` treats absent files as empty.
The `\ No newline at end of file` marker is a GNU diffutils convention (Incomplete
Lines), not POSIX text, and the message is locale-dependent — a reason parsers must
treat any `\ `-prefixed line as the marker, as git’s own `apply.c` does.
For binaries, GNU diff reports only `Binary files A and B differ`.

What the classic formats structurally cannot express is best summarized by Mercurial’s
own help text (see the Mercurial finding): executable bits and other permissions, copy
or rename information, changes in binary files, and creation or deletion of empty files.
Multi-file patches are bare concatenation with no set-level metadata, no identity of the
base being patched beyond file names and timestamps, and no machine-checkable schema.

### Git’s extended unified format

Git keeps unified hunks but adds a per-file extended header block after
`diff --git a/name b/name`: `old mode`/`new mode`, `deleted file mode`, `new file mode`,
`copy from`/`copy to`, `rename from`/`rename to`, `similarity index <n>%`,
`dissimilarity index <n>%`, and `index <hash>..<hash> <mode>` — the mode appearing on
the `index` line exactly when the file mode does not change.
Similarity is the percentage of unchanged lines, rounded down, with 100% reserved for
equal files. `/dev/null` appears only on `---`/`+++` lines, never in `diff --git`. Pure
renames and mode-only changes emit header-only sections with no `---`/`+++` and no
hunks, and the documentation warns that rename sets must be applied as a set, not
sequentially, because headers can swap names.
Symlinks are ordinary patches whose mode is `120000` and whose “content” is the target
path; gitlinks (`160000`) carry the submodule commit.

Two behaviors matter for byte fidelity.
Paths with unusual bytes are C-style quoted per `core.quotePath` — backslash escapes
plus octal for bytes above 0x80; double quotes, backslashes, and control characters are
always escaped, but a simple space is not “unusual”, so `diff --git a/x y b/x y` is
genuinely ambiguous and git’s own `apply.c` recovers names from `---`/`+++` or
`rename from`/`rename to` lines, falling back to a both-sides-same heuristic.
The no-newline marker is emitted by xdiff whenever the last record lacks `\n`, and
`git apply` accepts any `\ `-prefixed line as that marker without matching the localized
text.

Binary content has two representations: without `--binary`, a bare
`Binary files a/… and b/… differ` line (information-free); with `--binary`, a
`GIT binary patch` section containing a forward hunk and a reverse hunk (for `-R`), each
`literal <n>` or `delta <n>` (n = pre-deflate payload size), zlib-deflated and
base85-encoded with a per-line length prefix letter (`A`–`Z` = 1–26 bytes, `a`–`z` =
27–52). Applying a binary patch requires full blob oids on the `index` line —
`git apply` refuses without a full index line and verifies the preimage oid.
This makes `index` lines the anchoring mechanism of git patches: with `--full-index`
they name exact blobs, and `--3way` uses them to reconstruct a merge base (“attempt
3-way merge if the patch records the identity of blobs… and we have those blobs
available locally”).

Combined diff (`-c`/`--cc`) is a separate dialect for merges: `diff --combined`,
`index <p1>,<p2>..<res>`, optional `mode <m1>,<m2>..<m>`, hunk headers with
parents-plus-one `@` characters (`@@@ -r1 -r2 +res @@@`), and one marker column per
parent. It lists only files modified relative to all parents; `--cc` further drops hunks
where the result simply picked one parent.
The documentation is explicit that the format was deliberately shaped so it cannot be
fed to `patch -p1`: combined diffs are for reading, not applying.
Raw and porcelain forms round out the family: `--raw -z` gives NUL-framed
`:mode mode sha sha status[score]\tpath` records (status letters A C D M R T U, plus X
as “unknown, probably a bug”), and `--numstat` gives per-file added/deleted counts with
`-` for binaries — exactly the plumbing Metabrowser’s git adapter already consumes.

`git apply` is stricter than `patch(1)`: context must match exactly (no fuzz; `-C<n>`
can require less context but “by default no context is ever ignored”), though hunks may
land at an offset (“Hunk #N succeeded at L (offset M lines)”), with whitespace-tolerant
matching only under `--ignore-whitespace`, `--check` for dry runs, and
`--whitespace=fix|error` policies.
`git format-patch` wraps each commit in an mbox message: a
`From <sha> Mon Sep 17 00:00:00 2001` magic line, From/Date/Subject headers
(`[PATCH n/m]` series numbering), the commit message, a three-dash `---` separator whose
following commentary and diffstat are dropped on apply, the patch itself, and an RFC
3676 `-- ` signature defaulting to the git version number.
`git am` treats a three-dash line, a `diff -` line, or an `Index:` line as the start of
the patch.

### GitHub pull request representations

GitHub exposes three shapes.
First, media types on the PR and commit endpoints: `application/vnd.github.diff` (a git
unified diff; the docs simply defer to git-diff) and `application/vnd.github.patch`
(format-patch-style email text; the docs document the commit-level `.patch` URL suffix
and show its `From:` header, but never spell out the PR-level series composition).
The PR object’s `diff_url`/`patch_url` fields document the `…/pull/N.diff|.patch` web
URLs by example.
Larger diffs “may time out and return a 5xx status code”, and diffs with
binary data “will have no patch property”.

Second, the REST files list: `GET /repos/…/pulls/N/files` returns per-file objects —
`sha`, `filename`, `status`, `additions`, `deletions`, `changes`, `blob_url`, `raw_url`,
`contents_url`, optional `patch`, optional `previous_filename` — with `status` drawn
from `added, removed, modified, renamed, copied, changed, unchanged`. The response
“include[s] a maximum of 3000 files”, 30 per page by default and 100 max.
The `patch` string is bare hunk text: `@@` headers and body lines with no `diff --git`,
no `---`/`+++`, and no mode information.
Nothing in the documented schema carries modes, symlinks, or similarity scores; rename
information is only `status: renamed` plus `previous_filename`, and the `changed` /
`unchanged` statuses are not defined in terms of git’s letters (no documented equivalent
of T or U). A size threshold for omitting `patch` on large text files is not documented.

Third, documented limits.
The web UI’s diff limits page: no total diff beyond “20,000 lines that you can load or 1
MB of raw diff data”; per file 20,000 lines or 500 KB, with 400 lines and 20 KB
auto-loaded; at most 300 files rendered in a single diff; these numbers govern the UI,
and the API pages do not restate them.
The commonly cited 406 body naming a 20,000-line API cutoff is not in any official page
this research fetched (406 is documented only as “Unacceptable”). GraphQL exposes counts
and `changeType` per file but no patch text at all.
The lesson GitHub’s shape teaches: manifest-first with per-file hydration and explicit
truncation is what serving diffs at scale converges on — v1’s manifest, `availability`,
and `truncated`/`cursor` mirror it deliberately.

### JSON-native change formats

RFC 6902 JSON Patch is an array of operations (`add`, `remove`, `replace`, `move`,
`copy`, `test`) addressed by JSON Pointer, applied sequentially, with an explicit
all-or-nothing rule: any failed operation makes the whole patch unsuccessful.
The `test` operation is in-band anchoring — assert a value before changing it — and RFC
5789 layers the out-of-band version (ETag + `If-Match`, 409/412/422 status codes) on
top. RFC 7386 JSON Merge Patch (obsoleted editorially by RFC 7396) is the minimal
contrast: recursive object merge where `null` deletes a key, so arrays can only be
replaced wholesale and a value can never be set to null — simplicity purchased by giving
up expressiveness and preconditions entirely.
jsondiffpatch is a library convention with unnervingly compact encodings (`[new]` add,
`[old, new]` replace, `[old, 0, 0]` delete, `_`-prefixed original-index keys and
`['', idx, 3]` for array moves, embedded diff-match-patch text deltas), and is
reversible because deltas carry old values.

None of these address file trees, but they crystallize three design lessons v1 already
follows: patches need either in-band preconditions or out-of-band identity to fail
loudly on drift (v1: snapshot oids, `generation` tokens, and strict context matching in
the oracle); a registered, exact document shape makes patches machine-checkable before
application (v1: JSON Schema plus conformance corpus); and carrying old values buys
validation and reversibility at size cost (v1: hunks carry deleted lines, so modify
hunks are reversible in principle).

### Editor and agent edit formats

LSP `TextEdit`/`WorkspaceEdit` is the deterministic-editor pole.
Positions are zero-based line/character (UTF-16 code units by default, negotiable since
3.17); all edits in an array apply to the same original document state and “must never
overlap”; `documentChanges` sequences `TextDocumentEdit`s with explicit `CreateFile`,
`RenameFile`, `DeleteFile` resource operations, executed in order.
Anchoring is positional but pinned: edits carry an
`OptionalVersionedTextDocumentIdentifier`, and clients like VS Code fail an `applyEdit`
whose document “has changed in the meantime”.
`AnnotatedTextEdit`/`ChangeAnnotation` add machine-readable intent (label, description,
`needsConfirmation`) — the confirmation gate behind VS Code’s Refactor Preview.
VS Code’s own `WorkspaceEdit` mirrors all of this.

Agent-native formats abandon line numbers entirely.
OpenAI’s V4A `apply_patch` grammar (`*** Begin Patch` … `*** End Patch`, with
`*** Update File:`, `*** Add File:`, `*** Delete File:`, optional `*** Move to:`)
anchors hunks by context lines and `@@` markers that carry code context (class or
function headers, stackable when ambiguous), with the cookbook stating the design rule
outright: “we do not use line numbers in this diff format, as the context is enough to
uniquely identify code.”
The newer platform tool exposes typed `create_file`/`update_file`/`delete_file`
operations and explicitly delegates atomicity — all-or-nothing versus per-file — to the
integrating harness.
Aider’s benchmark-driven evolution says the same thing from the other side: its `diff`
format is SEARCH/REPLACE blocks; its `udiff` format keeps unified syntax but “tells GPT
not to include line numbers, and just interprets each hunk … as a search and replace
operation”, applies hunks flexibly (normalization, hunk splitting, whitespace tolerance
— disabling that flexibility gave a 9× increase in editing errors), and the switch to
udiff cut GPT-4 Turbo’s “lazy coding” dramatically (20% → 61% on their laziness
benchmark). Anthropic’s text-editor tool is the minimal content-anchored form:
`str_replace` requires `old_str` to match exactly and at exactly one location, with
prescribed errors for zero or multiple matches; `insert` takes a 1-indexed
`insert_line`. Morph’s fast-apply is a second family entirely: an abbreviated update
snippet with `// ... existing code ...` elisions plus an instruction, merged into the
full file by a dedicated apply model — semantic anchoring that trades determinism for
tolerance.

What agents need that classic patches lack, distilled: content anchors instead of line
numbers (models miscount and cannot track offsets across sequential edits); uniqueness
as a correctness gate rather than silent offset resolution; exact before/after payloads
with clear delimiters; explicit per-file verbs for create/delete/rename instead of
`/dev/null` conventions; flexible, repair-oriented application as a separate mode from
strict validation; staleness handling (LSP pins versions and fails; agents re-anchor by
content); and machine-readable intent metadata with optional confirmation.
Classic unified diffs carry none of these; git’s format carries the verbs and (via
`index` lines) identity, but keeps line numbers and silent offsets.

### Other version control systems (brief)

**Mercurial.** Plain `hg diff` is standard unified diff, and Mercurial’s help text is
explicit that this format “loses information” — executable status and permission bits,
copy or rename information, changes in binary files, and creation or deletion of empty
files — which is why the `--git` option and `diff.git` config enable git’s extended
format; it stays off by default only for compatibility with older tools, with a
documented warning that `hg export` silently drops metadata otherwise.
Independent confirmation that git’s extended header block is the de facto standard for
metadata-complete patch text.

**darcs.** Repositories are sequences of named primitive patches — hunk, addfile,
rmfile, adddir, rmdir, move, and token replace — each with an inverse, reordered via
commutation; dependencies are implicit in what fails to commute.
A patch is an algebraic object with explicit change semantics rather than text to
re-match, the maximal version of “semantic ops over textual hunks”; its cost is a format
nothing else can exchange.

**Jujutsu.** `jj diff` is a display command with `--git` (“Show a Git-format diff”),
`--color-words` (the default), `--stat`, and friends; jj defines no interchange format
of its own — its default backend is a git repository and interchange is git itself.
New VCS tooling is choosing git’s patch text rather than inventing another.

### File Diff Format v1 against the field

What v1 adds over every text format surveyed: resolved identity (`comparison_id`,
snapshot kinds with immutable oids or volatility `generation` tokens, explicit
`base_policy`) instead of filenames and timestamps; a change-set manifest with git’s
full A D M R C T U taxonomy, modes, entry types, and per-file `availability` states that
make gaps declared rather than silent; honest truncation (`truncated` + `cursor`, totals
with an `exact` flag); byte fidelity for non-UTF-8 paths and lines (`*_b64` beside
display projections) and for missing final newlines (`no_newline`); a JSON Schema with
`additionalProperties: false`, a conformance corpus binding the Python and browser
implementations, and an apply oracle that makes “fully modeled” testable — base tree in,
target tree out, byte-for-byte.
No surveyed format has the availability concept, the dual raw/display byte encoding, or
a cross-implementation conformance corpus; only RFC 6902 (media type + atomicity) and
LSP (typed spec) even have machine-checkable shapes, and neither covers file trees.

Probes run for this research fed real-world patch shapes to `parse_unified_patch` and
compared behavior against the survey.
Four defects were found and fixed during the research in commit `dbe4a7e` (parser
totalization plus regression tests):

1. Context-format input (`diff -c`) crashed — a Pydantic `ValidationError` escaped
   instead of the documented malformed-input-is-a-value behavior.
2. One-sided malformed sections generally (a section that never sees its `+++` line)
   produced schema-invalid `modified` entries with a single side.
3. GNU-style `---`/`+++` headers with tab-plus-timestamp kept the timestamp as part of
   the path (the same mechanism mangles svn-style ` (revision N)` suffixes).
4. Combined diffs (`--cc`, `@@@` hunks) parsed silently wrong: a `ready`, zero-hunk
   `modified` entry claiming no content change.

Verified as parsing correctly: git extended headers including rename/copy with C-style
quoted non-ASCII paths and similarity, mode-only changes, `/dev/null` creation and
deletion, `\ No newline` markers, `Binary files … differ` and `GIT binary patch`
detection (marked `availability: binary`), hunk-count validation, and byte-exact
non-UTF-8 line content.
Bounds are explicit and documented beside the constants (`MAX_PATCH_BYTES`,
`MAX_FILE_SECTIONS` in
[`patch_file.py`](../../../src/metabrowser/diff/adapters/patch_file.py)).

Still-open ingest gaps, confirmed by probe or by reading the parser against the survey:

- **GIT binary patch payloads.** The `literal`/`delta` base85 sections are detected but
  discarded; the file is honestly `binary`, but a `--binary` patch that fully contains
  the new content cannot hydrate an apply.
- **`index` lines are ignored entirely.** Both consequences matter: blob oids that
  [diff-sources-and-anchoring](../architecture/file-diff-format/diff-sources-and-anchoring.md)
  plans to use for the path-6 oid precheck are discarded, and the mode carried on the
  `index` line when modes don’t change is lost, so unchanged-mode executables parse as
  `100644`. Note the schema’s `contentRef.oid` pattern requires 40–64 hex chars, so
  abbreviated `index` oids cannot currently be stored at all — capturing them is a
  schema decision, not just a parser fix.
- **`git format-patch` mbox framing.** The `-- ` signature line after the final hunk
  breaks hunk-count validation and degrades the last file to `unsupported`; From/
  Subject/message metadata and the `---` commentary/diffstat region are not modeled.
  Since GitHub’s `.patch` media type is exactly this framing, this blocks a documented
  acquisition path.
- **GitHub REST bare-hunk `patch` strings.** With no `diff --git` or `---`/`+++` lines,
  the parser reports “no diff sections recognized”; ingesting the REST files endpoint
  needs a small adapter that builds the manifest from JSON fields and parses each
  `patch` string as bare hunks.
- **Combined diffs** are now refused rather than misparsed, but remain unmodeled (v1 has
  two snapshots plus `base_policy`; no multi-parent representation).
- Deliberately out: context, normal, and ed formats (see Recommendations).

## Key Insights

1. **Git’s extended unified format is the convergence point.** GitHub serves it,
   Mercurial documents plain unified as lossy and adopts it, jj emits it, and every
   pipeline in
   [diff-sources-and-anchoring](../architecture/file-diff-format/diff-sources-and-anchoring.md)
   already flows through it.
   Compatibility means fidelity to this one dialect, in both directions.
2. **Classic patch text has no identity; git smuggles it in `index` lines.** Blob oids
   are the only anchor a text patch carries (`--3way` and binary application depend on
   them), and our parser currently throws them away — the single highest-leverage ingest
   fix for the anchoring roadmap.
3. **A patch format and an apply policy are separate things.** The same unified text is
   applied strictly by the v1 oracle, strictly-with-offsets by `git apply`, and
   liberally with fuzz by `patch(1)`; aider found flexible application worth 9× fewer
   errors. v1 is right to keep a byte-exact oracle, and path 6 needs a distinct,
   explicitly-reported leniency mode rather than a looser oracle.
4. **Agent formats vote unanimously against line numbers.** V4A, aider, and
   `str_replace` all anchor by content with uniqueness gates; LSP keeps positions only
   by pinning document versions.
   v1’s hunks keep line numbers (correct for its role as a modeled git diff) — agent
   interop is an adapter that re-anchors, not a format change.
5. **Manifest-first with declared gaps is what scale forces.** GitHub’s 300-file UI
   rendering cap, 3000-file API cap, auto-loading 400 lines per file, and absent `patch`
   for binaries are ad-hoc versions of what v1 makes structural: `availability`,
   `truncated`/`cursor`, inexact totals.
6. **Every format that omits old content gives up validation.** JSON Merge Patch,
   GitHub’s REST metadata, and LSP edits cannot check what they replace; RFC 6902 `test`
   ops, git context lines, SEARCH blocks, and v1 hunks can.
   Carrying the old bytes is what makes the apply oracle possible — keep it.
7. **The lossiest surface we must speak is GitHub REST** (no modes, no symlinks, no
   similarity scores, undefined `changed`/`unchanged`); treat it as manifest metadata
   plus bare hunks, never as a source of record for entry types.

## Comparison Matrix

Legend: ● full support, ◐ partial or conventional, ○ absent.
“v1” is File Diff Format v1 as implemented today.

| Capability | POSIX unified/context | Git extended unified | GitHub REST files | RFC 6902 JSON Patch | LSP WorkspaceEdit | Agent blocks (V4A/aider) | File Diff v1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Multi-file change sets | ◐ concatenation only | ● per-file sections | ● array, capped 3000 | ◐ one target document | ● documentChanges | ● per-file verbs | ● manifest + patches |
| Renames + similarity | ○ | ● from/to + score | ◐ status + previous_filename, no score | ◐ move op | ◐ RenameFile op | ◐ V4A Move to | ● kind + similarity |
| Mode/permissions | ○ | ● mode lines + index-line mode | ○ | n/a | ○ | ○ | ● git modes |
| Symlinks | ○ | ● mode 120000, target as content | ○ | n/a | ○ | ○ | ● entry_type |
| Binary content | ○ note only (GNU) | ● literal/delta base85 | ◐ detected via absent patch | n/a | ○ | ○ | ◐ declared; payload via content refs, no text encoding |
| Non-UTF-8 paths | ◐ unspecified | ● C-style octal quoting | ○ JSON strings | n/a | ○ URIs | ○ | ● path_b64 |
| No-newline fidelity | ◐ GNU marker | ● marker | ◐ marker inside patch strings | n/a | ● exact text | ◐ exact payloads | ● no_newline flag |
| Merge/multi-parent | ○ | ◐ combined diff, read-only | ○ | ○ | ○ | ○ | ○ first_parent policy only |
| Apply/validation semantics | ◐ fuzz + offsets | ● strict context, offsets, --3way, --check | ○ display only | ● test ops, all-or-nothing | ◐ no-overlap, versioned, client applies | ◐ harness-defined, uniqueness gates | ● byte-exact oracle + availability contract |
| Streaming/truncation for huge diffs | ○ | ○ | ● pagination + documented limits | ○ | ○ | ○ | ● truncated/cursor, deferred/too_large |
| Identity/anchoring (what base?) | ○ names + timestamps | ◐ index blob oids (full with --full-index) | ◐ PR head/base shas in context | ◐ test ops (+ ETags per RFC 5789) | ● URI + document version | ◐ content anchors | ● snapshot oids + generation tokens; honest unanchored mode |
| Machine-validatable schema | ○ | ○ | ◐ OpenAPI shape | ● media type + RFC | ● typed spec | ○ | ● JSON Schema + conformance corpus |

## Recommendations

**(a) Ingest compatibility surface — what we must parse.** Git extended unified diff is
the surface, in all the concrete costumes it arrives in: `git diff` output,
GitHub/GitLab `.diff` downloads, `git format-patch`/GitHub `.patch` mbox framing
(headers, `---` commentary and diffstat, `-- ` signature), plain GNU/POSIX unified diffs
with tab-timestamps or `--label` headers, and GitHub REST file objects with bare-hunk
`patch` strings (via a small JSON adapter, not the text parser).
Combined diffs should be recognized and refused with a precise warning (now the behavior
post-`dbe4a7e`), not modeled.
Context, normal, and ed formats should stay out: `patch(1)` itself is the only remaining
consumer, every producer that emits them can emit unified, and a user with a context
diff can convert it externally; a recognizer that names the format in the warning is
worth having, a parser is not.

**(b) Emit surface — what we should write.** One emitter: hydrated `ChangeSetDocument` →
git-applyable extended unified text (quoted paths, mode lines, rename/copy headers with
similarity, `/dev/null` conventions, no-newline markers; `index` lines with full oids
when content refs carry them; `Binary files differ` placeholders for binary changes
until payload encoding is decided).
This is currently missing entirely — `metabrowser.diff` has parse and apply but no
emitter — and backward compatibility argues it is half the format’s value: it turns any
source (a GitHub PR, a worktree comparison, a future edit-history source) into text that
`git apply`, `patch(1)`, reviewers, and other tools accept.
Round-trip tests are the gate: `parse(emit(doc))` must equal `doc` for hydrated
documents, and `git apply` of emitted text onto the corpus base trees must reproduce the
target trees the oracle produces (equal `tree_hash`). Emitting format-patch mbox framing
and combined diffs is out of scope; emitting the manifest as `--raw`/`--numstat`
analogues is cheap and optional.

**(c) Parser gaps against the survey** (details and probe evidence in Findings): capture
`index` lines — oids for the path-6 precheck and the mode when modes don’t change —
which requires a schema decision because abbreviated oids don’t fit `contentRef.oid`
today; strip format-patch/mbox framing so GitHub `.patch` files parse cleanly and the
signature can’t corrupt the last file; add the REST files adapter for bare hunks; decide
GIT-binary-payload policy (minimum: record literal/delta kind and sizes so
`availability: binary` can say what full support would need; maximum: decode
base85+deflate into inline content refs, bounded); keep combined-diff refusal.
The four defects found by this research’s probes are already fixed in `dbe4a7e`.

**(d) Agent workflow needs beyond classic patches.** Two additions, neither a change to
the hunk model: an **anchored-apply mode** distinct from the oracle — `git apply`-style
offset search with per-hunk applied/offset/failed reporting (and optionally
whitespace-tolerant matching), which is also exactly the path-6 “annotate each file
clean or conflicted” engine; and an **agent-edit adapter** that accepts content-anchored
edits (SEARCH/REPLACE or V4A blocks) against a named snapshot, resolves them to
line-numbered hunks with the uniqueness gate agents rely on (exactly-one-match or a
precise error), and emits a v1 document — giving agent edits identity, validation, and
rendering for free. v1 already has what agent formats lack structurally: explicit file
verbs, snapshot identity, `generation` staleness tokens, and declared availability.
Worth considering, not urgent: an optional per-file or per-document annotation field
(intent label, needs-confirmation) mirroring LSP `ChangeAnnotation`, once a consumer
exists.

**(e) Does any existing format make part of v1 redundant?** No.
The overlap with git’s model is by design — kinds, modes, and similarity are git’s
semantics restated in validatable JSON, which is what makes ingest and emit lossless.
GitHub’s REST file object is a strict subset of the v1 manifest (no modes, entry types,
similarity, or availability), so it validates the manifest design rather than replacing
it. JSON Patch/Merge Patch operate on JSON values, not file trees; LSP edits assume a
live editor session; agent blocks assume a harness.
The one deliberate omission to keep deliberate: commit-level metadata (author, message,
series position) belongs to sources and providers (paths 4 and 7), not to the comparison
document — format-patch ingestion should surface it as source metadata, not grow the
schema.

## Next Steps

1. Track beads for the emitter (b), the ingest gaps (c), and the anchored-apply mode
   (d), sequenced emitter-first since round-trip tests then pin every later parser
   change.
2. Resolve the schema question for claimed anchors: where abbreviated `index` oids and
   index-line modes live (likely additive optional fields plus corpus cases; a
   `schema_version` bump only if validation semantics change).
3. Extend the conformance corpus with the survey-derived shapes as they land:
   format-patch framing, REST bare hunks, binary-payload declarations, and emit
   round-trip cases.
4. Decide the viewer’s highlighting architecture from the appendix: hunk-local
   highlighting as the unanchored default, whole-file highlight-then-diff when content
   refs resolve, full highlighting for added files now.
5. Fold the agent-edit adapter into the general diff rendering plan
   ([plan spec](../../specs/active/plan-2026-08-17-general-diff-rendering.md)) once the
   anchored-apply engine exists.

## Appendix: Syntax Highlighting in Diff Viewers

Two architectures exist.
**Highlight-then-diff** lexes or parses both complete file versions, then maps colors
onto diff lines: Monaco/VS Code (each diff side is a full `ITextModel` tokenized like
any buffer, with the rewritten diff engine layering `innerChanges` character-level
mappings on top), GitLab (server-side Rouge highlighting of the old and new blobs,
cached in Redis, with a documented plain-text fallback for huge files), Gitea since PR
#33766 (moved off per-hunk highlighting precisely because it “breaks multi-line
constructs like block comments and strings”), and difftastic as the limiting case
(tree-sitter parses whole files and the diff is computed on the syntax trees, so
highlighting falls out of parsing).
Lexer state flows from the top of the file, so block comments, strings, and heredocs
highlight correctly wherever hunks start; the cost is fetching both blobs and CPU, hence
caching and size fallbacks.
**Diff-then-highlight** lexes only the patch text, hunk by hunk, guessing language from
the filename: delta (a pager consuming patch text through a pipe, syntect-based, with
Levenshtein-inferred within-line emphasis) and Gitea before 2025. It needs no repository
access and scales with patch size, but the lexer starts cold at each hunk, so a hunk
opening mid-construct mis-tokenizes.
GitHub documents that PR diffs are syntax-highlighted (server-side and deferred — plain
text swapped for highlighted “as soon as they are ready”), with linguist for language
detection and tree-sitter for highlighting, but does not document hunk-local versus
whole-file for the PR view; its imperfect highlighting of hunks starting inside
multi-line constructs is observed behavior only.
In every viewer, intraline emphasis is an orthogonal second pass — pair removed/added
lines, compute character- or word-level changed spans, render as background styling on
top of whatever token colors exist (Monaco `innerChanges`, delta’s edit inference, jj’s
`--color-words`).

A 2026-08-25 follow-up reviewed the current Metabrowser implementation and pinned VS
Code source. File Diff Format v1 does not contain intraline spans, syntax tokens, or
split-row pairings, and it should not gain them for this feature.
They are derived browser enrichments: the patch remains the exact source record, while
the active renderer can replace or discard enrichment after an algorithm, theme, layout,
timeout, or size-policy change.
The VS Code-derived algorithm and ownership decision are recorded in the
[web diff viewer research](research-2026-07-17-web-diff-viewer-architecture.md#2026-08-25-addendum-intraline-refinement)
and Phase 4 of the
[general diff rendering plan](../specs/active/plan-2026-08-17-general-diff-rendering.md#phase-4-vs-code-derived-intraline-refinement).

Implications for the Metabrowser viewer:

- **Added whole files can be fully and correctly highlighted today, without anchoring**:
  an added file’s hunks contain the entire file, so whole-file lexing needs nothing but
  the patch. Render with clean full highlighting plus an “added” indicator — left gutter
  bar and a light added-tint background — keeping token colors as foreground and the
  add-tint strictly as background so the two layers compose.
  The same holds for deleted files.
- **Mixed hunks get optional hunk-local highlighting** (delta’s architecture) as the
  unanchored default, accepting the documented mid-construct caveat; when a comparison
  is anchored and content refs resolve, upgrade to whole-file highlight-then-diff
  (GitLab/Gitea architecture), with caching and a size fallback — the same availability
  machinery that gates patches gates the upgrade.
- **Per-file tabs with inline and rendered presentations**: the rendered (Markdown) tab
  needs whole-file content, which exists for added files from the patch alone and
  otherwise exactly when the comparison is anchored — so tab availability should be
  driven by the file’s content resolvability, not by file type; the inline tab always
  works. Intraline emphasis stays an overlay layer independent of tokenization, so it
  works identically in both highlighting modes.

## References

Project sources:

- [File Diff Format v1 contract](../architecture/file-diff-format/file-diff-format.md)
  (repo doc)
- [Diff sources, context, and anchoring](../architecture/file-diff-format/diff-sources-and-anchoring.md)
  (repo doc)
- [file-diff.schema.json](../../../src/metabrowser/data/file-diff-format/file-diff.schema.json)
  (schema)
- [patch_file.py parser](../../../src/metabrowser/diff/adapters/patch_file.py),
  [apply.py oracle](../../../src/metabrowser/diff/apply.py) (source)
- [General diff rendering plan](../../specs/active/plan-2026-08-17-general-diff-rendering.md)
  (spec)

POSIX and GNU (spec/manual):

- [POSIX diff](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/diff.html),
  [POSIX patch](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/patch.html)
  (spec)
- GNU diffutils manual:
  [Detailed Unified](https://www.gnu.org/software/diffutils/manual/html_node/Detailed-Unified.html),
  [Detailed Context](https://www.gnu.org/software/diffutils/manual/html_node/Detailed-Context.html),
  [Incomplete Lines](https://www.gnu.org/software/diffutils/manual/html_node/Incomplete-Lines.html),
  [index](https://www.gnu.org/software/diffutils/manual/html_node/index.html) (manual)

Git (official docs / source tree):

- [diff-generate-patch](https://git-scm.com/docs/diff-generate-patch),
  [diff-format](https://git-scm.com/docs/diff-format),
  [git-apply](https://git-scm.com/docs/git-apply),
  [git-format-patch](https://git-scm.com/docs/git-format-patch),
  [git-diff](https://git-scm.com/docs/git-diff) (official docs)
- git source: [apply.c](https://raw.githubusercontent.com/git/git/master/apply.c),
  [diff.c](https://raw.githubusercontent.com/git/git/master/diff.c),
  [base85.c](https://raw.githubusercontent.com/git/git/master/base85.c),
  [xdiff/xutils.c](https://raw.githubusercontent.com/git/git/master/xdiff/xutils.c),
  [core.adoc (quotePath)](https://raw.githubusercontent.com/git/git/master/Documentation/config/core.adoc)
  (source)

GitHub (official docs):

- [Pulls REST](https://docs.github.com/en/rest/pulls/pulls),
  [Commits REST](https://docs.github.com/en/rest/commits/commits),
  [Media types](https://docs.github.com/en/rest/using-the-rest-api/media-types),
  [Repository/diff limits](https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits),
  [GraphQL pulls](https://docs.github.com/en/graphql/reference/pulls)

JSON formats (RFC / repo docs):

- [RFC 6902 JSON Patch](https://www.rfc-editor.org/rfc/rfc6902),
  [RFC 7386 JSON Merge Patch](https://www.rfc-editor.org/rfc/rfc7386),
  [RFC 5789 HTTP PATCH](https://www.rfc-editor.org/rfc/rfc5789) (RFC)
- [jsondiffpatch delta docs](https://github.com/benjamine/jsondiffpatch/blob/master/docs/deltas.md)
  (repo docs)

Editor and agent formats (spec / vendor docs):

- [LSP 3.17 specification](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/)
  (spec)
- [OpenAI GPT-4.1 prompting guide (V4A)](https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide),
  [apply_patch tool guide](https://developers.openai.com/api/docs/guides/tools-apply-patch)
  (vendor docs)
- [aider edit formats](https://aider.chat/docs/more/edit-formats.html),
  [aider unified diffs write-up](https://aider.chat/docs/unified-diffs.html) (project
  docs)
- [Anthropic text editor tool](https://platform.claude.com/docs/en/docs/agents-and-tools/tool-use/text-editor-tool),
  [Morph apply](https://docs.morphllm.com/models/apply) (vendor docs)
- [VS Code API (WorkspaceEdit)](https://code.visualstudio.com/api/references/vscode-api)
  (official docs)

Other VCS (official wiki/docs):

- [Mercurial GitExtendedDiffFormat](https://wiki.mercurial-scm.org/GitExtendedDiffFormat),
  [darcs Theory](http://darcs.net/Theory),
  [darcs Using/Model](https://darcs.net/Using/Model),
  [Understanding Darcs/Patch theory](https://en.wikibooks.org/wiki/Understanding_Darcs/Patch_theory),
  [jj CLI reference](https://docs.jj-vcs.dev/latest/cli-reference/),
  [jj git compatibility](https://docs.jj-vcs.dev/latest/git-compatibility/)

Highlighting appendix (official blogs/docs/source):

- GitHub:
  [syntax-highlighted diffs (2014)](https://github.blog/2014-12-09-syntax-highlighted-diffs/),
  [deferred syntax highlighting (2022)](https://github.blog/changelog/2022-06-24-deferred-syntax-highlighting/),
  [code view (2023)](https://github.blog/2023-06-21-crafting-a-better-faster-code-view/),
  [linguist](https://github.com/github-linguist/linguist)
- VS Code release notes [v1.80](https://code.visualstudio.com/updates/v1_80),
  [v1.81](https://code.visualstudio.com/updates/v1_81),
  [v1.82](https://code.visualstudio.com/updates/v1_82); vscode source
  [editorCommon.ts](https://github.com/microsoft/vscode/blob/main/src/vs/editor/common/editorCommon.ts),
  [rangeMapping.ts](https://github.com/microsoft/vscode/blob/main/src/vs/editor/common/diff/rangeMapping.ts)
- [delta](https://github.com/dandavison/delta) and
  [manual](https://dandavison.github.io/delta/);
  [difftastic manual](https://difftastic.wilfred.me.uk/) and
  [author’s algorithm post](https://www.wilfred.me.uk/blog/2022/09/06/difftastic-the-fantastic-diff/)
- GitLab:
  [highlighting docs](https://docs.gitlab.com/user/project/repository/files/highlighting/),
  [diffs dev docs](https://docs.gitlab.com/development/merge_request_concepts/diffs/),
  [gitlab-org issue 432554](https://gitlab.com/gitlab-org/gitlab/-/issues/432554),
  [gitlab-org merge request 53768](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/53768);
  [Gitea pull 33766](https://github.com/go-gitea/gitea/pull/33766)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
