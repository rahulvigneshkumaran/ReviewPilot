import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0F172A", // Dark Slate Blue
        card: "#111827",       // Deep Charcoal Card background
        primary: "#4F46E5",    // Indigo
        secondary: "#7C3AED",  // Purple
        accent: "#A855F7",     // Accent Violet
        border: "#1E293B",     // Slate Border Color
        textPrimary: "#F8FAFC",// White-slate text
        textSecondary: "#94A3B8"// Grey-slate description text
      },
      animation: {
        "pulse-slow": "pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fadeIn 0.5s ease-out forwards",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        }
      }
    },
  },
  plugins: [],
};
export default config;
