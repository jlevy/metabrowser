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

A repaint elsewhere on the page used to take a row’s tooltip away too, under a pointer
that had not moved (mb-alff).
Now a surface’s hide puts away only a tooltip anchored in it, or one whose anchor has
left the document, and focus a rebuild puts back after removing the element that had it
leaves the tooltip be; focus moving between controls still puts it away.

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
  },
  "another surface's repaint leaves a row's tooltip": {
    "shown": {
      "html": "<b>size</b>",
      "display": "block",
      "visible": true,
      "left": "190px",
      "top": "126px"
    },
    "stillUp": {
      "html": "<b>size</b>",
      "display": "block",
      "visible": true,
      "left": "190px",
      "top": "126px"
    }
  },
  "a surface's repaint puts its own tooltip away": {
    "waiting": {
      "html": "",
      "display": "none",
      "visible": false,
      "left": "",
      "top": ""
    },
    "up": {
      "html": "<b>Python</b>",
      "display": "block",
      "visible": true,
      "left": "190px",
      "top": "526px"
    },
    "afterFade": {
      "html": "<b>Python</b>",
      "display": "none",
      "visible": false,
      "left": "190px",
      "top": "526px"
    }
  },
  "any surface's hide puts away a tooltip whose anchor is gone": {
    "up": {
      "html": "<b>size</b>",
      "display": "block",
      "visible": true,
      "left": "190px",
      "top": "126px"
    },
    "afterFade": {
      "html": "<b>size</b>",
      "display": "none",
      "visible": false,
      "left": "190px",
      "top": "126px"
    }
  },
  "focus put back after a rebuild leaves the tooltip": {
    "shown": {
      "html": "<b>size</b>",
      "display": "block",
      "visible": true,
      "left": "190px",
      "top": "126px"
    },
    "moved": {
      "html": "<b>size</b>",
      "display": "block",
      "visible": false,
      "left": "190px",
      "top": "126px"
    },
    "afterFade": {
      "html": "<b>size</b>",
      "display": "none",
      "visible": false,
      "left": "190px",
      "top": "126px"
    }
  },
  "focus moving during the delay puts the tooltip away": {
    "atDelay": {
      "html": "",
      "display": "none",
      "visible": false,
      "left": "",
      "top": ""
    }
  }
}
? 0
```
