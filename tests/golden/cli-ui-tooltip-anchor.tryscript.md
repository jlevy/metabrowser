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
A completed refresh cannot overwrite a fading link card, and its newer timing appears
when the Refresh tooltip opens.

A repaint elsewhere on the page used to take a row’s tooltip away too, under a pointer
that had not moved (mb-alff).
Now a surface’s hide puts away only a tooltip anchored in it, or one whose anchor has
left the document, and focus a rebuild puts back after removing the element that had it
leaves the tooltip be, as the focus a press on the folder’s name gives it does; focus
moving between controls still puts it away.
A key or press of the reader’s after that removal ends the repair, so the focus it gives
moves, and a repair still puts away a tooltip whose own anchor the rebuild removed.

A pointer that moved straight from one link’s card to the next, within the card’s fade,
used to bring the first card back and keep it up while the pointer rested on the second,
and so did moving from one `data-tip-text` element to the next and onto a child of it.
Now the next element’s tooltip appears at its own place, with the newest markup it was
given. A show again while the tooltip still waits takes the newer markup and keeps the
first show’s time, where it used to start the 300 ms over; a show again once it is up
changes nothing. Coming back onto the first element before the second’s delay ends keeps
the first one’s tooltip, which its own surface’s hide still puts away, and leaving
during a delay and coming back starts the delay again.

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
  "a rebuild the reader's key causes is still a repair": {
    "shown": {
      "html": "<b>size</b>",
      "display": "block",
      "visible": true,
      "left": "190px",
      "top": "126px"
    }
  },
  "the reader's key after a rebuild dropped focus moves it": {
    "up": {
      "html": "<b>size</b>",
      "display": "block",
      "visible": true,
      "left": "190px",
      "top": "126px"
    },
    "afterTab": {
      "html": "<b>size</b>",
      "display": "none",
      "visible": false,
      "left": "190px",
      "top": "126px"
    }
  },
  "a repair puts away a tooltip whose anchor the rebuild removed": {
    "up": {
      "html": "<b>Filters</b>",
      "display": "block",
      "visible": true,
      "left": "190px",
      "top": "66px"
    },
    "afterRepair": {
      "html": "<b>Filters</b>",
      "display": "none",
      "visible": false,
      "left": "190px",
      "top": "66px"
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
  },
  "straight to the next link within the fade shows the next card": {
    "first": {
      "html": "<b>#1</b> Title of 1",
      "display": "block",
      "visible": true,
      "left": "70px",
      "top": "126px"
    },
    "waiting": {
      "html": "<b>#1</b> Title of 1",
      "display": "block",
      "visible": false,
      "left": "70px",
      "top": "126px"
    },
    "second": {
      "html": "<b>#2</b> Title of 2",
      "display": "block",
      "visible": true,
      "left": "270px",
      "top": "126px"
    },
    "resting": {
      "html": "<b>#2</b> Title of 2",
      "display": "block",
      "visible": true,
      "left": "270px",
      "top": "126px"
    }
  },
  "from X to Y and onto Y's child shows Y's tip": {
    "atX": {
      "html": "Tip of X",
      "display": "block",
      "visible": true,
      "left": "70px",
      "top": "126px"
    },
    "atChild": {
      "html": "Tip of X",
      "display": "block",
      "visible": false,
      "left": "70px",
      "top": "126px"
    },
    "atY": {
      "html": "Tip of Y",
      "display": "block",
      "visible": true,
      "left": "270px",
      "top": "126px"
    },
    "resting": {
      "html": "Tip of Y",
      "display": "block",
      "visible": true,
      "left": "270px",
      "top": "126px"
    }
  },
  "Refresh timing keeps the fading link card and updates its own tooltip": {
    "waiting": {
      "html": "<b>#1</b> Review this pull request",
      "display": "block",
      "visible": false,
      "left": "70px",
      "top": "126px"
    },
    "complete": {
      "html": "Refreshed just now<div class=\"tip-detail\">3 requests · 900 B · 250ms · GitHub CLI</div>",
      "display": "block",
      "visible": true,
      "left": "270px",
      "top": "126px"
    },
    "shownUpdate": {
      "html": "Refreshed just now<div class=\"tip-detail\">2 requests · 0 B · 90ms · GitHub CLI</div>",
      "display": "block",
      "visible": true,
      "left": "270px",
      "top": "126px"
    }
  },
  "a show again while waiting keeps the first show's time": {
    "before": {
      "html": "",
      "display": "",
      "visible": false,
      "left": "",
      "top": ""
    },
    "onTime": {
      "html": "<b>#12</b> Keep the tail",
      "display": "block",
      "visible": true,
      "left": "70px",
      "top": "126px"
    },
    "later": {
      "html": "<b>#12</b> Keep the tail",
      "display": "block",
      "visible": true,
      "left": "70px",
      "top": "126px"
    }
  },
  "back onto the first within the second's delay keeps the first": {
    "back": {
      "html": "<b>#1</b>",
      "display": "block",
      "visible": true,
      "left": "70px",
      "top": "126px"
    },
    "resting": {
      "html": "<b>#1</b>",
      "display": "block",
      "visible": true,
      "left": "70px",
      "top": "126px"
    },
    "putAway": {
      "html": "<b>#1</b>",
      "display": "none",
      "visible": false,
      "left": "70px",
      "top": "126px"
    },
    "again": {
      "html": "<b>#1</b>",
      "display": "none",
      "visible": false,
      "left": "70px",
      "top": "126px"
    },
    "afterDelay": {
      "html": "<b>#2</b>",
      "display": "block",
      "visible": true,
      "left": "270px",
      "top": "126px"
    }
  }
}
? 0
```
