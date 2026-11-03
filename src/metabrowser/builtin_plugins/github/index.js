// GitHub built-in plugin.
//
// Owns one view: ("pull-request", "pull-request"), a pull request's page at
// /pull/<n>[/files]. The shell mounts it for that route; pull-page.js holds the page.
// The URL reducer, the gh credential helper, and pull-request records are Python.

import { watchMessageMeasure } from "./message-measure.js";
import { mountPullPage } from "./pull-page.js";

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser github plugin: SDK is unavailable");
}

mb.registerView("pull-request", "pull-request", {
  render(container, ctx) {
    const page = mountPullPage(container, ctx, mb);
    const stopMeasuring = watchMessageMeasure(container);
    return {
      ...page,
      dispose() {
        stopMeasuring();
        page.dispose();
      },
    };
  },
});
