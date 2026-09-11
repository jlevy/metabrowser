---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: persisted document reading width

This session loads the exact production document-width state machine from a command
line. It pins the 102-character default for a fresh profile, preserves an existing
preference, rejects malformed state, clamps and rounds edits, applies the live CSS
property, and persists the committed value under the host-wide preference key.

```console
$ node tests/dom/document-width-session.js
{
  "authority": {
    "default": 102,
    "injectedDefault": 102,
    "key": "metabrowser.docMaxChars",
    "max": 160,
    "min": 40
  },
  "bounds": {
    "above": 160,
    "below": 40,
    "fractional": 102
  },
  "storedProfiles": {
    "existing": 118,
    "fresh": 102,
    "malformed": 102
  },
  "liveApply": {
    "input": "88",
    "persisted": "88",
    "persistedWrites": [
      {
        "key": "metabrowser.docMaxChars",
        "value": "88"
      }
    ],
    "rootProperty": "88",
    "value": 88
  },
  "committedApply": {
    "input": "102",
    "persisted": "102",
    "persistedWrites": [
      {
        "key": "metabrowser.docMaxChars",
        "value": "88"
      },
      {
        "key": "metabrowser.docMaxChars",
        "value": "102"
      }
    ],
    "rootProperty": "102",
    "value": 102
  }
}
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
