---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: a tooltip whose anchor leaves the document

This session runs the shell’s own tooltip code, lifted verbatim from `app.js`, on a
clock it advances.
A tree row replaced during the 300 ms delay used to put the tooltip at
the top-left corner, where it stayed until another hover.
Now the tooltip does not appear, and one already up for another row is put away.
The ordinary hover, the next hover, and a caller with no anchor are unchanged.

```console
$ node tests/dom/tooltip-anchor-session.js
{
  "a row still in the document shows its tooltip under it": {
    "during": {
      "html": "",
      "display": "",
      "visible": false,
      "left": "",
      "top": ""
    },
    "shown": {
      "html": "<b>size</b>",
      "display": "block",
      "visible": true,
      "left": "190px",
      "top": "126px"
    }
  },
  "a row replaced during the delay shows nothing": {
    "atDelay": {
      "html": "",
      "display": "",
      "visible": false,
      "left": "",
      "top": ""
    },
    "afterFade": {
      "html": "",
      "display": "none",
      "visible": false,
      "left": "",
      "top": ""
    }
  },
  "the next hover shows normally": {
    "nextHover": {
      "html": "<b>new row</b>",
      "display": "block",
      "visible": true,
      "left": "190px",
      "top": "326px"
    }
  },
  "a tooltip already up is put away too": {
    "up": {
      "html": "<b>first</b>",
      "display": "block",
      "visible": true,
      "left": "190px",
      "top": "126px"
    },
    "atDelay": {
      "html": "<b>first</b>",
      "display": "block",
      "visible": false,
      "left": "190px",
      "top": "126px"
    },
    "afterFade": {
      "html": "<b>first</b>",
      "display": "none",
      "visible": false,
      "left": "190px",
      "top": "126px"
    }
  },
  "a tooltip with no anchor still appears": {
    "shown": {
      "html": "<b>no anchor</b>",
      "display": "block",
      "visible": true,
      "left": "",
      "top": ""
    }
  }
}
? 0
```
