---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Link’s Card Before Its Code Loads

Every link in authored text has the link card
([Tooltips on Links](../../docs/design-system.md#tooltips-on-links)), on every page,
whatever repository it serves.
A surface registers each link through the SDK (`metabrowser.previewLink` in
`static/plugin-sdk-views.js`), which keeps it until a pointer first rests on one, then
loads the card’s own bundle, `link-previews`, and hands its registry every link and that
rest.
This session runs the SDK’s view helpers whole, app.js’s own tooltip, and the exact
bundle, run when the SDK asks for it after the time the session gives the load, or
refused. Most pages are a plain folder’s, with no GitHub identity, whose Markdown
document links a file, a folder, another site, and a mail address, registered as the
Markdown enhancer registers them; one is a GitHub checkout’s, whose pull request’s text
the resolver reads.

Each log entry says when, in milliseconds, a link was registered and whether the SDK
answered that it has a card (`registered`, `card`), the pointer arrived on something
(`pointer`), the reader pressed (`press`), the SDK asked for the bundle (`load`) and it
ran (`loaded`) or failed, a provider read the server (`read`), the page warned
(`warned`), and what the reader sees (`sees`), with the element the tooltip is placed on
(`on`).

- `registered before the bundle`: four links registered, three with a card and the mail
  link without one, and nothing loaded with no pointer anywhere.
- `the first rest loads it`: the first rest loads the bundle, 30 ms, and the file’s card
  comes up on its link for that rest, the tooltip’s own delay after the bundle ran; the
  outside link’s and the folder’s follow, and the mail link shows none.
- `the first rest keeps its time`: on a GitHub checkout’s page, with a 100 ms load, the
  pull request’s title is read the intent delay after the pointer arrived and is in the
  card when it comes up.
- `left during the load`: the pointer leaves before the bundle runs, and no card comes
  up until the next rest, which loads nothing again.
- `pressed during the load`: a press ends the rest, as it ends one the card’s registry
  sees.
- `forgotten and disposed before the load`: a rest on a disposed document’s link loads
  nothing, and the forgotten link has no card once the bundle has run.
- `a failed load`: no card, one warning, no second load, and a link registered after has
  none.
- `a touch`: a tap loads nothing; the pointer’s rest after it does.

```console
$ node tests/dom/link-preview-loader-session.js
{
 "registered before the bundle": [
  {
   "at": 0,
   "registered": "the guide",
   "card": true
  },
  {
   "at": 0,
   "registered": "the docs folder",
   "card": true
  },
  {
   "at": 0,
   "registered": "elsewhere",
   "card": true
  },
  {
   "at": 0,
   "registered": "write to us",
   "card": false
  },
  {
   "at": 5000,
   "sees": null
  }
 ],
 "the first rest loads it": [
  {
   "at": 0,
   "registered": "the guide",
   "card": true
  },
  {
   "at": 0,
   "registered": "the docs folder",
   "card": true
  },
  {
   "at": 0,
   "registered": "elsewhere",
   "card": true
  },
  {
   "at": 0,
   "registered": "write to us",
   "card": false
  },
  {
   "at": 1000,
   "pointer": "the guide"
  },
  {
   "at": 1000,
   "load": "link-previews"
  },
  {
   "at": 1030,
   "loaded": "link-previews"
  },
  {
   "at": 1329,
   "sees": null
  },
  {
   "at": 1350,
   "sees": "docs/guide.md | “How to start” | Opens here in Metabrowser",
   "on": "the guide"
  },
  {
   "at": 1600,
   "pointer": "the body"
  },
  {
   "at": 1800,
   "pointer": "elsewhere"
  },
  {
   "at": 2200,
   "sees": "Opens example.com | “A page elsewhere”",
   "on": "elsewhere"
  },
  {
   "at": 2400,
   "pointer": "the body"
  },
  {
   "at": 2600,
   "pointer": "the docs folder"
  },
  {
   "at": 3000,
   "sees": "docs/ | Opens here in Metabrowser",
   "on": "the docs folder"
  },
  {
   "at": 3200,
   "pointer": "write to us"
  },
  {
   "at": 3600,
   "sees": null
  }
 ],
 "the first rest keeps its time": [
  {
   "at": 0,
   "pointer": "#12"
  },
  {
   "at": 0,
   "load": "link-previews"
  },
  {
   "at": 100,
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
   "at": 399,
   "sees": null
  },
  {
   "at": 420,
   "sees": "Pull request #12 | feat(links): preview what a link opens | Opens here in Metabrowser",
   "on": "#12"
  }
 ],
 "left during the load": [
  {
   "at": 0,
   "registered": "the guide",
   "card": true
  },
  {
   "at": 0,
   "pointer": "the guide"
  },
  {
   "at": 0,
   "load": "link-previews"
  },
  {
   "at": 10,
   "pointer": "the body"
  },
  {
   "at": 30,
   "loaded": "link-previews"
  },
  {
   "at": 800,
   "sees": null
  },
  {
   "at": 1000,
   "pointer": "the guide"
  },
  {
   "at": 1400,
   "sees": "docs/guide.md | “How to start” | Opens here in Metabrowser",
   "on": "the guide"
  }
 ],
 "pressed during the load": [
  {
   "at": 0,
   "registered": "the guide",
   "card": true
  },
  {
   "at": 0,
   "pointer": "the guide"
  },
  {
   "at": 0,
   "load": "link-previews"
  },
  {
   "at": 10,
   "press": "the guide"
  },
  {
   "at": 30,
   "loaded": "link-previews"
  },
  {
   "at": 800,
   "sees": null
  },
  {
   "at": 1000,
   "pointer": "the body"
  },
  {
   "at": 1200,
   "pointer": "the guide"
  },
  {
   "at": 1600,
   "sees": "docs/guide.md | “How to start” | Opens here in Metabrowser",
   "on": "the guide"
  }
 ],
 "forgotten and disposed before the load": [
  {
   "at": 0,
   "registered": "the guide",
   "card": true
  },
  {
   "at": 0,
   "registered": "elsewhere",
   "card": true
  },
  {
   "at": 0,
   "registered": "the docs folder",
   "card": true
  },
  {
   "at": 0,
   "forgot": "elsewhere",
   "disposed": "the changelog"
  },
  {
   "at": 0,
   "pointer": "the docs folder"
  },
  {
   "at": 800,
   "sees": null
  },
  {
   "at": 1000,
   "pointer": "the guide"
  },
  {
   "at": 1000,
   "load": "link-previews"
  },
  {
   "at": 1030,
   "loaded": "link-previews"
  },
  {
   "at": 1400,
   "sees": "docs/guide.md | “How to start” | Opens here in Metabrowser",
   "on": "the guide"
  },
  {
   "at": 1600,
   "pointer": "elsewhere"
  },
  {
   "at": 2000,
   "sees": null
  },
  {
   "at": 2200,
   "pointer": "the docs folder"
  },
  {
   "at": 2600,
   "sees": null
  }
 ],
 "a failed load": [
  {
   "at": 0,
   "registered": "the guide",
   "card": true
  },
  {
   "at": 0,
   "registered": "elsewhere",
   "card": true
  },
  {
   "at": 0,
   "pointer": "the guide"
  },
  {
   "at": 0,
   "load": "link-previews"
  },
  {
   "at": 30,
   "loaded": "link-previews",
   "failed": true
  },
  {
   "at": 30,
   "warned": "metabrowser: link cards are unavailable"
  },
  {
   "at": 800,
   "sees": null
  },
  {
   "at": 1000,
   "pointer": "the body"
  },
  {
   "at": 1200,
   "pointer": "elsewhere"
  },
  {
   "at": 1600,
   "sees": null
  },
  {
   "at": 1600,
   "registered": "the docs folder",
   "card": false
  },
  {
   "at": 1800,
   "pointer": "the docs folder"
  },
  {
   "at": 2200,
   "sees": null
  }
 ],
 "a touch": [
  {
   "at": 0,
   "registered": "the guide",
   "card": true
  },
  {
   "at": 0,
   "pointer": "the guide",
   "pointerType": "touch"
  },
  {
   "at": 800,
   "sees": null
  },
  {
   "at": 1000,
   "pointer": "the body",
   "pointerType": "touch"
  },
  {
   "at": 1200,
   "pointer": "the guide"
  },
  {
   "at": 1200,
   "load": "link-previews"
  },
  {
   "at": 1230,
   "loaded": "link-previews"
  },
  {
   "at": 1600,
   "sees": "docs/guide.md | “How to start” | Opens here in Metabrowser",
   "on": "the guide"
  }
 ]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
