---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: structured node tables

## Test: expand, collapse and page a branch in place, then dispose a pending page

```console
$ node tests/dom/structured-node-table-session.js
{
  "root": "FieldValue0Sequence (1)0Mapping (1)recordMapping (2)keep\"sibling\"Next page",
  "nested": "FieldValue0Sequence (1)0Mapping (1)recordMapping (2)id9007199254740993Morekeep\"sibling\"Next page",
  "paged": "FieldValue0Sequence (1)0Mapping (1)recordMapping (2)last9007199254740993First pagekeep\"sibling\"Next page",
  "positions": [
    {
      "path": [],
      "offset": 0,
      "depth": 3
    },
    {
      "path": [
        "0",
        0,
        "record"
      ],
      "offset": 0,
      "depth": 1
    },
    {
      "path": [
        "0",
        0,
        "record"
      ],
      "offset": 1,
      "depth": 1
    },
    {
      "path": [],
      "offset": 1,
      "depth": 3
    }
  ],
  "selections": [
    [],
    [
      "0",
      0,
      "record"
    ],
    [
      "0",
      0,
      "record"
    ],
    [
      "0",
      0,
      "record"
    ],
    []
  ]
}
? 0
```
