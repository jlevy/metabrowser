// How a count summary's status counts are painted, read in the page (docs/design-system.md,
// "Count Summaries Bold Their Numbers"; mb-8iwn): each `.summary-status-count`, "21 A", with
// its number's and its letter's computed ink and weight, the size it is set at, the ground
// under it, and its WCAG contrast on that ground, so a Chrome session can hold both to bold
// in the status's ink at a text's 4.5:1. The letter is the count's own text after its
// number, so its ink and weight are the count's span's.
//
// A function's source, for `Runtime.evaluate`: `(${STATUS_COUNTS})(element)` reads the status
// counts under *element*. tests/dom/diff-summary-chrome.mjs reads a commit's Diff summary
// with it, and tests/dom/git-commit-summary-chrome.mjs a commit's hover card.
export const STATUS_COUNTS = `(root) => {
  const canvas = document.createElement("canvas");
  canvas.width = 1;
  canvas.height = 1;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  // Paint *layers*, bottom first, over an opaque white page, and read the one pixel: each a
  // CSS color in any space, as the sRGB the screen shows, a translucent one over those under
  // it.
  const pixel = (layers) => {
    context.fillStyle = "#fff";
    context.fillRect(0, 0, 1, 1);
    for (const layer of layers) {
      context.fillStyle = layer;
      context.fillRect(0, 0, 1, 1);
    }
    return [...context.getImageData(0, 0, 1, 1).data.slice(0, 3)];
  };
  // Every background from the root down to *node*: the ground its text is drawn on.
  const grounds = (node) => {
    const layers = [];
    for (let at = node; at; at = at.parentElement) {
      const color = getComputedStyle(at).backgroundColor;
      if (color !== "rgba(0, 0, 0, 0)" && color !== "transparent") {
        layers.unshift(color);
      }
    }
    return layers;
  };
  // WCAG 2.2 relative luminance and contrast ratio, from 8-bit sRGB.
  const luminance = (rgb) => {
    const [r, g, b] = rgb.map((channel) => {
      const value = channel / 255;
      return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const contrast = (a, b) => {
    const [lighter, darker] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (lighter + 0.05) / (darker + 0.05);
  };
  const hex = (rgb) => "#" + rgb.map((channel) => channel.toString(16).padStart(2, "0")).join("");
  return [...root.querySelectorAll(".summary-status-count")].map((count) => {
    const number = count.querySelector(".summary-number");
    const own = getComputedStyle(count);
    const under = grounds(count);
    const ground = pixel(under);
    const ink = pixel([...under, own.color]);
    const letter = [...count.childNodes]
      .filter((node) => node.nodeType === Node.TEXT_NODE)
      .map((node) => node.textContent)
      .join("")
      .trim();
    return {
      text: count.textContent,
      status: count.dataset.fileStatus ?? null,
      statusPrimitive: count.classList.contains("file-change-status"),
      number:
        number === null
          ? null
          : [
              number.textContent,
              getComputedStyle(number).color,
              getComputedStyle(number).fontWeight,
            ],
      letter: [letter, own.color, own.fontWeight],
      size: own.fontSize,
      ground: hex(ground),
      layers: under,
      ink: hex(ink),
      contrast: Math.round(contrast(ink, ground) * 100) / 100,
    };
  });
}`;
