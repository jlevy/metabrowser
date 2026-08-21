// Built-in folder view and Overview contribution registration.

import { createCategoryPalette } from "./category_palette.js";
import { createFileOverviewPanel } from "./file_overview_panel.js";
import { createOverviewView } from "./overview.js";
import { createFolderOverviewRegistry } from "./overview_registry.js";
import { createReadmePanel } from "./readme_panel.js";
import { createFolderRollupControls } from "./rollup_controls.js";
import { createFolderRollupProjectionPool } from "./rollup_projection.js";
import { registerTreemap } from "./treemap.js";

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser folder plugin: SDK is unavailable");
}

// One palette for the page: a family's color is declared, so it does not
// depend on which folder is open or which panels happen to be mounted.
const palette = createCategoryPalette(window.METABROWSER_SETTINGS?.DISTRIBUTION_COLORS ?? []);
const registry = createFolderOverviewRegistry(mb);
const rollupControls = createFolderRollupControls(mb);
const rollupProjectionPool = createFolderRollupProjectionPool();
mb.folderOverview = registry;
registry.registerPanel(
  "folder.file-overview",
  createFileOverviewPanel(mb, palette, rollupProjectionPool, rollupControls),
);
registry.registerPanel("folder.readme", createReadmePanel(mb));
mb.registerView("folder", "overview", createOverviewView(mb, registry));
registerTreemap(mb, palette, rollupControls);
