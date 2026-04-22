import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        panel: "#0b1323",
        border: "#1f2a44",
        accent: "#14b8a6",
        danger: "#ef4444",
        warning: "#f59e0b",
        ink: "#e2e8f0"
      },
      boxShadow: {
        panel: "0 10px 40px rgba(2, 8, 23, 0.35)"
      }
    }
  },
  plugins: []
};

export default config;
