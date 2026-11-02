/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "var(--color-surface)",
        text: "var(--color-text)",
        primary: "var(--color-primary)",
        secondary: "var(--color-secondary)",
        ok: "var(--color-ok)",
        warn: "var(--color-warn)",
        critical: "var(--color-critical)",
      },
    },
  },
  plugins: [],
};
