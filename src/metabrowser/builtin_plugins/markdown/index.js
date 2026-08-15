// Built-in Markdown view registration.

import { analyzeMarkdownGraph } from "./graph_analysis.js";
import { mountRenderedMarkdown } from "./rendered.js";
import { renderMarkdownSource } from "./source.js";

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser markdown plugin: SDK is unavailable");
}

const mountRendered = (container, ctx, options = {}) =>
  mountRenderedMarkdown(container, ctx, mb, options);
const renderSource = (container, ctx) => renderMarkdownSource(container, ctx, mb);
const analyzeGraph = (options = {}) =>
  analyzeMarkdownGraph({
    limits: options.limits,
    readText: mb.fetchText,
    repository: mb.repository,
    signal: options.signal,
    snapshot: mb.fileCatalog.snapshot(),
  });

mb.builtins.markdown = { analyzeGraph, mountRendered, renderSource };
mb.registerView("markdown", "rendered", { render: mountRendered });
mb.registerView("markdown", "source", { render: renderSource });
