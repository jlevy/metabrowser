---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: agent-log chart lifecycle

These browserless sessions execute the complete production owners for agent-log chart
request ownership and shared chart lifecycle behavior.
They pin parallel asset and data loading, same-container supersession, independent
staged containers, theme repaint, replacement disposal, immutable chart specifications,
and final teardown.

```console
$ node tests/dom/agent-log-plugin-behavior.js
{
  "chartDisposeCalls": 1,
  "chartRenderCalls": 3,
  "chartRenderPayloads": [
    {
      "container": "primary",
      "id": "newer"
    },
    {
      "container": "left",
      "id": "left"
    },
    {
      "container": "right",
      "id": "right"
    }
  ],
  "independentWorkOverlaps": true,
  "hasDelegatedClick": true,
  "hasInlineKindHandler": false,
  "hasRawImage": false,
  "hasEscapedImage": true,
  "usesSharedMultiSelect": true,
  "usesWrappedChipCluster": true,
  "dynamicStartsPressed": true,
  "dynamicEndsUnpressed": true,
  "dynamicEventHidden": true,
  "unknownEventHiddenWhenFiltering": true,
  "mixedUnknownKindHasNoChip": true,
  "dynamicLabelIsReadable": true,
  "unknownEventRestoredWithAllKinds": true,
  "unknownKindLabelHidden": true,
  "unknownSummaryLabelHidden": true,
  "unknownSummaryValueVisible": true,
  "unknownFilterHidden": true,
  "singleKnownKindVisible": true,
  "singleKindFilterHidden": true
}
```

```console
$ node tests/dom/chart-theme-behavior.js
{
  "lazyMountCreatesNoChart": true,
  "directInitialColors": {
    "series": "light-series",
    "label": "light-label"
  },
  "directDarkColors": {
    "series": "dark-series",
    "label": "dark-label",
    "updateCalls": [
      "none"
    ]
  },
  "directUpdatesAfterDestroy": 1,
  "staticInputsPreserved": true,
  "staticUpdateCalls": 0,
  "firstRuntime": {
    "initialSeries": "dark-series",
    "oklchAlpha": "oklch(70% 0.1 95 / 0.13)",
    "destroyedOnRepaint": 1,
    "repaintedSeries": "light-series",
    "specTokenPreserved": "var(--chart-series-info)"
  },
  "stagedReplacement": {
    "firstCommitted": true,
    "firstSurvivesStaging": true,
    "firstDestroyedAtCommit": 1,
    "secondCommitted": true,
    "secondSurvivesCommit": true,
    "secondDestroyedOnRepaint": 1,
    "repaintedLabel": "Second series",
    "repaintedSeries": "dark-series"
  },
  "disposal": {
    "activeDestroyed": 1,
    "chartCountBeforePostDisposeTheme": 6,
    "chartCountAfterPostDisposeTheme": 6
  }
}
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
