/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["DM Sans", "Segoe UI", "sans-serif"],
        display: ["Fraunces", "Georgia", "serif"],
      },
      colors: {
        ink: "#07111f",
        panel: "#0d1b2e",
        line: "#1d3557",
        mint: "#5eead4",
        gold: "#fbbf24",
      },
      boxShadow: {
        glow: "0 0 40px rgba(94, 234, 212, 0.12)",
      },
    },
  },
  plugins: [],
};
