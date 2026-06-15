/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef4ff",
          100: "#d9e6ff",
          200: "#bcd2ff",
          300: "#8eb4ff",
          400: "#598cff",
          500: "#3366ff",
          600: "#1f47f5",
          700: "#1736dd",
          800: "#192fb2",
          900: "#1a2e8c",
        },
      },
      keyframes: {
        "pulse-fast": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
      },
      animation: {
        "pulse-fast": "pulse-fast 1s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
