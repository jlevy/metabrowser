---
cwd: ../..
sandbox: false
---
# Golden Test: A Title’s Conventional-Commit Prefix

A commit’s or a pull request’s title draws a conventional-commit prefix such as
`feat(ledger):` at regular weight and the rest of the title at the title’s own weight.
One function splits a title, `titlePrefix` in `static/formatters.js`, and `titleNodes`
and `titleHtml` beside it draw the prefix in a `span.title-prefix`. The plugin SDK’s
`mb.titleNodes` hands its title to the same function.
Every surface that shows a title draws it through one of them: the Pulls rows, the pull
request page’s title, its stack menu, its Conversation’s commits, Quick Search’s pull
requests, the Commits tab’s rows, a commit’s page, and its tooltip.

This browserless session runs the real formatter runtime and plugin SDK and records, for
each case, the prefix the split finds and its length in characters.
The transcript pins these behaviors:

- A prefix is a type of lowercase ASCII letters, an optional scope in parentheses, an
  optional `!`, and the colon.
  A scope is one or more characters other than parentheses, so a space or a comma may be
  in it, and an empty `()` is not a scope.
- A prefix counts only at 32 characters or fewer, the colon included, counted in code
  points: `feat(view-on-github):` and `fix(source-freshness, checkout):` count, and
  `test(source-freshness, checkout):` does not.
  The cap keeps a lowercase word and a parenthetical sentence before a colon, such as
  `note(this is how the cache and the scroller keep a row):`, the title’s own text.
- Whitespace and something else must follow the colon.
  A title with no space after its colon, or nothing but whitespace after it, has no
  prefix.
- An uppercase type, a type with a digit or a hyphen, a merge commit, and a `Revert "…"`
  title have no prefix.
  The split reads only the start of a title, so a revert’s quoted prefix stays its text.
- A title is split in two parts that are the whole title, and a title with no prefix is
  drawn as before: its text alone, and as markup what the SDK’s `escapeHtml` writes.
  The session fails if either ever differs, or if the SDK’s nodes differ from the
  shell’s.
- A caller that marks matches, as Quick Search does, gets each part with where it starts
  in the title.

```console
$ node tests/dom/title-prefix-session.js
{
  "cases": {
    "the request's example": {
      "title": "feat(ledger): chart strategies, range ba… (81 characters)",
      "prefix": "feat(ledger):",
      "characters": 13
    },
    "a type alone": {
      "title": "fix: keep the scroller rule and the Tab stop of a lost landing",
      "prefix": "fix:",
      "characters": 4
    },
    "a breaking change": {
      "title": "refactor(api)!: drop the version 1 routes",
      "prefix": "refactor(api)!:",
      "characters": 15
    },
    "a breaking change, no scope": {
      "title": "feat!: separate cache and config roots",
      "prefix": "feat!:",
      "characters": 6
    },
    "16 characters, the first cap": {
      "title": "refactor(stack): name the stack's Control chords",
      "prefix": "refactor(stack):",
      "characters": 16
    },
    "17 characters": {
      "title": "refactor(stacks): name the stack's Control chords",
      "prefix": "refactor(stacks):",
      "characters": 17
    },
    "17 characters, from this repository": {
      "title": "revert(markdown): restore the table of contents",
      "prefix": "revert(markdown):",
      "characters": 17
    },
    "a hyphenated scope, 21 characters": {
      "title": "feat(view-on-github): open the pull request on github.com",
      "prefix": "feat(view-on-github):",
      "characters": 21
    },
    "24 characters, from this repository": {
      "title": "fix(provider-resources): bound the resource reads",
      "prefix": "fix(provider-resources):",
      "characters": 24
    },
    "a scope with a space": {
      "title": "fix(ui, git): a landing waits for the HEAD read",
      "prefix": "fix(ui, git):",
      "characters": 13
    },
    "a scope with a space, 20 characters": {
      "title": "fix(commits, pulls): a landing waits for the HEAD read; stack keys wait",
      "prefix": "fix(commits, pulls):",
      "characters": 20
    },
    "exactly 32 characters": {
      "title": "fix(source-freshness, checkout): read the HEAD once",
      "prefix": "fix(source-freshness, checkout):",
      "characters": 32
    },
    "33 characters": {
      "title": "test(source-freshness, checkout): read the HEAD once",
      "prefix": null
    },
    "32 characters in code points": {
      "title": "refactor(🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀): launch the stack",
      "prefix": "refactor(🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀):",
      "characters": 32
    },
    "a sentence that looks like a prefix": {
      "title": "note(this is how the cache and the scroller keep a row): read on",
      "prefix": null
    },
    "an empty scope": {
      "title": "fix(): keep the scroller rule",
      "prefix": null
    },
    "no space after the colon": {
      "title": "fix:keep the scroller rule",
      "prefix": null
    },
    "no space after the colon, with a scope": {
      "title": "feat(ledger):chart strategies",
      "prefix": null
    },
    "an uppercase type": {
      "title": "Docs: link every shortcut description",
      "prefix": null
    },
    "an uppercase draft marker": {
      "title": "WIP: draft the next page",
      "prefix": null
    },
    "a digit in the type": {
      "title": "exp-040: measure large pull requests against github.com",
      "prefix": null
    },
    "a merge commit": {
      "title": "Merge pull request #400 from jlevy/claude/keymap-commits-landing-focus",
      "prefix": null
    },
    "a revert": {
      "title": "Revert \"fix(git): keep the scroller rule\"",
      "prefix": null
    },
    "a revert typed as one": {
      "title": "revert: \"fix(git): keep the scroller rule\"",
      "prefix": "revert:",
      "characters": 7
    },
    "an empty rest": {
      "title": "fix:",
      "prefix": null
    },
    "a rest of whitespace": {
      "title": "fix:   ",
      "prefix": null
    },
    "a long title": {
      "title": "perf: decide every region's box at first… (341 characters)",
      "prefix": "perf:",
      "characters": 5
    },
    "a long title with no prefix": {
      "title": "Perf: decide every region's box at first… (341 characters)",
      "prefix": null
    },
    "markup in the title": {
      "title": "fix(<b>): escape <em> & \"quotes\"",
      "prefix": "fix(<b>):",
      "characters": 9
    }
  },
  "noPrefixDrawsItsTextAlone": 13,
  "markup": {
    "nodes": [
      {
        "tag": "span",
        "class": "title-prefix",
        "children": [
          "feat(ledger):"
        ]
      },
      " chart strategies"
    ],
    "html": "<span class=\"title-prefix\">fix(&lt;b&gt;):</span> escape &lt;em&gt; &amp; &quot;quotes&quot;"
  },
  "parts": [
    {
      "text": "feat(ledger):",
      "start": 0
    },
    {
      "text": " chart strategies",
      "start": 13
    }
  ]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
