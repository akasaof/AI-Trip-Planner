/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F3F5F8",
        ink: "#12172B",
        "ink-soft": "#2B3350",
        teal: "#0EA5A0",
        "teal-dark": "#0B8580",
        amber: "#F2A93B",
        coral: "#E4572E",
        line: "#D8DCE6",
      },
      fontFamily: {
        display: ["'Space Grotesk'", "sans-serif"],
        body: ["'IBM Plex Sans'", "sans-serif"],
        mono: ["'IBM Plex Mono'", "monospace"],
      },
      backgroundImage: {
        barcode:
          "repeating-linear-gradient(90deg, var(--tw-barcode-color,#12172B) 0px, var(--tw-barcode-color,#12172B) 2px, transparent 2px, transparent 5px)",
      },
    },
  },
  plugins: [],
};
