// Built-in Markdown view registration.

import { mountRenderedMarkdown } from "./rendered.js";
import { renderMarkdownSource } from "./source.js";

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser markdown plugin: SDK is unavailable");
}

const mountRendered = (container, ctx, options = {}) =>
  mountRenderedMarkdown(container, ctx, mb, options);
const renderSource = (container, ctx) => renderMarkdownSource(container, ctx, mb);

mb.builtins.markdown = { mountRendered, renderSource };
mb.registerView("markdown", "rendered", { render: mountRendered });
mb.registerView("markdown", "source", { render: renderSource });
