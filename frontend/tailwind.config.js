const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

/** Colours are CSS variables (see index.css) so dark and light themes share class names. */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        base: token("base"), panel: token("panel"), raised: token("raised"), line: token("line"),
        ink: token("ink"), mute: token("mute"), faint: token("faint"),
        amber: token("amber"), steel: token("steel"),
        sev: { low: token("sev-low"), medium: token("sev-medium"), high: token("sev-high"), critical: token("sev-critical") },
        ok: token("ok"),
      },
      fontFamily: {
        display: ['"Bricolage Grotesque Variable"', "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ['"Instrument Sans Variable"', "ui-sans-serif", "system-ui", "sans-serif"],
      },
      borderRadius: { panel: "14px" },
    },
  },
  plugins: [],
};
