// A control with a payload read on click. The synchronous Clipboard.write call keeps
// WebKit's transient user activation while the promised text is being fetched.
/**
 * @param {Document} doc
 * @param {string} label
 * @param {(signal: AbortSignal) => Promise<string>} readText
 * @param {AbortSignal} signal
 */
export function createCopyButton(doc, label, readText, signal) {
  const view = doc.defaultView;
  const sdk = view?.metabrowser;
  const button = doc.createElement("button");
  button.type = "button";
  button.className = "icon-btn icon-btn-reveal";
  button.setAttribute("aria-label", label);
  button.dataset.tipText = label;
  button.dataset.mbCopyLabel = label;
  button.innerHTML = sdk?.icons.copy ?? "";
  sdk?.ownDelegate(button);

  async function text() {
    signal.throwIfAborted();
    const value = await readText(signal);
    signal.throwIfAborted();
    return value;
  }

  async function write() {
    const clipboard = view?.navigator.clipboard;
    if (!clipboard) {
      throw new Error("Clipboard unavailable");
    }
    if (view.ClipboardItem && typeof clipboard.write === "function") {
      const data = text().then((value) => new Blob([value], { type: "text/plain" }));
      // A platform can decline the write before it consumes the item's promise.
      void data.catch(() => {});
      await clipboard.write([new view.ClipboardItem({ "text/plain": data })]);
    } else {
      const value = await text();
      signal.throwIfAborted();
      await clipboard.writeText(value);
    }
  }

  let busy = false;
  button.addEventListener("click", () => {
    if (busy || signal.aborted || !sdk) {
      return;
    }
    busy = true;
    sdk.showCopyResult(
      button,
      write().finally(() => {
        busy = false;
      }),
    );
  });
  return button;
}
