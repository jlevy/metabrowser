- The [Folder Treemap](docs/design-system.md#folder-treemap) goes as deep as it has room
  for, instead of stopping at two levels: a folder too small for its label nests inside
  a thin frame, every cell names itself in its tooltip, and the cell budget spreads
  across the map by area.
  It draws up to twice as many cells, from a rollup of up to 4,000 nodes instead of
  1,200, so it reaches several levels further into a large repository.
  Every cell now lies inside its folder and the map’s border: cells on the right and
  bottom edges are no longer clipped, and small cells are no longer drawn larger than
  their share, over their neighbours.

- Plugins: `fetchRollup` and `watchRollup` accept `depth: "max"` and `top: "max"` for
  the deepest and widest tree `/api/rollup` serves, as the Treemap now asks for.
