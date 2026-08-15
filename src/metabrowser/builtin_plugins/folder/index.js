// Built-in folder view and Overview contribution registration.

import { createCategoryPalettePool } from "./category_palette.js";
import { createFileTotalsPanel } from "./file_totals_panel.js";
import { createFileTypeSummaryPanel } from "./file_type_summary.js";
import { createOverviewView } from "./overview.js";
import { createFolderOverviewRegistry } from "./overview_registry.js";
import { createReadmePanel } from "./readme_panel.js";
import { createFolderRollupControls } from "./rollup_controls.js";
import { registerTreemap } from "./treemap.js";

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser folder plugin: SDK is unavailable");
}

const palettePool = createCategoryPalettePool(
  window.METABROWSER_SETTINGS?.DISTRIBUTION_PALETTE_SLOTS ?? 12,
);
const registry = createFolderOverviewRegistry(mb);
const rollupControls = createFolderRollupControls(mb);
mb.folderOverview = registry;
registry.registerPanel("folder.file-totals", createFileTotalsPanel(mb, rollupControls));
registry.registerPanel(
  "folder.file-types",
  createFileTypeSummaryPanel(mb, palettePool, rollupControls),
);
registry.registerPanel("folder.readme", createReadmePanel(mb));
mb.registerView("folder", "overview", createOverviewView(mb, registry));
registerTreemap(mb, palettePool, rollupControls);
