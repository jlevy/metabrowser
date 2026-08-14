# Research: Markdown Link Navigation Across Repository Browsers

**Date:** 2026-08-13

**Author:** Metabrowser maintainers

**Status:** Complete

## Executive Summary

Markdown repositories do not have one link language.
They have a standard URL language, used by CommonMark and GitHub, plus optional dialects
that add lookup rules.
Obsidian wiki links are the most important additional dialect: `[[Note]]` means “find
the best matching note in this vault,” not “resolve this URL relative to the current
document.” Static-site generators introduce a third category in which a source file path
is compiled into a published page route.

Metabrowser should support these conventions through a layered resolver rather than a
single fuzzy path heuristic:

1. Parse the authored syntax without losing the original target.
2. Apply exact URL and filesystem semantics first.
3. Apply an explicit or confidently detected dialect adapter.
4. Return a typed internal, external, missing, ambiguous, unsafe, or unsupported result.
5. Navigate with a real browser pathname and reserve the fragment for the location
   inside the selected document.

The recommended canonical rendered-file URL is
`/view/<served-root-relative-path>#<document-fragment>`. For example,
`/view/docs/development.md#browser-development` identifies both a file and a heading.
This removes the current collision in which `location.hash` sometimes means a selected
file and sometimes means a heading.
It also makes ordinary sibling and parent-relative links behave naturally in new tabs,
on refresh, and with browser back and forward.

The implemented baseline covers standard Markdown links, images, headings, canonical
routes, history, and clear broken-link states together with an automatic Obsidian
Markdown-plugin adapter for wiki links, headings, named blocks, attachments, and media
embeds. Rich transclusion, backlinks, and generator-specific compilation remain later
capabilities without weakening the navigation contract.

## Questions Answered

1. Which link and anchor syntaxes occur in CommonMark, GitHub repositories, GitHub
   wikis, published documentation sites, editors, and Obsidian vaults?
2. How does each environment resolve relative paths, root-relative paths, extensionless
   targets, fragments, images, embeds, and ambiguous names?
3. Which behaviors can coexist automatically, and which require an explicit dialect or
   adapter?
4. What browser URL should represent a selected repository file and its in-document
   location?
5. How should Metabrowser classify internal files, external URLs, missing or ambiguous
   targets, non-Markdown assets, and unsafe paths?

## Scope

The primary scope is navigation among files under one Metabrowser served root.
The research covers standard inline and reference Markdown links, GitHub repository and
heading conventions, GitHub wikis, Obsidian wiki links and embeds, and representative
editor and static-site behavior.
It includes URL design, resolution order, security, accessibility, history, and
compatibility testing.

Editing, backlink indexing, graph visualization, complete transclusion rendering, remote
repository cloning, and exact compilation of every static-site generator are follow-up
capabilities. They are considered here only where the initial contract must leave room
for them.

## Decision Addendum: GitHub-Compatible Defaults

**Decision date:** 2026-08-13

The first implementation will make ordinary GitHub repository links work automatically,
without a repository-type setting, dialect selector, or whole-tree index.
This is the baseline against which later adapters are measured.

The canonical browser route remains `/view/<path>#<fragment>`, rather than exposing a
selected file directly at `/<path>`. Both shapes let a bare link such as `other.md` use
the browser’s relative-URL algorithm, but `/view/` is the safer default for a repository
browser:

| Route shape | Fit for Metabrowser |
| --- | --- |
| `/view/docs/guide.md` | Keeps browsed files in one explicit namespace, leaves `/api`, `/raw`, `/static`, and plugin routes unambiguous, and makes copied URLs recognizable as Metabrowser views. |
| `/docs/guide.md` | Resembles a published site, but lets arbitrary repository paths collide with application routes and makes a leading `/` ambiguous between repository content and the application origin. |

A future site-preview adapter may expose or emulate published routes when a site’s
configuration defines them.
It must not replace the repository-browser default.

### Phase 1 Default

Every standard Markdown target that GitHub resolves within the current repository should
resolve the same way in Metabrowser when that target exists beneath the served root:

- bare, `./`, and `../` paths resolve from the source document’s directory;
- a leading single `/` resolves from the served root, while `//host/path` remains a
  network URL;
- exact files, folders, fragments, queries, spaces, Unicode, reference-style links,
  sanitized raw-HTML links, images, and other local resources retain their distinct
  intents;
- fragment-only links remain in the current document;
- safe external URLs remain external; and
- missing, malformed, or root-escaping targets remain visible but do not acquire a
  guessed destination.

The final rendered element receives a canonical `href`, such as
`/view/docs/other.md#setup`, rather than relying only on a JavaScript click callback.
Normal clicks can use in-app navigation, while copy-link, keyboard activation,
modifier-click, middle-click, new tabs, reload, and browser history retain ordinary web
behavior. Embedded local resources use the safe raw-resource route because `/view/`
returns the application shell.

Exact standard links do not gain implicit `.md`, basename search, case folding, README
selection, or fuzzy matching.
Those fallbacks would make a broken GitHub link appear to work locally and would
introduce platform-dependent results.
Static-site source conventions and absolute GitHub `/blob/` URLs remain adapter work
rather than blocking the zero-configuration repository baseline.

### Implemented Obsidian Compatibility

Obsidian compatibility reuses the same route, navigation, safe-resource, and
resolved-result contracts.
A source-aware Markdown-plugin adapter parses self-identifying wiki syntax such as
`[[Note]]`, `[[Note#Heading|Label]]`, and `![[asset.png]]`, then produces the same
structured link intent used by standard anchors.

Wiki targets add optional `.md` lookup and a vault-wide basename or path-suffix search
only when the result is unique.
Duplicate note names remain ambiguous and are never resolved by arbitrary ordering.
Heading and named-block targets map to stable source-derived anchors in the rendered
document. Image and media embeds use the bounded safe-resource path; recursive note
transclusion, backlinks, and graph indexing remain later work.

Exact source-directory, explicit relative, and explicit vault-root results may resolve
while the file catalog is still growing.
Unique basename and path-suffix results remain visibly pending until the inventory is
complete, after which the still-current render is enhanced or reports every viable
ambiguity candidate.
This avoids using discovery order as a hidden tie-breaker.

Recognizing parsed wiki syntax does not change the meaning of ordinary Markdown links.
An `.obsidian/` directory may improve vault context later, but standard
GitHub-compatible resolution remains exact and automatic in every repository.
This addendum supersedes the earlier suggestion that the baseline expose `auto`,
`repository`, and `obsidian` as user-selectable policies.
Standard anchors and parsed wiki syntax identify themselves; only later site adapters
may require configuration or project detection.

### Clean-Break Implementation Directive

**Decision date:** 2026-08-13

The approved implementation plan makes a clean break from the current link router and
SDK shape. It supersedes the implementation-specific compatibility recommendations later
in this dated research record:

- `/view/<path>#<fragment>` is the only selected-file route.
  The old `/#<path>` form is deleted rather than read, migrated, redirected, or written
  in parallel.
- The navigation API may be redesigned and all bundled callers migrated atomically;
  preserving `openPath` is not an acceptance requirement.
- Exact GitHub repository links and standard Obsidian note, heading, named-block,
  occurrence-label, and media wiki-links are all required for the end-to-end baseline.
  Their phases describe dependency order, not optional product scope.
- Obsidian named-block links must land on real source-derived DOM targets.
  They are not deferred as unsupported metadata.
- Published-site adapters, remote GitHub URL localization, source-line locations,
  backlinks, graph features, metadata-alias lookup, multi-root navigation, and full note
  transclusion remain separate future features.

The comparative findings below remain useful evidence.
Where a later recommendation mentions legacy hash migration, preserving the old SDK, or
treating Obsidian navigation as a later optional release, this directive and the active
feature plan control.

## Findings

### Four Independent Layers

Link compatibility becomes tractable when four concerns remain separate.

| Layer | Question | Example |
| --- | --- | --- |
| Syntax | What did the author write? | `[Guide](guide.md)`, `[[Guide]]`, or `{% link guide.md %}` |
| Interpretation | Which link language applies? | URL-relative, vault lookup, or static-site source link |
| Resolution | What resource, if any, is selected? | Exact file, unique note, remote URL, or ambiguous candidates |
| Navigation | How does the browser represent and open it? | Canonical `href`, history entry, render, and fragment scroll |

CommonMark defines syntax and emits a link destination.
The web platform defines how a relative URL combines with a document base URL. GitHub
adds repository context and a heading-ID algorithm.
Obsidian adds vault lookup, aliases, block identifiers, and embeds.
A browser can support all of these only if it does not mistake a syntax rule for a
universal filesystem rule.

### Standard Markdown and Web URLs

[CommonMark 0.31.2](https://spec.commonmark.org/0.31.2/) defines these relevant forms:

| Form | Example | Resolution consequence |
| --- | --- | --- |
| Inline link | `[Guide](../guide.md "Guide")` | Destination is a URL string; title does not affect navigation. |
| Full reference | `[Guide][guide]` plus `[guide]: ../guide.md` | Same destination semantics after reference lookup. |
| Collapsed reference | `[Guide][]` | Label supplies the reference identifier. |
| Shortcut reference | `[Guide]` plus `[Guide]: ../guide.md` | Can resemble ordinary bracketed prose before parsing. |
| Image | `![Diagram](../assets/map.svg)` | Destination identifies an embedded resource rather than a navigation action. |
| Autolink | `<https://example.com>` | Explicit external URL. |
| Fragment | `[Setup](#setup)` | Location in the current document. |
| Query and fragment | `[Source](file.md?plain=1#L14)` | Path, query, and fragment are distinct URL components. |
| Raw HTML | `<a href="guide.md">Guide</a>` | Renderer and sanitizer policy determine whether it survives. |

The [WHATWG URL Standard](https://url.spec.whatwg.org/) resolves a relative URL against
the document base URL. The
[HTML Standard’s document-base rules](https://html.spec.whatwg.org/multipage/urls-and-fetching.html#document-base-urls)
make the page URL the fallback base when no `<base>` element is present.
CommonMark does not define repository roots, implicit `.md` suffixes, note-name search,
or what a web server should return for a directory.

The standard URL vocabulary includes distinctions that a resolver must preserve:

- `guide.md` and `./guide.md` are relative to the source document’s directory.
- `../guide.md` traverses one source directory upward.
- `/guide.md` is relative to the URL origin in an ordinary browser.
  Repository tools commonly reinterpret it as repository or workspace root.
- `#setup` retains the current path and changes only the fragment.
- `guide.md#setup` selects a file and a fragment.
- `guide.md?mode=raw#L14` also carries a query.
  The query is not part of the filename.
- `guide%20one.md` represents an encoded path segment.
  Encoded separators and multiple decoding passes must not become a way around the
  served-root boundary.

[GitHub Flavored Markdown](https://github.github.com/gfm/) is a strict CommonMark
superset. Its autolink extension recognizes more bare URLs and email addresses, but it
does not add Obsidian-style wiki-link resolution.

### GitHub Repository Markdown

GitHub’s
[basic writing and formatting documentation](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax)
documents source-file-relative links and images using bare, `./`, and `../` paths.
GitHub rewrites those destinations with the branch or commit context of the rendered
file. Leading `/` paths are repository-root-relative in repository content.
GitHub recommends relative paths because they continue to work in clones.

Important GitHub conventions are:

- Link destinations normally name exact repository files and retain their extensions.
- A directory destination opens repository navigation rather than implicitly choosing a
  Markdown file.
- The rendered URL includes repository, revision, and path context, such as
  `/OWNER/REPOSITORY/blob/REVISION/docs/guide.md`.
- A branch URL follows the branch as it changes.
  A URL containing a full commit SHA is a permalink to one revision, as described in
  [Getting permanent links to files](https://docs.github.com/en/repositories/working-with-files/using-files/getting-permanent-links-to-files).
- GitHub-specific cross-branch and cross-repository URL paths exist, but a local
  repository browser cannot safely reinterpret a path that escapes its served root.
- Ordinary repository Markdown does not interpret `[[Note]]` as a link.

GitHub creates heading IDs by lowercasing letters, replacing spaces with hyphens,
removing most punctuation and other whitespace, removing formatting markup, and
suffixing duplicate IDs with `-1`, `-2`, and so on.
Authors can also place a sanitized HTML anchor such as `<a name="stable-name"></a>`.
These rules make `guide.md#installation` useful across GitHub and local renderers that
use a compatible slugger.

GitHub’s code viewer also uses fragments such as `#L14` and `#L14-L20`; adding
`?plain=1` can show a Markdown file’s source with addressable lines.
These are viewer locations, not Markdown heading rules.
Metabrowser should recognize them only in a source-view or GitHub-URL adapter so a
genuine rendered anchor named `L14` is not silently reinterpreted.

GitHub-rendered source and a published documentation site are separate environments.
For example, the GitHub Docs repository uses extensionless, root-relative authored URLs
that its publishing system later adds locale and version context to, as documented in
[Using Markdown and Liquid in GitHub Docs](https://docs.github.com/en/contributing/writing-for-github-docs/using-markdown-and-liquid-in-github-docs).
That project convention is not a general GitHub Markdown rule.

### GitHub Wikis Are a Separate Repository and Renderer

A GitHub wiki is backed by a separate Git repository.
GitHub’s
[wiki editing documentation](https://docs.github.com/en/communities/documenting-your-project-with-wikis/editing-wiki-content)
shows ordinary Markdown links when a page uses Markdown.
It also documents `[[Nameofwikipage|Link Text]]` for pages written with MediaWiki
syntax. That syntax should not be treated as evidence that ordinary GitHub Markdown
supports wiki links.

Wiki page filenames determine page titles and the extension selects the renderer.
Relative links cannot cross automatically between the project repository and the wiki
repository. A Metabrowser session should therefore treat a checked-out wiki as its own
served root unless an explicit multi-root map says otherwise.

### Obsidian Markdown

Obsidian supports standard Markdown links and an additional vault-oriented language.
The official
[Internal links](https://github.com/obsidianmd/obsidian-help/blob/b8cf62bc2aac486dd0e2ec4cdaf7fa518b1a10a0/en/Linking%20notes%20and%20files/Internal%20links.md)
documentation defines the core forms:

| Form | Meaning |
| --- | --- |
| `[[Note]]` | Open a Markdown note; `.md` is optional. |
| `[[Folder/Note]]` | Open a note using a vault path. |
| `[[Note\|Label]]` | Open the target but display an alias at this occurrence. |
| `[[#Heading]]` | Open a heading in the current note. |
| `[[Note#Heading]]` | Open a heading in another note. |
| `[[Note#Parent#Child]]` | Identify a heading through its heading hierarchy. |
| `[[Note#^block-id]]` | Open a named block. |
| `![[Note]]` | Embed another note. |
| `![[Note#Heading]]` | Embed a note section. |
| `![[image.png\|640]]` | Embed media, with optional display metadata. |
| `[Note](Folder/Note.md)` | Standard Markdown alternative; spaces are URL-encoded. |

Non-Markdown attachments require their extension.
Obsidian can embed images, audio, video, PDFs, lists, canvases, whole notes, headings,
and blocks. Its
[Embed files](https://github.com/obsidianmd/obsidian-help/blob/b8cf62bc2aac486dd0e2ec4cdaf7fa518b1a10a0/en/Linking%20notes%20and%20files/Embed%20files.md)
documentation includes media dimensions and PDF parameters.
Opening a link and fully transcluding a target are therefore different actions even when
they share a target resolver.

Obsidian’s **New link format** setting controls what it writes: shortest unique path,
path relative to the current file, or full path from the vault root.
Its **Use Wikilinks** setting chooses wiki syntax or standard Markdown syntax for newly
generated links and embeds.
Existing files can contain all of the forms at once.

The public API exposes `getFirstLinkpathDest(linkpath, sourcePath)` as a “best match”
operation and `fileToLinktext` as a way to produce a unique link text.
The exact tie-breaking algorithm is not a public compatibility contract.
Metabrowser should match unambiguous Obsidian links and disclose ambiguity rather than
silently choosing one of several same-named notes.

Aliases belong to note metadata and authoring.
Obsidian normally writes a canonical target plus display text, such as
`[[Canonical note|Friendly name]]`; its
[Aliases documentation](https://github.com/obsidianmd/obsidian-help/blob/b8cf62bc2aac486dd0e2ec4cdaf7fa518b1a10a0/en/Linking%20notes%20and%20files/Aliases.md)
does not make `[[Friendly name]]` a universally portable target.
Aliases can improve search, completion, and candidate labels without becoming an unsafe
hidden fallback.

The
[Obsidian URI scheme](https://github.com/obsidianmd/obsidian-help/blob/b8cf62bc2aac486dd0e2ec4cdaf7fa518b1a10a0/en/Extending%20Obsidian/Obsidian%20URI.md)
adds URLs such as `obsidian://open?vault=Vault&file=Folder%2FNote`. These launch an
external application and are not internal browser paths.
They require a deliberate user gesture and an explicit custom-scheme allowlist.

### Editors and Static-Site Generators

Other widely used tools demonstrate why extensionless fallback cannot be global.

| Tool | Source-link behavior | Extra behavior relevant to Metabrowser |
| --- | --- | --- |
| [VS Code](https://code.visualstudio.com/docs/languages/markdown) | Bare, `./`, and `../` paths are source-relative; `/` is workspace-root-relative. | Heading completion, workspace heading search, link validation, and opt-in link updates on rename. No built-in wiki-link language. |
| [GitLab project Markdown](https://docs.gitlab.com/user/markdown/) | Exact relative paths navigate the project repository. | The project wiki is a separate repository. |
| [GitLab wiki Markdown](https://docs.gitlab.com/user/project/wiki/markdown/) | Standard links and wiki-page links resolve inside the wiki hierarchy. | Extensionless page slugs and `[[Page]]` forms are wiki-specific. |
| [MkDocs](https://www.mkdocs.org/user-guide/writing-your-docs/) | Authors normally link to source `.md` files relative to the current file. | Build rewrites them to `.html` or directory URLs; validation and root-relative behavior are configurable. |
| [Docusaurus](https://docusaurus.io/docs/next/markdown-features/links) | `.md` and `.mdx` destinations are source-file paths transformed to generated document URLs. | URL-path links are deliberately left as browser routes; `@site` and other project constructs require build context. |
| [Jekyll](https://jekyllrb.com/docs/liquid/tags/) | Ordinary Markdown URLs still work. | `{% link path/to/file.md %}` validates a source path and produces a built URL; `{% post_url ... %}` identifies a post. |
| GitHub Pages | Depends on the repository’s Jekyll or Actions build. | A link that works on the published site can intentionally differ from GitHub’s source view. |

An extensionless target such as `guide` can consequently mean at least four things: a
literal extensionless file, a published page route, an implicit `guide.md` note, or an
unresolved target. A directory-like target such as `guide/` may mean a real directory, a
generated pretty URL for `guide.md`, or `guide/index.md`. No universal guess is correct.

### Representative Source-Corpus Check

An illustrative scan of documentation at pinned revisions shows the coexistence of these
conventions. Standard link and image counts come from a CommonMark token parse.
Wiki-link occurrences exclude fenced and inline code.
“Internal forms” excludes schemes, empty targets, and fragment-only links; it records
lexical path forms rather than whether the target exists.

| Corpus | Files | Standard links / images | Wiki links / embeds | Internal standard path forms |
| --- | ---: | ---: | ---: | --- |
| Metabrowser docs before this brief at `4c689da` | 23 | 161 / 0 | 0 / 0 | 42 bare, 47 parent; 88 Markdown files |
| [Obsidian Help at `b8cf62b`](https://github.com/obsidianmd/obsidian-help/tree/b8cf62bc2aac486dd0e2ec4cdaf7fa518b1a10a0/en) | 173 | 441 / 7 | 1,523 / 284 | 4 bare; 2 Markdown files, 2 other files |
| [MkDocs docs at `2862536`](https://github.com/mkdocs/mkdocs/tree/2862536793b3c67d9d83c33e0dd6d50a791928f8/docs) | 19 | 465 / 9 | 2 / 0 | 58 bare, 16 dot, 155 parent; 219 Markdown files |
| [Docusaurus docs at `babf8c2`](https://github.com/facebook/docusaurus/tree/babf8c29da7e253b3b9307bdf6a76431b634e664/website/docs) | 94 | 1,027 / 23 | 0 / 0 | 34 bare, 164 dot, 183 parent, 52 root; 376 Markdown files, 33 extensionless |
| [VS Code root docs at `9245212`](https://github.com/microsoft/vscode/tree/9245212c26af8113b3b96392c04563623cd99811) | 4 | 58 / 3 | 0 / 0 | 5 bare; 3 Markdown files, 1 extensionless |

This is not a popularity survey.
It verifies that real repositories need exact `.md` paths, multiple relative path forms,
extensionless published routes, and wiki syntax.
It also shows why enabling repo-wide fuzzy lookup for every standard link would change
the meaning of ordinary project documentation.

### Current Metabrowser Behavior

The current implementation has useful pieces but no end-to-end link contract:

- The built-in Markdown plugin sends source to KPress and inserts the returned HTML. It
  does not intercept or rewrite document links.
- KPress preserves standard relative `href` and `src` values and uses a GitHub-style
  heading slugger. It renders `[[Note]]` and `![[asset]]` as literal text.
- KPress sanitation allows `http`, `https`, `mailto`, and `tel` destinations.
  It strips custom schemes such as `obsidian:` and does not allow a document-provided
  `<base>`.
- The selected file is encoded as `#<path>`. The same `location.hash` is also needed by
  document headings. A heuristic treats hashes containing a slash or file extension as
  paths and other hashes as anchors.
- Selecting a file calls `history.replaceState`, so ordinary lateral navigation does not
  create browser back and forward entries.
- The plugin SDK exposes `openPath(path)`, with no fragment, query, ambiguity, embed, or
  history policy.
- The CLI emits the legacy hash route.
  The server has no rendered-file pathname route that can survive a direct refresh.

If the browser is at `/#docs%2Fcurrent.md`, an untouched `href="other.md"` resolves to
`/other.md`, not `docs/other.md`; the server returns no rendered-file page there.
A URL also cannot express both the current selected file and `#heading` because the same
fragment is overloaded.
These are routing problems, not Markdown parser problems.

An executable KPress fixture confirmed the boundary: `other.md#Heading` and
`../img/a.png` survive unchanged, the rendered heading receives `id="heading"`, and
Obsidian wiki syntax remains text.
This is a good base for standard links once the browser route supplies the correct URL
context.

## Compatibility Model

### Syntax and Resolution Matrix

| Authored target | GitHub repository | Obsidian | Static-site source | Recommended Metabrowser policy |
| --- | --- | --- | --- | --- |
| `[x](b.md)` | Exact sibling file | Exact standard link | Usually exact source file | Exact source-relative lookup |
| `[x](./b.md)` | Exact sibling file | Exact standard link | Exact source file | Exact source-relative lookup |
| `[x](../b.md)` | Exact parent-relative file | Exact standard link | Exact source file | Normalize inside served root; reject escape |
| `[x](/b.md)` | Repository-root-relative | Vault-root-compatible in some workflows | Tool-dependent | Served-root-relative repository policy |
| `[x](b.md#heading)` | File plus GitHub slug | File plus heading | Source file, then built anchor | Resolve file and fragment separately |
| `[x](#heading)` | Current document heading | Current note heading | Current page heading | Same document; no refetch |
| `[x](guide)` | Literal path or URL | Literal standard path | Often published route | Exact literal file first; adapter only after that |
| `[x](guide/)` | Directory | Directory or literal path | Often pretty page URL | Exact directory first; site adapter may map an index |
| `![x](img/a.png)` | Repository image | Standard image embed | Built asset | Resolve safely and serve through the raw-resource route |
| `<a href="b.md">` | Sanitized HTML link | HTML link | Renderer-dependent | Apply the same safe standard-target resolver after sanitation |
| `[[Note]]` | Text in repository Markdown | Vault note lookup | Usually text | Obsidian adapter; unique candidate or ambiguity result |
| `[[Note#Heading\|x]]` | Text in repository Markdown | Note heading with display text | Usually text | Preserve target and label; resolve note then heading metadata |
| `[[Note#^id]]` | Text in repository Markdown | Named block | Usually text | Obsidian adapter and block index |
| `![[asset.png]]` | Text in repository Markdown | Vault embed | Usually text | Embed intent; safe resolver shared with navigation |
| `{% link b.md %}` | Text in source view | Text | Jekyll compile-time link | Jekyll adapter or explicit unsupported diagnostic |
| `obsidian://open?...` | External custom URL | Application action | External custom URL | Never internal; opt-in external launch only |
| GitHub `/blob/<sha>/b.md` | Exact remote revision | External URL | External URL | External unless that exact revision is mounted |

Reference-style Markdown links enter the same standard-target path after the Markdown
parser resolves their definition.
Images and embeds enter the same resource resolver but carry a different action, so they
cannot accidentally trigger page navigation.

### Dialect Selection

Metabrowser should expose `auto`, `repository`, `obsidian`, and `site` policies.
The selection order should be:

1. An explicit user or plugin choice wins.
2. Strong repository signals enable an adapter: `.obsidian/`, `mkdocs.yml`,
   `docusaurus.config.*`, or Jekyll configuration are examples.
3. Standard links always attempt exact resolution before a fallback adapter.
4. Wiki syntax can invoke the Obsidian adapter when it is actually parsed as wiki
   syntax, but ambiguous candidates remain ambiguous.
5. A weak clue such as one extensionless link must not silently change the whole
   repository’s semantics.

Detection is a convenience, not hidden global state.
The selected policy and a short resolution explanation should be visible in link
diagnostics.

### What “Support All Conventions” Means

Support should mean that Metabrowser recognizes an authored intent and produces an
honest result. It does not mean every target must be coerced into a local file.

| Status | Browser behavior |
| --- | --- |
| Internal | Expose a canonical local `href`; render or select the exact resource. |
| External | Preserve the safe URL and normal modifier/new-tab behavior. |
| Missing | Keep the authored target visible and mark the link as unresolved. |
| Ambiguous | Show candidates or a chooser; do not select arbitrarily. |
| Unsafe | Do not navigate; explain the root escape or disallowed scheme. |
| Unsupported | Identify the dialect construct and, where useful, show its source text. |

This graded result is more compatible than either a 404 or an aggressive fuzzy guess.

## Recommendations

### Adopt a Canonical Rendered-File Route

Use this public route contract:

```text
/view/<percent-encoded-served-root-relative-path>#<document-fragment>
```

Encode each path segment independently and preserve `/` as the path separator.
Parse and decode exactly once.
Reject NUL bytes, encoded separators, backslash-based traversal, and normalization above
the served root. Preserve case for exact lookup even on a case-insensitive host so links
do not become platform-dependent.

Examples from a source file at `docs/current.md` are:

| Authored link | Canonical destination |
| --- | --- |
| `other.md` | `/view/docs/other.md` |
| `../README.md#install` | `/view/README.md#install` |
| `/CONTRIBUTING.md` | `/view/CONTRIBUTING.md` |
| `#configuration` | `/view/docs/current.md#configuration` |
| `Folder/Note%20One.md` | `/view/docs/Folder/Note%20One.md` |

The server must return the application shell for a safe `/view/{path}` on direct GET so
refresh, copy-link, and open-in-new-tab work.
`/api`, `/raw`, `/static`, and other reserved namespaces stay outside `/view`.

Relative links under `/view/<source-directory>/` then use the browser’s native URL
algorithm for the common case.
A delegated handler still validates every internal target, rewrites served-root-relative
`/...` links into `/view/...`, blocks traversal, and keeps SPA navigation fast.

Do not use a dynamic `<base>` element.
It would affect shell scripts, API requests, and all other relative resources; it would
not solve root-relative or wiki links; and its “first base wins” behavior is awkward
after client-side navigation.
A canonical pathname gives the browser the correct context without changing global
document semantics.

Migrate legacy `/#<encoded-path>` links with `replaceState` after startup.
Use `pushState` for user-initiated file navigation, `replaceState` only for
normalization or automatic restoration, and `popstate` for back and forward.
The fragment then has one job: locate content inside the selected file.

### Use a Structured Link Intent and Result

Do not pass a partially decoded string through several heuristics.
The Markdown plugin should produce an intent, and the resolver should return a
disposition:

```text
LinkIntent = {
  syntax, sourcePath, authoredTarget, label, action
}

ResolvedTarget = {
  status, path?, query?, fragment?, mediaKind?, candidates?, reason?
}
```

`action` distinguishes navigation, image or media embedding, note transclusion, and an
external application launch.
The original target remains available for diagnostics, copying, and future
re-resolution.

The shell should own generic file routes, history, and safe file opening.
The built-in Markdown plugin should own CommonMark and Obsidian syntax, heading and
block metadata, and dialect-specific fallback.
This preserves the consumer-agnostic core and extends the existing `openPath(path)` SDK
without breaking it.
A structured navigation method can add fragment and action metadata while `openPath`
remains the simple exact-path case.

### Resolve Standard Links Exactly

For a standard Markdown or sanitized raw-HTML target:

1. Parse path, query, and fragment as URL components before decoding.
2. For an empty path or fragment-only target, retain the current source file.
3. Treat leading `/` as served-root-relative in repository browsing mode; otherwise
   combine the path with the source file’s directory.
4. Normalize `.` and `..` while refusing to cross the served root.
5. Look up the normalized path exactly through the existing safe-path and inventory
   helpers.
6. If it is a directory, open folder navigation.
   Do not silently choose `README.md` or `index.md` without an active site adapter.
7. Preserve the query and fragment as separate metadata.
8. If exact lookup fails, return missing unless a selected adapter defines a fallback.

Do not lowercase paths, append `.md`, search by basename, or fuzzy-rank ordinary
Markdown links by default.
A broken exact link is actionable information during a repository review.

### Add an Obsidian Resolver as a Markdown Dialect

The Obsidian adapter should parse target, subpath, display text, and embed intent before
looking at the filesystem.
Its safe, deterministic compatibility policy should be:

1. Honor an explicit vault-root or relative path and accept optional `.md` for notes.
2. Require an extension for non-Markdown assets.
3. Prefer an exact source-directory note when a basename alone identifies it.
4. Use a vault basename or path-suffix index only when it produces one candidate.
5. Return all viable candidates when several notes have the same link name.
6. Resolve `#Heading`, hierarchical headings, and `#^block-id` against metadata from the
   selected note.
7. Treat cross-vault heading-search forms used by Obsidian’s authoring UI as search
   intent, not a deterministic stored link.

Frontmatter aliases can enrich candidate labels and search.
They should not redirect a plain link silently unless a later, explicit compatibility
mode defines and tests that behavior.

Initially, render note and media embeds as bounded preview cards or ordinary open
actions. Full note transclusion needs recursion-depth, cycle, byte, render-time, and
disposal limits. It should reuse the same resolved target rather than inventing a second
lookup algorithm.

### Add Site and Remote-Repository Adapters Conservatively

A configured MkDocs, Docusaurus, or Jekyll adapter may try documented candidates after
exact lookup. Depending on the detected tool, candidates can include `target.md`,
`target.mdx`, `target/index.md`, or a configured navigation mapping.
The adapter should show its transformation in diagnostics.
It should not guess across the whole tree.

Absolute `http` and `https` links remain external by default.
A same-repository GitHub adapter may map a branch-head `/blob/<branch>/<path>` URL to
the current checkout only when repository identity matches and the UI discloses that it
is showing the local working tree.
A commit-pinned URL maps locally only if that exact revision is mounted.
Cross-repository links require an explicit mounted-root map.

Compile-time constructs such as Jekyll Liquid tags are recognized but unsupported until
their adapter has the relevant configuration.
Recognition should produce a useful diagnostic instead of a misleading local 404.

### Give Every Internal Link a Real `href`

Internal anchors should be rendered with the final canonical `href`, not only a click
callback. This preserves browser status previews, copy-link, keyboard access,
modifier-click, middle-click, open-in-new-tab, and reload.
The delegated click handler should intercept only an unmodified primary-button
activation that the SPA can handle.

After an asynchronous render, scroll to the fragment and focus only when the user’s
navigation action calls for it.
A same-document fragment should not refetch the file.
Heading resolution should use the existing GitHub-compatible IDs.
Obsidian heading text and block IDs should be mapped to actual DOM targets by the
Markdown adapter. Duplicate headings need deterministic suffixes and tests.

Missing and ambiguous links should remain visible and keyboard reachable.
A tooltip or details action can show the authored target, source path, active dialect,
candidate paths, and rejection reason.
Hover previews are a later enhancement and must be abortable and disposed when content
is replaced.

### Route Embedded Resources Through Safe File Access

Relative image and media destinations cannot be left as `/view/...` requests because
that route returns the application shell.
Resolve them against the source document and rewrite them to the existing safe
raw-resource endpoint, or a future dedicated asset route.
Preserve alt text and media type.
All reads must use the repository’s safe-path, inventory, and bounded-read helpers.

External media follows the application’s trust policy because fetching it can disclose
the user’s network address and viewing activity.
`javascript:`, `file:`, unsafe `data:`, root escapes, and automatic custom-scheme
launches must never become internal navigation.
Rendered documents must not be able to target application API or static namespaces by
masquerading as a repository path.

### Build the Index as an Enhancement, Not a Prerequisite

Exact relative links should resolve immediately without scanning the whole root.
Obsidian basename lookup, backlinks, broken-link reports, and graph views can use an
asynchronous index derived from the existing inventory.
Large-vault indexing must be bounded and must yield rather than adding synchronous work
to a server request path.
Navigation should remain useful while the index is incomplete.

## Validation Matrix

The implementation plan should create machine-readable fixtures with source path,
authored syntax, inventory, active dialect, expected status, resolved path, fragment,
and canonical URL. At minimum, fixtures should cover:

- inline, full-reference, collapsed-reference, shortcut-reference, raw-HTML, image, and
  fragment-only CommonMark links;
- bare, dot, parent, served-root, directory, `.md`, `.mdx`, extensionless, query, and
  fragment targets;
- spaces, Unicode, percent signs, literal `#` and `?` in filenames, duplicate decode
  attempts, backslashes, traversal, symlinks, and case differences;
- duplicate GitHub heading slugs, explicit HTML anchors, Obsidian hierarchical headings,
  and block identifiers;
- unique and duplicate Obsidian basenames, missing notes, aliases, non-Markdown
  attachments, links, and embeds;
- configured MkDocs, Docusaurus, and Jekyll candidates versus the same target without an
  adapter;
- external URLs, GitHub branch URLs, commit permalinks, custom schemes, and disallowed
  schemes;
- direct GET of `/view/...`, legacy hash migration, reserved namespaces, same-document
  navigation, asynchronous fragment scrolling, and back/forward restoration;
- unmodified clicks, modifier clicks, middle clicks, keyboard activation, new tabs, and
  broken or ambiguous link accessibility;
- renderer replacement and disposal, large-vault indexing, read-size limits, and no
  external network access in offline fixtures.

Browser tests should include a small GitHub-style repository, an Obsidian-style vault,
and static-site source fixtures.
The project-wide `make verify` gate remains required.

## Implementation Sequence

1. Introduce `/view/{path}`, hard-refresh support, legacy hash migration, structured
   navigation, push/pop history, and fragment scrolling.
2. Resolve and rewrite exact standard Markdown links, raw HTML links, images, folders,
   missing targets, and unsafe targets.
3. Add Obsidian parsing, unique-note lookup, heading and block navigation, ambiguity UI,
   and bounded embed placeholders.
4. Add configured static-site adapters, optional same-repository GitHub URL mapping,
   link diagnostics, backlinks, and richer transclusion based on measured demand.

The research brief is evidence and design input, not an implementation contract.
The first step before code changes is an active feature plan that fixes the route
migration, SDK shape, fixture schema, and acceptance criteria.
That follow-up is tracked as feature bead `mb-yq1f`.

## Research Completion

- [x] Built the syntax and resolution compatibility matrix.
- [x] Recorded current Metabrowser rendering and routing behavior.
- [x] Defined a canonical route, resolver pipeline, and fallback policy.
- [x] Identified implementation phases and validation fixtures.

## Methodology

Behavior was checked against specifications, official product documentation, public API
declarations, the current Metabrowser implementation, and an executable KPress fixture.
Representative public repositories were checked out read-only under the gitignored
`attic/` directory at the pinned commits in the corpus table.
No third-party dependencies or repository code were executed.

Recommendations that combine tool behavior are Metabrowser design inferences.
In particular, `/view/` is a proposed local route, ambiguity disclosure is a deliberate
safety policy, and dialect detection is a compatibility layer rather than a behavior
specified by CommonMark, GitHub, or Obsidian.

## References

### Standards and Web Platform

- [CommonMark 0.31.2](https://spec.commonmark.org/0.31.2/)
- [GitHub Flavored Markdown specification](https://github.github.com/gfm/)
- [WHATWG URL Standard](https://url.spec.whatwg.org/)
- [HTML document base URLs](https://html.spec.whatwg.org/multipage/urls-and-fetching.html#document-base-urls)
- [HTML navigation and history](https://html.spec.whatwg.org/multipage/nav-history-apis.html)

### GitHub and GitLab

- [GitHub basic writing and formatting syntax](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax)
- [GitHub README guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)
- [GitHub permanent file links](https://docs.github.com/en/repositories/working-with-files/using-files/getting-permanent-links-to-files)
- [GitHub permanent links to code](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-a-permanent-link-to-a-code-snippet)
- [GitHub wiki content](https://docs.github.com/en/communities/documenting-your-project-with-wikis/editing-wiki-content)
- [GitHub wiki pages](https://docs.github.com/en/communities/documenting-your-project-with-wikis/adding-or-editing-wiki-pages)
- [GitLab Flavored Markdown](https://docs.gitlab.com/user/markdown/)
- [GitLab wiki-specific Markdown](https://docs.gitlab.com/user/project/wiki/markdown/)

### Obsidian

- [Obsidian Flavored Markdown](https://obsidian.md/help/obsidian-flavored-markdown)
- [Internal links](https://github.com/obsidianmd/obsidian-help/blob/b8cf62bc2aac486dd0e2ec4cdaf7fa518b1a10a0/en/Linking%20notes%20and%20files/Internal%20links.md)
- [Embed files](https://github.com/obsidianmd/obsidian-help/blob/b8cf62bc2aac486dd0e2ec4cdaf7fa518b1a10a0/en/Linking%20notes%20and%20files/Embed%20files.md)
- [Aliases](https://github.com/obsidianmd/obsidian-help/blob/b8cf62bc2aac486dd0e2ec4cdaf7fa518b1a10a0/en/Linking%20notes%20and%20files/Aliases.md)
- [Obsidian settings](https://github.com/obsidianmd/obsidian-help/blob/b8cf62bc2aac486dd0e2ec4cdaf7fa518b1a10a0/en/User%20interface/Settings.md)
- [Obsidian URI](https://github.com/obsidianmd/obsidian-help/blob/b8cf62bc2aac486dd0e2ec4cdaf7fa518b1a10a0/en/Extending%20Obsidian/Obsidian%20URI.md)
- [Obsidian API link-resolution declarations](https://github.com/obsidianmd/obsidian-api/blob/cc1744324150c632416857c98964f87b1574a5fc/obsidian.d.ts)

### Editors and Site Generators

- [VS Code Markdown editing](https://code.visualstudio.com/docs/languages/markdown)
- [MkDocs writing documentation](https://www.mkdocs.org/user-guide/writing-your-docs/)
- [MkDocs configuration](https://www.mkdocs.org/user-guide/configuration/)
- [Docusaurus Markdown links](https://docusaurus.io/docs/next/markdown-features/links)
- [Docusaurus assets](https://www.docusaurus.io/docs/3.7.0/markdown-features/assets)
- [Jekyll link tags](https://jekyllrb.com/docs/liquid/tags/)
- [Jekyll URL filters](https://jekyllrb.com/docs/liquid/filters/)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
