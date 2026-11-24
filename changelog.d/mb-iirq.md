- The [Folder Treemap](docs/design-system.md#folder-treemap) and the Overview’s compact
  map paint their cells on a canvas rather than drawing an element for each, so they
  draw every file and folder the rollup holds down to a device pixel: a folder of
  hundreds of small files shows each one.
  Frames thin with depth, so deep folders keep their area for cells.
  Every cell still names itself in its tooltip and opens on a click, and the keyboard
  reaches every folder and file through one focusable control that the arrow keys move.
