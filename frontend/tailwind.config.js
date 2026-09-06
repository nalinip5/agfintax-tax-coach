/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ledger: {
          50: "#f4f7f5",
          100: "#e4ece7",
          200: "#c6d8cd",
          600: "#2f5d47",
          700: "#254a39",
          900: "#132a20",
        },
        clay: {
          500: "#a3623e",
          600: "#8a4f30",
        },
      },
      fontFamily: {
        serif: ["'Source Serif 4'", "Georgia", "serif"],
        sans: ["'Inter'", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
}
