// Binary built-in plugin — no JS-side renderer.
//
// Binary files have no views (the manifest declares no [[view]]
// blocks); the preview pane's no-views branch renders a static
// "No preview is available" message. This file exists so the plugin
// directory has the index.js the discovery layer expects, and so a
// future binary-specific renderer (hex dump, embedded preview) has
// an obvious place to land.
(() => {})();
