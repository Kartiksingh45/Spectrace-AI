import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1B1F27",
        accent: "#163150",
        trace: "#0E7C7E",
      },
    },
  },
  plugins: [],
};

export default config;
