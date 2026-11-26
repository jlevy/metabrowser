# Plan for Lean Language Support and a Repeatable Language Recipe

**Date:** 2026-11-25 (last updated 2026-11-26)

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Implemented on branch `claude/stoic-dijkstra-iyonj6`, in review.
Epic `mb-h7f9` tracks it.

## Overview

The owner asked, on 2026-11-25, to add Lean to Metabrowser end to end, “modeled on
standard tooling for syntax and any other related formats”: a known coding language with
GitHub’s color, highlighted source, and whatever else a language needs.
They also asked for the steps to be written down so the next language is repeatable, and
for an agent skill that points anyone asking for a new language at the right code and at
the official upstream documentation.

On 2026-11-26 they asked for the work to be mapped out in detail as beads and finished
end to end; for a minimal set of Metabrowser skills, each named with an `mb-` prefix,
including one for adding a plugin that refers to adding a language; and for the
documents this touches to be revised so they are current.

## Goals

- `.lean` files are the Lean family everywhere a family shows: the Files filter,
  Overview’s type breakdown, the Treemap, file colors, and the CLI.
- The family’s color is GitHub’s: the `color` linguist gives `Lean`, which its `Lean 4`
  entry inherits through `group: Lean`.
- Lean 4 source highlights in Source views and diffs as the official Lean 4 grammar
  highlights it.
- Lean fences in Markdown highlight, through the lexer KPress already uses.
- One document lists every surface a programming language touches; the `mb-add-language`
  skill routes to it, and `mb-add-plugin` routes plugin work to the plugin documents and
  on to it.

## Non-Goals

- **Lake and toolchain files.** `lakefile.toml` is TOML, `lake-manifest.json` is JSON,
  and `lakefile.lean` is `.lean`, so each already has a family and a grammar.
  `lean-toolchain` is one line of plain text that linguist does not classify; sniffing
  opens it as text. Classifying it as Lean would color a configuration file as code.
- **Build artifacts.** `.olean` and `.ilean` live under `.lake/`, which Lake’s own
  project template ignores in Git; linguist classifies neither.
- **Language-server features.** Goal states, the infoview, hover, and go-to-definition
  need a running Lean server, which a file browser does not have.
- **Markdown inside Lean comments.** The official grammar embeds a Markdown grammar in
  comments; the port draws a comment as one comment.
- **Renaming the shipped `metabrowser` skill.** Users install it by that name, and its
  name already says what it is for.

## Background

### Where a Language Lives Today

A programming language passes through four independent registries.
Each has its own upstream source of truth:

| Surface | Registry in this repository | Upstream source |
| --- | --- | --- |
| Family, group, extensions, color | `src/metabrowser/data/file-rollup-format/recommended-file-types.toml` | [linguist `languages.yml`](https://github.com/github-linguist/linguist/blob/main/lib/linguist/languages.yml) |
| Source and diff highlighting | `SYNTAX_LANGUAGE_BY_EXTENSION` in `src/metabrowser/file_extensions.py` | [Highlight.js supported languages](https://github.com/highlightjs/highlight.js/blob/main/SUPPORTED_LANGUAGES.md), or the language’s own grammar |
| Grammar not in the vendored common build | `devtools/vendor_assets.py` or `static/syntax/`, and `server.py`’s prefetched tier | the grammar’s package or repository |
| Markdown fences | KPress’s server-side highlighting | [Pygments lexers](https://pygments.org/docs/lexers/) |

### What Upstream Says About Lean

- **Linguist** has two entries: `Lean` (`.lean`, `.hlean`, color `#3d6ac9`) and `Lean 4`
  (`.lean`, alias `lean4`, `group: Lean`, no color of its own, so GitHub paints it as
  Lean). The `linguist-languages` npm mirror (9.5.0) predates the color, so the registry
  reads linguist’s `main`, not a mirror.
- **Highlight.js** has no Lean grammar in its core.
  Its supported-languages table lists the third-party
  [`highlightjs-lean`](https://github.com/leanprover-community/highlightjs-lean) 1.2.0,
  whose `master` is that release.
  It is a Lean 3 grammar: `abbrev`, `where`, `deriving`, `set_option`, and `#eval` are
  plain text, and a doc comment takes the keyword color.
- **The Lean project’s own grammar** is
  [`syntaxes/lean4.json`](https://github.com/leanprover/vscode-lean4/blob/master/vscode-lean4/syntaxes/lean4.json)
  in `leanprover/vscode-lean4` (Apache-2.0), the TextMate grammar VS Code, linguist’s
  `Lean 4` (`tm_scope: source.lean4`), and Shiki use.
- **Pygments** 2.20 (our lock) has `LeanLexer` (`lean`, `lean3`) and `Lean4Lexer`
  (`lean4`), so KPress highlights Lean fences with no change here.

## Design

**Mirror upstream exactly.** The family takes linguist’s name, extensions, and color;
the hue is that color in oklch, unchanged.
The kind lists linguist’s extensions, `.lean` and `.hlean`.

**Port the official grammar.** The Lean 3 grammar Highlight.js lists was vendored first
and replaced once the gap was measured: most Lean 4 declarations lost their keywords.
`static/syntax/lean.js` ports `lean4.json` rule for rule: every upstream regex is copied
verbatim into a constant of its own, TextMate scopes map to standard Highlight.js
scopes, and it registers as `lean` with the alias `lean4`. The Markdown grammar inside
comments is not ported.
What Oniguruma under TextMate and a JavaScript regex under Highlight.js read differently
is changed where a constant is compiled, by the entries of `ADAPTATIONS` in the file:
POSIX `[:space:]`, the Unicode `\b` and `\w`, a binder that stays on its line, and a
bound, `SCAN_LIMIT`, on each scan for a closing bracket.
The bound is there because Highlight.js gives a regex the whole file where TextMate
gives it a line: an unclosed `def {` or `trace[` rescanned the rest of the file at every
occurrence, and a file at the highlight limit froze the tab for most of a minute.
The measurement is beside the constant.
Highlight.js tries a mode’s contents before its `end`, the reverse of TextMate, so the
declaration-name pattern carries a lookahead of the upstream `end` and
`structure Point where` ends at `where` as upstream does.
The upstream file is pinned at vscode-lean4 commit `9ac77ca57bf7`, with its license, in
`tests/fixtures/vscode-lean4/`; `tests/test_lean_grammar.py` holds the port’s constants
to it in both directions and runs source for every constant and every adaptation through
the vendored runtime.
The port loads in the prefetched tier beside the TOML grammar; `server.py` records its
size there.

`sorry` and `admit`, which upstream marks invalid, keep a `sorry` scope, and the
stylesheet gives it the warning token.
Upstream’s rule names `#exit` too, but between two `\b`, so it never matches the command
at the start of a line; the port keeps that.

**Skills are routers.** `mb-add-language` and `mb-add-plugin` live in `.agents/skills/`,
linked from `.claude/skills/`, and send an agent to the documents; neither restates a
procedure.

## Implementation Plan

### Phase 1: Lean, the Recipe, and the Skills

- [x] Family and kind, registry revision 5, regenerated contract artifacts and goldens.
- [x] Port the official Lean 4 grammar, pin the upstream file, test the port against it.
- [x] Load the port in the prefetched tier; `.lean`/`.hlean` in
  `SYNTAX_LANGUAGE_BY_EXTENSION`; `sorry` styled with a design token.
- [x] Verify in Chrome: Source view, diff highlighting, file color, Markdown fence.
- [x] [Adding a Language](../../../adding-a-language.md), linked from Adding a File
  Type, the README, and Development.
- [x] `mb-add-language` and `mb-add-plugin` skills.
- [x] Revise the documents this touches: plugin authoring, browsing files, the plugin
  system, and Development.
- [x] Changelog fragment.

### Follow-Up

- KPress resolves a `lean` fence to Pygments’ Lean 3 lexer; `lean4` gets the Lean 4
  lexer. That choice is KPress’s, in its own repository.
- A Docs view for `.lean` files, below.

## Lean’s Documentation Tools

The owner asked on 2026-11-26 which other tools render Lean or its documentation, and
whether any is established enough to support.
The survey read a page of the Mathlib API documentation
(`mathlib4_docs/Mathlib/AlgebraicGeometry/Cover/Directed.html`) and the tools’ READMEs.

| Tool | What it is | Established | What Metabrowser does with it |
| --- | --- | --- | --- |
| [doc-gen4](https://github.com/leanprover/doc-gen4) | The Lean FRO’s API documentation generator: `lake build <lib>:docs` writes a static site to `.lake/build/doc` | Yes: Mathlib, Lean core, and most published Lean packages | Its `[source]` links are GitHub blob URLs with `#L42-L55` ranges, which Metabrowser’s Source view and GitHub URL reducer already accept |
| [Verso](https://github.com/leanprover/verso) | The Lean FRO’s authoring tool, behind the Lean reference manual and the books; documents are `.lean` files | Yes, and growing | Its sources are `.lean` files, so the Lean family and grammar cover them |
| vscode-lean4’s TextMate grammar | The editor grammar linguist and Shiki use | Yes | Ported as `static/syntax/lean.js` |
| Pygments `Lean4Lexer` | Server-side lexer | Yes | KPress highlights `lean4` fences with it |
| leanblueprint | A plasTeX blueprint of a formalization, with a dependency graph | Common in large formalization projects | None: its sources are LaTeX, a language of their own |
| Alectryon with LeanInk | Literate proofs with goal states | Lean 3 era; little Lean 4 use | None |

What the Mathlib page shows a reader of a `.lean` file expects: the module doc comment
(`/-! … -/`) rendered as Markdown with its headings as anchors; each declaration as a
block of attributes, kind, name, binders, and type, with its doc comment rendered
beneath; math in doc comments as TeX (MathJax there); and a source link to the
declaration’s line range.
All but the hyperlinked identifiers and instance lists come from the source text alone.

**Proposal, not scheduled:** a Docs view for `.lean` files in a built-in `lean` plugin,
next to Source: the module and declaration doc comments rendered through KPress, which
already renders Markdown and math, with each declaration’s header linking to its line
range in Source. It needs no compiled `.olean` files and no Lean toolchain.
Serving a doc-gen4 build itself needs no work beyond serving the folder.

## Testing Strategy

- `tests/test_lean_grammar.py`: the port against the pinned upstream grammar; source for
  every upstream rule and every adaptation through the vendored runtime, with the scopes
  it takes; and an unclosed opener repeated to the highlight limit, which must finish
  within the test’s node budget.
- `tests/test_file_extensions.py` and `test_plugin_sdk_syntax_token_contracts` hold the
  syntax registry to the loaded grammars; the shim loads every grammar in
  `static/vendor/` and `static/syntax/`.
- `devtools/file_type_contract.py` regenerates the conformance fixture, which pins
  `.lean` and `.hlean` to the family; `devtools/check_file_type_colors.py` holds the
  hue.
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
