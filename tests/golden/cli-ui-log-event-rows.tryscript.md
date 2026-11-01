---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: a JSONL log’s event rows answer the keyboard

A log row’s header opens the event’s raw payload.
This session renders the production agent-log and unknown-JSONL views, then dispatches
keys and clicks on the rows they wrote.
Each header is a button with a tab stop and an expanded state.
Enter and Space toggle it and keep the page from scrolling; other keys, a held key, and
a key inside the open payload are left alone; and a click toggles it as it always did.

```console
$ node tests/dom/log-event-row-session.js
{
  "agent-log": {
    "markup": [
      {
        "class": "log-event-header",
        "role": "button",
        "tabindex": "0",
        "aria-expanded": "false"
      },
      {
        "class": "log-event-header",
        "role": "button",
        "tabindex": "0",
        "aria-expanded": "false"
      }
    ],
    "Enter opens the row": {
      "expanded": true,
      "ariaExpanded": "true",
      "rawMounted": true,
      "defaultPrevented": true
    },
    "Space closes it": {
      "expanded": false,
      "ariaExpanded": "false",
      "rawMounted": true,
      "defaultPrevented": true
    },
    "a click on the summary opens the row": {
      "expanded": true,
      "ariaExpanded": "true",
      "rawMounted": true,
      "defaultPrevented": false
    },
    "Enter after a click closes it": {
      "expanded": false,
      "ariaExpanded": "false",
      "rawMounted": true,
      "defaultPrevented": true
    },
    "a key inside the open payload leaves the row": {
      "expanded": true,
      "ariaExpanded": "true",
      "rawMounted": true,
      "defaultPrevented": false
    }
  },
  "unknown-jsonl": {
    "markup": [
      {
        "class": "log-event-header",
        "role": "button",
        "tabindex": "0",
        "aria-expanded": "false"
      },
      {
        "class": "log-event-header",
        "role": "button",
        "tabindex": "0",
        "aria-expanded": "false"
      }
    ],
    "Enter opens the row": {
      "expanded": true,
      "ariaExpanded": "true",
      "rawMounted": true,
      "defaultPrevented": true
    },
    "Space closes it": {
      "expanded": false,
      "ariaExpanded": "false",
      "rawMounted": true,
      "defaultPrevented": true
    },
    "a click on the summary opens the row": {
      "expanded": true,
      "ariaExpanded": "true",
      "rawMounted": true,
      "defaultPrevented": false
    },
    "Enter after a click closes it": {
      "expanded": false,
      "ariaExpanded": "false",
      "rawMounted": true,
      "defaultPrevented": true
    },
    "a key inside the open payload leaves the row": {
      "expanded": true,
      "ariaExpanded": "true",
      "rawMounted": true,
      "defaultPrevented": false
    }
  }
}
? 0
```
