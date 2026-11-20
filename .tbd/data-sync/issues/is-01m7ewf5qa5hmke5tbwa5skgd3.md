---
type: is
id: is-01m7ewf5qa5hmke5tbwa5skgd3
title: "Wiki parser heading regexes backtrack superlinearly; ATX closing # needs whitespace"
kind: bug
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7wysdnvzch4gb5zvqwvn04e
created_at: 2026-11-15T05:56:47.465Z
updated_at: 2026-11-20T17:13:55.450Z
---
Deferred from review A on PR #437 (mb-a9be), suggestion A6: https://github.com/jlevy/metabrowser/pull/437#pullrequestreview-5909332132

The heading regexes in src/metabrowser/builtin_plugins/markdown/wiki-parser.js backtrack superlinearly on crafted lines (pre-existing):
- `findMarkdownHeading`'s ATX pattern pairs a lazy `(.+?)` with `[\t ]*#*[\t ]*$`. On `# ` followed by a long run of `#` and then a letter, each lazy extension rescans the tail.
- `headingText`'s link patterns rescan from every `[`.

By reading, both are at least quadratic in a backtracking engine. `assertLinearWork` does not meter regex work, and one line can be as long as the 2,000,000-character source cap. The review did not reproduce a slowdown; measure one before fixing.

The same ATX pattern strips a closing `#` run with no whitespace before it, which CommonMark does not: `## C#` is titled `C#` by KPress but named `C` by the parser, so `obsidian-heading-C` names it. This is hard to reach through an Obsidian link, where `#` separates heading levels.

Done when the ATX trim is procedural and linear (in the style of markdown-it's `skipSpacesBack` and `skipCharsStrBack`) and follows CommonMark's closing-sequence rule; `headingText` is linear; and a test pins both the timing bound on a crafted line and `## C#`'s name. PR #437 deliberately left these regexes unchanged.
