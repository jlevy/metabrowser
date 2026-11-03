// GitHub built-in plugin.
//
// Owns two views. ("pull-request", "pull-request") is a pull request's page at
// /pull/<n>[/files], which the shell mounts for that route; pull-page.js holds it.
// ("pull-request-list", "pull-request-list") is the list of them: the shell mounts it in the
// Pulls tab, with its host, and in the pane at /pulls; pulls-panel.js holds it.
// The URL reducer, the gh credential helper, and the records are Python.

import { mountPullPage } from "./pull-page.js";
import { mountPullsLanding, mountPullsPanel } from "./pulls-panel.js";

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser github plugin: SDK is unavailable");
}

mb.registerView("pull-request", "pull-request", {
  render: (container, ctx) => mountPullPage(container, ctx, mb),
});

mb.registerView("pull-request-list", "pull-request-list", {
  render: (container, ctx) =>
    ctx.pullsNav === undefined
      ? mountPullsLanding(container, ctx)
      : mountPullsPanel(container, ctx, mb),
});
