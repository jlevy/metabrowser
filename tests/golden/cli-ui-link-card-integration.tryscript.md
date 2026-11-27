---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: The Link Card Across Its Boundaries

A link in rendered text has the link card
([Tooltips on Links](../../docs/design-system.md#tooltips-on-links)).
`cli-ui-link-previews.tryscript.md` pins the card’s rules on its module alone, and
`cli-ui-link-preview-providers.tryscript.md` its data on a stand-in registry.
This session runs the boundaries between them for real, in one realm as one page does:
app.js’s own tooltip and its delegated listeners for short tips and focus, the
resolver’s `enhance` over a pull request’s text in a KPress host, the SDK it registers
each link through, which loads the card’s bundle at the first rest, here at once, the
card’s registry, and its providers, each read replaying the server’s recorded answer 40
ms later on the session’s clock.
`cli-ui-link-preview-loader.tryscript.md` pins what that load does when it takes time,
fails, or never comes.

Each log entry says when, in milliseconds, the pointer arrived on something (`pointer`),
the SDK asked for the card’s bundle (`load`) and it ran (`loaded`), focus moved
(`focus`), a provider read the server (`read`), and what the reader sees (`sees`), with
the element the tooltip is placed on (`on`).

- `rest`: the card comes up on the tooltip’s own delay with the title its catalog row
  gives, and goes when the pointer leaves.
- `handover`: the pointer moves straight from one link’s card onto the next link, and
  the next link’s card comes up on it.
- `focus during the read`: focus moves onto the link while its read is out, and no card
  comes back when it answers.
- `a failed read, then the next rest`: the first read fails, and the next rest reads
  again and says the title.
- `files the catalog leaves out`: a plain folder’s document links each of its files, and
  one the page’s Quick File catalog leaves out (`unlisted`: a hidden, a gitignored, and
  a symlinked file, which the folder opens all the same) has the card a file it lists
  (`listed`) has, but for its path: none is called missing.
- `a folder the tree totals`: a rest on a folder’s link before the tree has totaled it,
  then the next rest, once it has, says its totals.
- `an image inside a link`: the pointer crosses from a link’s words onto the chip of an
  image the page did not load and back; the card, saying the image’s address, is the one
  tooltip throughout.
- `a link to another site`: its card says where it goes, and nothing is read.

```console
$ node tests/dom/link-card-integration-session.js
{
 "rest": [
  {
   "at": 0,
   "pointer": "#12"
  },
  {
   "at": 0,
   "load": "link-previews"
  },
  {
   "at": 0,
   "loaded": "link-previews"
  },
  {
   "at": 250,
   "read": "github/pulls?q=12"
  },
  {
   "at": 250,
   "read": "github/pull?number=12&warm=1"
  },
  {
   "at": 299,
   "sees": null
  },
  {
   "at": 320,
   "sees": "Pull request #12 | feat(links): preview what a link opens | Opens here in Metabrowser",
   "on": "#12"
  },
  {
   "at": 700,
   "pointer": "the body"
  },
  {
   "at": 900,
   "sees": null
  }
 ],
 "handover": [
  {
   "at": 0,
   "pointer": "#12"
  },
  {
   "at": 0,
   "load": "link-previews"
  },
  {
   "at": 0,
   "loaded": "link-previews"
  },
  {
   "at": 250,
   "read": "github/pulls?q=12"
  },
  {
   "at": 250,
   "read": "github/pull?number=12&warm=1"
  },
  {
   "at": 700,
   "sees": "Pull request #12 | feat(links): preview what a link opens | Opens here in Metabrowser",
   "on": "#12"
  },
  {
   "at": 720,
   "pointer": "#13"
  },
  {
   "at": 970,
   "read": "github/pulls?q=13"
  },
  {
   "at": 970,
   "read": "github/pull?number=13&warm=1"
  },
  {
   "at": 1100,
   "sees": "Pull request #13 | Draft: a tooltip for every in-app link | Opens here in Metabrowser",
   "on": "#13"
  }
 ],
 "focus during the read": [
  {
   "at": 0,
   "pointer": "#14"
  },
  {
   "at": 0,
   "load": "link-previews"
  },
  {
   "at": 0,
   "loaded": "link-previews"
  },
  {
   "at": 250,
   "read": "github/pulls?q=14"
  },
  {
   "at": 250,
   "read": "github/pull?number=14&warm=1"
  },
  {
   "at": 260,
   "focus": "#14"
  },
  {
   "at": 280,
   "sees": null
  },
  {
   "at": 700,
   "sees": null
  }
 ],
 "a failed read, then the next rest": [
  {
   "at": 0,
   "pointer": "#15"
  },
  {
   "at": 0,
   "load": "link-previews"
  },
  {
   "at": 0,
   "loaded": "link-previews"
  },
  {
   "at": 250,
   "read": "github/pulls?q=15"
  },
  {
   "at": 250,
   "read": "github/pull?number=15&warm=1"
  },
  {
   "at": 700,
   "sees": "Pull request #15 | Opens here in Metabrowser",
   "on": "#15"
  },
  {
   "at": 800,
   "pointer": "the body"
  },
  {
   "at": 1000,
   "pointer": "#15"
  },
  {
   "at": 1250,
   "read": "github/pulls?q=15"
  },
  {
   "at": 1250,
   "read": "github/pull?number=15&warm=1"
  },
  {
   "at": 1700,
   "sees": "Pull request #15 | docs: the rule for tooltips on links | Opens here in Metabrowser",
   "on": "#15"
  }
 ],
 "files the catalog leaves out": [
  {
   "at": 0,
   "registered": "listed README.md",
   "card": true
  },
  {
   "at": 0,
   "registered": "listed docs/guide.md",
   "card": true
  },
  {
   "at": 0,
   "registered": "unlisted .github/CONTRIBUTING.md",
   "card": true
  },
  {
   "at": 0,
   "registered": "unlisted build/report.md",
   "card": true
  },
  {
   "at": 0,
   "registered": "unlisted alias.md",
   "card": true
  },
  {
   "at": 0,
   "pointer": "listed README.md"
  },
  {
   "at": 0,
   "load": "link-previews"
  },
  {
   "at": 0,
   "loaded": "link-previews"
  },
  {
   "at": 700,
   "sees": "README.md | Opens here in Metabrowser",
   "on": "listed README.md"
  },
  {
   "at": 800,
   "pointer": "the body"
  },
  {
   "at": 1000,
   "pointer": "listed docs/guide.md"
  },
  {
   "at": 1700,
   "sees": "docs/guide.md | Opens here in Metabrowser",
   "on": "listed docs/guide.md"
  },
  {
   "at": 1800,
   "pointer": "the body"
  },
  {
   "at": 2000,
   "pointer": "unlisted .github/CONTRIBUTING.md"
  },
  {
   "at": 2700,
   "sees": ".github/CONTRIBUTING.md | Opens here in Metabrowser",
   "on": "unlisted .github/CONTRIBUTING.md"
  },
  {
   "at": 2800,
   "pointer": "the body"
  },
  {
   "at": 3000,
   "pointer": "unlisted build/report.md"
  },
  {
   "at": 3700,
   "sees": "build/report.md | Opens here in Metabrowser",
   "on": "unlisted build/report.md"
  },
  {
   "at": 3800,
   "pointer": "the body"
  },
  {
   "at": 4000,
   "pointer": "unlisted alias.md"
  },
  {
   "at": 4700,
   "sees": "alias.md | Opens here in Metabrowser",
   "on": "unlisted alias.md"
  },
  {
   "at": 4800,
   "pointer": "the body"
  }
 ],
 "a folder the tree totals": [
  {
   "at": 0,
   "registered": "the docs",
   "card": true
  },
  {
   "at": 0,
   "pointer": "the docs"
  },
  {
   "at": 0,
   "load": "link-previews"
  },
  {
   "at": 0,
   "loaded": "link-previews"
  },
  {
   "at": 700,
   "sees": "docs/ | Opens here in Metabrowser",
   "on": "the docs"
  },
  {
   "at": 800,
   "pointer": "the body"
  },
  {
   "at": 1000,
   "pointer": "the docs"
  },
  {
   "at": 1700,
   "sees": "docs/ | 1 files · 48 B | Opens here in Metabrowser",
   "on": "the docs"
  }
 ],
 "an image inside a link": [
  {
   "at": 0,
   "pointer": "the link's words"
  },
  {
   "at": 0,
   "load": "link-previews"
  },
  {
   "at": 0,
   "loaded": "link-previews"
  },
  {
   "at": 250,
   "read": "github/pulls?q=12"
  },
  {
   "at": 250,
   "read": "github/pull?number=12&warm=1"
  },
  {
   "at": 400,
   "sees": "Pull request #12 | feat(links): preview what a link opens | Image from https://img.example/badge.svg | Opens here in Metabrowser",
   "on": "#12"
  },
  {
   "at": 450,
   "pointer": "the badge's chip"
  },
  {
   "at": 800,
   "sees": "Pull request #12 | feat(links): preview what a link opens | Image from https://img.example/badge.svg | Opens here in Metabrowser",
   "on": "#12"
  },
  {
   "at": 850,
   "pointer": "the link's words"
  },
  {
   "at": 1200,
   "sees": "Pull request #12 | feat(links): preview what a link opens | Image from https://img.example/badge.svg | Opens here in Metabrowser",
   "on": "#12"
  }
 ],
 "a link to another site": [
  {
   "at": 0,
   "pointer": "elsewhere"
  },
  {
   "at": 0,
   "load": "link-previews"
  },
  {
   "at": 0,
   "loaded": "link-previews"
  },
  {
   "at": 320,
   "sees": "Opens example.com in a new tab",
   "on": "elsewhere"
  }
 ]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
