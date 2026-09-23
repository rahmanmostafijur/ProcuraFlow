import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef4ff",
          100: "#dce6ff",
          200: "#b8cdff",
          300: "#8babff",
          400: "#5d84ff",
          500: "#3660f5",
          600: "#2748d1",
          700: "#2039a8",
          800: "#1e3286",
          900: "#1d2e6c",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
