import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        serif: ["var(--font-serif)", "Georgia", "serif"],
      },
      colors: {
        // rgb(var(...) / <alpha-value>) keeps existing usages like text-ink/60 or bg-ink/10
        // working, while the underlying rgb triplet flips between light/dark in globals.css.
        background: "rgb(var(--color-background) / <alpha-value>)",
        ink: "rgb(var(--color-ink) / <alpha-value>)",
        accent: "rgb(var(--color-accent) / <alpha-value>)",
        trace: "rgb(var(--color-trace) / <alpha-value>)",
        surface: "rgb(var(--color-surface) / <alpha-value>)",
      },
    },
  },
  plugins: [],
};

export default config;
