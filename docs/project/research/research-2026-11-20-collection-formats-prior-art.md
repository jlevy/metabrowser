# Research: Prior Art for Plain-Text Collections and Dashboards

**Date:** 2026-11-20

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Complete.
A survey; it recommends nothing on its own.

## Overview

This is the prior-art survey behind
[Collection Documents](research-2026-11-20-collection-documents.md), which weighs
options for a plain-text format whose link lists render as cards, reading lists, tables,
and boards in Metabrowser.

It records, for each tool, the syntax on disk, the data model, and what is worth copying
or avoiding. The last section draws out the patterns that recur.

**How it was checked.** These were read from their own documentation or source during
the survey: Obsidian Bases, Obsidian Kanban (the serializer source), JSON Canvas,
micromark and remark directives, MyST, Markdoc, Notion-flavored Markdown, Quarto
dashboards and listings, Auto Card Link, oEmbed, and TaskPaper.
Items marked “(from memory)” are well known but were not re-read, and should be checked
before anything is built on their details.

## Notion

**On disk.** Notion has no native file format.
It has two text forms:

- **Markdown and CSV export.** A database becomes a CSV plus one `.md` file per row.
  Row properties come out as plain `Key: Value` lines under the H1, not as frontmatter.
  Relations come out as IDs, formulas as static values, and only one view is exported.
  Linked views are effectively lost.

- **Notion-flavored Markdown.** This is the API and MCP form.
  It is CommonMark plus XML-like tags:

  ```html
  <database url="…" data-source-url="collection://…" inline="true">Reading list</database>
  <page url="…">Child page</page>
  <bookmark source="https://example.com" />
  <embed source="https://youtu.be/…" />
  <mention url="https://notion.so/…" type="database">Tasks</mention>
  <link-preview url="…" source="…" />
  <synced-block url="…">…</synced-block>
  <columns><column ratio="50">…</column><column ratio="50">…</column></columns>
  <callout icon="💡" color="yellow_bg">…</callout>
  ```

  View configuration lives in a separate view description, not in the Markdown.

**Data model.** A database (a data source) holds typed rows.
Each row is a page with a schema of properties: text, select, multi-select, date,
relation, rollup, formula, URL, files, and more.
Views sit on top of a data source and are typed: table, board, gallery, list, calendar,
timeline, chart, feed, map, and form.
Each view stores its own filter, sort, group, visible properties, and card cover or
size. A linked view is a view of a data source that lives somewhere else.

A URL draws in three tiers: a link mention is an inline chip, a bookmark block is a card
built from Open Graph metadata, and an embed is an iframe or oEmbed.

**Worth copying:**

- The split between a data source and its views.
- A small fixed set of view types.
- Mention, bookmark, and embed as three tiers of URL rendering.
- Self-closing tags whose only attribute is `source=`, which are easy for an agent to
  write.

**Worth avoiding:**

- Relations, rollups, and formulas.
- Synced blocks, which need a transclusion identity model.
- Opaque IDs in place of paths.

## Obsidian

### Bases

A `.base` file is pure YAML. The structure, from the official documentation:

```yaml
filters:
  or:
    - file.hasTag("tag")
    - and: ['file.hasTag("book")', 'file.hasLink("Textbook")']
    - not: ['file.inFolder("Required Reading")']
formulas:
  ppu: "(price / age).toFixed(2)"
properties:
  status: {displayName: Status}
summaries:
  customAverage: "values.mean().round(3)"
views:
  - type: table
    name: "My table"
    limit: 10
    groupBy: {property: note.status, direction: ASC}
    filters: {and: ['status != "done"']}
    order: [file.name, note.age, formula.ppu]
    summaries: {formula.ppu: Average}
```

- **View types:** `table`, `cards`, `list`, and, in later releases, `kanban` and `map`.
  Plugins add more.

- **Cards view keys** (from forum and plugin evidence): `image: note.cover`, `imageFit`,
  `imageAspectRatio`, `cardSize`.

- **No explicit item lists.** A base includes every file in the vault by default, and
  filters narrow it. There is no `from`.

- **Property namespaces:** `note.x` for frontmatter, `file.x` for `name`, `path`, `ext`,
  `mtime`, `tags`, and `links`, `formula.x`, and `this` for the embedding note.

- **Embedding:** `![[Books.base#View]]`, or an inline fenced block:

  ````markdown
  ```base
  filters: {and: ['file.hasTag("example")']}
  views: [{type: table, name: Table}]
  ```
  ````

**Worth copying:**

- A top-level `views:` list, each with `type` and `name`.
- Kanban as a view with `groupBy` plus a group order, so a board needs no new data
  model.
- `order:` as the list of visible properties.
- Views may store extra keys the core ignores, so plugin-specific configuration needs no
  schema change.
- The fenced `base` block for embedding.

**Worth avoiding:** the formula and expression language.
Its nested quoting (`'status != "done"'`) is hard on people and agents alike.

### Dataview

(From memory.) A query language in a fence, plus inline `key:: value` fields:

````markdown
```dataview
TABLE author, rating FROM #book WHERE status = "reading" SORT rating DESC
```
````

It is readable, but it is a language that has to be parsed and learned.
Bases is in effect its YAML replacement.

### Kanban Plugin

From the serializer source:

````markdown
---
kanban-plugin: board
---

## Todo

- [ ] Write spec [[spec.md]]
- [ ] Review PR

## Done

**Complete**
- [x] Ship v1

***

## Archive

- [x] old card

%% kanban:settings
```
{"kanban-plugin":"board","lane-width":272}
```
%%
````

- H2 headings are lanes, and task-list items are cards.
- `**Complete**` marks a lane whose items are checked automatically.
- `***` followed by `## Archive` holds archived cards.
- JSON settings sit in an Obsidian comment.

**Worth copying:** headings as lanes and list items as cards.
It reads perfectly on GitHub, and a move is a one-line diff.

**Worth avoiding:** the JSON blob inside `%%`, which GitHub does not hide, and magic
bold strings.

### JSON Canvas

The top level is `nodes[]` and `edges[]`. A node is `text`, `file` (with `file` and
`subpath`), `link` (with `url`), or `group` (with `label` and `background`). Every node
needs `id`, `x`, `y`, `width`, and `height`.

**Worth copying:** the node taxonomy (text, file, link, group) as the vocabulary for
collection items.

**Worth avoiding:** pixel coordinates, which are noisy in diffs and which an agent
cannot write well.

## Quarto and Pandoc

### Dashboards

```markdown
---
title: Ops
format: {dashboard: {orientation: columns}}
---
# Page One {orientation="rows"}
## Row {height=60%}
::: {.card title="Recent docs"}
- [Design](design.md)
:::
## Row {.tabset}
::: {.valuebox icon="pencil" color="primary"}
42
:::
```

H1 is a page, H2 a row or column, and H3 a nested level.
The heading text is discarded and its attributes size the region.
`.tabset` turns children into tabs; cells and `.card` divs become cards.

### Listings

This is the closest existing analogue.
Frontmatter declares the view and the body places it:

```yaml
listing:
  - id: reports
    contents: ["reports/*.qmd", archived-items.yaml]
    type: grid
    fields: [image, date, title, author]
    sort: ["date desc", title]
    categories: true
    filter-ui: [title]
    page-size: 18
```

```markdown
::: {#reports}
:::
```

An items file is a YAML list of
`{title, path, author, date, categories, description, image}` mappings.

**Worth copying:** `contents:` that mixes globs with explicit YAML items, `type:` plus
`fields:`, and the empty `::: {#id}` placement div.

### Pandoc Syntax

(From memory.) A fenced div is `::: {#id .class key="val"}` … `:::`, with at least three
colons. A bracketed span is `[text]{.class key=val}`, and a heading takes attributes as
`## Title {#id .class}`. GitHub renders the `:::` lines as literal paragraphs: ugly, but
the content stays visible.

## Tag and Directive Syntaxes

- **Markdoc.** A block tag is `{% callout type="note" %}…{% /callout %}`, and a
  self-closing one is `{% partial file="header.md" /%}`. Attributes are typed, and a
  schema declares each tag’s attributes and children, so a document validates with error
  levels, which helps an agent that writes it.
  GitHub shows `{% %}` literally.

- **MDX.** `<CardGrid><LinkCard title="…" href="…" /></CardGrid>` is real JSX with
  expressions and imports.
  It is unsafe to evaluate, and a stray `<` or `{` breaks parsing.
  It is too powerful for a data file.

- **MyST.** A directive is a backtick fence with a braced name and `:key: value` option
  lines, or a colon fence for Markdown bodies.
  Cards and grids (from memory):

  ```markdown
  ::::{grid} 1 1 2 3
  :::{card} Design doc
  :link: docs/design.md
  Summary text
  :::
  ::::
  ```

  On GitHub the backtick form degrades to a code block that still shows the options.

- **Generic directives (remark-directive).** Text is `:name[label]{attrs}`, a leaf is
  `::name[label]{attrs}` on its own line, and a container is `:::name[label]{attrs}` …
  `:::`. An example: `::card[Design doc]{href=docs/design.md image=cover.png}`. It is
  concise and one line per item, so diffs are clean.
  It is still a proposal, not CommonMark, and GitHub shows the raw text.

## Evidence and Observable Framework

(From memory.)

- **Evidence.** A named SQL fence followed by components that reference it by name:
  ````sql orders`, then `<DataTable data={orders}/>`. The pattern is a named data block,
  then a view component that names it.
- **Observable Framework.** Data loaders are files named for their output
  (`data/quakes.json.js`). They run at build time and their output is cached.
  The lesson: something that computes a list is a separate cached artifact, and code
  stays out of the collection file.

## Typed Objects Without Heavy Schemas

- **Logseq.** Block properties are `key:: value`. Simple queries are
  `{{query (and [[book]] (task TODO))}}`.
- **Tana supertags.** Tagging a node `#book` attaches the tag’s field template.
  The type is assigned by tagging, not by declaring.
- **Anytype.** An object has one Type plus Relations.
  A **Set** is a live query by Type or Relation and stores nothing.
  A **Collection** is a hand-curated list of any types.
  Both get views: grid, gallery, list, kanban, and calendar.

The Set and Collection split, a query against an explicit list, recurs everywhere:
Notion’s database against a page, Bases against a Markdown list, Quarto’s globs against
its items files.

## Bookmarks, Reading Lists, and Link Previews

- **Netscape bookmark HTML** (from memory) is the universal interchange format:

  ```html
  <!DOCTYPE NETSCAPE-Bookmark-file-1>
  <DL><p>
    <DT><H3>Folder</H3>
    <DL><p>
      <DT><A HREF="https://…" ADD_DATE="1700000000" TAGS="a,b">Title</A>
      <DD>Description
    </DL><p>
  </DL><p>
  ```

  Its fields are URL, title, add date, tags, description, and nesting as folders.

- **OPML** uses `<outline text="Title" type="link" url="…"/>`, nested.

- **Raindrop** imports a CSV of `url, folder, title, note, tags, created`. Its export
  adds an excerpt, a cover, and highlights.

- **Pocket** shut down in 2025; its export was a CSV of title, URL, time added, tags,
  and read status.

- **Instapaper** (from memory) exports `URL, Title, Selection, Folder, Timestamp`.

**What a URL card needs:**

| Field | Source |
| --- | --- |
| `url`, `title` | Required; the author writes them |
| `description`, `image`, `site_name`, `favicon` | Optional; Open Graph or oEmbed |
| `added`, `tags`, `status`, `note` | The user’s own |

**Where metadata comes from.** Open Graph supplies `og:title`, `og:description`,
`og:image`, `og:site_name`, and `og:url`, with Twitter Card fallbacks.
oEmbed is discovered through a `<link rel="alternate" type="application/json+oembed">`
element or a provider registry, and returns a type, title, provider name, thumbnail,
HTML, and `cache_age`.

**How tools fetch and cache it.** There are two strategies:

1. **Server-side fetch with a cache.** Notion, Raindrop, and Slack do this; the user’s
   file holds only the URL.

2. **Write the metadata into the document.** Obsidian’s Auto Card Link plugin does this
   with a YAML fence:

   ````markdown
   ```cardlink
   url: https://obsidian.md/
   title: "Obsidian"
   description: "…"
   host: obsidian.md
   favicon: https://obsidian.md/favicon.ico
   image: https://obsidian.md/images/banner.png
   ```
   ````

   Its stated reason is that the block “does not mess up your Markdown files unlike HTML
   tags”. It works offline and reproducibly, but it goes stale.

A hybrid is possible: fields the author wrote win, missing fields come from a cache
keyed by URL that honors `cache_age`, and the source file is never rewritten silently.

## Kanban as Text

- **Obsidian Kanban:** H2 lanes and checkbox cards, as above.

- **todo.txt** (from memory): one task per line, such as
  `(A) 2026-01-03 Draft spec +metabrowser @desk due:2026-02-01`. There are no lanes; a
  board needs a `status:` key.

- **TaskPaper:**

  ```text
  Metabrowser:
      - Draft spec @status(doing) @priority(1)
        A note line under the task
  ```

  Projects end with `:`, tasks start with `- `, and tags are `@tag(value)`.

- **GitHub Projects** has no text format.
  A board is a view grouped by a single-select Status field; table, board, and roadmap
  are views over the same items.

- **File-per-card tools** (Backlog.md, kanban-md) keep one Markdown file per task with a
  `status:` frontmatter key, and derive the board.
  This diffs well per card, but the board’s order has to be stored somewhere else.

There are two viable models:

1. **The board is a document.** A heading is a lane, a list item is a card, and order is
   document order. This is best for hand-curated boards and for GitHub rendering.
2. **The board is a view.** A group-by field and a group order over items that carry a
   status. This is best when cards are files or are shared with tables.

Bases, GitHub Projects, and Notion chose the second.
Obsidian Kanban chose the first.

## Blended Formats

(From memory unless noted.)

- **Starlight:** `<CardGrid><LinkCard title="…" href="…" description="…"/></CardGrid>`
  in MDX, with a Markdoc variant.
- **Docusaurus:** `<DocCardList />` generates cards from sidebar items, a query-style
  card grid.
- **Hugo shortcodes** (the Hextra theme):
  `{{< cards >}}{{< card link="docs/" title="Docs" icon="book" >}}{{< /cards >}}`,
  shown raw on GitHub.
- **Jekyll data files:** `_data/links.yml` holds a YAML list, and a template loops over
  it. Data and presentation are cleanly apart, at the cost of a second file.
- **GitHub rendering:** frontmatter shows as a table; task lists, `<details>`,
  `> [!NOTE]` alerts, and `mermaid` fences render; unknown fences render as readable
  code blocks; HTML comments are hidden; `:::`, `{% %}`, and `{{< >}}` appear as literal
  text; inline `style` attributes are stripped.
- **Awesome lists:** `## Category` headings over `- [Name](url) - Description.` items.
  This is the most widely understood convention for a collection in Markdown: GitHub
  renders it, it diffs per line, and language models write it fluently.

## Recurring Patterns

**P1. Frontmatter declares the views; the body is the item list.** Quarto listings,
Obsidian Kanban, and Hugo and Jekyll pages work this way.

- For: frontmatter becomes a table on GitHub and the body is an ordinary list; one item
  is one line; agents write ordinary links.
- Against: per-item properties beyond title, URL, and description need an inline
  convention (a trailing `key:: value`, TaskPaper’s `@tag(value)`, or a nested list of
  `key: value`), and each is a small grammar.

**P2. Headings are groups; list items are entries.** Obsidian Kanban, awesome lists,
Quarto dashboards, and TaskPaper projects work this way.

- For: lanes, gallery sections, and table groups come free; order is document order; a
  move is a one-line diff; it degrades perfectly.
- Against: tools add special markers (`**Complete**`, a settings comment) that do not
  degrade.

**P3. A fenced block with a YAML body.** Obsidian’s `base` and `cardlink` blocks, MyST
directives, and Evidence’s named SQL fences work this way.

- For: agents write YAML lists reliably; one key per line diffs well; several typed
  views can sit inside a prose document; a query source needs no new language.
- Against: on GitHub it is a visible code block whose links are not clickable.

**P4. A directive or tag per item.** remark-directive, Markdoc, Notion’s tags, MDX, and
Hugo shortcodes work this way.

- For: compact and expressive; a schema can validate attributes.
- Against: every flavor is noise on GitHub, except real HTML tags, which vanish there;
  attribute quoting and escaping is where agents slip.

**P5. A pure-YAML file with sources, views, and items.** Obsidian’s `.base`, JSON
Canvas, Jekyll’s `_data`, and Quarto’s items files work this way.

- For: the most machine-friendly and the easiest to validate against a schema; ideal for
  query-defined collections.
- Against: it is not prose, and GitHub shows only highlighted YAML.

Lessons that cut across all five:

- Explicit items and queries are both needed, and Quarto shows they can mix.
- A board can be a grouped view, so it shares items with a table and a gallery, with
  headings as the implicit group when items are inline.
- Fetched link metadata is safer in a cache keyed by URL than in the file.
- Coordinates, opaque IDs, and expression strings are what make these formats hard to
  write.

## References

- [Notion-flavored Markdown](https://developers.notion.com/guides/data-apis/notion-flavored-markdown)
  and [exporting content](https://www.notion.com/help/export-your-content) (official,
  Notion)
- [Obsidian Bases syntax](https://obsidian.md/help/bases/syntax),
  [views](https://obsidian.md/help/bases/views), and
  [creating a base](https://obsidian.md/help/bases/create-base) (official, Obsidian)
- [Obsidian Kanban](https://github.com/mgmeyers/obsidian-kanban) (source)
- [JSON Canvas 1.0](https://jsoncanvas.org/spec/1.0/) (specification)
- [Dataview](https://blacksmithgu.github.io/obsidian-dataview/) (official)
- [Quarto dashboard layout](https://quarto.org/docs/dashboards/layout.html) and
  [website listings](https://quarto.org/docs/websites/website-listings.html) (official,
  Quarto)
- [Pandoc divs and spans](https://pandoc.org/MANUAL.html#divs-and-spans) (official)
- [Markdoc tags](https://markdoc.dev/docs/tags) (official)
- [MyST syntax overview](https://mystmd.org/guide/syntax-overview) (official)
- [micromark directive extension](https://github.com/micromark/micromark-extension-directive),
  [remark-directive](https://github.com/remarkjs/remark-directive), and the
  [generic directives proposal](https://talk.commonmark.org/t/generic-directives-plugins-syntax/444)
- [MDX](https://mdxjs.com/) (official)
- [Evidence](https://docs.evidence.dev/) and
  [Observable Framework data loaders](https://observablehq.com/framework/loaders)
  (official)
- [Anytype sets and collections](https://doc.anytype.io/anytype-docs/basics/sets-and-collections)
  (official), [Logseq](https://docs.logseq.com/), and
  [Tana supertags](https://tana.inc/docs/supertags)
- [Open Graph](https://ogp.me/) and [oEmbed](https://oembed.com/) (specifications)
- [Auto Card Link](https://github.com/nekoshita/obsidian-auto-card-link) (source)
- [Raindrop import](https://help.raindrop.io/import) (official)
- [OPML 2.0](http://opml.org/spec2.opml) (specification)
- [todo.txt](https://github.com/todotxt/todo.txt) and
  [TaskPaper](https://www.taskpaper.com/guide/getting-started/) (official)
- [GitHub Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects)
  (official), [Backlog.md](https://github.com/MrLesk/Backlog.md), and
  [kanban-md](https://github.com/antopolskiy/kanban-md)
- [Starlight link cards](https://starlight.astro.build/components/link-cards/),
  [Hextra cards](https://imfing.github.io/hextra/docs/guide/shortcodes/cards/), and
  [Jekyll data files](https://jekyllrb.com/docs/datafiles/)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
