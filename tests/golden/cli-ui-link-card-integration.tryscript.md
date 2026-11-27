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
- `a file the tree gains`: a file the served tree lacks is called missing, and once the
  tree has it, the next rest says where it opens.
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
 "a file the tree gains": [
  {
   "at": 0,
   "pointer": "the old guide"
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
   "sees": "docs/old-guide.md | Not in the served files",
   "on": "the old guide"
  },
  {
   "at": 800,
   "pointer": "the body"
  },
  {
   "at": 1000,
   "pointer": "the old guide"
  },
  {
   "at": 1700,
   "sees": "docs/old-guide.md | Opens in the served working tree",
   "on": "the old guide"
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
