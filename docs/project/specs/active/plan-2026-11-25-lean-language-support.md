# Plan for Lean Language Support and a Repeatable Language Recipe

**Date:** 2026-11-25

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Approved 2026-11-25. Epic `mb-h7f9` tracks it.

## Overview

The owner asked, on 2026-11-25, to add Lean to Metabrowser end to end, “modeled on
standard tooling for syntax and any other related formats”: a known coding language with
GitHub’s color, highlighted source, and whatever else a language needs.
They also asked for the steps to be written down so the next language is repeatable, and
for an agent skill that points anyone asking for a new language at the right code and at
the official upstream documentation.

## Goals

- `.lean` files are the Lean family everywhere a family shows: the Files filter,
  Overview’s type breakdown, the Treemap, file colors, and the CLI.
- The family’s color is GitHub’s: the `color` linguist gives `Lean`, which its `Lean 4`
  entry inherits through `group: Lean`.
- Lean source opens as highlighted text in every Source view, through a grammar the
  Highlight.js project lists as Lean’s.
- Lean fences in Markdown highlight, through the lexer KPress already uses.
- One document lists every surface a programming language touches, and one small skill
  routes an agent to it.

## Non-Goals

- **Lake and toolchain files.** `lakefile.toml` is TOML, `lake-manifest.json` is JSON,
  and `lakefile.lean` is `.lean`, so each already has a family and a grammar.
  `lean-toolchain` is one line of plain text that linguist does not classify; sniffing
  opens it as text. Classifying it as Lean would color a configuration file as code.
- **Build artifacts.** `.olean` and `.ilean` live under `.lake/`, which Lake’s own
  project template ignores in Git; linguist classifies neither.
- **Language-server features.** Goal states, the infoview, hover, and go-to-definition
  need a running Lean server, which a file browser does not have.
- **A Lean 4 TextMate grammar.** Highlight.js does not read TextMate grammars, and
  shipping a second highlighter for one language is out of proportion.

## Background

### Where a Language Lives Today

A programming language passes through four independent registries.
Each has its own upstream source of truth:

| Surface | Registry in this repository | Upstream source |
| --- | --- | --- |
| Family, group, extensions, color | `src/metabrowser/data/file-rollup-format/recommended-file-types.toml` | [linguist `languages.yml`](https://github.com/github-linguist/linguist/blob/main/lib/linguist/languages.yml) |
| Source-view highlighting | `SYNTAX_LANGUAGE_BY_EXTENSION` in `src/metabrowser/file_extensions.py` | [Highlight.js supported languages](https://github.com/highlightjs/highlight.js/blob/main/SUPPORTED_LANGUAGES.md) |
| Grammar not in the vendored common build | `devtools/vendor_assets.py`, `server.py`’s prefetched tier | the grammar’s npm package |
| Markdown fences | KPress’s server-side highlighting | [Pygments lexers](https://pygments.org/docs/lexers/) |

The [Adding a File Type](../../architecture/arch-plugin-system.md#adding-a-file-type)
steps 6 and 7 name the first three; nothing names them together for a language, and the
TOML grammar was the only third-party-shaped addition so far.

### What Upstream Says About Lean

- **Linguist** has two entries: `Lean` (`.lean`, `.hlean`, color `#3d6ac9`) and `Lean 4`
  (`.lean`, alias `lean4`, `group: Lean`, no color of its own, so GitHub paints it as
  Lean). The `linguist-languages` npm mirror (9.5.0) predates the color, so the registry
  reads linguist’s `main`, not a mirror.
- **Highlight.js** has no Lean grammar in its core.
  Its supported-languages table lists the third-party
  [`highlightjs-lean`](https://github.com/leanprover-community/highlightjs-lean), from
  the `leanprover-community` organization.
- **Pygments** 2.20 (our lock) has `LeanLexer` (`lean`, `lean3`) and `Lean4Lexer`
  (`lean4`), so KPress highlights Lean fences with no change here.

### The Grammar Package, Reviewed

Against
[Review Before Adding](../../../../SUPPLY-CHAIN-SECURITY.md#review-before-adding):

1. **Necessary:** the vendored Highlight.js common build has no Lean grammar.
2. **Identity:** `highlightjs-lean`, repository `leanprover-community/highlightjs-lean`,
   BSD-3-Clause, published by a `leanprover-community` maintainer.
3. **Age:** 1.2.0 was published 2024-06-30, far past the 14-day cool-off.
4. **Artifacts:** three files; `dist/lean.min.js` (2,329 bytes) is a classic script
   whose banner says it was compiled for Highlight.js 11.9.0, the version vendored here,
   and it calls `hljs.registerLanguage("lean", …)`. No install scripts.
5. **Transitive growth:** no runtime dependencies.
6. **Lock delta:** one package.

The grammar predates Lean 4’s keyword set: `abbrev`, `where`, `deriving`, and
`set_option` are plain text.
Comments, strings, numbers, declarations, tactics, and attributes highlight.
That is upstream’s gap to close, not a reason to fork a grammar here.

## Design

**Mirror upstream exactly.** The family takes linguist’s name, extensions, and color;
the hue is that color in oklch, unchanged.
The kind lists linguist’s extensions, `.lean` and `.hlean`. The grammar is the one
Highlight.js lists, vendored byte for byte through the existing manifest, and loaded in
the prefetched tier beside the TOML grammar: it is a few kilobytes, needs only `hljs`,
and cannot block a paint.

`sorry` and `admit` get their own scope from the grammar (`hljs-sorry`). They mark an
unfinished proof, so the stylesheet gives them the warning token, the way the grammar’s
README suggests a color for them.

## Implementation Plan

### Phase 1: Lean, the Recipe, and the Skill

- [ ] Family and kind: `lean` in the recommended file types, `registry_revision`
  incremented, checked copies regenerated, color check run.
- [ ] Grammar: `highlightjs-lean` in `package.json` and the lock, a vendor entry, the
  manifest and license, the prefetched tier, and `.lean`/`.hlean` in
  `SYNTAX_LANGUAGE_BY_EXTENSION`.
- [ ] Style the `sorry` scope with a design token.
- [ ] Prove it: the syntax-token contract loads the grammar, a Source view of a Lean
  file highlights, and the CLI golden that shows a file’s family covers Lean.
- [ ] Document the recipe as a contributor guide that names every surface above and
  links each upstream source.
- [ ] Add a minimal agent skill that routes a language request to the guide.
- [ ] Changelog fragment.

## Testing Strategy

- `tests/test_file_extensions.py` and `test_plugin_sdk_syntax_token_contracts` already
  hold the syntax registry to the vendored grammars; the shim loads the new grammar.
- `devtools/file_type_contract.py` and `devtools/check_file_type_colors.py` hold the
  family.
- A CLI golden pins `metab --show` on a Lean file.
- `make verify`.

## Open Questions

None. `.hlean` is Lean 2’s homotopy type theory mode and is long retired, but linguist
lists it and the recipe mirrors linguist rather than editing it.

## References

- [Adding a Language](../../../adding-a-language.md), the recipe this plan writes
- [Adding a File Type](../../architecture/arch-plugin-system.md#adding-a-file-type)
- [File Rollup Format](../../architecture/file-rollup-format/file-rollup-format.md)
- [Lean language reference](https://lean-lang.org/doc/reference/latest/)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
