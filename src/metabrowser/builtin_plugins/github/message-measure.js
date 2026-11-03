// PR messages use the interface sans; its system face varies with the platform.
// Keep this measurement on the PR view's demand-loaded path, away from folder startup.
const SAMPLE =
  "The quick brown fox jumps over the lazy dog. A readable pull request keeps every file and comment close to its code.";

/**
 * Match a PR page's reading measure to the active system sans. The clean font keeps
 * its calibrated CSS advance. Only font-setting changes need measuring; size and
 * character-count changes remain CSS inputs. Returns the view's disposal callback.
 * @param {HTMLElement} host
 */
export function watchMessageMeasure(host) {
  const doc = host.ownerDocument;
  const root = doc.documentElement;
  let measuredFont = "";
  let measuredSize = "";
  let advance = "";

  function update() {
    if (root.getAttribute("data-app-font") !== "system") {
      host.style.removeProperty("--message-char-advance");
      return;
    }
    const style = getComputedStyle(root);
    const font = style.getPropertyValue("--prose-sans-font").trim();
    // System faces may use optical sizes, so measure at the rendered prose size.
    const size = style.getPropertyValue("--document-body-font-size").trim();
    if (font !== measuredFont || size !== measuredSize) {
      const context = doc.createElement("canvas").getContext("2d");
      if (context === null) {
        return;
      }
      context.font = `${size} ${font}`;
      const ratio = context.measureText(SAMPLE).width / SAMPLE.length / Number.parseFloat(size);
      if (!Number.isFinite(ratio) || ratio <= 0) {
        return;
      }
      measuredFont = font;
      measuredSize = size;
      advance = String(ratio);
    }
    host.style.setProperty("--message-char-advance", advance);
  }

  update();
  const observer = new MutationObserver(update);
  observer.observe(root, { attributes: true, attributeFilter: ["data-app-font", "style"] });
  return () => {
    observer.disconnect();
    host.style.removeProperty("--message-char-advance");
  };
}
