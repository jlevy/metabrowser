// The Mermaid entry markdown-diagram-frame-session.js publishes as the `mermaid` module
// bundle: the frame's real entry (diagram-frame-entry.js) imports this file by its URL, as
// it imports the vendored Mermaid in a browser, and its default export is the session's
// stand-in Mermaid, which records what the frame asks of it.
export default globalThis.diagramFrameSessionMermaid;
