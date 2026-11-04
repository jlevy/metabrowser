// Locale-aware numeric formatting shared by the shell and plugins.

(() => {
  const integerFormatter = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
  const byteUnits = ["B", "KB", "MB", "GB", "TB", "PB"];
  /** Byte counts above this boundary receive the shared stronger emphasis. */
  const SIZE_LARGE_THRESHOLD_BYTES = 1024 * 1024;
  /** File counts at or above this boundary receive the shared stronger emphasis. */
  const COUNT_LARGE_THRESHOLD = 1000;

  /** @param {number} value */
  function formatBytes(value) {
    let amount = Number.isFinite(value) && value > 0 ? value : 0;
    let unit = 0;
    while (amount >= 1024 && unit < byteUnits.length - 1) {
      amount /= 1024;
      unit += 1;
    }
    if (unit === 0) {
      return `${Math.round(amount)} B`;
    }
    return `${amount.toFixed(1)} ${byteUnits[unit]}`;
  }

  /** @param {number} value */
  function formatInteger(value) {
    return integerFormatter.format(Math.max(0, Math.trunc(Number(value) || 0)));
  }

  /** @param {number} value */
  function formatFileCount(value) {
    const count = Math.max(0, Math.trunc(Number(value) || 0));
    return `${formatInteger(count)} ${count === 1 ? "file" : "files"}`;
  }

  /** @param {number} value */
  function sizeClass(value) {
    return (Number(value) || 0) > SIZE_LARGE_THRESHOLD_BYTES ? "size-large" : "";
  }

  /** @param {number} value */
  function countClass(value) {
    return (Number(value) || 0) >= COUNT_LARGE_THRESHOLD ? "count-large" : "";
  }

  // Age tiers, coarsest first, as [suffix, milliseconds, class].
  // One table so every age anywhere abbreviates and colours the same:
  // an age is an age, whether it belongs to a file or a commit.
  /** @type {ReadonlyArray<readonly [string, number, string]>} */
  const AGE_TIERS = Object.freeze([
    ["y", 365 * 24 * 60 * 60 * 1000, "age-old"],
    ["mo", 30 * 24 * 60 * 60 * 1000, "age-old"],
    ["w", 7 * 24 * 60 * 60 * 1000, "age-wk"],
    ["d", 24 * 60 * 60 * 1000, "age-day"],
    ["h", 60 * 60 * 1000, "age-hr"],
    ["m", 60 * 1000, "age-min"],
  ]);

  /**
   * Compact or relative age and its tier class for an epoch-seconds timestamp.
   *
   * @param {number} epochSeconds
   * @param {{style?: "compact" | "relative"}} [options]
   * @returns {{label: string, className: string}}
   */
  function age(epochSeconds, options = {}) {
    const value = Number(epochSeconds);
    if (!Number.isFinite(value) || value <= 0) {
      return { label: "", className: "" };
    }
    const delta = Date.now() - value * 1000;
    const elapsed = Math.abs(delta);
    const relative = options.style === "relative";
    for (const [suffix, span, className] of AGE_TIERS) {
      if (elapsed >= span) {
        const amount = `${Math.round(elapsed / span)}${suffix}`;
        return {
          label: relative ? (delta < 0 ? `in ${amount}` : `${amount} ago`) : amount,
          className,
        };
      }
    }
    return { label: relative ? "just now" : "<1m", className: "age-sec" };
  }

  /** @param {number} epochSeconds @returns {string} */
  function ageClass(epochSeconds) {
    return age(epochSeconds).className;
  }

  window.MetabrowserFormatters = Object.freeze({
    age,
    ageClass,
    countClass,
    formatBytes,
    formatFileCount,
    formatInteger,
    sizeClass,
  });
})();
