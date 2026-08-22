/** Resuelve nombre de color / hex a CSS para la bolita en tablas JS. */
(function (global) {
  const NAMES = {
    rojo: "#ef4444", roja: "#ef4444", red: "#ef4444",
    azul: "#3b82f6", blue: "#3b82f6",
    verde: "#22c55e", green: "#22c55e",
    amarillo: "#eab308", amarilla: "#eab308", yellow: "#eab308",
    naranja: "#f97316", orange: "#f97316",
    rosa: "#ec4899", rosado: "#ec4899", rosada: "#ec4899", pink: "#ec4899",
    fucsia: "#d946ef", magenta: "#d946ef",
    morado: "#a855f7", morada: "#a855f7", purple: "#a855f7", violeta: "#8b5cf6", lila: "#c4b5fd",
    negro: "#171717", negra: "#171717", black: "#171717",
    blanco: "#f8fafc", blanca: "#f8fafc", white: "#f8fafc",
    gris: "#9ca3af", gray: "#9ca3af", grey: "#9ca3af",
    plateado: "#94a3b8", plateada: "#94a3b8", silver: "#94a3b8",
    dorado: "#ca8a04", dorada: "#ca8a04", gold: "#ca8a04",
    cafe: "#92400e", "café": "#92400e", marron: "#78350f", "marrón": "#78350f", brown: "#78350f",
    celeste: "#38bdf8", cyan: "#22d3ee", turquesa: "#14b8a6",
    beige: "#d6c6a8", crema: "#f5f0e6", coral: "#fb7185",
    bordo: "#7f1d1d", burdeos: "#7f1d1d", vino: "#7f1d1d", wine: "#7f1d1d",
    salmon: "#fda4af", "salmón": "#fda4af",
  };

  function colorToCss(value) {
    const raw = String(value || "").trim();
    if (!raw || raw === "-" || raw === "—") return null;
    const hex = raw.match(/^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/);
    if (hex) {
      let h = hex[1];
      if (h.length === 3) h = h.split("").map((c) => c + c).join("");
      return "#" + h.toLowerCase();
    }
    const key = raw.toLowerCase().replace(/\s+/g, " ");
    if (Object.prototype.hasOwnProperty.call(NAMES, key)) return NAMES[key] || null;
    const first = key.split(" ")[0];
    if (Object.prototype.hasOwnProperty.call(NAMES, first)) return NAMES[first] || null;
    return null;
  }

  function colorDotHtml(colorName) {
    const css = colorToCss(colorName);
    const label = colorName || "Sin color";
    if (css) {
      const extra =
        css === "transparent" || ["#fff", "#ffffff", "#f8fafc"].includes(css.toLowerCase())
          ? "box-shadow:inset 0 0 0 1px rgba(0,0,0,.15);"
          : "";
      return `<span class="w-3 h-3 rounded-full border border-black/15 shrink-0 inline-block" style="background-color:${css};${extra}" title="${label}"></span>`;
    }
    if (colorName && colorName !== "-" && colorName !== "—") {
      return `<span class="w-3 h-3 rounded-full border border-dashed border-gray-300 bg-gray-100 shrink-0 inline-block" title="${label}"></span>`;
    }
    return `<span class="w-3 h-3 rounded-full border border-gray-200 bg-gray-100 shrink-0 inline-block opacity-50" title="Sin color"></span>`;
  }

  global.ErpColorSwatch = { colorToCss, colorDotHtml };
})(window);
