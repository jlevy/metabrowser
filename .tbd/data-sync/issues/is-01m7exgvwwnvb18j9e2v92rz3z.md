---
type: is
id: is-01m7exgvwwnvb18j9e2v92rz3z
title: KPress's :root aliases replace the shell's --font-sans and --font-mono once a document loads
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-15T06:15:11.515Z
updated_at: 2026-11-15T06:15:11.515Z
---
Found in review A of #438 (finding A5, https://github.com/jlevy/metabrowser/pull/438#pullrequestreview-5909379904) and seen while measuring faces for mb-k838.

The shell links KPress's style-tokens.css before static/styles.css (server.py), so on first paint the shell's :root tokens win. KPress lists style-tokens.css as a stylesheet entry point, and loadKpressAssets in plugin-sdk.js dedupes only against its own loaded set, which starts empty. The first rendered document therefore appends a second link to style-tokens.css after styles.css, and KPress's `:root { --font-sans: var(--kpress-font-sans); --font-mono: var(--kpress-font-mono) }` compatibility aliases then win by order. html[data-app-font="system"] outranks :root, so under the system font set the shell's tokens still hold; under the default clean set they do not.

- --font-sans: chrome becomes KPress's Source Sans 3 stack without the Roboto fallback. It is the same vendored face, measured in headless Chrome for mb-k838.
- --font-mono: every piece of chrome code changes from "SF Mono", Consolas, "Liberation Mono", Menlo, monospace to ui-monospace, SFMono-Regular, Menlo, Consolas, monospace. What that draws has not been measured.
- The font-set comment at static/styles.css:139, "linked once in <head>", is untrue once a document loads.

Possible fixes: register the head link's URL in the SDK's loaded set so loadKpressAssets does not append it again, or declare the shell's base tokens on html:root so they outrank KPress's aliases. Measure --font-mono's drawn face before and after.
